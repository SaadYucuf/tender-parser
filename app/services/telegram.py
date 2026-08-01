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
DEFAULT_PARSE_MODE = object()


class TelegramClient:
    def __init__(self, settings: Settings, http_client: HttpClient) -> None:
        self.settings = settings
        self.http_client = http_client

    @property
    def enabled(self) -> bool:
        return bool(self.settings.telegram_bot_token and self.settings.telegram_chat_id)

    async def send_text(
        self,
        text: str,
        reply_markup: dict[str, object] | None = None,
        parse_mode: object = DEFAULT_PARSE_MODE,
    ) -> None:
        if not self.enabled:
            logger.info("Telegram disabled; message skipped")
            return
        assert self.settings.telegram_bot_token is not None
        assert self.settings.telegram_chat_id is not None
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        mode = self.settings.telegram_parse_mode if parse_mode is DEFAULT_PARSE_MODE else parse_mode
        chunks = split_message(text)
        for index, chunk in enumerate(chunks):
            payload: dict[str, object] = {
                "chat_id": self.settings.telegram_chat_id,
                "text": chunk,
                "disable_web_page_preview": False,
            }
            if mode:
                payload["parse_mode"] = mode
            if self.settings.telegram_thread_id:
                payload["message_thread_id"] = self.settings.telegram_thread_id
            if reply_markup and index == len(chunks) - 1:
                payload["reply_markup"] = reply_markup
            await self._post_message(url, payload)

    async def send_chat_text(
        self,
        chat_id: str,
        text: str,
        reply_markup: dict[str, object] | None = None,
        parse_mode: object = DEFAULT_PARSE_MODE,
    ) -> None:
        if not self.settings.telegram_bot_token:
            logger.info("Telegram disabled; chat message skipped")
            return
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        mode = self.settings.telegram_parse_mode if parse_mode is DEFAULT_PARSE_MODE else parse_mode
        chunks = split_message(text)
        for index, chunk in enumerate(chunks):
            payload: dict[str, object] = {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": False,
            }
            if mode:
                payload["parse_mode"] = mode
            if self.settings.telegram_thread_id and chat_id == self.settings.telegram_chat_id:
                payload["message_thread_id"] = self.settings.telegram_thread_id
            if reply_markup and index == len(chunks) - 1:
                payload["reply_markup"] = reply_markup
            await self._post_message(url, payload)

    async def get_updates(self, offset: int | None = None, timeout: int = 25) -> list[dict[str, object]]:
        if not self.settings.telegram_bot_token:
            return []
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/getUpdates"
        payload: dict[str, object] = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            payload["offset"] = offset
        response = await self.http_client.post_json(url, payload)
        if not isinstance(response, dict) or not response.get("ok"):
            raise RuntimeError("Telegram getUpdates failed")
        result = response.get("result", [])
        return result if isinstance(result, list) else []

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        if not self.settings.telegram_bot_token:
            return
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/answerCallbackQuery"
        payload: dict[str, object] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        await self.http_client.post_json(url, payload)

    async def _post_message(self, url: str, payload: dict[str, object]) -> None:
        try:
            await self.http_client.post_json(url, payload)
        except RuntimeError:
            if payload.get("parse_mode") != "MarkdownV2":
                raise
            fallback = dict(payload)
            fallback.pop("parse_mode", None)
            await self.http_client.post_json(url, fallback)

    async def send_test(self) -> None:
        await self.send_text(escape_md("MedTender AI Agent test xabari. Telegram sozlamalari ishlayapti."))


def escape_md(value: object) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)


def md_link(label: object, url: object) -> str:
    safe_url = str(url or "").replace("\\", "\\\\").replace(")", "\\)")
    return f"[{escape_md(label)}]({safe_url})"


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
            f"*Havola:* {md_link('tender sahifasi', tender.source_url)}",
        ]
    )


def format_update(tender: Tender, changed_fields: dict[str, tuple[object, object]]) -> str:
    lines = ["*🔄 Tender ma'lumotlari yangilandi*", "", f"*Tender:* {escape_md(tender.title)}"]
    for field, (old, new) in changed_fields.items():
        if field == "content_hash":
            continue
        lines.append(f"*{escape_md(field)}:* {escape_md(old)} → {escape_md(new)}")
    lines.extend(["", f"*Havola:* {md_link('tender sahifasi', tender.source_url)}"])
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
            f"*Havola:* {md_link('tender sahifasi', tender.source_url)}",
        ]
    )


def format_full_tender(tender: Tender) -> str:
    missing = "Ko'rsatilmagan"
    unknown = "Noma'lum"
    values = [
        "*📄 Tender bo'yicha to'liq ma'lumot*",
        "",
        f"*ID:* {tender.id}",
        f"*Manba:* {escape_md(tender.source)}",
        f"*Tender raqami:* {escape_md(tender.tender_number or missing)}",
        f"*Lot raqami:* {escape_md(tender.lot_number or missing)}",
        f"*Nomi:* {escape_md(tender.title)}",
        f"*Lot nomi:* {escape_md(tender.lot_name or missing)}",
        f"*Buyurtmachi:* {escape_md(tender.customer or unknown)}",
        f"*Hudud:* {escape_md(tender.customer_region or unknown)}",
        f"*Kategoriya:* {escape_md(tender.category)}",
        f"*Moslik:* {tender.relevance_score}%",
        f"*Summa:* {escape_md(fmt_amount(tender.amount, tender.currency))}",
        f"*E'lon sanasi:* {escape_md(fmt_date(tender.published_at))}",
        f"*Deadline:* {escape_md(fmt_date(tender.deadline))}",
        f"*Status:* {escape_md(tender.status or unknown)}",
        f"*Til:* {escape_md(tender.language or unknown)}",
        "",
        "*Tavsif:*",
        escape_md(tender.description or "Tavsif topilmadi."),
        "",
        "*Asosiy talablar:*",
        _requirements(tender),
        "",
        f"*Bid security:* {escape_md(tender.bid_security or missing)}",
        f"*Manufacturer authorization:* {escape_md(tender.manufacturer_authorization or missing)}",
        f"*Yetkazib berish/o'rnatish:* {escape_md(tender.delivery_requirements or missing)}",
        f"*Havola:* {md_link('tender sahifasi', tender.source_url)}",
    ]
    return "\n".join(values)


def format_tender_list(title: str, tenders: list[Tender], now: datetime) -> str:
    if not tenders:
        return f"*{escape_md(title)}*\n\nTender topilmadi\\."
    checker = DeadlineChecker()
    lines = [f"*{escape_md(title)}*", ""]
    for tender in tenders:
        lines.extend(
            [
                f"*#{tender.id}* {escape_md(tender.title)}",
                f"{escape_md(tender.category)} · {tender.relevance_score}% · {escape_md(checker.remaining_text(tender.deadline, now))}",
                md_link("Manba", tender.source_url),
                "",
            ]
        )
    return "\n".join(lines).strip()


def tender_inline_keyboard(tender: Tender) -> dict[str, object]:
    return {
        "inline_keyboard": [
            [{"text": "🔗 Manbaga o'tish", "url": tender.source_url}],
            [
                {"text": "📄 To'liq ma'lumot", "callback_data": f"full:{tender.id}"},
                {"text": "⭐ Saqlash", "callback_data": f"save:{tender.id}"},
            ],
            [
                {"text": "🔕 Kategoriyani mute", "callback_data": f"mute:{tender.id}"},
                {"text": "❌ Mos emas", "callback_data": f"bad:{tender.id}"},
            ],
        ]
    }


def reminder_inline_keyboard(tender: Tender) -> dict[str, object]:
    return {
        "inline_keyboard": [
            [
                {"text": "🔗 Manbaga o'tish", "url": tender.source_url},
                {"text": "✅ Ko'rib chiqdim", "callback_data": f"seen:{tender.id}"},
            ]
        ]
    }


def report_inline_keyboard() -> dict[str, object]:
    return {
        "inline_keyboard": [
            [
                {"text": "📊 Batafsil hisobot", "callback_data": "report:full"},
                {"text": "⚠️ Xatoliklar", "callback_data": "report:errors"},
            ]
        ]
    }


def format_daily_report(
    stats: dict[str, int],
    failed_sources: list[str],
    source_links: list[tuple[str, str]] | None = None,
    source_statuses: list[dict[str, object]] | None = None,
) -> str:
    if stats.get("new_active", 0) == 0:
        headline = "Bugungi tekshiruv yakunlandi. Yangi mos medtexnika tenderlari topilmadi."
    else:
        headline = "📊 Medtexnika tenderlari bo'yicha kunlik monitoring"
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
        lines.append(f"Xatoliklar: {', '.join(failed_sources)}")
    body = "\n".join(lines)
    if source_statuses:
        source_lines = ["", "Tekshirilgan manbalar:"]
        for item in source_statuses:
            status = "✅" if item.get("status") == "success" else "❌"
            found = item.get("found", 0)
            source_lines.append(f"{status} {item.get('name')} - {found} ta - {item.get('url')}")
        body = body + "\n" + "\n".join(source_lines)
    elif source_links:
        source_lines = ["", "Tekshirilgan manbalar:"]
        source_lines.extend(f"- {name}: {url}" for name, url in source_links if url)
        body = body + "\n" + "\n".join(source_lines)
    return body


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
