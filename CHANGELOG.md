# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-04

Initial release.

### Added

- `Pagemark` client with `convert()` and `aconvert()`. The async version is the
  implementation; the sync one wraps it in `asyncio.run()`. Pages run
  concurrently behind a semaphore (default 4).
- Works against any OpenAI-compatible endpoint. No provider constants, base
  URLs, or model defaults are baked in — the caller supplies `base_url`,
  `model`, and `api_key`. Key resolution order: explicit argument,
  `OPENAI_API_KEY`, then an error naming the `base_url`.
- Page rendering with pypdfium2 under a pixel budget, so `Page.dpi` reports the
  effective DPI after downscaling rather than the requested one.
- Text-layer anchoring: the PDF text layer and image-object placeholders are
  sent alongside the page image, middle-elided to roughly 6k characters.
- Five guardrails on every model response — repetition, truncation, coverage,
  hallucination, and refusal.
- A four-step escalation ladder (normal, reseed, high DPI, fallback prompt) with
  a per-step confidence ceiling, ending in a text-layer fallback. A page that
  fails every step is recorded with warnings instead of aborting the document.
- Cross-page assembly: running headers and footers are stripped, paragraphs
  split across a page break are rejoined, and hyphenated line breaks are healed.
- `ModelProfile` protocol with a self-registering profile registry and one
  built-in profile, `generic`.
- Typed output: `Document`, `Page`, `Block`, `Asset`, and `TokenUsage` pydantic
  models. Every page carries `confidence`, `warnings`, and `source`.
- Embedded PDF images extracted per page. Binary payloads live in a private
  attribute, so `model_dump_json()` stays free of them.
- `Document.save(md_path, assets_dir=...)` writes the Markdown and the images.
- Page selection via `pages`, accepting `"3"`, `"1-5"`, `"1-5,9,12-"`, or a
  `list[int]`. Out-of-range indices raise rather than being clipped silently.
- Optional CLI (`pagemark[cli]`) with `convert` and `doctor` commands.
- `py.typed` marker; the package type-checks under mypy strict.

[Unreleased]: https://github.com/uts58/pagemark/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/uts58/pagemark/releases/tag/v0.1.0
