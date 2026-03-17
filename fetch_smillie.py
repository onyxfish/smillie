"""
Fetch Smillie diary images from the Smithsonian AAA archive.

For each reference number 49-93 (mapping to years 1865-1909):
  1. Fetch the METS JSON manifest and save to data/{year}/mets.json
  2. Download each image listed in the manifest to data/{year}/{id}.jpg

The script is idempotent: existing files are skipped.
Writes are atomic (temp file + rename) to avoid corrupt files on interruption.
"""

import json
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_DIR = Path("data")

METS_URL = (
    "https://www.aaa.si.edu/get_mets"
    "?title=James%20D.%20Smillie%20and%20Smillie%20family%20papers%2C%201853-1957"
    "&itemRecordId=0"
    "&damsNetappsPath=AAA.smilsmil_ref{n}"
)

# ref49 -> 1865, ref93 -> 1909  (1865 - 49 = 1816)
REF_START = 49
REF_END = 93
YEAR_OFFSET = 1816

# Seconds to wait between image downloads (be polite to the server)
IMAGE_DELAY = 0.1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def id_from_url(image_url: str) -> str:
    """Extract the `id` query parameter from a delivery service URL."""
    qs = parse_qs(urlparse(image_url).query)
    ids = qs.get("id")
    if not ids:
        raise ValueError(f"No 'id' parameter found in URL: {image_url}")
    return ids[0]


def fetch_mets(session: requests.Session, n: int, mets_path: Path) -> dict | None:
    """Fetch the METS JSON for reference number `n` and save it. Returns parsed JSON."""
    url = METS_URL.format(n=n)
    print(f"  Fetching METS: {url}")
    try:
        resp = session.get(url, timeout=30)
    except requests.RequestException as exc:
        print(
            f"  WARNING: network error fetching METS for ref{n}: {exc}", file=sys.stderr
        )
        return None

    if resp.status_code != 200:
        print(
            f"  WARNING: METS request for ref{n} returned HTTP {resp.status_code}",
            file=sys.stderr,
        )
        return None

    tmp = mets_path.with_suffix(".tmp")
    try:
        tmp.write_text(resp.text, encoding="utf-8")
        tmp.rename(mets_path)
    except OSError as exc:
        print(f"  WARNING: could not write {mets_path}: {exc}", file=sys.stderr)
        tmp.unlink(missing_ok=True)
        return None

    return resp.json()


def fetch_image(session: requests.Session, image_url: str, img_path: Path) -> bool:
    """Download an image and save it atomically. Returns True on success."""
    try:
        resp = session.get(image_url, timeout=60)
    except requests.RequestException as exc:
        print(f"  WARNING: network error fetching {image_url}: {exc}", file=sys.stderr)
        return False

    if resp.status_code != 200:
        print(
            f"  WARNING: image request returned HTTP {resp.status_code} for {image_url}",
            file=sys.stderr,
        )
        return False

    tmp = img_path.with_suffix(".tmp")
    try:
        tmp.write_bytes(resp.content)
        tmp.rename(img_path)
    except OSError as exc:
        print(f"  WARNING: could not write {img_path}: {exc}", file=sys.stderr)
        tmp.unlink(missing_ok=True)
        return False

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    session = requests.Session()
    session.headers["User-Agent"] = "smillie-fetcher/0.1 (archival research)"

    for n in range(REF_START, REF_END + 1):
        year = YEAR_OFFSET + n
        year_dir = DATA_DIR / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[ref{n} -> {year}]")

        # ---- METS JSON ----
        mets_path = year_dir / "mets.json"
        if mets_path.exists():
            print(f"  Skip METS (exists): {mets_path}")
            try:
                data = json.loads(mets_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                print(
                    f"  WARNING: could not read {mets_path}: {exc} — re-fetching",
                    file=sys.stderr,
                )
                mets_path.unlink(missing_ok=True)
                data = fetch_mets(session, n, mets_path)
        else:
            data = fetch_mets(session, n, mets_path)

        if data is None:
            print(f"  Skipping images for {year} (no METS data).")
            continue

        results = data.get("results", {})
        if not results:
            print(f"  No images listed in METS for {year}.")
            continue

        # ---- Images ----
        for entry in results.values():
            image_url = entry.get("imageUrl", "")
            if not image_url:
                continue

            try:
                image_id = id_from_url(image_url)
            except ValueError as exc:
                print(f"  WARNING: {exc}", file=sys.stderr)
                continue

            img_path = year_dir / f"{image_id}.jpg"

            if img_path.exists():
                print(f"  Skip image (exists): {img_path.name}")
                continue

            print(f"  Fetching image: {img_path.name}")
            fetch_image(session, image_url, img_path)
            time.sleep(IMAGE_DELAY)

    print("\nDone.")


if __name__ == "__main__":
    main()
