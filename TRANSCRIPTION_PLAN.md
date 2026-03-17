# Smillie Diary Transcription Plan

## Overview

- **Subject:** James D. Smillie diary volumes, 1865–1909
- **Source:** Smithsonian Archives of American Art (AAA)
- **Total images:** 8,210
- **Volumes:** 45 (one per year, ref49–ref93)
- **Output directory:** `transcriptions/`

---

## Output Format

Each image produces one Markdown file at:

```
transcriptions/YYYY/AAA-AAA_smilsmil_XXXXXXX.md
```

### Frontmatter

```yaml
---
year: 1865
image: 1865/AAA-AAA_smilsmil_2303578.jpg
dates:
  - 1865-01-01
  - 1865-01-02
sections:
  - diary
---
```

- **`year`** — 4-digit integer year of the volume
- **`image`** — relative path from the repo root: `YYYY/filename.jpg`
- **`dates`** — ISO 8601 dates (`YYYY-MM-DD`) of all diary entries visible on the scan; empty list `[]` for non-diary pages
- **`sections`** — one or more of the content types listed below

### Section types

| Value | Description |
|---|---|
| `diary` | Dated personal diary entries |
| `cover` | Front or back cover (blank leather) |
| `title-page` | Printed title page / ownership inscription |
| `almanac` | Printed almanac / moon phases / calendar tables |
| `cash-account` | Handwritten monthly cash account ledger |
| `bills-payable` | Bills payable / receivable ledger |
| `address-list` | Handwritten names and addresses |
| `blank` | Empty page(s) with no content |

A single scan may contain multiple section types (e.g. an almanac table on the left page and a diary entry on the right).

### Body structure

Use `##` headings to separate each distinct section or day on the scan.

**Diary entries** — use the printed header verbatim as the heading:

```markdown
## January, Sunday 1, 1865

Painting on little oil sketch for Miss Sarah Marten until
2.30 o'clk. Then started from Studio and made 21 calls.
Clear, cold, windy day.

## Monday 2

Henry M. Butler died of Consumption...
```

**Later volumes (approx. 1890s onward)** have printed "Wea." and "Ther." fields in the header. Transcribe them on the first line of the entry body:

```markdown
## Sat. Jan. 2, 1909

**Weather:** [illegible]  **Temp:** [illegible]

A very fine day — to studio at about 10...
```

**Non-diary pages** — use the printed section title as the heading:

```markdown
## Cash Account — October

| Date | Description | Received | Paid |
|------|-------------|----------|------|
| 5    | Jno. Snedecor | $45.00 | |

## Bills Payable — January

*(empty)*
```

**Cover / blank pages:**

```markdown
## [Cover]

*(front cover, no text)*

## [Blank Page]

*(no content)*
```

### Illegibility conventions

| Situation | Markup |
|---|---|
| Single word unreadable | `[illegible]` |
| Multiple words unreadable, approximate count known | `[illegible — ~3 words]` |
| Physically torn or missing | `[torn]` |
| Page too damaged to read at all | `[illegible — entire passage]` |
.jpg`
