from __future__ import annotations

import logging
import os

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


def resolve_api_key(base_url: str, api_key: str | None) -> str:
    if api_key is not None:
        return api_key

    env_openai = os.environ.get("OPENAI_API_KEY")
    if env_openai:
        return env_openai

    raise ValueError(f"No API key for {base_url}. Pass api_key= or set OPENAI_API_KEY.")


def build_chat_model(
    model: str,
    base_url: str,
    api_key: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    **kwargs: object,
) -> ChatOpenAI:
    resolved_key = resolve_api_key(base_url, api_key)

    return ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=resolved_key,  # type: ignore[arg-type]
        temperature=temperature,
        # pydantic declares this field as max_tokens with a max_completion_tokens
        # alias; mypy only sees the alias, but both work at runtime.
        max_tokens=max_tokens,  # type: ignore[call-arg]
        **kwargs,  # type: ignore[arg-type]
    )
