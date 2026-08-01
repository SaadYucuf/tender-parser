from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser


def now_tz(tz_name: str = "Asia/Tashkent") -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def parse_datetime(value: str | None, tz_name: str = "Asia/Tashkent") -> datetime | None:
    if not value:
        return None
    text = " ".join(value.split())
    if not text:
        return None
    try:
        parsed = date_parser.parse(text, dayfirst=True, fuzzy=True)
    except (ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo(tz_name))
    return parsed.astimezone(ZoneInfo(tz_name))
