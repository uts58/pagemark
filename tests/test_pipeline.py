from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from pagemark import Pagemark
from pagemark.models import PageSource
from pagemark.pipeline import parse_page_spec


def test_parse_page_spec_none() -> None:
    assert parse_page_spec(None, 5) == [0, 1, 2, 3, 4]


def test_parse_page_spec_list() -> None:
    assert parse_page_spec([1, 3, 5], 5) == [0, 2, 4]


def test_parse_page_spec_string_single() -> None:
    assert parse_page_spec("3", 5) == [2]


def test_parse_page_spec_string_range() -> None:
    assert parse_page_spec("2-4", 5) == [1, 2, 3]


def test_parse_page_spec_string_open_end() -> None:
    assert parse_page_spec("3-", 5) == [2, 3, 4]


def test_parse_page_spec_string_open_start() -> None:
    assert parse_page_spec("-3", 5) == [0, 1, 2]


def test_parse_page_spec_string_mixed() -> None:
    assert parse_page_spec("1,3-4", 5) == [0, 2, 3]


def test_parse_page_spec_out_of_range() -> None:
    with pytest.raises(ValueError, match="out of range"):
        parse_page_spec([6], 5)


def test_parse_page_spec_range_out_of_range() -> None:
    with pytest.raises(ValueError, match="out of bounds"):
        parse_page_spec("1-10", 5)


async def test_aconvert_single_page(simple_pdf: Path) -> None:
    fake_response = "# Hello World\n\nThis is a test document."
    fake_model = FakeListChatModel(responses=[fake_response])

    client = Pagemark(chat_model=fake_model)
    doc = await client.aconvert(str(simple_pdf), concurrency=1)

    assert len(doc.pages) == 1
    assert doc.pages[0].source == PageSource.VLM
    assert doc.pages[0].index == 0
    assert "Hello World" in doc.markdown


async def test_aconvert_multipage(multipage_pdf: Path) -> None:
    responses = [
        f"# Page {i}\n\nContent for page {i} with enough text to pass guardrails."
        for i in range(1, 6)
    ]
    fake_model = FakeListChatModel(responses=responses)

    client = Pagemark(chat_model=fake_model)
    doc = await client.aconvert(str(multipage_pdf), concurrency=2)

    assert len(doc.pages) == 5
    for page in doc.pages:
        assert page.width > 0
        assert page.height > 0


async def test_aconvert_page_range(multipage_pdf: Path) -> None:
    responses = [
        f"# Page {i}\n\nContent for page {i} with text to pass checks." for i in [1, 2, 3]
    ]
    fake_model = FakeListChatModel(responses=responses)

    client = Pagemark(chat_model=fake_model)
    doc = await client.aconvert(str(multipage_pdf), pages="1-3", concurrency=1)

    assert len(doc.pages) == 3


async def test_aconvert_refusal_triggers_fallback(simple_pdf: Path) -> None:
    responses = [
        "I'm sorry, I cannot process this image.",
        "I'm sorry, I cannot process this image.",
        "I'm sorry, I cannot process this image.",
        "I'm sorry, I cannot process this image.",
    ]
    fake_model = FakeListChatModel(responses=responses)

    client = Pagemark(chat_model=fake_model)
    doc = await client.aconvert(str(simple_pdf), concurrency=1)

    assert len(doc.pages) == 1
    assert doc.pages[0].source == PageSource.TEXT_LAYER
    assert doc.pages[0].confidence < 0.5


def test_client_base_url_and_chat_model_conflict() -> None:
    fake_model = FakeListChatModel(responses=["test"])
    with pytest.raises(ValueError, match="not both"):
        Pagemark(base_url="http://example.com/v1", chat_model=fake_model)


def test_client_requires_base_url_or_chat_model() -> None:
    with pytest.raises(ValueError, match="required"):
        Pagemark()
