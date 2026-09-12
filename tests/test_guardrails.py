from __future__ import annotations

from pagemark.guardrails import (
    CheckName,
    all_passed,
    check_coverage,
    check_hallucination,
    check_refusal,
    check_repetition,
    check_truncation,
    run_guardrails,
)


def test_repetition_clean() -> None:
    text = "The quick brown fox jumps over the lazy dog. " * 5
    result = check_repetition(text)
    assert result.passed


def test_repetition_loop() -> None:
    text = "the same words " * 200
    result = check_repetition(text)
    assert not result.passed


def test_truncation_normal() -> None:
    result = check_truncation("some text", "stop")
    assert result.passed


def test_truncation_length() -> None:
    result = check_truncation("some text", "length")
    assert not result.passed


def test_coverage_good() -> None:
    anchor = "hello world this is a test document with some content"
    output = "hello world this is a test document with some content and extras"
    result = check_coverage(output, anchor)
    assert result.passed
    assert result.score > 0.8


def test_coverage_bad() -> None:
    anchor = "hello world this is a test document with important content"
    output = "completely different unrelated text about something else entirely"
    result = check_coverage(output, anchor)
    assert not result.passed


def test_coverage_no_anchor() -> None:
    result = check_coverage("anything", "")
    assert result.passed


def test_hallucination_clean() -> None:
    anchor = "the quick brown fox jumps over the lazy dog"
    output = "the quick brown fox jumps over the lazy dog"
    result = check_hallucination(output, anchor)
    assert result.passed
    assert result.score < 0.1


def test_hallucination_high() -> None:
    anchor = "hello"
    output = "completely fabricated text that has nothing whatsoever to do " * 5
    result = check_hallucination(output, anchor)
    assert not result.passed


def test_refusal_detected() -> None:
    result = check_refusal("I'm sorry, I cannot process this image.")
    assert not result.passed


def test_refusal_empty() -> None:
    result = check_refusal("")
    assert not result.passed


def test_refusal_clean() -> None:
    result = check_refusal("# Introduction\n\nThis is a normal document with content.")
    assert result.passed


def test_run_guardrails_all_pass() -> None:
    text = "The quick brown fox jumps over the lazy dog and more text here."
    anchor = "The quick brown fox jumps over the lazy dog and more text here."
    results = run_guardrails(text, anchor, "stop")
    assert all_passed(results)
    assert len(results) == 5


def test_run_guardrails_truncation_fails() -> None:
    text = "The quick brown fox jumps over the lazy dog and more text."
    results = run_guardrails(text, text, "length")
    assert not all_passed(results)
    failed = [r for r in results if not r.passed]
    assert any(r.check == CheckName.TRUNCATION for r in failed)
