from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.db import Notification, SourceRun, Tender, TenderSource
from app.models.schemas import TenderRecord


@dataclass
class UpsertResult:
    tender: Tender
    status: str
    changed_fields: dict[str, tuple[object, object]]


class TenderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, record: TenderRecord, now: datetime) -> UpsertResult:
        if not record.dedupe_key or not record.content_hash:
            raise ValueError("TenderRecord must include dedupe_key and content_hash")

        tender = self.session.scalar(select(Tender).where(Tender.dedupe_key == record.dedupe_key))
        if tender is None:
            tender = Tender(
                external_id=record.external_id,
                source=record.source,
                tender_number=record.tender_number,
                lot_number=record.lot_number,
                title=record.title,
                lot_name=record.lot_name,
                customer=record.customer,
                customer_region=record.customer_region,
                category=str(record.category),
                amount=record.amount,
                currency=record.currency,
                published_at=record.published_at,
                deadline=record.deadline,
                status=record.status,
                language=record.language,
                relevance_score=record.relevance_score,
                description=record.description,
                required_documents="\n".join(record.required_documents) if record.required_documents else None,
                bid_security=record.bid_security,
                manufacturer_authorization=record.manufacturer_authorization,
                delivery_requirements=record.delivery_requirements,
                source_url=str(record.source_url),
                first_seen_at=now,
                last_seen_at=now,
                content_hash=record.content_hash,
                dedupe_key=record.dedupe_key,
            )
            self.session.add(tender)
            self.session.flush()
            self._ensure_source(tender, record)
            return UpsertResult(tender=tender, status="new", changed_fields={})

        changed_fields = self._changed_fields(tender, record)
        tender.last_seen_at = now
        self._ensure_source(tender, record)
        if changed_fields:
            self._apply(tender, record)
            return UpsertResult(tender=tender, status="updated", changed_fields=changed_fields)
        return UpsertResult(tender=tender, status="duplicate", changed_fields={})

    def mark_sent(self, tender: Tender, notification_type: str, chat_id: str | None, status: str, error: str | None = None) -> None:
        now = datetime.now(tz=tender.last_seen_at.tzinfo)
        if status == "sent" and notification_type in {"new", "updated"}:
            tender.last_sent_at = now
        self.session.add(
            Notification(
                tender_id=tender.id,
                notification_type=notification_type,
                telegram_chat_id=chat_id,
                status=status,
                error_message=error,
            )
        )

    def active_tenders(self, now: datetime, max_days: int) -> list[Tender]:
        return list(
            self.session.scalars(
                select(Tender)
                .where(Tender.deadline.is_not(None), Tender.deadline >= now)
                .order_by(Tender.deadline.asc())
            )
        )

    def was_notification_sent(self, tender_id: int, notification_type: str) -> bool:
        return (
            self.session.scalar(
                select(Notification.id)
                .where(Notification.tender_id == tender_id, Notification.notification_type == notification_type, Notification.status == "sent")
                .limit(1)
            )
            is not None
        )

    def latest_runs(self, limit: int = 20) -> list[SourceRun]:
        return list(self.session.scalars(select(SourceRun).order_by(desc(SourceRun.started_at)).limit(limit)))

    def _ensure_source(self, tender: Tender, record: TenderRecord) -> None:
        existing = self.session.scalar(
            select(TenderSource.id).where(
                TenderSource.tender_id == tender.id,
                TenderSource.source_name == record.source,
                TenderSource.source_url == str(record.source_url),
            )
        )
        if existing is None:
            self.session.add(
                TenderSource(
                    tender_id=tender.id,
                    source_name=record.source,
                    source_url=str(record.source_url),
                    external_id=record.external_id,
                )
            )

    def _changed_fields(self, tender: Tender, record: TenderRecord) -> dict[str, tuple[object, object]]:
        candidates = {
            "deadline": record.deadline,
            "amount": record.amount,
            "status": record.status,
            "title": record.title,
            "customer": record.customer,
            "content_hash": record.content_hash,
        }
        return {field: (getattr(tender, field), value) for field, value in candidates.items() if getattr(tender, field) != value}

    def _apply(self, tender: Tender, record: TenderRecord) -> None:
        for field in (
            "external_id",
            "source",
            "tender_number",
            "lot_number",
            "title",
            "lot_name",
            "customer",
            "customer_region",
            "amount",
            "currency",
            "published_at",
            "deadline",
            "status",
            "language",
            "relevance_score",
            "description",
            "bid_security",
            "manufacturer_authorization",
            "delivery_requirements",
            "content_hash",
        ):
            value = getattr(record, field)
            if field == "category":
                value = str(value)
            setattr(tender, field, value)
        tender.category = str(record.category)
        tender.required_documents = "\n".join(record.required_documents) if record.required_documents else None
        tender.source_url = str(record.source_url)
