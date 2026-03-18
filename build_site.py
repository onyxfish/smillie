#!/usr/bin/env python3
"""
build_site.py - Generate data files for the Smillie Diaries web viewer.

Produces:
  - site/public/data/manifest.json
  - site/public/data/year-index.json
  - site/public/data/date-index.json
  - site/public/data/transcriptions/YYYY/STEM.json (one per transcribed image)
  - pagefind-source/YYYY/STEM.html (one per diary page, for search indexing)

Usage:
  python build_site.py                # Full corpus (all years)
  python build_site.py --year 1865    # Single year
  python build_site.py --years 1865 1866 1873  # Multiple years
"""

import argparse
import html
import json
import re
from pathlib import Path


# Directories
ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
TRANSCRIPTIONS_DIR = ROOT / "transcriptions"
OUTPUT_DIR = ROOT / "site" / "public" / "data"
PAGEFIND_DIR = ROOT / "pagefind-source"

# All diary years in the collection
ALL_YEARS = list(range(1865, 1910))


def strip_artifact(content: str) -> str:
    """Remove the spurious opening fenced code block artifact from transcription files."""
    return re.sub(r"^```\n.*?\n```\n\n", "", content, flags=re.DOTALL)


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    Parse YAML frontmatter using regex (no PyYAML dependency).
    Returns (frontmatter_dict, body).
    """
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not fm_match:
        return {}, content

    fm_text = fm_match.group(1)
    body = content[fm_match.end() :]

    # Extract dates from both pages
    all_dates = re.findall(r"- (\d{4}-\d{2}-\d{2})", fm_text)

    # Parse sections for left and right pages
    left_sections = []
    right_sections = []

    # Find left page sections
    left_match = re.search(r"left:\s*\n(.*?)(?=right:|$)", fm_text, re.DOTALL)
    if left_match:
        sections_match = re.search(
            r"sections:\s*\n(.*?)(?=\n\s*\w|\Z)", left_match.group(1), re.DOTALL
        )
        if sections_match:
            left_sections = re.findall(r"- (\w[\w-]*)", sections_match.group(1))

    # Find right page sections
    right_match = re.search(r"right:\s*\n(.*)", fm_text, re.DOTALL)
    if right_match:
        sections_match = re.search(
            r"sections:\s*\n(.*?)(?=\n\s*\w|\Z)", right_match.group(1), re.DOTALL
        )
        if sections_match:
            right_sections = re.findall(r"- (\w[\w-]*)", sections_match.group(1))

    return {
        "dates": all_dates,
        "left_sections": left_sections,
        "right_sections": right_sections,
    }, body


def split_pages(body: str) -> tuple[str, str]:
    """
    Split body into left and right page Markdown.
    Returns (left_md, right_md).
    """
    left_match = re.search(
        r"^## Left Page\n(.*?)(?=^## Right Page|\Z)", body, re.MULTILINE | re.DOTALL
    )
    right_match = re.search(r"^## Right Page\n(.*)", body, re.MULTILINE | re.DOTALL)

    left_md = left_match.group(1).strip() if left_match else ""
    right_md = right_match.group(1).strip() if right_match else ""

    return left_md, right_md


def strip_markdown(text: str) -> str:
    """
    Convert Markdown to plain text for Pagefind indexing.
    Strips headings, bold, italic, links, and tables.
    Preserves [illegible] markers.
    """
    # Remove headings
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    # Remove links but keep text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove table rows (lines starting with |)
    text = re.sub(r"^\|.*\|$", "", text, flags=re.MULTILINE)
    # Remove table dividers
    text = re.sub(r"^[-|:\s]+$", "", text, flags=re.MULTILINE)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_date_title(dates: list[str]) -> str:
    """Format dates for the HTML title (e.g., 'January 1-2, 1865')."""
    if not dates:
        return ""

    months = [
        "",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]

    if len(dates) == 1:
        y, m, d = dates[0].split("-")
        return f"{months[int(m)]} {int(d)}, {y}"

    # Multiple dates - format as range if same month/year
    first = dates[0]
    last = dates[-1]
    y1, m1, d1 = first.split("-")
    y2, m2, d2 = last.split("-")

    if y1 == y2 and m1 == m2:
        return f"{months[int(m1)]} {int(d1)}-{int(d2)}, {y1}"
    elif y1 == y2:
        return f"{months[int(m1)]} {int(d1)} - {months[int(m2)]} {int(d2)}, {y1}"
    else:
        return f"{months[int(m1)]} {int(d1)}, {y1} - {months[int(m2)]} {int(d2)}, {y2}"


def load_mets(year: int) -> list[dict]:
    """
    Load mets.json for a year and return entries sorted by orderLabel.
    Each entry has: orderLabel, fileUri, imageUrl
    """
    mets_path = DATA_DIR / str(year) / "mets.json"
    if not mets_path.exists():
        return []

    with open(mets_path) as f:
        data = json.load(f)

    results = data.get("results", {})
    # Sort by orderLabel (numeric)
    entries = sorted(results.values(), key=lambda x: int(x["orderLabel"]))
    return entries


def process_year(
    year: int, manifest: dict, year_index: dict, date_index: dict, start_index: int
) -> int:
    """
    Process all images for a year.
    Returns the count of images processed.
    """
    entries = load_mets(year)
    if not entries:
        print(f"  {year}: no mets.json found")
        return 0

    year_str = str(year)
    tx_year_dir = TRANSCRIPTIONS_DIR / year_str
    out_tx_dir = OUTPUT_DIR / "transcriptions" / year_str
    pf_year_dir = PAGEFIND_DIR / year_str

    out_tx_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for entry in entries:
        seq = int(entry["orderLabel"])
        file_uri = entry["fileUri"]
        image_id = f"{year_str}/{seq:04d}"

        # Add to manifest
        manifest[image_id] = file_uri
        count += 1

        # Try to load transcription
        tx_path = tx_year_dir / f"{file_uri}.md"
        if not tx_path.exists():
            continue

        content = tx_path.read_text()
        content = strip_artifact(content)
        fm, body = parse_frontmatter(content)
        left_md, right_md = split_pages(body)

        # Write transcription JSON
        tx_json = {
            "id": image_id,
            "dates": fm.get("dates", []),
            "sections": {
                "left": fm.get("left_sections", []),
                "right": fm.get("right_sections", []),
            },
            "left": left_md,
            "right": right_md,
        }

        tx_out_path = out_tx_dir / f"{file_uri}.json"
        with open(tx_out_path, "w") as f:
            json.dump(tx_json, f, ensure_ascii=False)

        # Update date index (first occurrence wins)
        for date in fm.get("dates", []):
            if date not in date_index:
                date_index[date] = image_id

        # Generate Pagefind stub if diary content exists
        has_diary = "diary" in fm.get("left_sections", []) or "diary" in fm.get(
            "right_sections", []
        )

        if has_diary:
            pf_year_dir.mkdir(parents=True, exist_ok=True)

            # Extract only diary text (strip non-diary content)
            diary_text = []
            if "diary" in fm.get("left_sections", []):
                diary_text.append(strip_markdown(left_md))
            if "diary" in fm.get("right_sections", []):
                diary_text.append(strip_markdown(right_md))

            plain_text = "\n\n".join(diary_text)
            date_title = format_date_title(fm.get("dates", []))

            pf_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(date_title)}</title>
</head>
<body>
  <article data-pagefind-body data-pagefind-meta="url:/{image_id}">
    {html.escape(plain_text)}
  </article>
</body>
</html>
"""
            pf_path = pf_year_dir / f"{file_uri}.html"
            pf_path.write_text(pf_html)

    # Update year index
    year_index[year_str] = {
        "start": start_index,
        "count": count,
    }

    return count


def build(years: list[int]):
    """Build all data files for the specified years."""

    # Create output directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {}
    year_index = {}
    date_index = {}

    total_images = 0
    total_transcriptions = 0

    print(f"Building data for {len(years)} year(s)...")

    for year in years:
        count = process_year(year, manifest, year_index, date_index, total_images)

        # Count transcriptions
        tx_dir = OUTPUT_DIR / "transcriptions" / str(year)
        tx_count = len(list(tx_dir.glob("*.json"))) if tx_dir.exists() else 0

        print(f"  {year}: {count} images, {tx_count} transcriptions")
        total_images += count
        total_transcriptions += tx_count

    # Write manifest.json
    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, ensure_ascii=False)
    print(f"\nWrote {manifest_path} ({len(manifest)} entries)")

    # Write year-index.json
    year_index_path = OUTPUT_DIR / "year-index.json"
    with open(year_index_path, "w") as f:
        json.dump(year_index, f, ensure_ascii=False)
    print(f"Wrote {year_index_path} ({len(year_index)} years)")

    # Write date-index.json
    date_index_path = OUTPUT_DIR / "date-index.json"
    with open(date_index_path, "w") as f:
        json.dump(date_index, f, ensure_ascii=False)
    print(f"Wrote {date_index_path} ({len(date_index)} dates)")

    # Count Pagefind stubs
    pf_count = (
        sum(1 for _ in PAGEFIND_DIR.rglob("*.html")) if PAGEFIND_DIR.exists() else 0
    )
    print(f"Wrote {pf_count} Pagefind stubs to {PAGEFIND_DIR}/")

    print(f"\nTotal: {total_images} images, {total_transcriptions} transcriptions")


def main():
    parser = argparse.ArgumentParser(
        description="Generate data files for the Smillie Diaries web viewer."
    )
    parser.add_argument("--year", type=int, help="Process a single year")
    parser.add_argument(
        "--years", type=int, nargs="+", help="Process multiple specific years"
    )

    args = parser.parse_args()

    if args.year:
        years = [args.year]
    elif args.years:
        years = args.years
    else:
        years = ALL_YEARS

    # Validate years
    for year in years:
        if year < 1865 or year > 1909:
            parser.error(f"Year {year} is outside the valid range (1865-1909)")

    build(sorted(years))


if __name__ == "__main__":
    main()
