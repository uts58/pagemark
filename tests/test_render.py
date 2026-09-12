from __future__ import annotations

from pathlib import Path

from pagemark.render import open_pdf, page_count, render_page


def test_open_and_count(simple_pdf: Path) -> None:
    pdf = open_pdf(simple_pdf)
    assert page_count(pdf) == 1


def test_render_page_dimensions(simple_pdf: Path) -> None:
    pdf = open_pdf(simple_pdf)
    img = render_page(pdf, 0)
    assert img.width > 0
    assert img.height > 0
    assert img.dpi > 0
    assert img.page_index == 0


def test_render_page_data_uri(simple_pdf: Path) -> None:
    pdf = open_pdf(simple_pdf)
    img = render_page(pdf, 0)
    assert img.data_uri.startswith("data:image/png;base64,")
    assert len(img.data) > 100


def test_render_respects_max_pixels(simple_pdf: Path) -> None:
    pdf = open_pdf(simple_pdf)
    img = render_page(pdf, 0, dpi=300, max_pixels=100_000)
    assert img.pixels <= 110_000


def test_render_multipage(multipage_pdf: Path) -> None:
    pdf = open_pdf(multipage_pdf)
    assert page_count(pdf) == 5
    for i in range(5):
        img = render_page(pdf, i)
        assert img.page_index == i
        assert img.width > 0
