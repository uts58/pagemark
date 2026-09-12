"""pagemark: PDF-to-Markdown converter using vision-language models."""

from __future__ import annotations

import logging

from pagemark.client import Pagemark as Pagemark
from pagemark.models import Asset, Block, BlockType, Document, Page, PageSource, TokenUsage

__version__ = "0.1.0"
__all__ = [
    "Asset",
    "Block",
    "BlockType",
    "Document",
    "Page",
    "PageSource",
    "Pagemark",
    "TokenUsage",
]

logging.getLogger(__name__).addHandler(logging.NullHandler())
