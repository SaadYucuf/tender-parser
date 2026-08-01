from __future__ import annotations

import abc
import logging
import re
from dataclasses import dataclass
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup, Tag

from app.models.schemas import TenderRecord
from app.parsers.keywords import KEYWORDS
from app.utils.dates import parse_datetime
from app.utils.http import HttpClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchEndpoint:
    url: str
    query_param: str = "q"
    extra_params: dict[str, str] | None = None


@dataclass
class ParseStats:
    source: str
    records_found: int = 0
    error: str | None = None


class SourceParser(abc.ABC):
    source_name: str

    @abc.abstractmethod
    async def fetch(self, client: HttpClient) -> list[TenderRecord]:
        raise NotImplementedError


class GenericSearchParser(SourceParser):
    base_url: str
    endpoints: list[SearchEndpoint]
    country_filter: str | None = None
    max_keywords: int = 18

    async def fetch(self, client: HttpClient) -> list[TenderRecord]:
        records: list[TenderRecord] = []
        seen_urls: set[str] = set()
        for endpoint in self.endpoints:
            for keyword in self.keywords():
                params = dict(endpoint.extra_params or {})
                params[endpoint.query_param] = keyword
                url = self._url_with_params(endpoint.url, params)
                try:
                    html = await client.get_text(endpoint.url, params=params)
                except Exception as exc:
                    logger.warning("source fetch failed", extra={"source": self.source_name, "url": url, "error": str(exc)})
                    continue
                for record in self.parse_html(html, page_url=endpoint.url):
                    if self.country_filter and self.country_filter.lower() not in (record.raw_text or record.title).lower():
                        continue
                    if str(record.source_url) in seen_urls:
                        continue
                    seen_urls.add(str(record.source_url))
                    records.append(record)
        return records

    def keywords(self) -> list[str]:
        return KEYWORDS[: self.max_keywords]

    def parse_html(self, html: str, page_url: str | None = None) -> list[TenderRecord]:
        soup = BeautifulSoup(html, "html.parser")
        candidates = self._candidate_blocks(soup)
        records = [record for block in candidates if (record := self._block_to_record(block, page_url or self.base_url)) is not None]
        if not records:
            records = self._links_to_records(soup, page_url or self.base_url)
        return records

    def _candidate_blocks(self, soup: BeautifulSoup) -> list[Tag]:
        selectors = [
            "[class*=tender]",
            "[class*=lot]",
            "[class*=notice]",
            "[class*=purchase]",
            "article",
            "tr",
            "li",
        ]
        blocks: list[Tag] = []
        seen: set[int] = set()
        for selector in selectors:
            for node in soup.select(selector):
                node_id = id(node)
                if node_id in seen:
                    continue
                text = node.get_text(" ", strip=True)
                if len(text) >= 35 and self._looks_relevant_text(text):
                    seen.add(node_id)
                    blocks.append(node)
        return blocks

    def _links_to_records(self, soup: BeautifulSoup, page_url: str) -> list[TenderRecord]:
        records: list[TenderRecord] = []
        for link in soup.find_all("a", href=True):
            text = link.get_text(" ", strip=True)
            if len(text) < 20 or not self._looks_relevant_text(text):
                continue
            records.append(
                TenderRecord(
                    source=self.source_name,
                    title=text[:500],
                    source_url=urljoin(page_url, link["href"]),
                    raw_text=text,
                    language=self._detect_language(text),
                )
            )
        return records

    def _block_to_record(self, block: Tag, page_url: str) -> TenderRecord | None:
        text = block.get_text(" ", strip=True)
        if not self._looks_relevant_text(text):
            return None
        link = block.find("a", href=True)
        source_url = urljoin(page_url, link["href"]) if link else page_url
        title = self._extract_title(block, text)
        deadline = self._extract_deadline(text)
        amount, currency = self._extract_amount(text)
        status = self._extract_status(text)
        number = self._extract_number(text)
        return TenderRecord(
            external_id=number,
            source=self.source_name,
            tender_number=number,
            title=title[:500],
            customer=self._extract_customer(text),
            amount=amount,
            currency=currency,
            deadline=deadline,
            status=status,
            language=self._detect_language(text),
            source_url=source_url,
            raw_text=text,
        )

    def _extract_title(self, block: Tag, text: str) -> str:
        for selector in ("h1", "h2", "h3", "h4", "a", "td"):
            node = block.select_one(selector)
            if node:
                candidate = node.get_text(" ", strip=True)
                if len(candidate) >= 10:
                    return candidate
        return text[:240]

    def _extract_deadline(self, text: str):
        patterns = [
            r"(?:deadline|end date|closing date|submission deadline|срок подачи|дата окончания|qabul qilish muddati)[:\s-]*(.{6,32})",
            r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}(?:\s+\d{1,2}:\d{2})?\b",
            r"\b\d{4}-\d{2}-\d{2}(?:\s+\d{1,2}:\d{2})?\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return parse_datetime(match.group(1) if match.groups() else match.group(0))
        return None

    def _extract_amount(self, text: str) -> tuple[float | None, str | None]:
        match = re.search(r"([\d\s.,]{4,})\s*(UZS|сум|so'm|sum|USD|EUR)", text, re.IGNORECASE)
        if not match:
            return None, None
        raw = match.group(1).replace(" ", "").replace(",", ".")
        if raw.count(".") > 1:
            raw = raw.replace(".", "")
        try:
            amount = float(raw)
        except ValueError:
            return None, match.group(2).upper()
        currency = match.group(2).upper().replace("СУМ", "UZS").replace("SO'M", "UZS").replace("SUM", "UZS")
        return amount, currency

    def _extract_status(self, text: str) -> str | None:
        for status in ("Active", "Open", "Published", "Прием предложений", "Активный", "Qabul qilinmoqda"):
            if status.lower() in text.lower():
                return status
        return None

    def _extract_number(self, text: str) -> str | None:
        match = re.search(r"(?:№|No\.?|N\s*|ID|Lot)\s*[:#-]?\s*([A-ZА-Я0-9][A-ZА-Я0-9./_-]{3,})", text, re.IGNORECASE)
        return match.group(1) if match else None

    def _extract_customer(self, text: str) -> str | None:
        match = re.search(r"(?:customer|buyurtmachi|заказчик)[:\s-]+(.{5,100}?)(?:deadline|срок|summa|сумма|$)", text, re.IGNORECASE)
        return match.group(1).strip(" .;:-") if match else None

    def _looks_relevant_text(self, text: str) -> bool:
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in KEYWORDS)

    def _detect_language(self, text: str) -> str:
        lowered = text.lower()
        if re.search(r"[а-яё]", lowered):
            return "ru"
        if any(word in lowered for word in ("the", "equipment", "deadline", "supply")):
            return "en"
        return "uz"

    def _url_with_params(self, url: str, params: dict[str, str]) -> str:
        return f"{url}?{urlencode(params)}"
