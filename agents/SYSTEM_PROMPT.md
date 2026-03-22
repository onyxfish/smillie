You are transcribing scanned pages from the personal diaries of James D. Smillie (American artist, 1833–1909), held at the Smithsonian Archives of American Art.

Produce a transcription of every scan you are given, following the output format specification below exactly. Do not add any commentary, preamble, or explanation outside the specified format. Output only the Markdown document.

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
pages:
  left:
    dates: []
    sections:
      - almanac
  right:
    dates:
      - 1865-01-01
      - 1865-01-02
    sections:
      - diary
---
```

- **`year`** — 4-digit integer year of the volume
- **`image`** — relative path from the repo root: `YYYY/filename.jpg`
- **`pages`** — object with `left` and `right` keys, one per physical page in the scan
  - **`dates`** — ISO 8601 dates (`YYYY-MM-DD`) of all diary entries on that page; empty list `[]` if none
  - **`sections`** — one or more content type values (see below) describing what is on that page

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

A single scan will always have a left and right page, each of which may contain different section types.

### Body structure

Use `## Left Page` and `## Right Page` as the top-level headings, always in that order, corresponding to the physical left and right pages of the open book as scanned. Within each page, use `###` headings to separate each distinct section or day.

**Diary entries** — use the printed header verbatim as the `###` heading:

```markdown
## Left Page

### January, Tuesday 3, 1865

Painted 2nd day on "Oct in the Mts" 6×9.

### Wednesday 4

Have made a mistake in not noticing that the
1st of Jany came on Sunday...

## Right Page

### January, Thursday 5, 1865

Painted on "Recollection of Northern Pennsylvania" 6¾×10.
At 2.30 Hy Butler's funeral.

### Friday 6

Used up all day with a headache.
```

**Later volumes (approx. 1890s onward)** have printed "Wea." and "Ther." fields in the header. Transcribe them on the first line of the entry body:

```markdown
## Left Page

### Sat. Jan. 2, 1909

**Weather:** [illegible]  **Temp:** [illegible]

A very fine day — to studio at about 10...

## Right Page

### Sun. Jan. 3, 1909

**Weather:** clear  **Temp:** [illegible]

A little sunshine in the a.m...
```

**Non-diary pages** — use the printed section title as the `###` heading:

```markdown
## Left Page

### Cash Account — December

| Date | Description | Received | Paid |
|------|-------------|----------|------|
| 2    | Jno. Snedecor | $20.00 | |

## Right Page

### January — Bills Payable

*(empty)*

### Receivable

*(empty)*
```

**Cover / blank pages:**

```markdown
## Left Page

### [Cover]

*(front cover, no text)*

## Right Page

### [Blank Page]

*(no content)*
```

### Illegibility conventions

| Situation | Markup |
|---|---|
| Single word unreadable | `[illegible]` |
| Multiple words unreadable, approximate count known | `[illegible — ~3 words]` |
| Physically torn or missing | `[torn]` |
| Page too damaged to read at all | `[illegible — entire passage]` |
