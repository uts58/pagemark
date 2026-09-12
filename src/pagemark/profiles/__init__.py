from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class PageParse:
    markdown: str


@runtime_checkable
class ModelProfile(Protocol):
    name: str
    dpi: int
    max_pixels: int
    supports_anchor: bool

    def build_prompt(self, anchor: str) -> str: ...

    def parse(self, raw: str) -> PageParse: ...

    def fallback_prompt(self, anchor: str) -> str: ...


_PROFILES: dict[str, ModelProfile] = {}


def register(profile: ModelProfile) -> ModelProfile:
    _PROFILES[profile.name] = profile
    return profile


def get_profile(name: str) -> ModelProfile:
    if name not in _PROFILES:
        raise ValueError(f"Unknown profile {name!r}. Available: {list(_PROFILES.keys())}")
    return _PROFILES[name]


def default_profile() -> ModelProfile:
    return _PROFILES["generic"]
