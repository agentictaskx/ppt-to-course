# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Claude Code skill that converts PowerPoint (PPTX) or PDF slide decks into interactive single-page HTML courses. Forked from codebase-to-course-v2 with slide-specific extraction, 7 subject themes, and optional PNG infographic export.

## Commands

```bash
# Extract slides from PPTX
python skill/scripts/extract-pptx.py <file.pptx> <output_dir>

# Extract slides from PDF
python skill/scripts/extract-pdf.py <file.pdf> <output_dir>

# Install Python dependencies
pip install -r skill/scripts/requirements.txt

# Compile course JSON into HTML
node skill/build/compile.js <course-content.json> --output ./output --mode single

# Export HTML to PNG infographic (requires Puppeteer)
node skill/scripts/export-png.js <course.html> <output.png>
```

## Architecture

```
Slide deck → Extract (Python) → slide-profile.json + images
    → LLM generates course-content.json → compile.js assembles HTML
    → Optional: export-png.js screenshots to PNG
```

### Pipeline Stages

1. **Extract** — `extract-pptx.py` or `extract-pdf.py` produces `slide-profile.json` (per `schemas/slide-profile.schema.json`) + `assets/` (images) + `references/` (slide PNGs for visual inspection)
2. **Theme Select** — auto-detected from content, 7 options in `skill/themes/*.json` (science, coding, finance, engineering, medical, humanities, default)
3. **Generate** — LLM produces `course-content.json` per module, conforming to `schemas/course-content.schema.json`
4. **Build** — `compile.js` assembles JSON + templates into self-contained HTML
5. **Export** — Optional Puppeteer-based PNG screenshot for social sharing

### Key Design Decisions (see DECISIONS.md)

- **D1:** Forked from codebase-to-course-v2 (independent copy, not shared)
- **D2:** Text-first extraction with OCR fallback for both PPTX and PDF
- **D3:** Image handling: Regenerate as HTML/SVG > Embed base64 > Text description (always present as helper)
- **D6:** Actors are domain concepts (Supply/Demand/Price), not code components

### Image Concurrency Rule

**Never read multiple image files (PNG, JPG) in parallel.** Always read images one at a time. Parallel image reads cause API Error 400.

## File Structure

```
skill/
├── SKILL.md                    # AI instructions (how to use this skill)
├── schemas/
│   ├── course-content.schema.json   # Course data shape
│   └── slide-profile.schema.json    # Slide extraction shape
├── scripts/
│   ├── extract-pptx.py         # PPTX → slide-profile.json (python-pptx)
│   ├── extract-pdf.py          # PDF → slide-profile.json (PyMuPDF)
│   ├── export-png.js           # HTML → PNG screenshot (Puppeteer)
│   └── requirements.txt        # Python deps
├── build/
│   └── compile.js              # JSON + templates → HTML
├── templates/                  # Static HTML/CSS/JS templates
└── themes/                     # 7 subject theme JSON files
extracted/                      # Working directory for extracted slide data
```
