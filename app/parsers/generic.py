from __future__ import annotations

from app.models.schemas import TenderRecord
from app.parsers.base import GenericSearchParser, SearchEndpoint
from app.sources import SourceConfig
from app.utils.http import HttpClient


class ConfiguredGenericParser(GenericSearchParser):
    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.source_name = config.name
        self.base_url = str(config.base_url)
        urls = [str(url) for url in config.entry_urls] or [str(config.base_url)]
        self.endpoints = [SearchEndpoint(url, "q") for url in urls]
        self.country_filter = config.country_filter
        self.direct_pages_only = bool(config.entry_urls)
        self.max_keywords = 8

    async def fetch(self, client: HttpClient) -> list[TenderRecord]:
        try:
            return await super().fetch(client)
        except Exception:
            # Generic sources are best-effort. SourceRun captures the error in MonitorService.
            raise
