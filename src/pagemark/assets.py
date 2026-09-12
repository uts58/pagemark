from __future__ import annotations

import io
import logging

import pypdfium2 as pdfium
from PIL import Image

from pagemark.models import Asset

logger = logging.getLogger(__name__)

_IMAGE_OBJ_TYPE = 2  # FPDF_PAGEOBJ_IMAGE


def extract_images(
    pdf: pdfium.PdfDocument,
    page_index: int,
) -> list[tuple[Asset, bytes]]:
    page = pdf[page_index]
    results: list[tuple[Asset, bytes]] = []
    img_idx = 0

    try:
        for obj in page.get_objects():
            if obj.type != _IMAGE_OBJ_TYPE:
                continue

            try:
                bitmap = obj.get_bitmap()
                pil_image: Image.Image = bitmap.to_pil()
                if pil_image.mode != "RGB":
                    pil_image = pil_image.convert("RGB")

                buf = io.BytesIO()
                pil_image.save(buf, format="PNG")
                png_bytes = buf.getvalue()

                try:
                    pos = obj.get_pos()
                    bbox: tuple[float, float, float, float] = (
                        pos[0],
                        pos[1],
                        pos[2],
                        pos[3],
                    )
                except Exception:
                    bbox = (0.0, 0.0, float(pil_image.width), float(pil_image.height))

                filename = f"page_{page_index + 1}_img_{img_idx}.png"
                asset = Asset(
                    filename=filename,
                    page_index=page_index,
                    bbox=bbox,
                    mime_type="image/png",
                )
                results.append((asset, png_bytes))
                img_idx += 1

            except Exception:
                logger.debug(
                    "Failed to extract image object %d from page %d",
                    img_idx,
                    page_index,
                    exc_info=True,
                    extra={"page_index": page_index},
                )
    except Exception:
        logger.debug(
            "Failed to enumerate objects on page %d",
            page_index,
            exc_info=True,
            extra={"page_index": page_index},
        )

    return results
