from __future__ import annotations

import gzip
import logging
from collections import Counter
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CheckName(str, Enum):
    REPETITION = "repetition"
    TRUNCATION = "truncation"
    COVERAGE = "coverage"
    HALLUCINATION = "hallucination"
    REFUSAL = "refusal"


@dataclass
class GuardrailResult:
    check: CheckName
    passed: bool
    score: float
    detail: str


_REFUSAL_PATTERNS = [
    "i'm sorry",
    "i cannot",
    "i can't",
    "i am unable",
    "i apologize",
    "as an ai",
    "i'm not able",
    "i am not able",
]

_NGRAM_SIZE = 4
_NGRAM_THRESHOLD = 0.15
_COMPRESSION_THRESHOLD = 0.10
_COVERAGE_THRESHOLD = 0.25
_HALLUCINATION_THRESHOLD = 0.70
_MIN_OUTPUT_LENGTH = 20


def run_guardrails(
    text: str,
    anchor: str,
    finish_reason: str | None = None,
) -> list[GuardrailResult]:
    results: list[GuardrailResult] = [
        check_repetition(text),
        check_truncation(text, finish_reason),
        check_coverage(text, anchor),
        check_hallucination(text, anchor),
        check_refusal(text),
    ]
    for r in results:
        if not r.passed:
            logger.warning(
                "Guardrail failed: %s (score=%.3f) — %s",
                r.check.value,
                r.score,
                r.detail,
                extra={"check": r.check.value, "score": r.score},
            )
    return results


def all_passed(results: list[GuardrailResult]) -> bool:
    return all(r.passed for r in results)


def check_repetition(text: str) -> GuardrailResult:
    if len(text) < 50:
        return GuardrailResult(CheckName.REPETITION, True, 0.0, "too short to check")

    compression = _compression_ratio(text)
    if compression < _COMPRESSION_THRESHOLD:
        return GuardrailResult(
            CheckName.REPETITION,
            False,
            compression,
            f"compression ratio {compression:.3f} below threshold {_COMPRESSION_THRESHOLD}",
        )

    ngram_freq = _max_ngram_frequency(text, _NGRAM_SIZE)
    if ngram_freq > _NGRAM_THRESHOLD:
        return GuardrailResult(
            CheckName.REPETITION,
            False,
            ngram_freq,
            f"ngram frequency {ngram_freq:.3f} above threshold {_NGRAM_THRESHOLD}",
        )

    return GuardrailResult(
        CheckName.REPETITION,
        True,
        max(compression, ngram_freq),
        "ok",
    )


def check_truncation(text: str, finish_reason: str | None) -> GuardrailResult:
    truncated = finish_reason == "length"
    return GuardrailResult(
        CheckName.TRUNCATION,
        not truncated,
        1.0 if truncated else 0.0,
        f"finish_reason={finish_reason}" if truncated else "ok",
    )


def check_coverage(text: str, anchor: str) -> GuardrailResult:
    if not anchor or not anchor.strip():
        return GuardrailResult(CheckName.COVERAGE, True, 1.0, "no anchor (scanned page)")

    anchor_tokens = _tokenize(anchor)
    output_tokens = _tokenize(text)

    if not anchor_tokens:
        return GuardrailResult(CheckName.COVERAGE, True, 1.0, "empty anchor tokens")

    recalled = anchor_tokens & output_tokens
    score = len(recalled) / len(anchor_tokens)

    passed = score >= _COVERAGE_THRESHOLD
    return GuardrailResult(
        CheckName.COVERAGE,
        passed,
        score,
        f"coverage {score:.3f}" + ("" if passed else f" below {_COVERAGE_THRESHOLD}"),
    )


def check_hallucination(text: str, anchor: str) -> GuardrailResult:
    if not anchor or not anchor.strip():
        return GuardrailResult(CheckName.HALLUCINATION, True, 0.0, "no anchor (scanned page)")

    anchor_tokens = _tokenize(anchor)
    output_words = text.lower().split()

    if not output_words:
        return GuardrailResult(CheckName.HALLUCINATION, True, 0.0, "empty output")

    novel = sum(1 for w in output_words if w not in anchor_tokens)
    score = novel / len(output_words)

    passed = score <= _HALLUCINATION_THRESHOLD
    return GuardrailResult(
        CheckName.HALLUCINATION,
        passed,
        score,
        f"hallucination rate {score:.3f}"
        + ("" if passed else f" above {_HALLUCINATION_THRESHOLD}"),
    )


def check_refusal(text: str) -> GuardrailResult:
    stripped = text.strip()
    if len(stripped) < _MIN_OUTPUT_LENGTH:
        return GuardrailResult(
            CheckName.REFUSAL,
            False,
            1.0,
            f"output too short ({len(stripped)} chars)",
        )

    lower = stripped.lower()
    for pattern in _REFUSAL_PATTERNS:
        if pattern in lower[:200]:
            return GuardrailResult(CheckName.REFUSAL, False, 1.0, f"refusal pattern: {pattern!r}")

    return GuardrailResult(CheckName.REFUSAL, True, 0.0, "ok")


def _compression_ratio(text: str) -> float:
    encoded = text.encode("utf-8")
    if not encoded:
        return 1.0
    compressed = gzip.compress(encoded, compresslevel=6)
    return len(compressed) / len(encoded)


def _max_ngram_frequency(text: str, n: int) -> float:
    words = text.split()
    if len(words) < n:
        return 0.0
    ngrams = [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]
    if not ngrams:
        return 0.0
    counter = Counter(ngrams)
    return counter.most_common(1)[0][1] / len(ngrams)


def _tokenize(text: str) -> set[str]:
    return {w for w in text.lower().split() if len(w) > 1}
