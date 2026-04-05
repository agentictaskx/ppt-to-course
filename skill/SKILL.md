---
name: ppt-to-course
description: "Turn any PowerPoint or PDF slide deck into a beautiful, interactive single-page HTML course. Uses a schema-driven pipeline: extraction scripts parse slides into structured JSON, the LLM generates course content, and a build script assembles the final HTML. Supports 7 subject themes and optional PNG infographic export for social media sharing. Trigger phrases: 'ppt to course', 'slides to course', 'convert this presentation', 'presentation to course', 'pdf slides to course', 'turn these slides into a course', 'ppt-to-course'."
---

# PPT-to-Course

Transform slide decks into interactive, single-page HTML courses. Extract content from PPTX or PDF, generate structured course JSON, and build a polished learning experience.

**You do NOT generate HTML, CSS, or JavaScript.** You generate JSON that conforms to the course content schema. The build script (`build/compile.js`) assembles the final course from your JSON + static templates.

## Workflow

### Step 1: First-Run Welcome

When triggered without a specific file:

> **I can turn any slide deck into an interactive course that teaches the material in a visual, engaging way.**
>
> Just point me at a presentation:
> - **A local file** -- e.g., "turn ./slides.pptx into a course"
> - **A PDF** -- e.g., "convert presentation.pdf to a course"
> - **A URL** -- e.g., "make a course from https://example.com/deck.pptx"
>
> I'll extract all slides, images, charts, and speaker notes, then reorganize everything into an interactive learning experience with quizzes, animations, and visual explanations.

If given a URL, download the file first.

### Step 2: Input Detection & Extraction

1. **Detect file type** from extension: `.pptx` or `.pdf`
2. **Install Python dependencies** if not already available:
   ```bash
   pip install -r ~/.claude/skills/ppt-to-course/scripts/requirements.txt
   ```
3. **Run the appropriate extraction script:**
   - PPTX:
     ```bash
     python ~/.claude/skills/ppt-to-course/scripts/extract-pptx.py <file> <output_dir>
     ```
   - PDF:
     ```bash
     python ~/.claude/skills/ppt-to-course/scripts/extract-pdf.py <file> <output_dir>
     ```
4. **Both scripts produce:**
   - `slide-profile.json` -- structured extraction conforming to `schemas/slide-profile.schema.json`
   - `assets/` -- extracted images
   - `references/` -- reference renders of each slide as PNG (for LLM visual inspection)

5. **Show summary and wait for confirmation:**

> "This is **[title]** -- [N] slides. Detected subject: **[subject]**. [M] images extracted. Ready to generate the course?"

Wait for user confirmation before proceeding.

### Step 3: Theme Selection

1. **Auto-suggest theme** based on `detected_subject` from the slide profile:
   - `science` -> `themes/science.json`
   - `coding` -> `themes/coding.json`
   - `finance` -> `themes/finance.json`
   - `engineering` -> `themes/engineering.json`
   - `medical` -> `themes/medical.json`
   - `humanities` -> `themes/humanities.json`
   - `general` -> `themes/default.json`

2. Present the suggestion: "Based on the content, I'd suggest the **[theme]** theme. Want to use it, or pick a different one?"

3. User confirms or picks different theme.

4. Read the theme JSON from `~/.claude/skills/ppt-to-course/themes/[theme].json` and use its hints throughout generation.

### Step 4: Generate Course Content -> JSON

Generate course content as JSON conforming to `schemas/course-content.schema.json`.

**Generate per-module** -- write each module as a separate JSON object, then combine into the final course content file. This prevents quality degradation in later modules.

**Generation order:**
1. Course metadata (title, subtitle, accent color from theme, actors from key concepts, glossary)
2. Module 1 content
3. Module 2 content
4. ... (one at a time)

**During generation:**
- Use the **Slide -> Course Element Mapping Table** (below) to decide how each slide's content translates
- Apply the **Image Handling Strategy** (below) for all visuals
- Use the theme's `metaphor_style`, `quiz_style`, `tone`, and `actor_generation_hints`
- Read reference images from `references/` to visually inspect charts/diagrams the text extraction may have missed

**Output:** Write `course-content.json` to the output directory.

### Step 5: Build -> HTML

Run the build script to compile the course:

```bash
node ~/.claude/skills/ppt-to-course/build/compile.js course-content.json --output ./output --mode both
```

This produces:
- `output/course.html` -- single self-contained file (distributable)
- `output/dev/` -- multi-file version (for iteration)

Open `output/course.html` in the browser for the user to review.

### Step 6: Iterate & Export

**Iteration:** If the user wants changes to a specific module:
1. Regenerate only that module's JSON
2. Update `course-content.json`
3. Re-run the build script

**PNG Export (optional):** For social media sharing as a long-form infographic:
```bash
node ~/.claude/skills/ppt-to-course/scripts/export-png.js output/course.html output/infographic.png
```

---

## Content Guidelines

### Target Audience

**Learners encountering this material for the first time** -- people reviewing slide content without a live presenter. Assume the audience does NOT have the benefit of the speaker walking them through slides. The course must stand alone as a complete learning experience. Every technical term needs a glossary definition.

### Curriculum Design (4-7 modules)

| Position | Purpose | How it maps to slides |
|---|---|---|
| 1 | Introduction & big picture | Title slide + opening slides that set context |
| 2 | Core concepts explained | Key content slides with foundational ideas |
| 3 | How the pieces connect | Relationship/process/workflow slides |
| 4 | Deep dive: details & evidence | Data-heavy slides, charts, tables |
| 5 | Practical implications | Application slides, examples, case studies |
| 6 | Challenges & edge cases | Warning slides, caveats, limitations |
| 7 | Summary & next steps | Closing slides, takeaways |

Adapt the number of modules to the presentation's complexity. A 10-slide deck might only need 3-4 modules. A 60-slide deck might need 6-7. Section divider slides are natural module boundaries.

### Content Rules

1. **Max 2-3 sentences per prose block.** If writing a 4th sentence, convert to a visual element instead.
2. **Every screen >= 50% visual** -- diagrams, cards, animations, anything non-paragraph.
3. **One concept per screen.** If you need more space, add another screen.
4. **Unique metaphors per concept.** NEVER reuse metaphors. Each concept gets its own analogy.
5. **Speaker notes are gold.** Notes often contain richer explanations than slide text. Expand them into prose and visual elements -- don't discard them.
6. **Quizzes test application, not memory.** "Given this scenario, which approach would you choose?" NOT "What does acronym X stand for?"

### Required Elements Per Module
- At least 1 translation/code block OR equivalent visual element (e.g., a `diff_view`, `step_cards`, or `custom_html` with a recreated chart)
- At least 1 quiz (3-5 questions, placed at end)
- At least 3 screens

### Required Across Entire Course
- At least 1 group chat animation (concepts "discussing" with each other)
- At least 1 data flow animation (showing how ideas/data connect)

### Glossary

Define every technical term. Be extremely aggressive -- if there's even a 1% chance a learner doesn't know a word, add it to the glossary. The build script auto-injects tooltips on first occurrence per module.

---

## Slide -> Course Element Mapping Table

| Slide Content | -> Course Element | Notes |
|---|---|---|
| Bullet list (3-6 items) | `step_cards` or `icon_rows` | Visual cards > bullets. Always. |
| Comparison / before-after | `diff_view` | Side-by-side comparison |
| Process / workflow | `flow` animation | Interactive step-through with concept actors |
| System / architecture diagram | `architecture` | Clickable components; regenerate as SVG if possible |
| Code snippet | `translation` | Code <-> English side-by-side |
| Key insight / quote | `callout` (accent) | Highlighted insight box |
| Warning / caveat | `callout` (warning) | Alert styling |
| Chart (bar/line/pie) | `custom_html` with regenerated SVG/Chart.js | Regenerate 1:1 from data; fallback: embed original image |
| Photo / screenshot | `custom_html` with `<img>` | Embed as base64 data URI |
| Table | `custom_html` with styled `<table>` | Recreate with course CSS classes |
| Section divider slide | New module boundary | Use as structural break between modules |
| Speaker notes | Expand into `prose` | Notes are richer than slide text -- use them |
| Multi-column layout | `pattern_cards` grid | Cards preserve multi-column intent |
| Definition / terminology | `badge_list` | Term + definition pairs |
| Timeline / sequential events | `step_cards` | Numbered sequential cards |
| Equation / formula | `custom_html` with styled math | Recreate with HTML/MathML if possible |

---

## Image Handling Strategy (3-Tier)

### 1. Regenerate (preferred)

Charts, simple diagrams, tables, and flowcharts -> recreate as HTML/CSS/SVG with matching data and style within a `custom_html` element.

**When to regenerate:**
- Bar/line/pie/scatter charts (use Chart.js or inline SVG)
- Simple flowcharts and process diagrams (use CSS flexbox/grid + borders)
- Tables (use `<table>` with course CSS)
- Simple comparison diagrams (use CSS grid)

The regenerated version is interactive, resolution-independent, and matches the course design system.

### 2. Embed original (fallback)

Photos, complex illustrations, screenshots, logos -> embed as base64 `<img>` inside a `custom_html` element.

**When to embed:**
- Photographs and real-world images
- Complex illustrations with many elements
- Screenshots of UIs or applications
- Brand logos and icons
- Any diagram too complex to faithfully regenerate

Read the image file from `assets/`, base64-encode it, and embed:
```html
<img src="data:image/png;base64,..." alt="Description" style="max-width:100%;border-radius:8px;">
```

### 3. Text description (helper)

**Always** add descriptive text alongside any visual -- whether regenerated or embedded. This ensures:
- Accessibility for screen readers
- Learning value even without the image
- Context that the original slide assumed the presenter would provide verbally

Use `prose` elements before/after the visual, or captions within the `custom_html`.

---

## Actor Generation

Presentations have **concepts that interact**, not code components. Identify 3-5 key concepts from the slide content and cast them as actors for `chat` and `flow` elements.

**Examples by domain:**
| Domain | Example Actors |
|---|---|
| Finance | Supply, Demand, Price, Risk, Return |
| Science | Hypothesis, Experiment, Data, Theory, Evidence |
| Engineering | Design, Prototype, Test, Iterate, Deploy |
| Medical | Symptom, Diagnosis, Treatment, Outcome, Prevention |
| Coding | Client, Server, Database, Cache, API |
| Humanities | Thesis, Evidence, Context, Counterargument, Synthesis |
| General | Problem, Analysis, Solution, Validation, Result |

Use the theme's `actor_generation_hints` to guide actor selection. Actors power group chat animations where concepts "discuss" their relationships, making abstract ideas tangible.

---

## JSON Schema Quick Reference

### Element Types

| Type | Key Fields | Use When |
|---|---|---|
| `prose` | `content` (HTML string) | Short text blocks (<= 3 sentences) |
| `translation` | `file`, `code_lines[{code, english}]` | Explaining code snippets from slides |
| `chat` | `messages[{sender, text}]` | Concepts "talking" to each other |
| `flow` | `steps[{from, to, label, highlight}]` | Data/concept flow between actors |
| `callout` | `variant`, `title`, `content` | Insight boxes (accent/info/warning) |
| `step_cards` | `steps[{title, description}]` | Sequential processes or lists |
| `pattern_cards` | `cards[{icon, title, description}]` | Feature/concept grids |
| `icon_rows` | `items[{icon, title, description}]` | Component/concept lists |
| `file_tree` | `tree` (nested nodes) | File/hierarchy structures |
| `architecture` | `zones[{label, components[]}]` | System/concept architecture diagrams |
| `badge_list` | `badges[{code, description}]` | Term/definition annotations |
| `layer_toggle` | `layers{html, css, js}` | Layer-by-layer demo |
| `spot_the_bug` | `lines[{code, is_bug}]`, `bug_explanation` | Bug-finding challenge |
| `diff_view` | `before{code}`, `after{code}`, `description` | Before/after comparison |
| `custom_html` | `html` (raw HTML) | Escape hatch: charts, embedded images, tables, formulas |

### What You Do NOT Generate

- No CSS (static template handles all styling)
- No JavaScript (static script handles all interactivity)
- No HTML scaffolding (base template handles layout)
- No `<style>` or `<script>` tags
- No tooltip markup (build script auto-injects from glossary)

You ONLY output structured JSON. The build pipeline handles everything else.
