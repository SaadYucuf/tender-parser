from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.schemas import TenderRecord
from app.services.deduplicator import Deduplicator


def test_dedupe_key_matches_same_tender_from_different_sources():
    deadline = datetime(2026, 8, 20, 15, 0, tzinfo=ZoneInfo("Asia/Tashkent"))
    first = TenderRecord(
        source="SSV",
        tender_number="MRI-2026-01",
        title="MRI system",
        customer="O'zmedimpeks",
        deadline=deadline,
        source_url="https://example.com/a",
    )
    second = TenderRecord(
        source="UNGM",
        tender_number="MRI-2026-01",
        title="MRI system",
        customer="O'zmedimpeks",
        deadline=deadline,
        source_url="https://example.com/b",
    )

    dedupe = Deduplicator()

    assert dedupe.dedupe_key(first) == dedupe.dedupe_key(second)


def test_content_hash_changes_when_deadline_changes():
    dedupe = Deduplicator()
    first = TenderRecord(source="test", title="MRI", deadline=datetime(2026, 8, 20), source_url="https://example.com/a")
    second = TenderRecord(source="test", title="MRI", deadline=datetime(2026, 8, 21), source_url="https://example.com/a")

    assert dedupe.content_hash(first) != dedupe.content_hash(second)
