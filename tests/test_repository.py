from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.db import Base
from app.models.schemas import TenderRecord
from app.repositories.tenders import TenderRepository
from app.services.deduplicator import Deduplicator


def test_upsert_does_not_mark_timezone_only_deadline_change_as_update():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    dedupe = Deduplicator()
    now = datetime(2026, 8, 1, 8, 0, tzinfo=ZoneInfo("Asia/Tashkent"))
    aware_deadline = datetime(2026, 8, 5, 11, 23, 17, tzinfo=ZoneInfo("Asia/Tashkent"))
    first = dedupe.enrich(
        TenderRecord(
            source="eTender UZEX",
            tender_number="123",
            title="MRI scanner",
            customer="Customer",
            deadline=aware_deadline,
            status="Active",
            source_url="https://etender.uzex.uz/lot/123",
        )
    )
    second = dedupe.enrich(first.model_copy(update={"deadline": aware_deadline.replace(tzinfo=None)}))

    with session_factory() as session:
        repo = TenderRepository(session)
        repo.upsert(first, now)
        session.commit()
        result = repo.upsert(second, now)

    assert result.status == "duplicate"


def test_upsert_falls_back_to_existing_source_url_when_dedupe_key_changes():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    dedupe = Deduplicator()
    now = datetime(2026, 8, 1, 8, 0, tzinfo=ZoneInfo("Asia/Tashkent"))
    first = dedupe.enrich(
        TenderRecord(
            source="eTender UZEX",
            tender_number="123",
            title="MRI scanner",
            customer="Customer",
            deadline=datetime(2026, 8, 5, 11, 0),
            status="Active",
            source_url="https://etender.uzex.uz/lot/123",
        )
    )
    second = dedupe.enrich(first.model_copy(update={"title": "MRI scanner and installation"}))

    with session_factory() as session:
        repo = TenderRepository(session)
        created = repo.upsert(first, now)
        session.commit()
        result = repo.upsert(second, now)
        session.commit()
        count = session.query(created.tender.__class__).count()

    assert result.tender.id == created.tender.id
    assert count == 1
