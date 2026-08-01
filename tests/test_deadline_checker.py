from datetime import timedelta

from app.services.deadline_checker import DeadlineChecker
from app.utils.dates import parse_datetime
from app.utils.dates import now_tz


def test_expired_deadline_is_not_active():
    now = now_tz()

    assert not DeadlineChecker().is_active_record(now - timedelta(minutes=1), "Active", now)


def test_cancelled_status_is_not_active():
    now = now_tz()

    assert not DeadlineChecker().is_active_record(now + timedelta(days=2), "Cancelled", now)


def test_active_future_deadline_is_active():
    now = now_tz()

    assert DeadlineChecker().is_active_record(now + timedelta(days=2), "Published", now)


def test_iso_date_is_year_month_day_not_dayfirst():
    parsed = parse_datetime("2026-08-03T08:10:17")

    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 8
    assert parsed.day == 3
