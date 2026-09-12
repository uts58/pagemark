from __future__ import annotations

import itertools
import re
from collections import Counter

from markdown_it import MarkdownIt

from pagemark.models import Block, BlockType, Page

_ARTIFACT_FENCE_RE = re.compile(r"^```(?:markdown|md)?\s*\n", re.MULTILINE)
_ARTIFACT_FENCE_CLOSE_RE = re.compile(r"\n```\s*$")
_ARTIFACT_PREAMBLE_RE = re.compile(
    r"^(?:Here is|Below is|The following is)[^\n]*:\s*\n",
    re.IGNORECASE | re.MULTILINE,
)
_HYPHEN_RE = re.compile(r"(\w)-\n(\w)")

_TOKEN_MAP: dict[str, BlockType] = {
    "heading": BlockType.HEADING,
    "paragraph": BlockType.PARAGRAPH,
    "table": BlockType.TABLE,
    "fence": BlockType.CODE,
    "code_block": BlockType.CODE,
    "bullet_list": BlockType.LIST,
    "ordered_list": BlockType.LIST,
    "image": BlockType.FIGURE,
    "math_block": BlockType.FORMULA,
    "blockquote": BlockType.PARAGRAPH,
}


def clean_artifacts(text: str) -> str:
    text = _ARTIFACT_FENCE_RE.sub("", text)
    text = _ARTIFACT_FENCE_CLOSE_RE.sub("", text)
    text = _ARTIFACT_PREAMBLE_RE.sub("", text)
    return text.strip()


def parse_blocks(markdown: str) -> list[Block]:
    md = MarkdownIt()
    tokens = md.parse(markdown)
    blocks: list[Block] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]

        if tok.type == "heading_open":
            level = int(tok.tag[1]) if tok.tag and tok.tag.startswith("h") else 1
            content = tokens[i + 1].content if i + 1 < len(tokens) else ""
            blocks.append(Block(type=BlockType.HEADING, text=content, level=level))
            i += 3
            continue

        if tok.type == "paragraph_open":
            content = tokens[i + 1].content if i + 1 < len(tokens) else ""
            if content.startswith("!["):
                blocks.append(Block(type=BlockType.FIGURE, text=content))
            else:
                blocks.append(Block(type=BlockType.PARAGRAPH, text=content))
            i += 3
            continue

        if tok.type == "fence":
            blocks.append(Block(type=BlockType.CODE, text=tok.content))
            i += 1
            continue

        if tok.type == "code_block":
            blocks.append(Block(type=BlockType.CODE, text=tok.content))
            i += 1
            continue

        if tok.type in ("bullet_list_open", "ordered_list_open"):
            list_text_parts: list[str] = []
            i += 1
            while i < len(tokens) and tokens[i].type not in (
                "bullet_list_close",
                "ordered_list_close",
            ):
                if tokens[i].type == "inline":
                    list_text_parts.append(tokens[i].content)
                i += 1
            blocks.append(Block(type=BlockType.LIST, text="\n".join(list_text_parts)))
            i += 1
            continue

        if tok.type == "table_open":
            table_parts: list[str] = []
            i += 1
            while i < len(tokens) and tokens[i].type != "table_close":
                if tokens[i].type == "inline":
                    table_parts.append(tokens[i].content)
                i += 1
            blocks.append(Block(type=BlockType.TABLE, text="\n".join(table_parts)))
            i += 1
            continue

        if tok.type == "math_block":
            blocks.append(Block(type=BlockType.FORMULA, text=tok.content))
            i += 1
            continue

        i += 1

    return blocks


def strip_headers_footers(pages: list[Page], threshold: float = 0.3) -> list[Page]:
    if len(pages) < 4:
        return pages

    first_lines: Counter[str] = Counter()
    last_lines: Counter[str] = Counter()

    for page in pages:
        lines = page.markdown.strip().splitlines()
        if lines:
            first_lines[lines[0].strip()] += 1
        if len(lines) > 1:
            last_lines[lines[-1].strip()] += 1

    min_count = int(len(pages) * threshold)
    header_lines = {line for line, count in first_lines.items() if count >= min_count and line}
    footer_lines = {line for line, count in last_lines.items() if count >= min_count and line}

    if not header_lines and not footer_lines:
        return pages

    updated: list[Page] = []
    for page in pages:
        lines = page.markdown.strip().splitlines()
        if lines and lines[0].strip() in header_lines:
            lines = lines[1:]
        if lines and lines[-1].strip() in footer_lines:
            lines = lines[:-1]
        new_md = "\n".join(lines).strip()
        updated.append(page.model_copy(update={"markdown": new_md}))

    return updated


def join_paragraphs(pages: list[Page]) -> list[Page]:
    if len(pages) < 2:
        return pages

    result: list[Page] = [pages[0]]
    for prev_page, curr_page in itertools.pairwise(pages):
        prev_md = prev_page.markdown.rstrip()
        curr_md = curr_page.markdown.lstrip()

        if prev_md and curr_md and prev_md[-1] not in ".!?:;\"')" and curr_md[0].islower():
            joined_md = prev_md + " " + curr_md
            result[-1] = result[-1].model_copy(update={"markdown": joined_md})
        else:
            result.append(curr_page)

    return result


def dehyphenate(text: str) -> str:
    return _HYPHEN_RE.sub(r"\1\2", text)


def stitch_pages(pages: list[Page]) -> str:
    parts: list[str] = []
    for page in pages:
        md = dehyphenate(page.markdown.strip())
        if md:
            parts.append(md)
    return "\n\n".join(parts)
