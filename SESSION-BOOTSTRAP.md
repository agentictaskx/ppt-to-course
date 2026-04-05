# ppt-to-course — Session Bootstrap

**Last updated:** 2026-04-05
**Status:** v1 implementation complete, awaiting first dry run

## What This Is

A Claude Code skill that converts PowerPoint (PPTX) or PDF slide decks into interactive single-page HTML courses. Built as a fork of `codebase-to-course-v2` with custom extraction scripts.

## Skill Location

```
~/.claude/skills/ppt-to-course/     (19 files, 234 KB)
```

## Test Files Available

```
C:/Users/nealzhang/project/pptx-to-course/
├── Video PPT.pptx          # 54 MB — test deck
└── 北大炒股课.ppt            # 17 MB — Chinese finance lecture (NOTE: .ppt not .pptx)
```

**Known gap:** The extractor uses `python-pptx` which only supports `.pptx` format. The `北大炒股课.ppt` file is old `.ppt` format and will need conversion or a different parser.

## Plan & Design Docs

- **Implementation plan:** `~/.claude/plans/polished-singing-blossom.md`
- **Design decisions:** See `DECISIONS.md` in this directory
- **Skill README:** `~/.claude/skills/ppt-to-course/README.md`

## Architecture Overview

```
PPT/PDF ──→ extract-pptx.py / extract-pdf.py ──→ slide-profile.json
                                                        │
                                                        ▼
                                              LLM generates course JSON
                                                        │
                                                        ▼
                                              compile.js ──→ course.html
                                                        │
                                                        ▼ (optional)
                                              export-png.js ──→ infographic.png
```

## File Inventory

| Category | Files | Notes |
|---|---|---|
| **Skill definition** | `SKILL.md` | 6-step workflow, mapping table, image strategy |
| **Schemas** | `schemas/slide-profile.schema.json` | NEW — extracted slide data |
| | `schemas/course-content.schema.json` | Forked from codebase-to-course-v2 |
| **Extraction** | `scripts/extract-pptx.py` (41 KB) | Enhanced from frontend-slides |
| | `scripts/extract-pdf.py` (36 KB) | PyMuPDF + OCR fallback |
| **Build** | `build/compile.js` (25 KB) | Forked from codebase-to-course-v2 |
| | `templates/base.html, styles.css, scripts.js` | Forked as-is |
| **Export** | `scripts/export-png.js` (7 KB) | Puppeteer full-page screenshot |
| **Themes** | `themes/*.json` (7 files) | default, science, coding, finance, engineering, medical, humanities |
| **Docs** | `README.md`, `scripts/requirements.txt` | Setup and usage |

## Key Design Decisions

1. **Forked pipeline** (not shared) — independent evolution from codebase-to-course-v2
2. **Text-first + OCR fallback** — both PPTX and PDF use same strategy
3. **3-tier image handling** — regenerate as HTML/SVG > embed original > text description as helper
4. **Puppeteer for PNG** — Node.js already required for compile.js
5. **7 themes** — LLM hints only (accent color, metaphor style, quiz style, tone), CSS stays consistent
6. **Actors = concepts** — presentations have interacting concepts, not code components

## Dependencies

```bash
# Python (required)
pip install python-pptx PyMuPDF Pillow pytesseract

# Node.js (required for build)
node build/compile.js  # uses only fs/path, no npm install needed

# Puppeteer (optional, for PNG export)
npm install -g puppeteer
```

## Next Steps (Dry Run Checklist)

- [ ] Install Python deps: `pip install -r ~/.claude/skills/ppt-to-course/scripts/requirements.txt`
- [ ] Test PPTX extraction: `python extract-pptx.py "Video PPT.pptx" ./test-output/`
- [ ] Test PDF extraction: export a PPTX to PDF, run `python extract-pdf.py`
- [ ] Handle .ppt format: `北大炒股课.ppt` is old format — needs conversion or LibreOffice
- [ ] Test full pipeline: invoke `ppt to course` with a real file
- [ ] Test PNG export: `node export-png.js course.html infographic.png`
- [ ] Fix any issues found during dry run

## Known Issues / Watch For

1. **Old .ppt format**: `python-pptx` doesn't support `.ppt` — only `.pptx`. May need `libreoffice --convert-to pptx` as preprocessing step.
2. **Slide rendering**: `extract-pptx.py` tries COM/LibreOffice for slide PNGs, with Pillow placeholder fallback. May need LibreOffice installed for best results.
3. **OCR dependency**: `pytesseract` requires system Tesseract installation. Gracefully handled when missing.
4. **Large presentations**: 50+ slide decks may need careful module splitting to avoid LLM quality degradation.
5. **Chart regeneration**: The LLM decides whether to regenerate or embed — quality depends on how well the slide profile captures chart data.
