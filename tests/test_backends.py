from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from pagemark.backends import resolve_api_key


def test_api_key_explicit() -> None:
    assert resolve_api_key("https://example.com/v1", "my-key") == "my-key"


def test_api_key_from_openai_env() -> None:
    with patch.dict(os.environ, {"OPENAI_API_KEY": "oai-key"}, clear=False):
        assert resolve_api_key("https://example.com/v1", None) == "oai-key"


def test_api_key_missing_raises() -> None:
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("OPENAI_API_KEY", None)
        with pytest.raises(ValueError, match="No API key"):
            resolve_api_key("https://example.com/v1", None)
