from __future__ import annotations

import hashlib
import re

from app.models.schemas import TenderRecord


IMPORTANT_FIELDS = (
    "title",
    "lot_name",
    "customer",
    "amount",
    "currency",
    "deadline",
    "status",
    "description",
    "required_documents",
    "bid_security",
    "manufacturer_authorization",
    "delivery_requirements",
)


class Deduplicator:
    def enrich(self, record: TenderRecord) -> TenderRecord:
        record.dedupe_key = self.dedupe_key(record)
        record.content_hash = self.content_hash(record)
        return record

    def dedupe_key(self, record: TenderRecord) -> str:
        primary = "|".join(
            self._norm(part)
            for part in [
                record.tender_number or record.external_id,
                record.lot_number,
                record.customer,
                record.title,
                record.deadline.isoformat() if record.deadline else None,
                str(record.amount) if record.amount is not None else None,
            ]
            if part
        )
        if not primary:
            primary = self._norm(f"{record.source}|{record.source_url}|{record.title}")
        return hashlib.sha256(primary.encode("utf-8")).hexdigest()

    def content_hash(self, record: TenderRecord) -> str:
        payload = []
        for field in IMPORTANT_FIELDS:
            value = getattr(record, field)
            if isinstance(value, list):
                value = "|".join(value)
            elif hasattr(value, "isoformat"):
                value = value.isoformat()
            payload.append(self._norm(str(value or "")))
        return hashlib.sha256("\n".join(payload).encode("utf-8")).hexdigest()

    def _norm(self, value: str) -> str:
        return re.sub(r"\s+", " ", value.lower()).strip()
