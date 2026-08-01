from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl


Priority = Literal["critical", "high", "medium", "low"]


class SourceConfig(BaseModel):
    id: str
    name: str
    base_url: HttpUrl | str
    enabled: bool = True
    priority: Priority
    source_type: str
    country: str | None = None
    country_filter: str | None = None
    requires_official_verification: bool = False
    requires_javascript: bool = False
    requires_login: bool = False
    supports_api: bool = False
    check_interval_minutes: int = 720
    parser: str
    entry_urls: list[HttpUrl | str] = Field(default_factory=list)
    alternate_urls: list[HttpUrl | str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def load_source_configs(path: str | Path = "config/sources.yaml") -> list[SourceConfig]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    sources = [SourceConfig.model_validate(item) for item in data.get("sources", [])]
    return sorted(
        [source for source in sources if source.enabled],
        key=lambda item: (PRIORITY_ORDER[item.priority], sources.index(item)),
    )
