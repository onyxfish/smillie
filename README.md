# James David Smillie's Diary

This repository contains a transcriptions of the diaries of James David Smillie for the years 1865 to 1909, and a web application for browsing through them. The physical diaries are stored in the [_James D. Smillie and Smillie family papers, 1853-1957_](https://www.aaa.si.edu/collections/james-d-smillie-and-smillie-family-papers-13469/series-1) in the Archives of American Art.

Transcriptions of these diaries were created by feeding photographs from the archives to Anthropic's Claude Sonnet 4.6 model. These transcriptions have not been human verified, but spot checks have found them to be highly accurate.

All source code in this repository has been created with the assistance of AI.

## What's in this repository?

## Transcriptions

The raw transcriptions are stored in the `transcriptions` folder in Markdown with YAML frontmatter. For example, here is the frontmatter from `transcriptions/1865/AAA-AAA_smilsmil_2303578.md`.

```yaml
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
```

Please note the original photographs are NOT stored in this repository as they are very large (7.4G).