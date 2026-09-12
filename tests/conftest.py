from __future__ import annotations

from pathlib import Path

import pytest
from fpdf import FPDF

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _make_pdf(filename: str, builder: object) -> Path:
    path = FIXTURES_DIR / filename
    if path.exists():
        return path
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    pdf: FPDF = builder  # type: ignore[assignment]
    pdf.output(str(path))
    return path


@pytest.fixture(scope="session")
def simple_pdf() -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Hello World", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, "This is a test document.", new_x="LMARGIN", new_y="NEXT")
    return _make_pdf("simple.pdf", pdf)


@pytest.fixture(scope="session")
def multipage_pdf() -> Path:
    pdf = FPDF()
    for i in range(1, 6):
        pdf.add_page()
        pdf.set_font("Helvetica", size=14)
        pdf.cell(0, 10, f"Page {i} Header", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(
            0,
            10,
            f"Content on page {i}. This paragraph has enough text to be meaningful "
            f"for testing purposes. It covers topics relevant to page number {i}.",
        )
    return _make_pdf("multipage.pdf", pdf)


@pytest.fixture(scope="session")
def table_pdf() -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Table Example", new_x="LMARGIN", new_y="NEXT")
    col_w = 40
    headers = ["Name", "Age", "City"]
    rows = [
        ["Alice", "30", "New York"],
        ["Bob", "25", "London"],
        ["Carol", "35", "Tokyo"],
    ]
    for h in headers:
        pdf.cell(col_w, 10, h, border=1)
    pdf.ln()
    for row in rows:
        for cell in row:
            pdf.cell(col_w, 10, cell, border=1)
        pdf.ln()
    return _make_pdf("table.pdf", pdf)


@pytest.fixture(scope="session")
def two_column_pdf() -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    col_w = 85
    x_left = 15
    x_right = 110
    pdf.set_xy(x_left, 20)
    pdf.multi_cell(col_w, 5, "Left column text. " * 10)
    pdf.set_xy(x_right, 20)
    pdf.multi_cell(col_w, 5, "Right column text. " * 10)
    return _make_pdf("two_column.pdf", pdf)


@pytest.fixture(scope="session")
def empty_page_pdf() -> Path:
    pdf = FPDF()
    pdf.add_page()
    return _make_pdf("empty_page.pdf", pdf)
