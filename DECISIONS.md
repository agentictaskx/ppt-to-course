# ppt-to-course — Design Decisions

## Decision Log

### D1: Fork vs Reuse Build Pipeline
**Decision:** Fork (independent copy)
**Date:** 2026-04-05
**Rationale:** User chose fork for independent evolution. The forked files are: `compile.js`, `course-content.schema.json`, `base.html`, `styles.css`, `scripts.js`. Only change to `compile.js` is branding — `SKILL_DIR` already resolves relative to `__dirname`.
**Trade-off:** Duplicated maintenance vs independent evolution. Bug fixes in codebase-to-course-v2 won't auto-propagate.

### D2: Unified Extraction Strategy
**Decision:** Text-first with OCR fallback for BOTH PPTX and PDF
**Date:** 2026-04-05
**Rationale:** User wanted consistent strategy. For PPTX, `python-pptx` provides structured text; for PDF, `PyMuPDF` provides text with font metadata. Both fall back to Tesseract OCR when text extraction yields <20 chars but images are present (indicating scanned/image-heavy content).

### D3: Image Handling — 3-Tier Strategy
**Decision:** Regenerate > Embed > Text Helper
**Date:** 2026-04-05
**Rationale:** User emphasized wanting to "fully understand charts and either recreate them or reuse them." Priority order:
1. **Regenerate** charts/diagrams as HTML/CSS/SVG (interactive, resolution-independent)
2. **Embed original** image as base64 (preserves visual fidelity)
3. **Text description** always accompanies any visual as helper context

User explicitly said text description is "the helper whenever needed" — not a "last resort." It should always be present alongside visuals.

### D4: PNG Export via Puppeteer
**Decision:** Node.js Puppeteer for HTML → PNG screenshot
**Date:** 2026-04-05
**Rationale:** Node.js already required for compile.js. Puppeteer takes full-page screenshot at 1200px width with 2x device scale. User wants this for social media sharing ("long-form infographic").

### D5: All 7 Themes at Launch
**Decision:** Ship all 7 themes: default, science, coding, finance, engineering, medical, humanities
**Date:** 2026-04-05
**Rationale:** User wanted comprehensive coverage from day one. Themes are LLM generation hints only (JSON files with metaphor style, quiz style, tone, actor hints, icon suggestions). The CSS design system stays consistent across all themes — only `accent_color` changes the visual appearance.

### D6: Actors = Domain Concepts
**Decision:** Presentation actors are domain concepts, not code components
**Date:** 2026-04-05
**Rationale:** Unlike codebase-to-course where actors are code components (API, Database, Frontend), presentations have interacting concepts. Examples:
- Finance: "Supply", "Demand", "Price"
- Science: "Hypothesis", "Experiment", "Data"
- Engineering: "Load", "Structure", "Material"
These actors power `chat` and `flow` interactive elements.

### D7: Slide → Course Element Mapping
**Decision:** 13-row mapping table in SKILL.md
**Date:** 2026-04-05
**Rationale:** Deterministic mapping from slide content patterns to course element types. The LLM uses this table when generating course-content.json. Key mappings:
- Bullet lists → `step_cards` or `icon_rows` (visual cards > boring bullets)
- Charts → `custom_html` with regenerated SVG (or embedded image fallback)
- Speaker notes → expanded `prose` blocks (notes are richer than slide text)
- Section dividers → module boundaries

## Source Skills Referenced

| Skill | What We Took | Path |
|---|---|---|
| **codebase-to-course-v2** | Build pipeline (compile.js, templates, course-content schema), workflow structure, content rules, design system | `~/.claude/skills/codebase-to-course-v2/` |
| **frontend-slides** | PPTX extraction pattern (extract-pptx.py), style preset concept | `~/.claude/skills/frontend-slides/` |

## Research: Document Processing Libraries

| Library | Stars | Used For | In Our Skill |
|---|---|---|---|
| python-pptx | ~5K | PPTX text/image/table extraction | `extract-pptx.py` |
| PyMuPDF (fitz) | ~22K | PDF text/image extraction, page rendering | `extract-pdf.py` |
| Pillow | ~12K | Image processing, slide rendering fallback | Both extractors |
| pytesseract | ~5K | OCR for scanned/image-heavy pages | Both extractors (optional) |
| Puppeteer | ~89K | Headless Chrome for HTML→PNG | `export-png.js` |
| reveal.js | ~67K | Considered but not used | N/A — we generate our own HTML |
| html2canvas | ~32K | Considered but not used | N/A — Puppeteer is more reliable |
