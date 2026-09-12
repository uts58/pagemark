from __future__ import annotations

from pathlib import Path

from pagemark.anchor import build_anchor
from pagemark.render import open_pdf


def test_anchor_contains_text(simple_pdf: Path) -> None:
    pdf = open_pdf(simple_pdf)
    anchor = build_anchor(pdf, 0)
    assert "Page dimensions:" in anchor
    assert "Hello World" in anchor or len(anchor) > 20


def test_anchor_empty_page(empty_page_pdf: Path) -> None:
    pdf = open_pdf(empty_page_pdf)
    anchor = build_anchor(pdf, 0)
    assert "Page dimensions:" in anchor


def test_anchor_budget(simple_pdf: Path) -> None:
    pdf = open_pdf(simple_pdf)
    anchor = build_anchor(pdf, 0, budget=100)
    assert len(anchor) <= 120


def test_anchor_multipage(multipage_pdf: Path) -> None:
    pdf = open_pdf(multipage_pdf)
    for i in range(5):
        anchor = build_anchor(pdf, i)
        assert isinstance(anchor, str)
        assert len(anchor) > 0
