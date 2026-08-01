from __future__ import annotations

import logging
import re
from datetime import datetime

from app.config import Settings
from app.models.db import Tender
from app.services.deadline_checker import DeadlineChecker
from app.utils.http import HttpClient

logger = logging.getLogger(__name__)

TELEGRAM_LIMIT = 4096


class TelegramClient:
    def __init__(self, settings: Settings, http_client: HttpClient) -> None:
        self.settings = settings
        self.http_client = http_client

    @property
    def enabled(self) -> bool:
        return bool(self.settings.telegram_bot_token and self.settings.telegram_chat_id)

    async def send_text(self, text: str) -> None:
        if not self.enabled:
            logger.info("Telegram disabled; message skipped")
            return
        assert self.settings.telegram_bot_token is not None
        assert self.settings.telegram_chat_id is not None
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        for chunk in split_message(text):
            payload: dict[str, object] = {
                "chat_id": self.settings.telegram_chat_id,
                "text": chunk,
                "parse_mode": self.settings.telegram_parse_mode,
                "disable_web_page_preview": False,
            }
            if self.settings.telegram_thread_id:
                payload["message_thread_id"] = self.settings.telegram_thread_id
            await self.http_client.post_json(url, payload)

    async def send_test(self) -> None:
        await self.send_text(escape_md("MedTender AI Agent test xabari. Telegram sozlamalari ishlayapti."))


def escape_md(value: object) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)


def split_message(text: str) -> list[str]:
    if len(text) <= TELEGRAM_LIMIT:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.splitlines(keepends=True):
        if current_len + len(line) > TELEGRAM_LIMIT - 20:
            chunks.append("".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line)
    if current:
        chunks.append("".join(current))
    return chunks


def fmt_date(value: datetime | None) -> str:
    return value.strftime("%d.%m.%Y, %H:%M") if value else "Noma'lum"


def fmt_amount(amount: float | None, currency: str | None) -> str:
    if amount is None:
        return "Ko'rsatilmagan"
    return f"{amount:,.2f} {currency or ''}".replace(",", " ")


def format_new_tender(tender: Tender, now: datetime) -> str:
    checker = DeadlineChecker()
    requirements = _requirements(tender)
    customer = tender.customer or "Noma'lum"
    lot = tender.lot_number or tender.lot_name or "Ko'rsatilmagan"
    return "\n".join(
        [
            "*🆕 Yangi medtexnika tenderi*",
            "",
            f"*Buyurtmachi:* {escape_md(customer)}",
            f"*Tender:* {escape_md(tender.title)}",
            f"*Lot:* {escape_md(lot)}",
            f"*Summa:* {escape_md(fmt_amount(tender.amount, tender.currency))}",
            f"*Deadline:* {escape_md(fmt_date(tender.deadline))}",
            f"*Qolgan vaqt:* {escape_md(checker.remaining_text(tender.deadline, now))}",
            f"*Kategoriya:* {escape_md(tender.category)}",
            f"*Moslik:* {tender.relevance_score}%",
            f"*Manba:* {escape_md(tender.source)}",
            "",
            "*Qisqa tavsif:*",
            escape_md(tender.description or "Manba matni asosida avtomatik aniqlangan tender."),
            "",
            "*Asosiy talablar:*",
            requirements,
            "",
            f"*Havola:* {escape_md(tender.source_url)}",
        ]
    )


def format_update(tender: Tender, changed_fields: dict[str, tuple[object, object]]) -> str:
    lines = ["*🔄 Tender ma'lumotlari yangilandi*", "", f"*Tender:* {escape_md(tender.title)}"]
    for field, (old, new) in changed_fields.items():
        if field == "content_hash":
            continue
        lines.append(f"*{escape_md(field)}:* {escape_md(old)} → {escape_md(new)}")
    lines.extend(["", f"*Havola:* {escape_md(tender.source_url)}"])
    return "\n".join(lines)


def format_reminder(tender: Tender, now: datetime) -> str:
    checker = DeadlineChecker()
    customer = tender.customer or "Noma'lum"
    return "\n".join(
        [
            f"*⚠️ Tender yopilishiga {escape_md(checker.remaining_text(tender.deadline, now))} qoldi*",
            "",
            f"*Tender:* {escape_md(tender.title)}",
            f"*Buyurtmachi:* {escape_md(customer)}",
            f"*Deadline:* {escape_md(fmt_date(tender.deadline))}",
            f"*Havola:* {escape_md(tender.source_url)}",
        ]
    )


def format_daily_report(stats: dict[str, int], failed_sources: list[str]) -> str:
    if stats.get("new_active", 0) == 0:
        headline = "*Bugungi tekshiruv yakunlandi\\. Yangi mos medtexnika tenderlari topilmadi\\.*"
    else:
        headline = "*📊 Medtexnika tenderlari bo'yicha kunlik monitoring*"
    lines = [
        headline,
        "",
        f"Tekshirilgan manbalar: {stats.get('sources_checked', 0)} ta",
        f"Topilgan tenderlar: {stats.get('found', 0)} ta",
        f"Yangi faol tenderlar: {stats.get('new_active', 0)} ta",
        f"Yangilangan tenderlar: {stats.get('updated', 0)} ta",
        f"Muddati yaqin tenderlar: {stats.get('reminders', 0)} ta",
        f"Dublikatlar: {stats.get('duplicates', 0)} ta",
        f"Xatolik yuz bergan manbalar: {len(failed_sources)} ta",
    ]
    if failed_sources:
        lines.append(f"Xatoliklar: {escape_md(', '.join(failed_sources))}")
    return "\n".join(escape_md(line) if not line.startswith("*") else line for line in lines)


def _requirements(tender: Tender) -> str:
    values = [line.strip() for line in (tender.required_documents or "").splitlines() if line.strip()]
    if not values:
        values = [
            tender.manufacturer_authorization,
            tender.delivery_requirements,
            tender.bid_security,
        ]
    values = [value for value in values if value]
    if not values:
        return escape_md("- hujjatlarni manbadan qo'lda tekshiring")
    return "\n".join(f"• {escape_md(value)}" for value in values[:8])
