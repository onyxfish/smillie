"""
Transcribe Smillie diary scans using the Claude vision API.

For each pending image in transcriptions/progress.csv:
  1. Base64-encode data/YYYY/filename.jpg
  2. Call the Claude API with the output format spec as the system prompt
  3. Write the response to transcriptions/YYYY/filename.md (atomic)
  4. Mark the row done in progress.csv

The script is idempotent: done rows with existing .md files are skipped.
Progress is tracked in transcriptions/progress.csv, not in TRANSCRIPTION_PLAN.md.
The "Output Format" section of TRANSCRIPTION_PLAN.md is used verbatim as the
system prompt, so editing the spec there automatically updates the prompt.

Usage:
  python transcribe_smillie.py                   # all pending, 5 workers
  python transcribe_smillie.py --year 1865       # one year only
  python transcribe_smillie.py --year 1865 --limit 3  # quick test
  python transcribe_smillie.py --retry-errors    # re-attempt errored rows
  python transcribe_smillie.py --workers 10 --model claude-opus-4-5
"""

import argparse
import base64
import csv
import os
import sys
import threading
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
PLAN_MD = Path("TRANSCRIPTION_PLAN.md")

CSV_FIELDS = ["year", "image", "status", "model", "transcribed_at", "error"]

YEARS = range(1865, 1910)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_WORKERS = 5
MAX_TOKENS = 4096


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------


def load_csv(csv_path: Path) -> list[dict]:
    """Load all rows from the progress CSV."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_csv(csv_path: Path, rows: list[dict]) -> None:
    """Overwrite the progress CSV with the given rows."""
    tmp = csv_path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    tmp.rename(csv_path)


def update_row(
    csv_path: Path,
    lock: threading.Lock,
    year: str,
    image: str,
    status: str,
    model: str,
    error: str = "",
) -> None:
    """Thread-safe update of a single row in the progress CSV."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with lock:
        rows = load_csv(csv_path)
        for row in rows:
            if row["year"] == str(year) and row["image"] == image:
                row["status"] = status
                row["model"] = model
                row["transcribed_at"] = now
                row["error"] = error
                break
        save_csv(csv_path, rows)


# ---------------------------------------------------------------------------
# CSV initialisation
# ---------------------------------------------------------------------------


def init_csv(data_dir: Path, csv_path: Path, out_dir: Path) -> None:
    """
    Create progress.csv if it doesn't exist, or reconcile it with what's on disk.

    - Adds rows for any images not yet listed.
    - Resets done→pending for any row whose .md output file is missing.
    """
    # Build the full expected set of (year, image) pairs from data/
    expected: dict[tuple[str, str], None] = {}
    for year in YEARS:
        year_dir = data_dir / str(year)
        if not year_dir.is_dir():
            continue
        for img in sorted(year_dir.glob("*.jpg")):
            expected[(str(year), img.name)] = None

    if not csv_path.exists():
        print(f"Creating {csv_path} ({len(expected):,} rows)...")
        rows = [
            {
                "year": year,
                "image": image,
                "status": "pending",
                "model": "",
                "transcribed_at": "",
                "error": "",
            }
            for year, image in expected
        ]
        out_dir.mkdir(parents=True, exist_ok=True)
        save_csv(csv_path, rows)
        return

    # CSV exists — reconcile
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
            md_path = out_dir / row["year"] / Path(row["image"]).stem
            md_path = md_path.with_suffix(".md")
            if not md_path.exists():
                row["status"] = "pending"
                row["model"] = ""
                row["transcribed_at"] = ""
                row["error"] = ""
                reset += 1

    if added or reset:
        save_csv(csv_path, rows)
        if added:
            print(f"  Added {added} new rows to {csv_path}")
        if reset:
            print(f"  Reset {reset} done→pending rows (missing .md files)")


# ---------------------------------------------------------------------------
# System prompt extraction
# ---------------------------------------------------------------------------


def extract_system_prompt(plan_path: Path) -> str:
    """
    Extract the 'Output Format' section from TRANSCRIPTION_PLAN.md as the
    system prompt. Slices from '## Output Format' up to (but not including)
    '## Checklist'.
    """
    text = plan_path.read_text(encoding="utf-8")
    start_marker = "## Output Format"
    end_marker = "## Checklist"

    start = text.find(start_marker)
    end = text.find(end_marker)

    if start == -1 or end == -1:
        raise ValueError(
            f"Could not find '## Output Format' and/or '## Checklist' "
            f"sections in {plan_path}"
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
# Transcription
# ---------------------------------------------------------------------------


def transcribe_image(
    client: anthropic.Anthropic,
    year: str,
    image: str,
    system_prompt: str,
    model: str,
    out_dir: Path,
) -> tuple[str, str]:
    """
    Transcribe a single image via the Claude API.

    Returns (status, error_message) where status is 'done' or 'error'.
    Writes the transcription atomically to out_dir/year/stem.md on success.
    """
    img_path = DATA_DIR / year / image
    if not img_path.exists():
        return "error", f"image file not found: {img_path}"

    # Read and encode image
    img_bytes = img_path.read_bytes()
    img_b64 = base64.standard_b64encode(img_bytes).decode("ascii")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": img_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                f"Transcribe this diary scan.\n"
                                f"Image path: {year}/{image}"
                            ),
                        },
                    ],
                }
            ],
        )
    except anthropic.APIError as exc:
        return "error", f"API error: {exc}"

    content = response.content[0].text if response.content else ""
    if not content.strip():
        return "error", "empty response from API"

    # Write atomically
    md_dir = out_dir / year
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / (Path(image).stem + ".md")
    tmp = md_path.with_suffix(".tmp")

    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.rename(md_path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        return "error", f"write error: {exc}"

    return "done", ""


# ---------------------------------------------------------------------------
# Work queue
# ---------------------------------------------------------------------------


def build_work_queue(
    csv_path: Path,
    year_filter: int | None,
    retry_errors: bool,
    limit: int | None,
) -> list[dict]:
    """Return the list of rows to process."""
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
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcribe Smillie diary scans via the Claude vision API."
    )
    parser.add_argument(
        "--year",
        type=int,
        metavar="YYYY",
        help="Process only this year (e.g. 1865)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Process at most N images (useful for test runs)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        metavar="N",
        help=f"Concurrent API workers (default: {DEFAULT_WORKERS})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Also retry rows currently marked as error",
    )
    args = parser.parse_args()

    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "Error: ANTHROPIC_API_KEY environment variable is not set.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check plan file exists
    if not PLAN_MD.exists():
        print(f"Error: {PLAN_MD} not found.", file=sys.stderr)
        sys.exit(1)

    # Initialise CSV and output directory
    TRANSCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    init_csv(DATA_DIR, PROGRESS_CSV, TRANSCRIPTIONS_DIR)

    # Extract system prompt from plan
    try:
        system_prompt = extract_system_prompt(PLAN_MD)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Build work queue
    queue = build_work_queue(PROGRESS_CSV, args.year, args.retry_errors, args.limit)

    if not queue:
        print("Nothing to do — all items are already done.")
        return

    year_desc = f" for {args.year}" if args.year else ""
    print(
        f"Transcribing {len(queue):,} images{year_desc} "
        f"with {args.workers} worker(s) using {args.model}..."
    )

    client = anthropic.Anthropic(api_key=api_key)
    csv_lock = threading.Lock()

    done_count = 0
    error_count = 0

    def process(row: dict) -> tuple[dict, str, str]:
        status, error = transcribe_image(
            client=client,
            year=row["year"],
            image=row["image"],
            system_prompt=system_prompt,
            model=args.model,
            out_dir=TRANSCRIPTIONS_DIR,
        )
        update_row(
            csv_path=PROGRESS_CSV,
            lock=csv_lock,
            year=row["year"],
            image=row["image"],
            status=status,
            model=args.model,
            error=error,
        )
        return row, status, error

    with tqdm(total=len(queue), unit="img") as pbar:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(process, row): row for row in queue}
            try:
                for future in as_completed(futures):
                    row, status, error = future.result()
                    if status == "done":
                        done_count += 1
                        pbar.set_postfix(done=done_count, err=error_count)
                    else:
                        error_count += 1
                        tqdm.write(f"  ERROR {row['year']}/{row['image']}: {error}")
                        pbar.set_postfix(done=done_count, err=error_count)
                    pbar.update(1)
            except KeyboardInterrupt:
                print("\nInterrupted — waiting for in-flight requests to finish...")
                executor.shutdown(wait=True, cancel_futures=True)

    print(f"\nDone. {done_count:,} transcribed, {error_count:,} errors.")
    if error_count:
        print(f"  Re-run with --retry-errors to attempt failed items again.")


if __name__ == "__main__":
    main()
