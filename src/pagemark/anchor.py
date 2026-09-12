from __future__ import annotations

import logging

import pypdfium2 as pdfium

logger = logging.getLogger(__name__)

_DEFAULT_BUDGET = 6000
_IMAGE_OBJ_TYPE = 2  # FPDF_PAGEOBJ_IMAGE


def build_anchor(
    pdf: pdfium.PdfDocument,
    page_index: int,
    budget: int = _DEFAULT_BUDGET,
) -> str:
    page = pdf[page_index]
    w_pts = page.get_width()
    h_pts = page.get_height()

    parts: list[str] = [f"Page dimensions: {w_pts:.0f} x {h_pts:.0f} pt"]

    text = _extract_text(page)
    image_lines = _extract_image_objects(page)

    if image_lines:
        parts.append("\n".join(image_lines))

    if text:
        parts.append(text)

    raw = "\n\n".join(parts)
    if len(raw) <= budget:
        logger.debug(
            "Anchor for page %d: %d chars (within budget %d)",
            page_index,
            len(raw),
            budget,
            extra={"page_index": page_index},
        )
        return raw

    return _middle_elide(raw, budget)


def _extract_text(page: pdfium.PdfPage) -> str:
    try:
        textpage = page.get_textpage()
        text: str = textpage.get_text_range()
        return text.strip()
    except Exception:
        return ""


def _extract_image_objects(page: pdfium.PdfPage) -> list[str]:
    lines: list[str] = []
    try:
        for obj in page.get_objects():
            if obj.type == _IMAGE_OBJ_TYPE:
                try:
                    pos = obj.get_pos()
                    left, bottom, right, top = pos
                    w = abs(right - left)
                    h = abs(top - bottom)
                    lines.append(f"[image {w:.0f}x{h:.0f} at {left:.0f},{bottom:.0f}]")
                except Exception:
                    lines.append("[image]")
    except Exception:
        pass
    return lines


def _middle_elide(text: str, budget: int) -> str:
    if len(text) <= budget:
        return text
    keep = budget - 20
    head_len = keep * 2 // 3
    tail_len = keep - head_len
    return text[:head_len] + "\n[... elided ...]\n" + text[-tail_len:]
