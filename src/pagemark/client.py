from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pagemark.backends import build_chat_model
from pagemark.models import Document
from pagemark.pipeline import ProgressCallback
from pagemark.pipeline import aconvert as _pipeline_aconvert

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from pagemark.profiles import ModelProfile


class Pagemark:
    """Client for converting PDFs to Markdown using vision-language models.

    Either ``base_url`` or ``chat_model`` is required.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        chat_model: BaseChatModel | None = None,
    ) -> None:
        if chat_model is not None and base_url is not None:
            raise ValueError("Pass either chat_model or base_url/api_key, not both")
        if chat_model is None and base_url is None:
            raise ValueError("Either base_url or chat_model is required")
        self._base_url = base_url
        self._api_key = api_key
        self._chat_model = chat_model

    def convert(
        self,
        pdf_path: str,
        *,
        model: str | None = None,
        max_tokens: int = 2048,
        profile: str | ModelProfile | None = None,
        pages: str | list[int] | None = None,
        concurrency: int | None = None,
    ) -> Document:
        """Convert a PDF to Markdown. Sync wrapper around :meth:`aconvert`."""
        return asyncio.run(
            self.aconvert(
                pdf_path,
                model=model,
                max_tokens=max_tokens,
                profile=profile,
                pages=pages,
                concurrency=concurrency,
            )
        )

    async def aconvert(
        self,
        pdf_path: str,
        *,
        model: str | None = None,
        max_tokens: int = 2048,
        profile: str | ModelProfile | None = None,
        pages: str | list[int] | None = None,
        concurrency: int | None = None,
        progress: ProgressCallback | None = None,
    ) -> Document:
        """Convert a PDF to Markdown asynchronously."""
        chat_model, model_id = self._resolve(model, max_tokens)
        return await _pipeline_aconvert(
            pdf_path,
            chat_model=chat_model,
            model_id=model_id,
            profile=profile,
            pages=pages,
            concurrency=concurrency,
            progress=progress,
        )

    def _resolve(self, model: str | None, max_tokens: int) -> tuple[BaseChatModel, str]:
        if self._chat_model is not None:
            model_id = model or getattr(self._chat_model, "model_name", None) or "custom"
            return self._chat_model, model_id
        if model is None:
            raise ValueError("model is required")
        assert self._base_url is not None
        return build_chat_model(
            model, base_url=self._base_url, api_key=self._api_key, max_tokens=max_tokens
        ), model
