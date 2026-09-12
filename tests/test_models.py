from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pagemark.models import (
    Asset,
    Block,
    BlockType,
    Document,
    Page,
    PageSource,
    TokenUsage,
)


def test_block_creation() -> None:
    b = Block(type=BlockType.HEADING, text="Title", level=1)
    assert b.type == BlockType.HEADING
    assert b.level == 1


def test_page_defaults() -> None:
    p = Page(
        index=0,
        width=612,
        height=792,
        dpi=200,
        markdown="# Hello",
        source=PageSource.VLM,
        confidence=0.95,
    )
    assert p.blocks == []
    assert p.warnings == []
    assert p.usage is None


def test_document_json_roundtrip() -> None:
    page = Page(
        index=0,
        width=612,
        height=792,
        dpi=200,
        blocks=[Block(type=BlockType.PARAGRAPH, text="Hello world")],
        markdown="Hello world",
        source=PageSource.VLM,
        confidence=0.9,
        warnings=["test warning"],
        usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )
    doc = Document(
        pages=[page],
        markdown="Hello world",
        model_id="test-model",
    )
    js = doc.model_dump_json(indent=2)
    data = json.loads(js)
    assert data["model_id"] == "test-model"
    assert len(data["pages"]) == 1
    assert data["pages"][0]["confidence"] == 0.9


def test_document_save() -> None:
    doc = Document(
        pages=[
            Page(
                index=0,
                width=612,
                height=792,
                dpi=200,
                markdown="# Test",
                source=PageSource.VLM,
                confidence=0.9,
            )
        ],
        markdown="# Test",
        assets=[Asset(filename="img.png", page_index=0)],
    )
    doc._asset_data = {"img.png": b"\x89PNG fake data"}

    with tempfile.TemporaryDirectory() as tmpdir:
        md_path = Path(tmpdir) / "out.md"
        assets_dir = Path(tmpdir) / "assets"
        doc.save(md_path, assets_dir=assets_dir)
        assert md_path.read_text(encoding="utf-8") == "# Test"
        assert (assets_dir / "img.png").read_bytes() == b"\x89PNG fake data"
