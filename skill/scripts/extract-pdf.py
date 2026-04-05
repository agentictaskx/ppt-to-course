#!/usr/bin/env python3
"""
PDF content extractor for ppt-to-course skill.

Extracts ALL content from a PDF file (typically slide deck exports) and
produces a slide-profile.json conforming to slide-profile.schema.json,
plus extracted images in assets/ and reference PNGs in references/.

Strategy: Text-first with OCR fallback.
- PyMuPDF (fitz) provides structured text with font metadata
- For scanned/image-heavy pages with <20 chars extractable text,
  fall back to rendering at 300 DPI + OCR via pytesseract

Usage:
    python extract-pdf.py <input.pdf> [output_dir]

Dependencies:
    Required: PyMuPDF (fitz), Pillow
    Optional: pytesseract (for OCR fallback on scanned pages)
"""

import json
import logging
import os
import sys
from io import BytesIO
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF is required. Install with: pip install PyMuPDF")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    Image = None
    print("WARNING: Pillow not installed. Image processing will be limited.")

try:
    import pytesseract

    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("extract-pdf")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MONOSPACE_FONTS = {
    "consolas",
    "courier",
    "couriernew",
    "courier new",
    "courier-new",
    "jetbrainsmono",
    "jetbrains mono",
    "firacode",
    "fira code",
    "firamono",
    "fira mono",
    "sourcecodepro",
    "source code pro",
    "cascadiacode",
    "cascadia code",
    "cascadiamono",
    "cascadia mono",
    "menlo",
    "monaco",
    "sfmono",
    "sf mono",
    "robotomono",
    "roboto mono",
    "ubuntumono",
    "ubuntu mono",
    "dejavusansmono",
    "dejavu sans mono",
    "liberationmono",
    "liberation mono",
    "lucidaconsole",
    "lucida console",
    "andalemono",
    "andale mono",
}

BULLET_CHARS = {
    "\u2022",  # bullet
    "\u2023",  # triangular bullet
    "\u25aa",  # black small square
    "\u25ab",  # white small square
    "\u25cf",  # black circle
    "\u25cb",  # white circle
    "\u25a0",  # black square
    "\u25a1",  # white square
    "\u2013",  # en dash
    "\u2014",  # em dash
    "\u25b6",  # black right-pointing triangle
    "\u25b8",  # black right-pointing small triangle
    "\u2043",  # hyphen bullet
    "\u27a4",  # black right arrowhead
    "-",
    ">",
}


# ---------------------------------------------------------------------------
# Helper: Normalise font name for comparison
# ---------------------------------------------------------------------------
def _normalise_font(font_name):
    """Lowercase and strip common suffixes for font comparison."""
    if not font_name:
        return ""
    fn = font_name.lower()
    # Strip bold/italic/regular suffixes
    for suffix in (
        "-bold",
        "-italic",
        "-bolditalic",
        "-regular",
        "-medium",
        ",bold",
        ",italic",
        ",bolditalic",
        ",regular",
        "bold",
        "italic",
        "regular",
    ):
        if fn.endswith(suffix):
            fn = fn[: -len(suffix)]
    return fn.strip("-").strip(",").strip()


def _is_monospace(font_name):
    """Check if font is a known monospace font."""
    norm = _normalise_font(font_name)
    return norm in MONOSPACE_FONTS


def _is_bold(font_name, flags):
    """Check if text is bold based on font name or flags."""
    if flags is not None and (flags & 2 ** 4):  # bit 4 = bold
        return True
    if font_name and any(
        kw in font_name.lower() for kw in ("bold", "heavy", "black", "semibold")
    ):
        return True
    return False


def _is_italic(font_name, flags):
    """Check if text is italic based on font name or flags."""
    if flags is not None and (flags & 2):  # bit 1 = italic
        return True
    if font_name and any(kw in font_name.lower() for kw in ("italic", "oblique")):
        return True
    return False


def _color_from_int(color_int):
    """Convert integer color to hex string."""
    if color_int is None or color_int == 0:
        return None
    # fitz stores colors as integers; convert to hex
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    if r == 0 and g == 0 and b == 0:
        return None  # Skip black (default)
    return f"{r:02X}{g:02X}{b:02X}"


# ---------------------------------------------------------------------------
# Core: is_scanned_page
# ---------------------------------------------------------------------------
def is_scanned_page(page):
    """
    Returns True if page has <20 chars of extractable text but contains images.
    This indicates a scanned/image-heavy page needing OCR.
    """
    text = page.get_text().strip()
    image_list = page.get_images(full=True)
    return len(text) < 20 and len(image_list) > 0


# ---------------------------------------------------------------------------
# Core: extract_text_blocks
# ---------------------------------------------------------------------------
def extract_text_blocks(page):
    """
    Extract text blocks from page using page.get_text("dict").
    Returns a list of raw block dicts with font metadata.
    """
    page_dict = page.get_text("dict")
    page_width = page_dict.get("width", page.rect.width)
    page_height = page_dict.get("height", page.rect.height)

    blocks = []

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:  # type 0 = text block
            continue

        block_text_parts = []
        block_fonts = []
        block_sizes = []
        block_colors = []
        block_flags_list = []
        block_bbox = block.get("bbox", (0, 0, page_width, page_height))

        for line in block.get("lines", []):
            line_text = ""
            for span in line.get("spans", []):
                span_text = span.get("text", "")
                if not span_text.strip():
                    continue
                line_text += span_text
                block_fonts.append(span.get("font", ""))
                block_sizes.append(span.get("size", 12))
                block_flags_list.append(span.get("flags", 0))
                # Color in fitz is an integer
                block_colors.append(span.get("color", 0))

            if line_text.strip():
                block_text_parts.append(line_text.strip())

        full_text = "\n".join(block_text_parts).strip()
        if not full_text:
            continue

        avg_size = sum(block_sizes) / len(block_sizes) if block_sizes else 12
        primary_font = block_fonts[0] if block_fonts else ""
        primary_flags = block_flags_list[0] if block_flags_list else 0
        primary_color_int = block_colors[0] if block_colors else 0

        # Position as percentage of page
        x0, y0, x1, y1 = block_bbox
        position = {
            "left_pct": round((x0 / page_width) * 100, 2) if page_width else 0,
            "top_pct": round((y0 / page_height) * 100, 2) if page_height else 0,
            "width_pct": round(((x1 - x0) / page_width) * 100, 2) if page_width else 0,
            "height_pct": round(
                ((y1 - y0) / page_height) * 100, 2
            ) if page_height else 0,
        }

        blocks.append(
            {
                "text": full_text,
                "lines": block_text_parts,
                "font": primary_font,
                "font_size": round(avg_size, 1),
                "flags": primary_flags,
                "color_int": primary_color_int,
                "position": position,
                "bbox": block_bbox,
                "is_monospace": _is_monospace(primary_font),
                "is_bold": _is_bold(primary_font, primary_flags),
                "is_italic": _is_italic(primary_font, primary_flags),
            }
        )

    return blocks


# ---------------------------------------------------------------------------
# Core: classify_text_block
# ---------------------------------------------------------------------------
def classify_text_block(block, page_height, all_sizes):
    """
    Classify a text block into:
    heading, subheading, body_text, bullet_list, numbered_list,
    code_block, table, quote, caption, formula

    Heuristics:
    - Large bold text near top → heading
    - Bullet chars (bullet, -, >, square) at start → bullet_list
    - Numbered pattern (1., 2., a., i.) → numbered_list
    - Monospace font → code_block
    - Font size thresholds for subheading vs body
    """
    text = block["text"]
    font_size = block["font_size"]
    is_mono = block["is_monospace"]
    bold = block["is_bold"]
    top_pct = block["position"]["top_pct"]
    lines = block.get("lines", [text])

    # Compute size percentile relative to all blocks
    max_size = max(all_sizes) if all_sizes else font_size
    min_size = min(all_sizes) if all_sizes else font_size
    avg_size = sum(all_sizes) / len(all_sizes) if all_sizes else font_size

    # Code block: monospace font
    if is_mono:
        return "code_block"

    # Bullet list: lines start with bullet characters
    bullet_lines = 0
    for line in lines:
        stripped = line.strip()
        if stripped and (
            stripped[0] in BULLET_CHARS
            or stripped.startswith("- ")
            or stripped.startswith("* ")
        ):
            bullet_lines += 1

    if bullet_lines > 0 and bullet_lines >= len(lines) * 0.5:
        return "bullet_list"

    # Numbered list: lines start with number patterns
    import re

    numbered_lines = 0
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\d+[\.\)]\s", stripped) or re.match(
            r"^[a-zA-Z][\.\)]\s", stripped
        ):
            numbered_lines += 1

    if numbered_lines > 0 and numbered_lines >= len(lines) * 0.5:
        return "numbered_list"

    # Heading: large + bold + near top
    if font_size >= avg_size * 1.4 and bold and top_pct < 25:
        return "heading"

    # Heading fallback: significantly larger than average
    if font_size >= avg_size * 1.6:
        return "heading"

    # Subheading: moderately large or bold
    if font_size >= avg_size * 1.2 and bold:
        return "subheading"

    # Caption: small text
    if font_size < avg_size * 0.75:
        return "caption"

    # Quote: starts with quotation marks
    if text.strip().startswith('"') or text.strip().startswith("\u201c"):
        return "quote"

    # Formula: math-heavy
    math_chars = set("=+-*/^{}[]()\\|_<>")
    if len(text) > 3 and sum(1 for c in text if c in math_chars) / len(text) > 0.25:
        return "formula"

    return "body_text"


# ---------------------------------------------------------------------------
# Core: detect_columns
# ---------------------------------------------------------------------------
def detect_columns(blocks):
    """
    Cluster blocks by x-position to determine column count.
    Returns column_count (1, 2, or 3).
    """
    if not blocks:
        return 1

    left_positions = [b["position"]["left_pct"] for b in blocks]
    if not left_positions:
        return 1

    # Cluster by rounding to nearest 15%
    clusters = set()
    for lp in left_positions:
        cluster = round(lp / 15) * 15
        clusters.add(cluster)

    # Filter out very close clusters (within 10%)
    sorted_clusters = sorted(clusters)
    merged = [sorted_clusters[0]]
    for c in sorted_clusters[1:]:
        if c - merged[-1] >= 15:
            merged.append(c)

    return min(len(merged), 3)


# ---------------------------------------------------------------------------
# Core: render_page_image
# ---------------------------------------------------------------------------
def render_page_image(page, dpi=150):
    """
    Render page as a PNG image at specified DPI.
    Returns (PIL.Image, bytes) or (None, None) on failure.
    """
    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")

        pil_img = None
        if Image:
            pil_img = Image.open(BytesIO(img_bytes))

        return pil_img, img_bytes
    except Exception as e:
        log.warning("  Page render failed: %s", e)
        return None, None


# ---------------------------------------------------------------------------
# Core: ocr_page
# ---------------------------------------------------------------------------
def ocr_page(page):
    """
    Render page at 300 DPI and run pytesseract OCR.
    Returns a list of text block dicts with approximate positions.
    """
    if not HAS_TESSERACT:
        log.info("  pytesseract not available; skipping OCR")
        return []

    if not Image:
        log.info("  Pillow not available; skipping OCR")
        return []

    try:
        # Render at 300 DPI for OCR quality
        mat = fitz.Matrix(300 / 72, 300 / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        pil_img = Image.open(BytesIO(img_bytes))

        # Run OCR with bounding box data
        try:
            ocr_data = pytesseract.image_to_data(
                pil_img, output_type=pytesseract.Output.DICT
            )
        except Exception:
            # Fallback to plain text
            ocr_text = pytesseract.image_to_string(pil_img)
            if not ocr_text or len(ocr_text.strip()) < 5:
                return []
            return [
                {
                    "text": ocr_text.strip(),
                    "lines": [
                        line.strip()
                        for line in ocr_text.split("\n")
                        if line.strip()
                    ],
                    "font": "ocr",
                    "font_size": 12,
                    "flags": 0,
                    "color_int": 0,
                    "position": {
                        "left_pct": 0,
                        "top_pct": 0,
                        "width_pct": 100,
                        "height_pct": 100,
                    },
                    "bbox": (0, 0, page.rect.width, page.rect.height),
                    "is_monospace": False,
                    "is_bold": False,
                    "is_italic": False,
                }
            ]

        # Group OCR words into blocks by block_num
        img_w, img_h = pil_img.size
        page_w = page.rect.width
        page_h = page.rect.height

        block_groups = {}
        for i in range(len(ocr_data["text"])):
            text = ocr_data["text"][i].strip()
            conf = int(ocr_data["conf"][i]) if ocr_data["conf"][i] != "-1" else 0
            if not text or conf < 30:
                continue

            block_num = ocr_data["block_num"][i]
            if block_num not in block_groups:
                block_groups[block_num] = {
                    "texts": [],
                    "x_min": img_w,
                    "y_min": img_h,
                    "x_max": 0,
                    "y_max": 0,
                }

            bg = block_groups[block_num]
            bg["texts"].append(text)
            x = ocr_data["left"][i]
            y = ocr_data["top"][i]
            w = ocr_data["width"][i]
            h = ocr_data["height"][i]
            bg["x_min"] = min(bg["x_min"], x)
            bg["y_min"] = min(bg["y_min"], y)
            bg["x_max"] = max(bg["x_max"], x + w)
            bg["y_max"] = max(bg["y_max"], y + h)

        blocks = []
        for bn, bg in block_groups.items():
            combined = " ".join(bg["texts"])
            if len(combined.strip()) < 2:
                continue
            blocks.append(
                {
                    "text": combined,
                    "lines": [combined],
                    "font": "ocr",
                    "font_size": 12,
                    "flags": 0,
                    "color_int": 0,
                    "position": {
                        "left_pct": round((bg["x_min"] / img_w) * 100, 2) if img_w else 0,
                        "top_pct": round((bg["y_min"] / img_h) * 100, 2) if img_h else 0,
                        "width_pct": round(
                            ((bg["x_max"] - bg["x_min"]) / img_w) * 100, 2
                        ) if img_w else 0,
                        "height_pct": round(
                            ((bg["y_max"] - bg["y_min"]) / img_h) * 100, 2
                        ) if img_h else 0,
                    },
                    "bbox": (
                        bg["x_min"] * (page_w / img_w),
                        bg["y_min"] * (page_h / img_h),
                        bg["x_max"] * (page_w / img_w),
                        bg["y_max"] * (page_h / img_h),
                    ),
                    "is_monospace": False,
                    "is_bold": False,
                    "is_italic": False,
                }
            )

        return blocks

    except Exception as e:
        log.warning("  OCR failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Image extraction
# ---------------------------------------------------------------------------
def extract_images(page, page_num, assets_dir, extracted_images):
    """Extract embedded images from a page. Returns list of image IDs."""
    image_ids = []
    image_list = page.get_images(full=True)

    for img_idx, img_info in enumerate(image_list, start=1):
        xref = img_info[0]
        try:
            base_image = page.parent.extract_image(xref)
            if not base_image:
                continue

            image_bytes = base_image["image"]
            ext = base_image.get("ext", "png")
            width = base_image.get("width", 0)
            height = base_image.get("height", 0)

            # Skip very small images (likely decorative)
            if width < 10 or height < 10:
                continue

            image_name = f"page{page_num}_img{img_idx}.{ext}"
            image_path = os.path.join(assets_dir, image_name)

            with open(image_path, "wb") as f:
                f.write(image_bytes)

            img_id = f"img_{page_num}_{img_idx}"
            image_ids.append(img_id)

            content_type = _guess_image_content_type(ext, width, height)

            extracted_images.append(
                {
                    "id": img_id,
                    "path": f"assets/{image_name}",
                    "source_slide": page_num,
                    "width": width,
                    "height": height,
                    "content_type": content_type,
                    "description": "",
                    "regenerable": False,
                }
            )

        except Exception as e:
            log.warning("  Image extraction error on page %d, img %d: %s", page_num, img_idx, e)

    return image_ids


def _guess_image_content_type(ext, width, height):
    """Heuristic guess of image content type."""
    ext_lower = ext.lower() if ext else ""
    if ext_lower == "svg":
        return "diagram"
    if ext_lower in ("emf", "wmf"):
        return "diagram"
    if ext_lower == "ico":
        return "icon"
    if width < 80 and height < 80:
        return "icon"
    if width > 400 and height > 400:
        # Large image: could be photo, screenshot, or diagram
        return "unknown"
    return "unknown"


# ---------------------------------------------------------------------------
# Slide type detection
# ---------------------------------------------------------------------------
def detect_slide_type(page_data):
    """
    Detect slide/page type based on content composition:
    title, section_divider, content, two_column, image_heavy,
    code, chart, table, blank, closing
    """
    content_blocks = page_data.get("content_blocks", [])
    images = page_data.get("images", [])
    total_text = " ".join(b.get("content", "") for b in content_blocks)
    word_count = len(total_text.split())
    image_count = len(images)
    text_block_count = len(content_blocks)

    has_code = any(b.get("type") == "code_block" for b in content_blocks)
    has_table = any(b.get("type") == "table" for b in content_blocks)
    has_heading = any(b.get("type") == "heading" for b in content_blocks)

    # Blank
    if text_block_count == 0 and image_count == 0:
        return "blank"

    # Table-heavy
    if has_table:
        return "table"

    # Code-heavy
    code_blocks = sum(1 for b in content_blocks if b.get("type") == "code_block")
    if has_code and code_blocks >= text_block_count * 0.5:
        return "code"

    # Image-heavy
    if image_count > 0 and (image_count >= text_block_count or word_count < 30):
        return "image_heavy"

    # Title page: heading + few elements + short text
    if has_heading and text_block_count <= 3 and word_count < 30:
        return "title"

    # Section divider
    if has_heading and text_block_count <= 2 and word_count < 15:
        return "section_divider"

    # Two-column detection
    left_blocks = [
        b for b in content_blocks if b.get("position", {}).get("left_pct", 0) < 40
    ]
    right_blocks = [
        b for b in content_blocks if b.get("position", {}).get("left_pct", 0) > 50
    ]
    if left_blocks and right_blocks and len(left_blocks) >= 2 and len(right_blocks) >= 2:
        return "two_column"

    # Closing
    lower_text = total_text.lower()
    closing_keywords = {"thank you", "thanks", "questions", "q&a", "contact", "the end"}
    if any(kw in lower_text for kw in closing_keywords) and word_count < 30:
        return "closing"

    # Chart heuristic: check for chart-related keywords in small text pages
    chart_keywords = {"chart", "graph", "figure", "axis", "x-axis", "y-axis"}
    if image_count > 0 and any(kw in lower_text for kw in chart_keywords):
        return "chart"

    return "content"


# ---------------------------------------------------------------------------
# Layout hints
# ---------------------------------------------------------------------------
def compute_layout_hints(content_blocks, images):
    """Compute layout hints for a page."""
    has_header = any(
        b.get("type") in ("heading", "subheading") for b in content_blocks
    )
    column_count = detect_columns(
        [
            {"position": b.get("position", {"left_pct": 0})}
            for b in content_blocks
        ]
    )

    type_counts = {}
    for b in content_blocks:
        t = b.get("type", "body_text")
        type_counts[t] = type_counts.get(t, 0) + 1

    if images and len(images) > sum(type_counts.values()):
        dominant = "image"
    elif type_counts:
        dominant = max(type_counts, key=type_counts.get)
    else:
        dominant = "image" if images else "empty"

    return {
        "has_header": has_header,
        "column_count": column_count,
        "dominant_element": dominant,
    }


# ---------------------------------------------------------------------------
# Build content_blocks from raw text blocks
# ---------------------------------------------------------------------------
def _build_content_blocks(raw_blocks, page_height):
    """
    Convert raw text blocks into classified content_blocks for output.
    Groups consecutive bullet/numbered items into lists.
    """
    all_sizes = [b["font_size"] for b in raw_blocks]

    content_blocks = []
    current_list_items = []
    current_list_type = None
    current_list_position = None

    for block in raw_blocks:
        block_type = classify_text_block(block, page_height, all_sizes)

        # Handle list grouping
        if block_type in ("bullet_list", "numbered_list"):
            items = _extract_list_items(block["text"], block_type)
            if current_list_type == block_type:
                current_list_items.extend(items)
            else:
                # Flush previous list
                if current_list_items:
                    content_blocks.append(
                        _make_list_block(
                            current_list_type, current_list_items, current_list_position
                        )
                    )
                current_list_type = block_type
                current_list_items = items
                current_list_position = block["position"]
        else:
            # Flush pending list
            if current_list_items:
                content_blocks.append(
                    _make_list_block(
                        current_list_type, current_list_items, current_list_position
                    )
                )
                current_list_items = []
                current_list_type = None
                current_list_position = None

            cb = {
                "type": block_type,
                "content": block["text"],
                "position": block["position"],
            }

            # Add formatting
            formatting = {}
            if block["is_bold"]:
                formatting["bold"] = True
            if block["is_italic"]:
                formatting["italic"] = True
            if block["font_size"]:
                formatting["font_size_pt"] = block["font_size"]
            color = _color_from_int(block["color_int"])
            if color:
                formatting["color"] = color

            if formatting:
                cb["formatting"] = formatting

            content_blocks.append(cb)

    # Flush trailing list
    if current_list_items:
        content_blocks.append(
            _make_list_block(current_list_type, current_list_items, current_list_position)
        )

    return content_blocks


def _extract_list_items(text, list_type):
    """Extract individual list items from a block of text."""
    lines = text.split("\n")
    items = []
    import re

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if list_type == "bullet_list":
            # Remove leading bullet characters
            for bc in BULLET_CHARS:
                if stripped.startswith(bc):
                    stripped = stripped[len(bc) :].strip()
                    break
            if stripped.startswith("* "):
                stripped = stripped[2:]
        elif list_type == "numbered_list":
            stripped = re.sub(r"^[\d]+[\.\)]\s*", "", stripped)
            stripped = re.sub(r"^[a-zA-Z][\.\)]\s*", "", stripped)
        if stripped:
            items.append(stripped)

    return items if items else [text.strip()]


def _make_list_block(list_type, items, position):
    """Create a list block dict."""
    return {
        "type": list_type or "bullet_list",
        "content": "\n".join(items),
        "items": items,
        "position": position
        or {"left_pct": 0, "top_pct": 0, "width_pct": 100, "height_pct": 100},
    }


# ---------------------------------------------------------------------------
# Presentation metadata
# ---------------------------------------------------------------------------
def _extract_pdf_metadata(doc, file_path):
    """Extract document-level metadata."""
    metadata = doc.metadata or {}

    title = metadata.get("title", "")
    author = metadata.get("author", "")
    subject = metadata.get("subject", "")

    # If no title from metadata, try first page heading
    if not title and len(doc) > 0:
        first_page = doc[0]
        blocks = extract_text_blocks(first_page)
        if blocks:
            # Largest font block on first page = likely title
            largest = max(blocks, key=lambda b: b["font_size"])
            title = largest["text"].split("\n")[0].strip()

    # Detect language and subject from all text
    all_text = ""
    for page_num in range(min(len(doc), 5)):  # Sample first 5 pages
        page = doc[page_num]
        all_text += page.get_text() + " "

    detected_language = _detect_language(all_text)
    detected_subject = _detect_subject(all_text)

    # Extract subtitle from first page if available
    subtitle = ""
    if len(doc) > 0:
        first_page = doc[0]
        blocks = extract_text_blocks(first_page)
        if len(blocks) >= 2:
            # Sort by font size descending
            sorted_blocks = sorted(blocks, key=lambda b: b["font_size"], reverse=True)
            if sorted_blocks[0]["text"].strip() == title.strip() and len(sorted_blocks) > 1:
                subtitle = sorted_blocks[1]["text"].split("\n")[0].strip()

    return {
        "title": title,
        "subtitle": subtitle,
        "author": author,
        "slide_count": len(doc),
        "source_type": "pdf",
        "source_file": os.path.basename(file_path),
        "detected_language": detected_language,
        "detected_subject": detected_subject,
    }


def _detect_language(text):
    """Simple heuristic language detection."""
    cjk_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    if cjk_count > len(text) * 0.1:
        return "zh"
    kr_count = sum(1 for c in text if "\uac00" <= c <= "\ud7af")
    if kr_count > len(text) * 0.1:
        return "ko"
    jp_count = sum(
        1 for c in text if "\u3040" <= c <= "\u30ff" or "\u31f0" <= c <= "\u31ff"
    )
    if jp_count > len(text) * 0.05:
        return "ja"
    return "en"


def _detect_subject(text):
    """Simple heuristic subject detection based on keyword density."""
    lower = text.lower()
    subjects = {
        "science": [
            "hypothesis", "experiment", "data", "variable", "control",
            "observation", "theory", "molecule", "cell", "organism",
        ],
        "coding": [
            "function", "class", "variable", "algorithm", "api",
            "code", "programming", "software", "database", "deploy",
        ],
        "finance": [
            "revenue", "profit", "market", "investment", "stock",
            "portfolio", "gdp", "inflation", "dividend", "asset",
        ],
        "engineering": [
            "design", "system", "component", "specification", "testing",
            "requirement", "architecture", "prototype", "manufacturing",
        ],
        "medical": [
            "patient", "diagnosis", "treatment", "symptom", "clinical",
            "disease", "therapy", "medication", "surgery", "health",
        ],
        "humanities": [
            "culture", "history", "philosophy", "literature", "society",
            "art", "ethics", "narrative", "identity", "interpretation",
        ],
    }

    scores = {}
    for subj, keywords in subjects.items():
        score = sum(lower.count(kw) for kw in keywords)
        if score > 0:
            scores[subj] = score

    if scores:
        return max(scores, key=scores.get)
    return "general"


# ===========================================================================
# Main extraction
# ===========================================================================
def extract_pdf(file_path, output_dir="."):
    """
    Extract all content from a PDF file.
    Produces slide-profile.json + assets/ + references/.
    """
    log.info("Opening %s", file_path)
    doc = fitz.open(file_path)

    # Create output directories
    assets_dir = os.path.join(output_dir, "assets")
    references_dir = os.path.join(output_dir, "references")
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(references_dir, exist_ok=True)

    extracted_images = []
    slides_data = []

    # Document metadata
    pres_meta = _extract_pdf_metadata(doc, file_path)
    log.info(
        "Document: '%s' (%d pages)", pres_meta["title"], pres_meta["slide_count"]
    )

    for page_num in range(len(doc)):
        page = doc[page_num]
        slide_num = page_num + 1
        log.info("Processing page %d/%d...", slide_num, len(doc))

        page_height = page.rect.height

        # Step 1: Check if scanned page
        scanned = is_scanned_page(page)

        # Step 2: Extract text blocks
        if scanned:
            log.info("  Scanned page detected; running OCR...")
            raw_blocks = ocr_page(page)
            if raw_blocks:
                log.info("  OCR recovered %d block(s)", len(raw_blocks))
            else:
                log.info("  OCR produced no results")
        else:
            raw_blocks = extract_text_blocks(page)

        # Step 3: Extract images
        image_ids = extract_images(page, slide_num, assets_dir, extracted_images)

        # Step 4: ALWAYS render reference PNG
        ref_png_name = f"page_{slide_num:03d}.png"
        ref_png_path = os.path.join(references_dir, ref_png_name)
        pil_img, img_bytes = render_page_image(page, dpi=150)
        if img_bytes:
            with open(ref_png_path, "wb") as f:
                f.write(img_bytes)
            log.info("  Reference image: references/%s", ref_png_name)

        # Step 5: Classify text blocks
        content_blocks = _build_content_blocks(raw_blocks, page_height)

        # Step 6: Determine title
        slide_title = ""
        for cb in content_blocks:
            if cb.get("type") == "heading":
                slide_title = cb["content"].split("\n")[0].strip()
                break
        if not slide_title:
            for cb in content_blocks:
                if cb.get("type") == "subheading":
                    slide_title = cb["content"].split("\n")[0].strip()
                    break

        # Step 7: Speaker notes (PDFs typically don't have these)
        speaker_notes = ""

        # Step 8: Build page data for type detection
        page_data = {
            "content_blocks": content_blocks,
            "images": image_ids,
        }

        # Step 9: Detect slide type
        slide_type = detect_slide_type(page_data)

        # Step 10: Layout hints
        layout_hints = compute_layout_hints(content_blocks, image_ids)

        # Assemble slide data
        slide_data = {
            "number": slide_num,
            "title": slide_title,
            "slide_type": slide_type,
            "content_blocks": content_blocks,
            "speaker_notes": speaker_notes,
            "images": image_ids,
            "layout_hints": layout_hints,
        }
        slides_data.append(slide_data)

        # Console summary
        log.info(
            "  Page %d: '%s' [%s] -- %d block(s), %d image(s)%s",
            slide_num,
            slide_title or "(untitled)",
            slide_type,
            len(content_blocks),
            len(image_ids),
            " (OCR)" if scanned else "",
        )

    doc.close()

    # Build output
    output = {
        "presentation": pres_meta,
        "slides": slides_data,
        "extracted_images": extracted_images,
    }

    output_path = os.path.join(output_dir, "slide-profile.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    log.info("=" * 60)
    log.info("Extraction complete!")
    log.info("  Pages: %d", len(slides_data))
    log.info("  Images extracted: %d", len(extracted_images))
    log.info("  Output: %s", output_path)
    log.info("  Assets: %s", assets_dir)
    log.info("  References: %s", references_dir)

    return output


# ===========================================================================
# CLI
# ===========================================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract-pdf.py <input.pdf> [output_dir]")
        print()
        print("Extracts all content from a PDF file and produces:")
        print("  - slide-profile.json  (structured content data)")
        print("  - assets/             (extracted images)")
        print("  - references/         (rendered page PNGs)")
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    if not os.path.isfile(input_file):
        log.error("File not found: %s", input_file)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    extract_pdf(input_file, output_dir)
