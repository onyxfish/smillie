# Product Specification: The Diaries of James David Smillie (1833–1909)

## Project Identity

| | |
|---|---|
| **Site name** | The Diaries of James David Smillie (1833–1909) |
| **Domain** | smilliediaries.com |

---

## Content & Data

- 8,210 diary photographs spanning 1865–1909, organized by year (~108–199 images per year)
- Each photograph is a two-page spread of the physical diary
- Each image has a corresponding Markdown transcription with YAML frontmatter containing: year, image filename, left/right page dates, and section types (`diary`, `almanac`, `cover`, `cash-account`, `title-page`, `address-list`, `bills-payable`, `blank`)
- The full corpus of 8,210 images will be available at launch; images lacking a transcription must be handled gracefully (show image with a "Transcription not yet available" placeholder)
- The site must be testable and runnable locally against a partial dataset

---

## URL Structure

| Resource | URL Pattern |
|---|---|
| Viewer (first image) | `smilliediaries.com/` |
| Specific photograph | `smilliediaries.com/1865/0001` |
| About page | `smilliediaries.com/about` |
| Images | `smilliediaries.com/images/1865/AAA-AAA_smilsmil_XXXXXXX.jpg` |

URLs update via `pushState` as the user navigates. The browser back/forward buttons work correctly. Copying the URL from the address bar always produces a link that returns to the same photograph.

---

## Pages

### Viewer (SPA — `index.html`)

The primary page. Implemented as a single-page application; the HTML shell is served for all viewer routes and client-side routing handles navigation.

**Layout (top to bottom):**

1. **Site header** — site name ("The Diaries of James David Smillie"), link to About page
2. **Navigation bar** — Prev/Next buttons + current position indicator (e.g. "1865 · 1 of 108")
3. **Date scrubber** — horizontal timeline slider spanning 1865–1909 (see §Navigation & Date Controls)
4. **Date picker** — full calendar date input for jumping to a specific date
5. **Search bar** — inline search input, opens results overlay
6. **Photograph** — full-width (constrained max-width) two-page-spread image
7. **Transcription** — rendered Markdown below the image; left and right page sections displayed together
8. **Prev/Next navigation** — repeated at the bottom for convenience

**Non-diary pages:** When the current image is a cover, almanac, blank page, etc., display the image and transcription as normal but suppress the date display.

**Missing transcriptions:** If a transcription file does not exist for an image, show the image with a tasteful placeholder message: "Transcription not yet available."

### About Page (`about/index.html`)

Static HTML page. Content sections:

- **Who James David Smillie was** — brief biography of the diary's author (1833–1909, American artist and engraver)
- **How transcriptions were made** — explain the Claude AI transcription process (Anthropic Claude Sonnet, batch API), accuracy caveats, note that transcriptions have not been human-verified but spot checks found them highly accurate
- **Source and provenance** — credit the Smithsonian Archives of American Art as the source; include required attribution language and link to the original collection
- **Licensing** — three distinct licenses covering different parts of the project (see §Licensing)
- **How to cite this resource** — suggested academic citation format
- **Contact / corrections** — how to report transcription errors (TK)
- **Technical notes** — static site, open source, build process overview

---

## Navigation & Date Controls

### Prev/Next

- "Previous" and "Next" buttons move one photograph (spread) at a time
- Wraps across year boundaries — pressing Next from the last image of 1865 goes to the first image of 1866
- Keyboard accessible: ← → arrow keys navigate prev/next

### Date Scrubber

- Horizontal `<input type="range">` slider
- Spans the full date range of the corpus (1865–1909)
- Year marker labels displayed above or below the track
- Image loads **on release** (not live while dragging) to avoid excessive image fetching
- Current position is reflected on the slider as the user navigates by other means

### Date Picker

- Full calendar date input (native `<input type="date">` or lightweight custom picker)
- Jumps to the photograph containing the selected date
- The mapping from calendar date → photograph identifier is pre-computed at build time and stored in `date-index.json`
- If the exact date has no diary entry (skipped day, non-diary page), jump to the nearest available date

### Search

- Search bar visible in the viewer toolbar
- Opens a results panel/overlay showing: matched text snippet, date/year, link to that photograph
- Powered by **Pagefind** — index built at the end of the static site build step
- After initial index chunk download, search is entirely client-side
- No search results should link to non-diary pages (covers, almanac pages, etc.) — TBD based on Pagefind configuration

---

## Visual Design

**Principles:** Clean, modern, understated. The photographs and transcribed text are the focus. No visual clutter.

**Palette:** Neutral whites and grays, single warm accent color, light mode only (initially).

**Typography:** A high-quality serif or humanist sans-serif for body text, honoring the historical content without affectation. System font stack or a single well-chosen web font (minimal load).

**Image display:** Full-width within a constrained max-width container (~900–1100px). Image is not cropped or zoomed by default.

**Responsiveness:** Desktop and tablet are the primary targets. Mobile is best-effort — the two-page-spread photographs are inherently wide, so a mobile layout will be constrained.

**Accessibility:** Keyboard navigable, ARIA labels on interactive controls, sufficient color contrast.

---

## Build Pipeline

Technology: **Python** (existing codebase) + **Vite** (JS/CSS bundler)

### Build Steps

1. **`python build_site.py`** — reads all `transcriptions/YYYY/*.md` files, parses YAML frontmatter, and produces:
   - `site/data/manifest.json` — ordered list of all images with metadata (year, sequence number, filename, dates, section types, transcription availability)
   - `site/data/date-index.json` — map from ISO date strings (`YYYY-MM-DD`) to photograph identifiers (`YYYY/NNNN`)
   - `site/index.html` — SPA shell
   - `site/about/index.html` — About page

2. **`npm run build`** (Vite) — bundles JS/CSS, copies assets, outputs to `dist/`

3. **`npx pagefind --site dist`** — crawls the built site, generates chunked client-side search index in `dist/pagefind/`

4. **`aws s3 sync dist/ s3://[bucket]/`** — deploys all static files; images are uploaded separately to `s3://[bucket]/images/`

### Local Development

```sh
python build_site.py   # generate manifest.json, date-index.json, HTML shells
npm run dev            # Vite dev server with hot module reload
```

The Python build step can be run against any subset of transcriptions (e.g. a single year) for fast local iteration.

### Directory Structure

```
smillie/
├── transcriptions/          # Source transcription .md files (existing)
├── site/                    # Source files for the web app
│   ├── index.html           # SPA shell (generated by build_site.py)
│   ├── about/
│   │   └── index.html       # About page (generated by build_site.py)
│   ├── data/
│   │   ├── manifest.json    # Generated
│   │   └── date-index.json  # Generated
│   ├── js/
│   │   ├── main.js          # SPA entry point
│   │   ├── viewer.js        # Image + transcription display
│   │   ├── nav.js           # Prev/Next, keyboard navigation
│   │   ├── scrubber.js      # Timeline slider
│   │   ├── datepicker.js    # Date input + lookup
│   │   └── search.js        # Pagefind search UI
│   └── css/
│       └── style.css        # All styles
├── dist/                    # Build output (gitignored)
├── build_site.py            # Python build script (to be written)
├── package.json             # Vite config + npm scripts
├── fetch_smillie.py         # Existing
├── transcribe_smillie.py    # Existing
└── ...
```

---

## Infrastructure

- **Hosting:** AWS S3 (static website) + **CloudFront** (CDN, HTTPS, custom domain)
- **Single bucket:** both static site assets and images (`/images/YYYY/filename.jpg`)
- **Domain:** smilliediaries.com — DNS pointed at CloudFront distribution
- **HTTPS:** via CloudFront + ACM certificate
- **No server-side logic** of any kind; the site functions entirely from S3-served static files
- **Redeployment:** running the build pipeline and syncing to S3 is the complete update process — no ongoing maintenance required

---

## Licensing

| Content | License |
|---|---|
| Smithsonian diary photographs | Fair use under Section 108 of the U.S. Copyright Act. Attribution to the Smithsonian Archives of American Art required. Images may only be used for personal, educational, and other non-commercial purposes. |
| Transcriptions and original site content | [CC-BY-NC-4.0](https://creativecommons.org/licenses/by-nc/4.0/) |
| Source code | [MIT](https://opensource.org/licenses/MIT) |

---

## Development Plan

### Phase 1 — Data & Build Foundation
1. Write `build_site.py`: parse all transcription frontmatter, produce `manifest.json` and `date-index.json`
2. Add `package.json` with Vite dev/build configuration
3. Establish directory structure: `site/` (source), `dist/` (build output)

### Phase 2 — Viewer Core
4. Build the viewer SPA shell: HTML structure, CSS design system (variables, typography, layout)
5. Image display: load and render photograph from S3/local path
6. Transcription display: fetch and render Markdown for the current image
7. Prev/Next navigation with URL updates via `pushState`
8. Keyboard navigation (← →)

### Phase 3 — Date Controls
9. Timeline scrubber: range input spanning full date range, year labels, loads image on release
10. Date picker: `<input type="date">`, lookup in `date-index.json`, jump to nearest image

### Phase 4 — Search
11. Integrate Pagefind into build pipeline
12. Build search UI: search bar, results overlay with snippets and links

### Phase 5 — About Page & Licensing
13. Write About/FAQ page content and HTML

### Phase 6 — Infrastructure
14. S3 bucket setup: static website hosting, bucket policy, image upload
15. CloudFront distribution: HTTPS, smilliediaries.com, cache behaviors
16. DNS configuration
17. Deployment script / Makefile target

### Phase 7 — Polish & QA
18. Test with partial and full datasets
19. Cross-browser and responsive checks
20. Accessibility pass (keyboard navigation, ARIA labels, focus management)
21. Performance review (image loading, search index size, Pagefind chunk loading)
