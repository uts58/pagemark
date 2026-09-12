from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr


class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    FIGURE = "figure"
    CODE = "code"
    LIST = "list"
    FORMULA = "formula"
    CAPTION = "caption"
    FOOTNOTE = "footnote"


class PageSource(str, Enum):
    VLM = "vlm"
    TEXT_LAYER = "text_layer"


class Block(BaseModel):
    type: BlockType
    text: str
    level: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    image_path: str | None = None


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Page(BaseModel):
    index: int
    width: float
    height: float
    dpi: int
    blocks: list[Block] = Field(default_factory=list)
    markdown: str
    source: PageSource
    confidence: float
    warnings: list[str] = Field(default_factory=list)
    usage: TokenUsage | None = None


class Asset(BaseModel):
    filename: str
    page_index: int
    bbox: tuple[float, float, float, float] | None = None
    mime_type: str = "image/png"


class Document(BaseModel):
    pages: list[Page]
    markdown: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    assets: list[Asset] = Field(default_factory=list)
    model_id: str | None = None
    _asset_data: dict[str, bytes] = PrivateAttr(default_factory=dict)

    def save(
        self,
        md_path: str | Path,
        assets_dir: str | Path | None = None,
    ) -> None:
        md_path = Path(md_path)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(self.markdown, encoding="utf-8")

        if assets_dir is not None and self.assets:
            ad = Path(assets_dir)
            ad.mkdir(parents=True, exist_ok=True)
            for asset in self.assets:
                data = self._asset_data.get(asset.filename)
                if data:
                    (ad / asset.filename).write_bytes(data)
