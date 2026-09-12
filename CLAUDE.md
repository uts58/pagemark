# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

pagemark is a PDF-to-Markdown converter that uses vision-language models. It works with any OpenAI-compatible endpoint — the user provides their own `base_url`, `model`, and `api_key`. The core value proposition is detecting and recovering from failures that VLMs produce (repetition loops, truncation, dropped columns, hallucinated tables) rather than silently passing them through.

## Commands

```bash
uv sync                              # install all deps including dev group
uv sync --extra cli --extra eval     # add optional extras
uv run pytest                        # run all unit tests (56 currently)
uv run pytest tests/test_render.py   # run one test file
uv run pytest -k "test_anchor"       # run tests matching a name
uv run pytest -m integration         # integration tests (need live endpoints)
uv run ruff check src/ tests/        # lint
uv run ruff format --check src/ tests/  # format check
uv run mypy src/                     # type check (strict mode)
uv run pagemark convert in.pdf -o out.md --model qwen3-vl:8b --base-url http://localhost:11434/v1
uv run pagemark doctor --base-url http://localhost:11434/v1 --model qwen3-vl:8b  # probe /models
```

## Architecture

```
pdf -> render + anchor -> prompt (profile) -> ChatOpenAI -> guardrails -> parse -> assemble -> Document
       pypdfium2          per-model           langchain      retry ladder   md-it    stitching   md + json
```

Source layout: `src/pagemark/`. The public entry point is `Pagemark` (defined in `client.py`, re-exported from `__init__.py`). Users create a `Pagemark(base_url=..., api_key=...)` client, then call `client.convert()` (sync) or `client.aconvert()` (async). The async version is the real implementation; the sync wrapper is `asyncio.run(self.aconvert(...))`.

**Module map:**

| module | role |
| --- | --- |
| `client.py` | `Pagemark` class: holds connection config, resolves the chat model, exposes `convert()` / `aconvert()` |
| `pipeline.py` | orchestration: `aconvert` (internal), `convert_page`, the escalation ladder, `parse_page_spec` |
| `render.py` | `open_pdf`, `page_count`, `render_page` -> `PageImage` (png bytes + data URI) |
| `anchor.py` | `build_anchor`: text layer + image-object placeholders + page dimensions |
| `backends.py` | `resolve_api_key`, `build_chat_model` — the only place `ChatOpenAI` is constructed |
| `profiles/` | `ModelProfile` protocol, registry, and the one built-in profile (`generic`) |
| `guardrails.py` | five checks plus `run_guardrails` / `all_passed` |
| `assemble.py` | markdown-it block parsing **and** cross-page stitching |
| `assets.py` | `extract_images`: embedded PDF image objects -> PNG bytes |
| `models.py` | pydantic types: `Document`, `Page`, `Block`, `Asset`, `TokenUsage`, enums |
| `cli.py` | typer app with two commands: `convert`, `doctor` |

There is no `parse.py` — markdown parsing (`parse_blocks`) lives in `assemble.py` alongside the stitching functions that consume it.

**Per-page flow** (`convert_page`): render the page to an image, build the anchor from the text layer, send image + anchor to the VLM, clean the raw output with `profile.parse()`, score it with the guardrails, and only then parse it into typed blocks.

**Escalation ladder** (`convert_page`): four attempts, each with a confidence ceiling, then a text-layer fallback.

1. `normal` — profile DPI/pixels, standard prompt — ceiling 0.95
2. `reseed` — same render, `temperature=0.3`, `seed=42` — ceiling 0.85
3. `high_dpi` — DPI x1.5 (capped at 400), pixels x1.5 — ceiling 0.75
4. `fallback_prompt` — `profile.fallback_prompt()`, a shorter instruction — ceiling 0.60
5. exhausted -> `PageSource.TEXT_LAYER`, confidence 0.30, warnings preserved

Final confidence is `min(ceiling, coverage_score)`. Exceptions inside a step are caught and logged, then the ladder continues — a bad page never aborts the document.

**Guardrails** (`guardrails.py`): all five run on every attempt; any failure escalates.

- `repetition` — gzip compression ratio < 0.10, or top 4-gram frequency > 0.15
- `truncation` — `finish_reason == "length"`
- `coverage` — share of anchor tokens present in the output, must be >= 0.25; auto-passes when the anchor is empty (scanned page)
- `hallucination` — share of output words absent from the anchor, must be <= 0.70; auto-passes with no anchor
- `refusal` — output under 20 chars, or a refusal phrase in the first 200 chars

**Profiles** (`profiles/`): a `ModelProfile` is a `runtime_checkable` Protocol with `name`, `dpi`, `max_pixels`, `supports_anchor`, `build_prompt(anchor)`, `parse(raw) -> PageParse`, and `fallback_prompt(anchor)`. Implementations self-register via `register()` at import time; `pipeline.py` imports `profiles.generic` for that side effect. `generic` (DPI 200, 1.5M pixels, anchor-aware) targets general instruct VLMs and strips code fences, preambles, and sign-offs in `parse()`. The protocol is the extension point for specialized OCR models later.

**Assembly order matters** (`aconvert`): pages are sorted by index, then `strip_headers_footers` (lines repeating on >=30% of pages, only when >=4 pages), then `join_paragraphs` (merges a page into the previous one when the previous ends mid-sentence and the next starts lowercase — this can reduce the page count in the stitched output), then `stitch_pages` (dehyphenates and joins with blank lines).

**Assets**: `extract_images` pulls embedded image objects per page. `Document.assets` holds the metadata; the PNG bytes live in the `_asset_data` `PrivateAttr`, so `model_dump_json()` stays free of binary payloads. `Document.save(md_path, assets_dir=...)` writes both.

## Hard constraints

- **langchain-openai only, never the langchain meta-package.** The direct deps are langchain-core, openai, and tiktoken (which transitively pull langsmith, httpx, orjson, requests, and friends — a `pagemark[cli]` install resolves to roughly 50 packages). No agents/chains.
- **pypdfium2, not PyMuPDF.** PyMuPDF is AGPL-3.0. All runtime deps must be MIT/Apache-2.0/BSD. The project ships under MIT.
- **No hardcoded providers.** No named-provider constants, base URLs, or model defaults anywhere. The user brings their own endpoint.
- **No `with_structured_output()` on the OCR call.** Many OCR-tuned VLMs lack tool-calling and break under a forced schema. Get raw text, parse it ourselves.
- **No global state.** Never call `set_llm_cache()` or `logging.basicConfig()`. Logging uses `logging.getLogger(__name__)` with a `NullHandler` on the root `pagemark` logger. The CLI is the only place that attaches a handler, and it attaches to the `pagemark` logger, not the root.
- **No `print()` in library code.** CLI uses rich console on stderr for display. Library code uses the logging hierarchy exclusively.
- **Never log secrets.** Log which env var an API key was resolved from, never the value. Full prompts/responses at DEBUG only, truncated, with image payloads replaced by `<image WxH>`.
- **Image blocks use the explicit OpenAI shape** (`{"type": "image_url", "image_url": {"url": "data:..."}}`) rather than langchain's standard block format. Non-OpenAI servers are strictest about this path.
- **`detail: "high"` is opt-in per profile**, not a default. Several self-hosted servers reject unknown keys.

## API key resolution order

Explicit argument on the `Pagemark` constructor, then `OPENAI_API_KEY` env var, then raise naming the base_url. The constructor requires either `base_url` or `chat_model` (not both). `model` is passed per-call to `convert()` / `aconvert()` and is required when using the `base_url` path.

## Gotchas

- **Rendering blocks the event loop.** `render_page`, `build_anchor`, and `extract_images` are synchronous pypdfium2 calls made from inside async tasks with no thread offload. The concurrency semaphore (default 4) therefore bounds in-flight model calls, not CPU work. Anything that moves this to threads must account for the single `PdfDocument` handle shared by all page tasks.
- **Anchor budget is 6000 chars** with middle elision (`[... elided ...]`), so long pages send a head and a tail, not the full text layer.
- **Pixel budget beats DPI.** Render at profile DPI, then downscale to `max_pixels` preserving aspect ratio. `PageImage.dpi` reports the *effective* DPI after downscaling, and that is what lands in `Page.dpi`.
- The `eval` extra (rapidfuzz, datasets) is declared but no eval code exists yet.

## Conventions

- Python >=3.10, `src/` layout, hatchling build backend, `py.typed` marker, version read from `__init__.__version__`.
- ruff (line-length 99, rules `E,F,W,I,UP,B,SIM,RUF`), mypy strict, pytest + pytest-asyncio (`asyncio_mode = "auto"`).
- Pin dependency floors, not ceilings, except `langchain-openai>=1.0,<2`.
- Unit tests must run with no network and no GPU, using langchain's `FakeListChatModel`. Integration tests are gated on `-m integration` and require env vars for live endpoints.
- Test PDFs are generated with fpdf2 by session-scoped fixtures in `tests/conftest.py` and cached in `tests/fixtures/` — never commit binary fixtures.
- Every `Page` in the output carries `confidence`, `warnings`, and `source` (vlm/text_layer). Surface failures, don't hide them.
