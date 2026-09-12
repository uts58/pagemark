from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Protocol

import pypdfium2 as pdfium
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

import pagemark.profiles.generic  # noqa: F401  register the built-in profile
from pagemark.anchor import build_anchor
from pagemark.assemble import (
    join_paragraphs,
    parse_blocks,
    stitch_pages,
    strip_headers_footers,
)
from pagemark.assets import extract_images
from pagemark.guardrails import CheckName, GuardrailResult, all_passed, run_guardrails
from pagemark.models import (
    Asset,
    Document,
    Page,
    PageSource,
    TokenUsage,
)
from pagemark.profiles import ModelProfile, default_profile, get_profile
from pagemark.render import PageImage, open_pdf, page_count, render_page

logger = logging.getLogger(__name__)

_DEFAULT_CONCURRENCY = 4
_ESCALATION_CONFIDENCE = [0.95, 0.85, 0.75, 0.60]
_TEXT_LAYER_CONFIDENCE = 0.30


class ProgressCallback(Protocol):
    def __call__(self, page_index: int, total_pages: int, status: str) -> None: ...


def parse_page_spec(
    spec: str | list[int] | None,
    total_pages: int,
) -> list[int]:
    if spec is None:
        return list(range(total_pages))

    if isinstance(spec, list):
        for p in spec:
            if p < 1 or p > total_pages:
                raise ValueError(f"Page {p} out of range (1-{total_pages})")
        return [p - 1 for p in spec]

    indices: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            segments = part.split("-", 1)
            start_s, end_s = segments[0].strip(), segments[1].strip()
            start = int(start_s) if start_s else 1
            end = int(end_s) if end_s else total_pages
            if start < 1 or end > total_pages or start > end:
                raise ValueError(f"Page range {part!r} out of bounds (1-{total_pages})")
            indices.extend(range(start - 1, end))
        else:
            p = int(part)
            if p < 1 or p > total_pages:
                raise ValueError(f"Page {p} out of range (1-{total_pages})")
            indices.append(p - 1)

    return indices


async def _invoke_model(
    chat_model: BaseChatModel,
    prompt: str,
    page_image: PageImage,
    **kwargs: Any,
) -> tuple[str, str | None, TokenUsage | None]:
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": page_image.data_uri}},
        ]
    )

    response = await chat_model.ainvoke([message], **kwargs)

    content = response.content
    text = content if isinstance(content, str) else str(content)

    finish_reason: str | None = None
    usage: TokenUsage | None = None
    meta = getattr(response, "response_metadata", {}) or {}
    if isinstance(meta, dict):
        finish_reason = meta.get("finish_reason")
        usage_raw = meta.get("token_usage") or meta.get("usage")
        if isinstance(usage_raw, dict):
            usage = TokenUsage(
                prompt_tokens=usage_raw.get("prompt_tokens", 0),
                completion_tokens=usage_raw.get("completion_tokens", 0),
                total_tokens=usage_raw.get("total_tokens", 0),
            )

    logger.debug(
        "Model response (page): %.500s",
        text,
        extra={"finish_reason": finish_reason},
    )

    return text, finish_reason, usage


async def convert_page(
    pdf: pdfium.PdfDocument,
    page_index: int,
    chat_model: BaseChatModel,
    profile: ModelProfile,
) -> Page:
    page_obj = pdf[page_index]
    w_pts = page_obj.get_width()
    h_pts = page_obj.get_height()

    anchor = build_anchor(pdf, page_index) if profile.supports_anchor else ""

    attempts: list[tuple[int, int, str]] = [
        (profile.dpi, profile.max_pixels, "normal"),
        (profile.dpi, profile.max_pixels, "reseed"),
        (min(int(profile.dpi * 1.5), 400), int(profile.max_pixels * 1.5), "high_dpi"),
        (profile.dpi, profile.max_pixels, "fallback_prompt"),
    ]

    last_warnings: list[str] = []

    for step_idx, (dpi, max_px, strategy) in enumerate(attempts):
        try:
            page_image = render_page(pdf, page_index, dpi=dpi, max_pixels=max_px)

            if strategy == "fallback_prompt":
                prompt = profile.fallback_prompt(anchor)
            else:
                prompt = profile.build_prompt(anchor)

            kwargs: dict[str, Any] = {}
            if strategy == "reseed":
                kwargs["temperature"] = 0.3
                kwargs["seed"] = 42

            raw_text, finish_reason, usage = await _invoke_model(
                chat_model, prompt, page_image, **kwargs
            )

            parsed = profile.parse(raw_text)
            results = run_guardrails(parsed.markdown, anchor, finish_reason)

            if all_passed(results):
                confidence = min(
                    _ESCALATION_CONFIDENCE[step_idx],
                    _coverage_from_results(results),
                )
                blocks = parse_blocks(parsed.markdown)
                logger.info(
                    "Page %d completed (source=vlm, step=%s, confidence=%.2f)",
                    page_index,
                    strategy,
                    confidence,
                    extra={
                        "page_index": page_index,
                        "source": "vlm",
                        "step": strategy,
                    },
                )
                return Page(
                    index=page_index,
                    width=w_pts,
                    height=h_pts,
                    dpi=dpi,
                    blocks=blocks,
                    markdown=parsed.markdown,
                    source=PageSource.VLM,
                    confidence=confidence,
                    warnings=[r.detail for r in results if not r.passed],
                    usage=usage,
                )

            last_warnings = [f"{r.check.value}: {r.detail}" for r in results if not r.passed]
            logger.info(
                "Page %d step %s failed guardrails: %s",
                page_index,
                strategy,
                ", ".join(last_warnings),
                extra={"page_index": page_index, "step": strategy},
            )

        except Exception:
            logger.warning(
                "Page %d step %s raised an exception",
                page_index,
                strategy,
                exc_info=True,
                extra={"page_index": page_index, "step": strategy},
            )
            last_warnings = [f"exception during {strategy}"]

    logger.warning(
        "Page %d falling back to text layer after exhausting escalation ladder",
        page_index,
        extra={"page_index": page_index, "source": "text_layer"},
    )

    text_layer = anchor if anchor else ""
    blocks = parse_blocks(text_layer) if text_layer else []
    return Page(
        index=page_index,
        width=w_pts,
        height=h_pts,
        dpi=profile.dpi,
        blocks=blocks,
        markdown=text_layer,
        source=PageSource.TEXT_LAYER,
        confidence=_TEXT_LAYER_CONFIDENCE,
        warnings=["fell back to text layer", *last_warnings],
    )


def _coverage_from_results(results: list[GuardrailResult]) -> float:
    for r in results:
        if r.check == CheckName.COVERAGE:
            return max(r.score, 0.3)
    return 0.95


async def aconvert(
    pdf_path: str,
    *,
    chat_model: BaseChatModel,
    model_id: str = "custom",
    profile: str | ModelProfile | None = None,
    pages: str | list[int] | None = None,
    concurrency: int | None = None,
    progress: ProgressCallback | None = None,
) -> Document:
    if isinstance(profile, str):
        prof = get_profile(profile)
    elif profile is not None:
        prof = profile
    else:
        prof = default_profile()

    pdf = open_pdf(pdf_path)
    total = page_count(pdf)
    page_indices = parse_page_spec(pages, total)

    if concurrency is None:
        concurrency = _DEFAULT_CONCURRENCY

    sem = asyncio.Semaphore(concurrency)

    logger.info(
        "Starting conversion: %d pages, concurrency=%d, model=%s",
        len(page_indices),
        concurrency,
        model_id,
        extra={"total_pages": len(page_indices), "concurrency": concurrency, "model": model_id},
    )
    start_time = time.monotonic()

    async def _do_page(idx: int) -> Page:
        async with sem:
            if progress:
                progress(idx, total, "started")
            page = await convert_page(pdf, idx, chat_model, prof)
            if progress:
                progress(idx, total, "completed")
            return page

    tasks = [_do_page(idx) for idx in page_indices]
    completed_pages = await asyncio.gather(*tasks)

    sorted_pages = sorted(completed_pages, key=lambda p: p.index)

    sorted_pages = strip_headers_footers(sorted_pages)
    sorted_pages = join_paragraphs(sorted_pages)
    markdown = stitch_pages(sorted_pages)

    all_assets: list[Asset] = []
    asset_data: dict[str, bytes] = {}
    for idx in page_indices:
        for asset, data in extract_images(pdf, idx):
            all_assets.append(asset)
            asset_data[asset.filename] = data

    elapsed = time.monotonic() - start_time
    logger.info(
        "Conversion finished: %d pages in %.1fs",
        len(sorted_pages),
        elapsed,
        extra={"elapsed": elapsed, "total_pages": len(sorted_pages)},
    )

    doc = Document(
        pages=sorted_pages,
        markdown=markdown,
        metadata={"source_path": str(pdf_path), "total_source_pages": total},
        assets=all_assets,
        model_id=model_id,
    )
    doc._asset_data = asset_data
    return doc
