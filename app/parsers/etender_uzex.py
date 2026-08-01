from __future__ import annotations

from app.models.schemas import TenderRecord
from app.parsers.base import GenericSearchParser, SearchEndpoint
from app.utils.dates import parse_datetime
from app.utils.http import HttpClient


class EtenderUzexParser(GenericSearchParser):
    source_name = "eTender UZEX"
    base_url = "https://etender.uzex.uz"
    api_url = "https://apietender.uzex.uz/api/common/TradeList"
    endpoints = [
        SearchEndpoint("https://etender.uzex.uz/search", "search"),
        SearchEndpoint("https://etender.uzex.uz/lot/list", "filter"),
    ]

    async def fetch(self, client: HttpClient) -> list[TenderRecord]:
        records: list[TenderRecord] = []
        seen: set[int] = set()
        page_size = 100
        # Public frontend API. It returns currently visible active trades ordered by deadline.
        for start in range(1, 801, page_size):
            payload = {"from": start, "to": start + page_size - 1}
            data = await client.post_json(self.api_url, payload)
            if not isinstance(data, list) or not data:
                break
            for item in data:
                if not isinstance(item, dict):
                    continue
                record = self._item_to_record(item)
                if record and item.get("id") not in seen:
                    seen.add(int(item.get("id") or 0))
                    records.append(record)
            total = self._total_count(data)
            if total is not None and start + page_size > total:
                break
        return records

    def _item_to_record(self, item: dict[str, object]) -> TenderRecord | None:
        title = str(item.get("name") or "").strip()
        lot_id = item.get("id")
        if not title or lot_id is None:
            return None
        amount = item.get("cost")
        try:
            parsed_amount = float(amount) if amount is not None else None
        except (TypeError, ValueError):
            parsed_amount = None
        url = f"https://etender.uzex.uz/lot/{lot_id}"
        return TenderRecord(
            external_id=str(lot_id),
            source=self.source_name,
            tender_number=str(item.get("display_no") or lot_id),
            title=title,
            customer=str(item.get("seller_name") or "").strip() or None,
            customer_region=str(item.get("region_name") or "").strip() or None,
            amount=parsed_amount,
            currency=str(item.get("currency_codeabc") or item.get("currency_name") or "").strip() or None,
            published_at=parse_datetime(str(item.get("start_date") or "")),
            deadline=parse_datetime(str(item.get("end_date") or "")),
            status="Active",
            language=self._detect_language(title),
            source_url=url,
            raw_text=" ".join(
                str(value)
                for value in [
                    item.get("display_no"),
                    item.get("name"),
                    item.get("seller_name"),
                    item.get("region_name"),
                    item.get("district_name"),
                    item.get("category_name"),
                ]
                if value
            ),
        )

    def _total_count(self, data: list[object]) -> int | None:
        for item in data:
            if isinstance(item, dict) and item.get("total_count") is not None:
                try:
                    return int(item["total_count"])
                except (TypeError, ValueError):
                    return None
        return None
