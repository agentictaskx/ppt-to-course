# ppt-to-course — History

## 2026-04-05: v1 Implementation

### Session Summary
Created the complete `ppt-to-course` Claude Code skill from scratch.

### Process
1. **Research phase**: Explored `codebase-to-course-v2` skill (8 files, schema-driven pipeline), `frontend-slides` skill (PPTX extraction), and GitHub document processing ecosystem
2. **Planning phase**: Created detailed implementation plan with 8 tasks across 3 phases. User clarified:
   - Fork (not reuse) build pipeline
   - Text-first + OCR fallback for both PPTX and PDF
   - Puppeteer for PNG export
   - All 7 themes at launch
   - Image handling: regenerate > embed > text helper (not "last resort")
3. **Implementation phase**: Delegated to 3 parallel Engineer subagents:
   - Phase 1 (timed out, re-delegated): SKILL.md, schemas, forked build pipeline
   - Phase 2: extract-pptx.py, extract-pdf.py
   - Phase 3: 7 themes, export-png.js, requirements.txt, README.md

### Files Created (19 total, 234 KB)
```
~/.claude/skills/ppt-to-course/
├── SKILL.md                          (13 KB)
├── schemas/
│   ├── slide-profile.schema.json     (6.5 KB)
│   └── course-content.schema.json    (13.7 KB, forked)
├── scripts/
│   ├── extract-pptx.py               (41 KB)
│   ├── extract-pdf.py                (36 KB)
│   ├── export-png.js                 (6.7 KB)
│   └── requirements.txt              (71 B)
├── build/
│   └── compile.js                    (25 KB, forked)
├── templates/
│   ├── base.html                     (1.7 KB, forked)
│   ├── styles.css                    (38.5 KB, forked)
│   └── scripts.js                    (26 KB, forked)
├── themes/
│   ├── default.json                  (1.7 KB)
│   ├── science.json                  (2 KB)
│   ├── coding.json                   (2.2 KB)
│   ├── finance.json                  (2.3 KB)
│   ├── engineering.json              (2.4 KB)
│   ├── medical.json                  (2.5 KB)
│   └── humanities.json               (2.5 KB)
└── README.md                         (9.6 KB)
```

### Status
- Skill is detected by Claude Code (appears in skills list)
- No dry run performed yet
- Test files available: `Video PPT.pptx` (54 MB), `北大炒股课.ppt` (17 MB, old .ppt format)
