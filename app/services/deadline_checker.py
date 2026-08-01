from __future__ import annotations

from datetime import datetime

from app.models.db import Tender


ACTIVE_STATUSES = ("active", "open", "published", "прием", "актив", "qabul")
CLOSED_STATUSES = ("closed", "cancel", "awarded", "completed", "archive", "закры", "отмен", "bekor", "tuzilgan")


class DeadlineChecker:
    def is_active_record(self, deadline: datetime | None, status: str | None, now: datetime) -> bool:
        if deadline is not None and deadline <= now:
            return False
        normalized = (status or "").lower()
        if any(value in normalized for value in CLOSED_STATUSES):
            return False
        return True

    def reminder_due(self, tender: Tender, now: datetime, days: int) -> bool:
        if tender.deadline is None or tender.deadline <= now:
            return False
        remaining = tender.deadline - now
        return 0 <= remaining.total_seconds() <= days * 86400

    def remaining_text(self, deadline: datetime | None, now: datetime) -> str:
        if deadline is None:
            return "Noma'lum"
        delta = deadline - now
        if delta.total_seconds() < 0:
            return "Muddati tugagan"
        days = delta.days
        hours = delta.seconds // 3600
        if days:
            return f"{days} kun {hours} soat"
        return f"{hours} soat"
