from __future__ import annotations

from pagemark.assemble import (
    clean_artifacts,
    dehyphenate,
    join_paragraphs,
    parse_blocks,
    stitch_pages,
    strip_headers_footers,
)
from pagemark.models import BlockType, Page, PageSource


def _page(index: int, markdown: str) -> Page:
    return Page(
        index=index,
        width=612,
        height=792,
        dpi=200,
        markdown=markdown,
        source=PageSource.VLM,
        confidence=0.9,
    )


def test_clean_artifacts_fence() -> None:
    text = "```markdown\n# Hello\nWorld\n```"
    assert clean_artifacts(text) == "# Hello\nWorld"


def test_clean_artifacts_preamble() -> None:
    text = "Here is the markdown conversion:\n# Title\nContent"
    assert clean_artifacts(text) == "# Title\nContent"


def test_parse_blocks_heading() -> None:
    blocks = parse_blocks("# Title\n\nSome text.")
    assert len(blocks) >= 2
    assert blocks[0].type == BlockType.HEADING
    assert blocks[0].text == "Title"
    assert blocks[0].level == 1


def test_parse_blocks_paragraph() -> None:
    blocks = parse_blocks("Just a paragraph.")
    assert len(blocks) == 1
    assert blocks[0].type == BlockType.PARAGRAPH


def test_parse_blocks_code() -> None:
    blocks = parse_blocks("```python\nprint('hello')\n```")
    assert any(b.type == BlockType.CODE for b in blocks)


def test_parse_blocks_list() -> None:
    blocks = parse_blocks("- item one\n- item two\n- item three")
    assert any(b.type == BlockType.LIST for b in blocks)


def test_strip_headers_footers() -> None:
    pages = [_page(i, f"HEADER\nContent for page {i}\nPage {i} of 10") for i in range(10)]
    result = strip_headers_footers(pages)
    for p in result:
        assert not p.markdown.startswith("HEADER")


def test_strip_headers_footers_short() -> None:
    pages = [_page(0, "Only one page")]
    result = strip_headers_footers(pages)
    assert result[0].markdown == "Only one page"


def test_join_paragraphs_continuation() -> None:
    pages = [
        _page(0, "This sentence continues on the next page with no ending"),
        _page(1, "punctuation here and keeps going."),
    ]
    result = join_paragraphs(pages)
    assert len(result) == 1
    assert "continues on the next page" in result[0].markdown
    assert "punctuation here" in result[0].markdown


def test_join_paragraphs_no_continuation() -> None:
    pages = [
        _page(0, "This sentence ends properly."),
        _page(1, "New paragraph starts here."),
    ]
    result = join_paragraphs(pages)
    assert len(result) == 2


def test_dehyphenate() -> None:
    assert dehyphenate("hyphen-\nated") == "hyphenated"
    assert dehyphenate("no-hyphen") == "no-hyphen"


def test_stitch_pages() -> None:
    pages = [_page(0, "First page."), _page(1, "Second page.")]
    result = stitch_pages(pages)
    assert "First page." in result
    assert "Second page." in result
