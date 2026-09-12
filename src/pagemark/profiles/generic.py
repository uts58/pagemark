from __future__ import annotations

import re

from pagemark.profiles import PageParse, register

_FENCE_RE = re.compile(r"^```(?:markdown|md|)?\s*\n", re.MULTILINE)
_FENCE_CLOSE_RE = re.compile(r"\n```\s*$")
_PREAMBLE_RE = re.compile(
    r"^(?:Here is|Below is|The following is)[^\n]*"
    r"(?:markdown|transcription|conversion)[^\n]*:\s*\n",
    re.IGNORECASE | re.MULTILINE,
)
_SIGNOFF_RE = re.compile(
    r"\n(?:Let me know|Feel free|I hope|Is there anything)[^\n]*$",
    re.IGNORECASE,
)

_SYSTEM_PROMPT = (
    "You are a document OCR assistant. Convert the provided page image to Markdown. "
    "Preserve all text, tables, formulas, headings, lists, and structure exactly as shown. "
    "Do not summarize, omit, or rephrase any content. "
    "Output only the Markdown, with no preamble or commentary."
)

_ANCHOR_SECTION = (
    "\n\n---\nReference text extracted from the PDF"
    " (may contain OCR errors or ordering issues):\n\n"
    "{anchor}\n---"
)

_FALLBACK_INSTRUCTION = (
    "Convert this page image to Markdown. Reproduce all visible text faithfully."
)


class GenericProfile:
    name: str = "generic"
    dpi: int = 200
    max_pixels: int = 1_500_000
    supports_anchor: bool = True

    def build_prompt(self, anchor: str) -> str:
        prompt = _SYSTEM_PROMPT
        if anchor:
            prompt += _ANCHOR_SECTION.format(anchor=anchor)
        return prompt

    def parse(self, raw: str) -> PageParse:
        text = raw.strip()
        text = _FENCE_RE.sub("", text)
        text = _FENCE_CLOSE_RE.sub("", text)
        text = _PREAMBLE_RE.sub("", text)
        text = _SIGNOFF_RE.sub("", text)
        return PageParse(markdown=text.strip())

    def fallback_prompt(self, anchor: str) -> str:
        prompt = _FALLBACK_INSTRUCTION
        if anchor:
            prompt += _ANCHOR_SECTION.format(anchor=anchor)
        return prompt


_profile = GenericProfile()
register(_profile)
