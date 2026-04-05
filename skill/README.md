# ppt-to-course

Converts PowerPoint presentations (`.pptx`) and PDF slide decks into interactive, single-page HTML courses. The skill extracts all content from each slide — text, images, charts, tables, speaker notes — reorganizes it into an engaging learning experience with quizzes, animated walkthroughs, and interactive diagrams, and outputs a self-contained HTML file. Charts and diagrams are regenerated as HTML/SVG when possible; original images are embedded as fallback. An optional PNG export produces a long-form infographic suitable for sharing on social media.

## Quick Start

### From a PPTX file

```
ppt to course

> Here's my presentation: quarterly-review.pptx
```

The skill will:
1. Extract all slides, images, tables, charts, and speaker notes
2. Show you a summary and suggest a theme
3. Generate an interactive HTML course module by module
4. Open the result in your browser

### From a PDF

```
slides to course

> Convert this PDF: strategy-deck.pdf
```

Works the same way. PDF extraction uses text-first parsing with OCR fallback for scanned or image-heavy pages.

### With a specific theme

```
ppt to course using the finance theme

> Here's the deck: market-analysis.pptx
```

## Prerequisites

### Python 3.8+

Required for content extraction from PPTX and PDF files.

```bash
pip install -r scripts/requirements.txt
```

This installs:
- **python-pptx** — PPTX parsing (text, shapes, tables, charts, images)
- **PyMuPDF** — PDF parsing (text extraction, image extraction, page rendering)
- **Pillow** — Image processing
- **pytesseract** — OCR fallback for scanned/image-heavy slides

### Node.js 18+

Required for building the HTML course and optional PNG export.

```bash
# For PNG export only (optional)
npm install puppeteer
```

### Tesseract OCR (optional)

Only needed if your slides are scanned images or have very little extractable text.

- **Windows:** Download installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
- **macOS:** `brew install tesseract`
- **Linux:** `sudo apt install tesseract-ocr`

If Tesseract is not installed, the skill will still work — it just won't be able to OCR scanned pages. You'll see a warning, not an error.

## Themes

Seven built-in themes control how the LLM generates course content — the metaphors it uses, how quizzes are framed, and the overall tone. The visual design system (CSS) stays consistent across all themes; themes influence *content generation*, not styling.

| Theme | Accent | Best For | Tone |
|-------|--------|----------|------|
| **default** | vermillion | General presentations, business, productivity | Friendly, clear, conversational |
| **science** | teal | Biology, chemistry, physics, research | Curious, precise, evidence-based |
| **coding** | forest | Software engineering, DevOps, architecture | Technical, practical, example-driven |
| **finance** | amber | Markets, investing, corporate finance, economics | Analytical, strategic, numbers-driven |
| **engineering** | coral | Mechanical, electrical, civil, systems engineering | Systematic, precise, safety-conscious |
| **medical** | teal | Clinical medicine, pharmacology, anatomy | Clinical, empathetic, case-based |
| **humanities** | vermillion | Philosophy, history, literature, social sciences | Reflective, nuanced, multi-perspective |

The skill auto-detects the best theme from your slide content and suggests it. You can always override:

```
Use the medical theme for this presentation
```

Theme files live in `themes/` as JSON. You can inspect or modify them to customize generation behavior.

## PNG Export

After generating an HTML course, you can export it as a long-form PNG infographic:

```bash
node scripts/export-png.js output/course.html output/infographic.png
```

### Options

```
node scripts/export-png.js <input.html> <output.png> [--width 1200]
```

| Argument | Description | Default |
|----------|-------------|---------|
| `input.html` | Path to the generated HTML course | (required) |
| `output.png` | Path for the output PNG file | (required) |
| `--width N` | Viewport width in pixels | 1200 |

### Custom Chrome path

If you have Chrome/Chromium installed and don't want Puppeteer to download its own:

```bash
npm install puppeteer-core
PUPPETEER_EXECUTABLE_PATH="/path/to/chrome" node scripts/export-png.js course.html out.png
```

## How It Works

### Extraction Pipeline

```
PPTX/PDF  -->  extract-pptx.py / extract-pdf.py  -->  slide-profile.json + assets/
```

The extractors produce a structured `slide-profile.json` that captures every slide's content with formatting, layout hints, and image metadata. Each slide is also rendered as a reference PNG for visual inspection by the LLM.

### Content Generation

```
slide-profile.json + theme + reference images  -->  LLM  -->  course-content.json
```

The LLM reads the extracted profile and generates interactive course elements:

| Slide Content | Becomes |
|---------------|---------|
| Bullet lists | Step cards, icon rows |
| Comparisons | Side-by-side diff views |
| Process flows | Animated flow walkthroughs |
| Architecture diagrams | Clickable SVG components |
| Code snippets | Code-to-English translations |
| Charts (bar/line/pie) | Regenerated SVG/Chart.js |
| Photos/screenshots | Embedded images with descriptions |
| Tables | Styled HTML tables |
| Speaker notes | Expanded prose explanations |
| Section dividers | Module boundaries |

### Build

```
course-content.json  -->  compile.js  -->  course.html
```

The compiler assembles the final self-contained HTML file with all styles, scripts, and assets inlined.

## File Structure

```
ppt-to-course/
├── SKILL.md                          # Skill definition (triggers, workflow)
├── README.md                         # This file
├── schemas/
│   ├── slide-profile.schema.json     # Extracted slide data structure
│   └── course-content.schema.json    # Course JSON schema (forked)
├── scripts/
│   ├── extract-pptx.py               # PPTX content extractor
│   ├── extract-pdf.py                # PDF content extractor (PyMuPDF + OCR)
│   ├── export-png.js                 # HTML-to-PNG via Puppeteer
│   └── requirements.txt              # Python dependencies
├── build/
│   └── compile.js                    # HTML compiler
├── templates/
│   ├── base.html                     # HTML shell
│   ├── styles.css                    # Design system
│   └── scripts.js                    # Interactive behaviors
└── themes/
    ├── default.json
    ├── science.json
    ├── coding.json
    ├── finance.json
    ├── engineering.json
    ├── medical.json
    └── humanities.json
```

## Troubleshooting

### "No module named 'pptx'" or "No module named 'fitz'"

Python dependencies aren't installed. Run:

```bash
pip install -r scripts/requirements.txt
```

If you use virtual environments:

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux
pip install -r scripts/requirements.txt
```

### "TesseractNotFoundError" or OCR warnings

Tesseract OCR is optional. If you see this warning, it means:
- Your slides have scanned/image-heavy pages that need OCR
- Tesseract isn't installed on your system

**To fix:** Install Tesseract (see Prerequisites above) and make sure it's on your PATH.

**To ignore:** If your slides are text-based (not scanned images), OCR isn't needed. The warning is informational — extraction will still work for all text-based content.

### "Error: Puppeteer is not installed"

PNG export requires Puppeteer. Install it:

```bash
npm install puppeteer
```

If npm install hangs on the Chromium download, you can use an existing Chrome:

```bash
npm install puppeteer-core
set PUPPETEER_EXECUTABLE_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
node scripts/export-png.js course.html out.png
```

### "Could not find expected browser" (Puppeteer)

Puppeteer's bundled Chromium may not have downloaded correctly. Try:

```bash
npx puppeteer browsers install chrome
```

### PNG export looks wrong (missing animations, hidden elements)

The export script forces all animations visible and all chat messages shown. If elements are still hidden, the CSS class names may have changed. Check that:
- Animated elements use the `.animate-in` class
- Chat messages use the `.chat-message` class

### Extraction produces empty or minimal content

1. **For PPTX:** The file might use non-standard shapes or embedded objects. Check if the presentation opens correctly in PowerPoint.
2. **For PDF:** The file might be image-only (scanned). Install Tesseract for OCR support.
3. **Check the reference images** in the `assets/` folder — they show exactly what the extractor saw on each page.

### Large presentations take too long

Course content is generated module by module to maintain quality. For very large decks (50+ slides):
- Consider splitting into logical sections
- The skill will automatically create module boundaries at section dividers
- Each module generates independently, so quality stays consistent

### Charts aren't regenerated (showing as embedded images)

Chart regeneration works best when:
- Charts use standard types (bar, line, pie, scatter)
- Data is accessible in the chart object (PPTX) or clearly labeled (PDF)
- The chart isn't too complex (>10 series may fall back to image)

When regeneration isn't possible, the original image is embedded at full quality with a text description alongside it.
