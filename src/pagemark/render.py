from __future__ import annotations

import base64
import io
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PageImage:
    data: bytes
    width: int
    height: int
    dpi: int
    page_index: int
    data_uri: str = field(repr=False)

    @property
    def pixels(self) -> int:
        return self.width * self.height


def open_pdf(pdf_path: str | Path) -> pdfium.PdfDocument:
    return pdfium.PdfDocument(str(pdf_path))


def page_count(pdf: pdfium.PdfDocument) -> int:
    return len(pdf)


def render_page(
    pdf: pdfium.PdfDocument,
    page_index: int,
    dpi: int = 200,
    max_pixels: int = 1_500_000,
) -> PageImage:
    page = pdf[page_index]
    scale = dpi / 72.0
    bitmap = page.render(scale=scale)
    pil_image: Image.Image = bitmap.to_pil()

    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")

    w, h = pil_image.size
    current_pixels = w * h

    if current_pixels > max_pixels:
        ratio = math.sqrt(max_pixels / current_pixels)
        new_w = max(1, int(w * ratio))
        new_h = max(1, int(h * ratio))
        pil_image = pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        w, h = new_w, new_h
        effective_dpi = int(dpi * ratio)
    else:
        effective_dpi = dpi

    buf = io.BytesIO()
    pil_image.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()
    b64 = base64.b64encode(png_bytes).decode("ascii")
    data_uri = f"data:image/png;base64,{b64}"

    logger.debug(
        "Rendered page %d: %dx%d @ %d dpi (%d px)",
        page_index,
        w,
        h,
        effective_dpi,
        w * h,
        extra={"page_index": page_index, "width": w, "height": h, "dpi": effective_dpi},
    )

    return PageImage(
        data=png_bytes,
        width=w,
        height=h,
        dpi=effective_dpi,
        page_index=page_index,
        data_uri=data_uri,
    )
