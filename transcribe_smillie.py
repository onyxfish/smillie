"""
Transcribe Smillie diary scans using the Claude Batch API and Files API.

Three-step workflow:

  1. --upload   Upload all images to the Anthropic Files API (free storage,
                paid only when consumed). Idempotent: skips already-uploaded
                images. Stores file_ids in transcriptions/file_ids.csv.

  2. --submit   Build and submit a single Message Batch using stored file_ids.
                Returns immediately with a batch_id. Marks rows as 'submitted'
                in transcriptions/progress.csv.

  3. --collect  Check batch status. When ended, streams results and writes
                transcriptions/YYYY/filename.md for each succeeded result.
                Marks rows done/error in progress.csv.

All steps are idempotent and resumable. Progress is tracked in CSV files,
not in TRANSCRIPTION_PLAN.md (which is used only as the system prompt source).

Usage:
  python transcribe_smillie.py --upload
  python transcribe_smillie.py --submit
  python transcribe_smillie.py --collect

  python transcribe_smillie.py --upload --workers 10
  python transcribe_smillie.py --submit --year 1865 --limit 5   # test batch
  python transcribe_smillie.py --submit --retry-errors
  python transcribe_smillie.py --collect --batch-id msgbatch_xyz
  python transcribe_smillie.py --model claude-opus-4-6 --submit
"""

import argparse
import csv
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

DATA_DIR = Path("data")
TRANSCRIPTIONS_DIR = Path("transcriptions")
PROGRESS_CSV = TRANSCRIPTIONS_DIR / "progress.csv"
FILE_IDS_CSV = TRANSCRIPTIONS_DIR / "file_ids.csv"
BATCHES_CSV = TRANSCRIPTIONS_DIR / "batches.csv"
PLAN_MD = Path("TRANSCRIPTION_PLAN.md")

PROGRESS_FIELDS = ["year", "image", "status", "model", "transcribed_at", "error"]
FILE_IDS_FIELDS = ["year", "image", "file_id", "uploaded_at"]
BATCHES_FIELDS = [
    "batch_id",
    "submitted_at",
    "status",
    "total",
    "succeeded",
    "errored",
    "expired",
]

YEARS = range(1865, 1910)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_WORKERS = 5
MAX_TOKENS = 4096

FILES_API_BETA = "files-api-2025-04-14"


# ---------------------------------------------------------------------------
# Generic CSV helpers
# ---------------------------------------------------------------------------


def load_csv(csv_path: Path) -> list[dict]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_csv(csv_path: Path, fields: list[str], rows: list[dict]) -> None:
    """Atomically overwrite a CSV file."""
    tmp = csv_path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    tmp.rename(csv_path)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# progress.csv
# ---------------------------------------------------------------------------


def init_progress_csv(data_dir: Path, csv_path: Path, out_dir: Path) -> None:
    """
    Create progress.csv if absent, or reconcile with images on disk.
    - Adds rows for any images not yet listed.
    - Resets done→pending for any row whose .md file is missing.
    - Resets submitted→pending for rows that were never collected
      (i.e. submitted but no .md file exists).
    """
    expected: dict[tuple[str, str], None] = {}
    for year in YEARS:
        year_dir = data_dir / str(year)
        if not year_dir.is_dir():
            continue
        for img in sorted(year_dir.glob("*.jpg")):
            expected[(str(year), img.name)] = None

    out_dir.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        print(f"Creating {csv_path} ({len(expected):,} rows)...")
        rows = [
            {
                "year": y,
                "image": img,
                "status": "pending",
                "model": "",
                "transcribed_at": "",
                "error": "",
            }
            for y, img in expected
        ]
        save_csv(csv_path, PROGRESS_FIELDS, rows)
        return

    rows = load_csv(csv_path)
    existing = {(r["year"], r["image"]) for r in rows}

    added = 0
    for year, image in expected:
        if (year, image) not in existing:
            rows.append(
                {
                    "year": year,
                    "image": image,
                    "status": "pending",
                    "model": "",
                    "transcribed_at": "",
                    "error": "",
                }
            )
            added += 1

    reset = 0
    for row in rows:
        if row["status"] == "done":
            md_path = out_dir / row["year"] / (Path(row["image"]).stem + ".md")
            if not md_path.exists():
                row["status"] = "pending"
                row["model"] = ""
                row["transcribed_at"] = ""
                row["error"] = ""
                reset += 1

    if added or reset:
        save_csv(csv_path, PROGRESS_FIELDS, rows)
        if added:
            print(f"  Added {added} new rows to {csv_path}")
        if reset:
            print(f"  Reset {reset} rows → pending (missing .md files)")


def update_progress_rows(
    csv_path: Path,
    lock: threading.Lock,
    updates: list[tuple[str, str, str, str, str]],
) -> None:
    """
    Thread-safe bulk update of progress rows.
    updates: list of (year, image, status, model, error)
    """
    update_map = {
        (y, img): (status, model, error) for y, img, status, model, error in updates
    }
    ts = now_utc()
    with lock:
        rows = load_csv(csv_path)
        for row in rows:
            key = (row["year"], row["image"])
            if key in update_map:
                status, model, error = update_map[key]
                row["status"] = status
                row["model"] = model
                row["transcribed_at"] = ts
                row["error"] = error
        save_csv(csv_path, PROGRESS_FIELDS, rows)


def build_work_queue(
    csv_path: Path,
    year_filter: int | None,
    retry_errors: bool,
    limit: int | None,
) -> list[dict]:
    rows = load_csv(csv_path)
    queue = []
    for row in rows:
        if year_filter is not None and int(row["year"]) != year_filter:
            continue
        if row["status"] == "pending":
            queue.append(row)
        elif row["status"] == "error" and retry_errors:
            queue.append(row)
    if limit is not None:
        queue = queue[:limit]
    return queue


# ---------------------------------------------------------------------------
# file_ids.csv
# ---------------------------------------------------------------------------


def init_file_ids_csv(data_dir: Path, csv_path: Path) -> None:
    """Create file_ids.csv if absent, adding a row per image with empty file_id."""
    expected = []
    for year in YEARS:
        year_dir = data_dir / str(year)
        if not year_dir.is_dir():
            continue
        for img in sorted(year_dir.glob("*.jpg")):
            expected.append((str(year), img.name))

    if not csv_path.exists():
        print(f"Creating {csv_path} ({len(expected):,} rows)...")
        rows = [
            {"year": y, "image": img, "file_id": "", "uploaded_at": ""}
            for y, img in expected
        ]
        save_csv(csv_path, FILE_IDS_FIELDS, rows)
        return

    rows = load_csv(csv_path)
    existing = {(r["year"], r["image"]) for r in rows}
    added = 0
    for year, image in expected:
        if (year, image) not in existing:
            rows.append(
                {"year": year, "image": image, "file_id": "", "uploaded_at": ""}
            )
            added += 1
    if added:
        save_csv(csv_path, FILE_IDS_FIELDS, rows)
        print(f"  Added {added} new rows to {csv_path}")


def load_file_id_map(csv_path: Path) -> dict[tuple[str, str], str]:
    """Return {(year, image): file_id} for all rows that have a file_id."""
    return {
        (r["year"], r["image"]): r["file_id"]
        for r in load_csv(csv_path)
        if r["file_id"]
    }


def update_file_id(
    csv_path: Path,
    lock: threading.Lock,
    year: str,
    image: str,
    file_id: str,
) -> None:
    """Thread-safe update of a single file_id row."""
    ts = now_utc()
    with lock:
        rows = load_csv(csv_path)
        for row in rows:
            if row["year"] == year and row["image"] == image:
                row["file_id"] = file_id
                row["uploaded_at"] = ts
                break
        save_csv(csv_path, FILE_IDS_FIELDS, rows)


# ---------------------------------------------------------------------------
# batches.csv
# ---------------------------------------------------------------------------


def init_batches_csv(csv_path: Path) -> None:
    if not csv_path.exists():
        save_csv(csv_path, BATCHES_FIELDS, [])


def append_batch_row(csv_path: Path, batch_id: str, total: int) -> None:
    rows = load_csv(csv_path) if csv_path.exists() else []
    rows.append(
        {
            "batch_id": batch_id,
            "submitted_at": now_utc(),
            "status": "in_progress",
            "total": total,
            "succeeded": 0,
            "errored": 0,
            "expired": 0,
        }
    )
    save_csv(csv_path, BATCHES_FIELDS, rows)


def update_batch_row(csv_path: Path, batch_id: str, **kwargs) -> None:
    rows = load_csv(csv_path)
    for row in rows:
        if row["batch_id"] == batch_id:
            row.update(kwargs)
            break
    save_csv(csv_path, BATCHES_FIELDS, rows)


def latest_active_batch_id(csv_path: Path) -> str | None:
    """Return the most recently submitted batch that isn't marked ended."""
    if not csv_path.exists():
        return None
    rows = load_csv(csv_path)
    active = [r for r in rows if r["status"] != "ended"]
    return active[-1]["batch_id"] if active else None


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def extract_system_prompt(plan_path: Path) -> str:
    text = plan_path.read_text(encoding="utf-8")
    start = text.find("## Output Format")
    end = text.find("## Checklist")
    if start == -1 or end == -1:
        raise ValueError(
            f"Could not find '## Output Format' and/or '## Checklist' in {plan_path}"
        )
    spec = text[start:end].strip()
    return (
        "You are transcribing scanned pages from the personal diaries of "
        "James D. Smillie (American artist, 1833–1909), held at the "
        "Smithsonian Archives of American Art.\n\n"
        "Produce a transcription of every scan you are given, following "
        "the output format specification below exactly. Do not add any "
        "commentary, preamble, or explanation outside the specified format. "
        "Output only the Markdown document.\n\n" + spec
    )


# ---------------------------------------------------------------------------
# --upload
# ---------------------------------------------------------------------------


def cmd_upload(args: argparse.Namespace, client: anthropic.Anthropic) -> None:
    """Upload all images that don't yet have a file_id."""
    TRANSCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    init_file_ids_csv(DATA_DIR, FILE_IDS_CSV)

    rows = load_csv(FILE_IDS_CSV)
    pending = [r for r in rows if not r["file_id"]]

    if not pending:
        print("All images already uploaded.")
        return

    print(f"Uploading {len(pending):,} images with {args.workers} worker(s)...")

    lock = threading.Lock()
    uploaded = 0
    errors = 0

    def upload_one(row: dict) -> tuple[dict, str, str]:
        img_path = DATA_DIR / row["year"] / row["image"]
        if not img_path.exists():
            return row, "", f"file not found: {img_path}"
        try:
            with img_path.open("rb") as f:
                result = client.beta.files.upload(
                    file=(img_path.name, f, "image/jpeg"),
                    extra_headers={"anthropic-beta": FILES_API_BETA},
                )
            return row, result.id, ""
        except anthropic.APIError as exc:
            return row, "", f"API error: {exc}"

    with tqdm(total=len(pending), unit="img") as pbar:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(upload_one, row): row for row in pending}
            try:
                for future in as_completed(futures):
                    row, file_id, error = future.result()
                    if file_id:
                        update_file_id(
                            FILE_IDS_CSV, lock, row["year"], row["image"], file_id
                        )
                        uploaded += 1
                        pbar.set_postfix(ok=uploaded, err=errors)
                    else:
                        errors += 1
                        tqdm.write(f"  ERROR {row['year']}/{row['image']}: {error}")
                        pbar.set_postfix(ok=uploaded, err=errors)
                    pbar.update(1)
            except KeyboardInterrupt:
                print("\nInterrupted — waiting for in-flight uploads to finish...")
                executor.shutdown(wait=True, cancel_futures=True)

    print(f"\nUpload complete. {uploaded:,} uploaded, {errors:,} errors.")
    if errors:
        print("  Re-run --upload to retry failed uploads.")


# ---------------------------------------------------------------------------
# --submit
# ---------------------------------------------------------------------------


def cmd_submit(args: argparse.Namespace, client: anthropic.Anthropic) -> None:
    """Build and submit a Message Batch from pending rows."""
    TRANSCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    init_progress_csv(DATA_DIR, PROGRESS_CSV, TRANSCRIPTIONS_DIR)
    init_batches_csv(BATCHES_CSV)

    # Check all file_ids are present
    if not FILE_IDS_CSV.exists():
        print("Error: file_ids.csv not found. Run --upload first.", file=sys.stderr)
        sys.exit(1)

    file_id_map = load_file_id_map(FILE_IDS_CSV)

    # Extract system prompt
    try:
        system_prompt = extract_system_prompt(PLAN_MD)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Build queue
    queue = build_work_queue(PROGRESS_CSV, args.year, args.retry_errors, args.limit)

    if not queue:
        print("Nothing to submit — no pending rows.")
        return

    # Check all queued rows have a file_id
    missing = [
        (r["year"], r["image"])
        for r in queue
        if (r["year"], r["image"]) not in file_id_map
    ]
    if missing:
        print(
            f"Error: {len(missing):,} image(s) have no file_id. Run --upload first.",
            file=sys.stderr,
        )
        for y, img in missing[:5]:
            print(f"  {y}/{img}", file=sys.stderr)
        if len(missing) > 5:
            print(f"  ... and {len(missing) - 5} more", file=sys.stderr)
        sys.exit(1)

    year_desc = f" for {args.year}" if args.year else ""
    print(f"Building batch of {len(queue):,} requests{year_desc}...")

    # Construct batch requests
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    requests = []
    for row in queue:
        file_id = file_id_map[(row["year"], row["image"])]
        requests.append(
            Request(
                custom_id=f"{row['year']}_{Path(row['image']).stem}",
                params=MessageCreateParamsNonStreaming(
                    model=args.model,
                    max_tokens=MAX_TOKENS,
                    system=system_prompt,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "file",
                                        "file_id": file_id,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": (
                                        f"Transcribe this diary scan.\n"
                                        f"Image path: {row['year']}/{row['image']}"
                                    ),
                                },
                            ],
                        }
                    ],
                ),
            )
        )

    print("Submitting batch...")
    try:
        batch = client.messages.batches.create(
            requests=requests,
            extra_headers={"anthropic-beta": FILES_API_BETA},
        )
    except anthropic.APIError as exc:
        print(f"Error submitting batch: {exc}", file=sys.stderr)
        sys.exit(1)

    # Record batch and mark rows submitted
    append_batch_row(BATCHES_CSV, batch.id, len(queue))

    lock = threading.Lock()
    updates = [(r["year"], r["image"], "submitted", args.model, "") for r in queue]
    update_progress_rows(PROGRESS_CSV, lock, updates)

    print(f"\nBatch submitted: {batch.id}")
    print(f"  {len(queue):,} requests queued.")
    print(f"  Run --collect to check status and retrieve results when ready.")


# ---------------------------------------------------------------------------
# --collect
# ---------------------------------------------------------------------------


def write_md(out_dir: Path, year: str, image: str, content: str) -> str:
    """Write transcription atomically. Returns '' on success, error string on failure."""
    md_dir = out_dir / year
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / (Path(image).stem + ".md")
    tmp = md_path.with_suffix(".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.rename(md_path)
        return ""
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        return f"write error: {exc}"


def cmd_collect(args: argparse.Namespace, client: anthropic.Anthropic) -> None:
    """Check batch status; if ended, stream and write results."""
    init_batches_csv(BATCHES_CSV)

    batch_id = args.batch_id or latest_active_batch_id(BATCHES_CSV)
    if not batch_id:
        print("No active batch found. Run --submit first.", file=sys.stderr)
        sys.exit(1)

    print(f"Checking batch {batch_id}...")
    try:
        batch = client.messages.batches.retrieve(batch_id)
    except anthropic.APIError as exc:
        print(f"Error retrieving batch: {exc}", file=sys.stderr)
        sys.exit(1)

    counts = batch.request_counts
    print(f"  Status:     {batch.processing_status}")
    print(f"  Processing: {counts.processing}")
    print(f"  Succeeded:  {counts.succeeded}")
    print(f"  Errored:    {counts.errored}")
    print(f"  Expired:    {counts.expired}")
    print(f"  Canceled:   {counts.canceled}")

    if batch.processing_status != "ended":
        print("\nBatch is still processing. Run --collect again later.")
        return

    print("\nBatch ended — collecting results...")

    succeeded = 0
    errored = 0
    lock = threading.Lock()

    try:
        for result in client.messages.batches.results(batch_id):
            # custom_id is "YYYY_stem" (e.g. "1865_AAA-AAA_smilsmil_2303576")
            parts = result.custom_id.split("_", 1)
            if len(parts) != 2:
                tqdm.write(
                    f"  WARNING: unexpected custom_id format: {result.custom_id}"
                )
                continue
            year, stem = parts
            image = stem + ".jpg"

            if result.result.type == "succeeded":
                content = result.result.message.content
                text = content[0].text if content else ""
                if not text.strip():
                    err = "empty response"
                    update_progress_rows(
                        PROGRESS_CSV, lock, [(year, image, "error", "", err)]
                    )
                    errored += 1
                    tqdm.write(f"  ERROR {result.custom_id}: {err}")
                else:
                    err = write_md(TRANSCRIPTIONS_DIR, year, image, text)
                    if err:
                        update_progress_rows(
                            PROGRESS_CSV, lock, [(year, image, "error", "", err)]
                        )
                        errored += 1
                        tqdm.write(f"  ERROR {result.custom_id}: {err}")
                    else:
                        update_progress_rows(
                            PROGRESS_CSV,
                            lock,
                            [(year, image, "done", batch.processing_status, "")],
                        )
                        succeeded += 1

            elif result.result.type == "errored":
                err_detail = str(result.result.error)
                update_progress_rows(
                    PROGRESS_CSV, lock, [(year, image, "error", "", err_detail)]
                )
                errored += 1
                tqdm.write(f"  ERROR {result.custom_id}: {err_detail}")

            elif result.result.type == "expired":
                update_progress_rows(
                    PROGRESS_CSV, lock, [(year, image, "error", "", "expired")]
                )
                errored += 1
                tqdm.write(f"  EXPIRED {result.custom_id}")

    except anthropic.APIError as exc:
        print(f"Error streaming results: {exc}", file=sys.stderr)
        sys.exit(1)

    # Update batches.csv
    update_batch_row(
        BATCHES_CSV,
        batch_id,
        status="ended",
        succeeded=succeeded,
        errored=errored,
        expired=counts.expired,
    )

    print(f"\nCollect complete. {succeeded:,} transcribed, {errored:,} errors.")
    if errored:
        print("  Re-run --submit --retry-errors to resubmit failed items.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcribe Smillie diary scans via the Claude Batch + Files APIs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python transcribe_smillie.py --upload
  python transcribe_smillie.py --submit
  python transcribe_smillie.py --collect
  python transcribe_smillie.py --submit --year 1865 --limit 5
  python transcribe_smillie.py --submit --retry-errors
  python transcribe_smillie.py --collect --batch-id msgbatch_xyz
  python transcribe_smillie.py --upload --workers 10
""",
    )

    # Commands (mutually exclusive)
    cmd_group = parser.add_mutually_exclusive_group(required=True)
    cmd_group.add_argument(
        "--upload", action="store_true", help="Upload images to the Files API"
    )
    cmd_group.add_argument(
        "--submit", action="store_true", help="Submit a Message Batch"
    )
    cmd_group.add_argument(
        "--collect",
        action="store_true",
        help="Collect results from the most recent batch",
    )

    # Shared options
    parser.add_argument(
        "--year",
        type=int,
        metavar="YYYY",
        help="Restrict to a single year (--submit only)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Process at most N items (--upload / --submit)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        metavar="N",
        help=f"Concurrent workers (default: {DEFAULT_WORKERS})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Claude model (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Re-include error rows (--submit only)",
    )
    parser.add_argument(
        "--batch-id", metavar="ID", help="Explicit batch ID to collect (--collect only)"
    )

    args = parser.parse_args()

    # Validate
    if (args.year or args.retry_errors) and not args.submit:
        parser.error("--year and --retry-errors are only valid with --submit")
    if args.batch_id and not args.collect:
        parser.error("--batch-id is only valid with --collect")

    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "Error: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr
        )
        sys.exit(1)

    # Check plan file (needed for --submit)
    if args.submit and not PLAN_MD.exists():
        print(f"Error: {PLAN_MD} not found.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    if args.upload:
        cmd_upload(args, client)
    elif args.submit:
        cmd_submit(args, client)
    elif args.collect:
        cmd_collect(args, client)


if __name__ == "__main__":
    main()
