from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.models.db import Tender
from app.models.schemas import Category
from app.parsers import build_parsers
from app.repositories.database import session_scope
from app.repositories.tenders import TenderRepository
from app.services.monitor import MonitorService
from app.services.telegram import (
    TelegramClient,
    escape_md,
    format_full_tender,
    format_tender_list,
    report_inline_keyboard,
    tender_inline_keyboard,
)
from app.utils.dates import now_tz
from app.utils.http import HttpClient

logger = logging.getLogger(__name__)


USER_COMMANDS = """Foydalanuvchi buyruqlari:
/start - botni ishga tushirish
/help - qo'llanma
/status - oxirgi tekshiruv holati
/today - kunlik hisobot
/latest - oxirgi tenderlar
/search <so'z> - faol tenderlardan qidirish
/deadlines - 3 kun ichida yopiladigan tenderlar
/categories - kategoriya menyusi
/mute <kategoriya> - kategoriyani o'chirish
/unmute <kategoriya> - kategoriyani qayta yoqish
/settings - sozlamalar"""

ADMIN_COMMANDS = """Admin buyruqlari:
/run - monitoringni darhol ishga tushirish
/test_sources - manbalarni tekshirish
/test_telegram - test xabar
/resend <tender_id> - tenderni qayta yuborish
/report - oxirgi run statistikasi
/cleanup - cleanup holati
/pause - avtomatik monitoringni to'xtatish
/resume - monitoringni qayta yoqish
/errors - oxirgi xatoliklar
/addkeyword <til> <so'z> - keyword qo'shish uchun action yozish
/removekeyword <so'z> - keyword o'chirish uchun action yozish
/sources - manbalar holati"""


class TelegramBotService:
    def __init__(self, settings: Settings, session_factory: sessionmaker) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.http_client = HttpClient(
            max(settings.request_timeout_seconds, 35),
            settings.request_retries,
            settings.request_backoff_seconds,
        )
        self.telegram = TelegramClient(settings, self.http_client)
        self.monitor = MonitorService(settings, session_factory)
        self.offset: int | None = None

    async def poll_forever(self) -> None:
        logger.info("telegram bot polling started")
        poll_timeout = 25
        while True:
            try:
                updates = await self.telegram.get_updates(self.offset, timeout=poll_timeout)
                for update in updates:
                    update_id = update.get("update_id")
                    if isinstance(update_id, int):
                        self.offset = update_id + 1
                    await self.handle_update(update)
            except Exception:
                logger.exception("telegram polling failed")
                await asyncio.sleep(5)

    async def handle_update(self, update: dict[str, object]) -> None:
        if "callback_query" in update:
            callback = update["callback_query"]
            if isinstance(callback, dict):
                await self._handle_callback(callback)
            return
        message = update.get("message")
        if not isinstance(message, dict):
            return
        text = str(message.get("text") or "").strip()
        if not text.startswith("/"):
            return
        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        user = message.get("from") if isinstance(message.get("from"), dict) else {}
        chat_id = str(chat.get("id") or "")
        user_id = str(user.get("id") or chat_id)
        await self._handle_command(chat_id, user_id, text)

    async def _handle_command(self, chat_id: str, user_id: str, text: str) -> None:
        command, _, arg = text.partition(" ")
        command = command.split("@", 1)[0].lower()
        is_admin = chat_id in self.settings.admin_chat_ids or user_id in self.settings.admin_chat_ids

        if command in {"/start", "/help"}:
            body = USER_COMMANDS if not is_admin else f"{USER_COMMANDS}\n\n{ADMIN_COMMANDS}"
            await self.telegram.send_chat_text(chat_id, escape_md(body))
            return
        if command == "/status":
            await self.telegram.send_chat_text(chat_id, self._status_text())
            return
        if command in {"/today", "/report"}:
            if command == "/report" and not is_admin:
                await self._admin_denied(chat_id)
                return
            await self.telegram.send_chat_text(chat_id, self._runs_text(limit=20), reply_markup=report_inline_keyboard())
            return
        if command == "/latest":
            await self._send_latest(chat_id)
            return
        if command == "/search":
            await self._send_search(chat_id, arg)
            return
        if command == "/deadlines":
            await self._send_deadlines(chat_id)
            return
        if command == "/categories":
            await self.telegram.send_chat_text(chat_id, escape_md("Kategoriyani tanlang:"), self._categories_keyboard())
            return
        if command in {"/mute", "/unmute"}:
            await self._record_action(chat_id, user_id, command.removeprefix("/"), value=arg.strip())
            await self.telegram.send_chat_text(chat_id, escape_md("Sozlama saqlandi."))
            return
        if command == "/settings":
            await self.telegram.send_chat_text(chat_id, escape_md("Sozlamalar: kategoriya mute/unmute actionlari saqlanadi."))
            return

        if not is_admin:
            await self._admin_denied(chat_id)
            return
        await self._handle_admin_command(chat_id, user_id, command, arg)

    async def _handle_admin_command(self, chat_id: str, user_id: str, command: str, arg: str) -> None:
        if command == "/run":
            await self.telegram.send_chat_text(chat_id, escape_md("Monitoring ishga tushdi. Natijalar shu chatga yuboriladi."))
            summary = await self.monitor.run_once(send_report=True, force=True)
            await self.telegram.send_chat_text(chat_id, escape_md(f"Run tugadi: {summary.stats()}"))
            return
        if command == "/test_sources":
            await self.telegram.send_chat_text(chat_id, escape_md("Manbalar health-check boshlandi."))
            await self.telegram.send_chat_text(chat_id, await self._test_sources_text())
            return
        if command == "/test_telegram":
            await self.telegram.send_chat_text(chat_id, escape_md("MedTender AI Agent test xabari."))
            return
        if command == "/resend":
            await self._resend(chat_id, arg)
            return
        if command == "/cleanup":
            await self.telegram.send_chat_text(chat_id, self._cleanup_text())
            return
        if command == "/pause":
            pause_file = Path(self.settings.monitoring_pause_file)
            pause_file.parent.mkdir(parents=True, exist_ok=True)
            pause_file.write_text("paused\n", encoding="utf-8")
            await self.telegram.send_chat_text(chat_id, escape_md("Avtomatik monitoring pause qilindi."))
            return
        if command == "/resume":
            Path(self.settings.monitoring_pause_file).unlink(missing_ok=True)
            await self.telegram.send_chat_text(chat_id, escape_md("Avtomatik monitoring qayta yoqildi."))
            return
        if command == "/errors":
            await self.telegram.send_chat_text(chat_id, self._errors_text())
            return
        if command == "/sources":
            await self.telegram.send_chat_text(chat_id, self._sources_text())
            return
        if command == "/addkeyword":
            await self._record_action(chat_id, user_id, "addkeyword", value=arg.strip())
            await self.telegram.send_chat_text(chat_id, escape_md("Keyword qo'shish actioni saqlandi."))
            return
        if command == "/removekeyword":
            await self._record_action(chat_id, user_id, "removekeyword", value=arg.strip())
            await self.telegram.send_chat_text(chat_id, escape_md("Keyword o'chirish actioni saqlandi."))
            return
        await self.telegram.send_chat_text(chat_id, escape_md("Noma'lum buyruq. /help ni yuboring."))

    async def _handle_callback(self, callback: dict[str, object]) -> None:
        data = str(callback.get("data") or "")
        callback_id = str(callback.get("id") or "")
        message = callback.get("message") if isinstance(callback.get("message"), dict) else {}
        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        user = callback.get("from") if isinstance(callback.get("from"), dict) else {}
        chat_id = str(chat.get("id") or self.settings.telegram_chat_id or "")
        user_id = str(user.get("id") or chat_id)
        action, _, raw_value = data.partition(":")

        if action == "report":
            text = self._errors_text() if raw_value == "errors" else self._runs_text(limit=30)
            await self.telegram.send_chat_text(chat_id, text)
            await self.telegram.answer_callback_query(callback_id, "Hisobot yuborildi")
            return
        if action == "cat":
            await self._send_category(chat_id, raw_value)
            await self.telegram.answer_callback_query(callback_id, "Kategoriya ochildi")
            return

        tender_id = _safe_int(raw_value)
        if tender_id is None:
            await self.telegram.answer_callback_query(callback_id, "Callback noto'g'ri")
            return
        with session_scope(self.session_factory) as session:
            repo = TenderRepository(session)
            tender = repo.get_tender(tender_id)
            if tender is None:
                await self.telegram.answer_callback_query(callback_id, "Tender topilmadi")
                return
            if action == "full":
                await self.telegram.send_chat_text(chat_id, format_full_tender(tender), tender_inline_keyboard(tender))
            elif action == "save":
                repo.record_user_action(user_id, chat_id, "save", tender_id=tender.id)
                await self.telegram.send_chat_text(chat_id, escape_md(f"Tender #{tender.id} saqlandi."))
            elif action == "mute":
                repo.record_user_action(user_id, chat_id, "mute", tender_id=tender.id, value=tender.category)
                await self.telegram.send_chat_text(chat_id, escape_md(f"{tender.category} kategoriyasi mute qilindi."))
            elif action == "bad":
                repo.record_user_action(user_id, chat_id, "not_relevant", tender_id=tender.id, value=tender.category)
                await self.telegram.send_chat_text(chat_id, escape_md("Feedback saqlandi: mos emas."))
            elif action == "seen":
                repo.record_user_action(user_id, chat_id, "seen", tender_id=tender.id)
            await self.telegram.answer_callback_query(callback_id, "Saqlandi")

    def _status_text(self) -> str:
        now = now_tz(self.settings.tz)
        with session_scope(self.session_factory) as session:
            repo = TenderRepository(session)
            active_count = session.scalar(select(func.count(Tender.id)).where(Tender.deadline.is_not(None), Tender.deadline >= now)) or 0
            latest_run = repo.latest_runs(limit=1)
        paused = Path(self.settings.monitoring_pause_file).exists()
        latest = latest_run[0].started_at.strftime("%d.%m.%Y %H:%M") if latest_run else "hali yo'q"
        return escape_md(f"Status: {'pause' if paused else 'active'}\nOxirgi tekshiruv: {latest}\nFaol tenderlar: {active_count}")

    def _runs_text(self, limit: int = 20) -> str:
        with session_scope(self.session_factory) as session:
            runs = TenderRepository(session).latest_runs(limit=limit)
        if not runs:
            return escape_md("Run tarixi topilmadi.")
        lines = ["Oxirgi monitoring runlari:"]
        for run in runs:
            lines.append(
                f"{run.started_at:%d.%m %H:%M} {run.source_name}: {run.status}, found={run.records_found}, "
                f"new={run.new_records}, upd={run.updated_records}, dup={run.duplicate_records}"
            )
        return escape_md("\n".join(lines))

    async def _send_latest(self, chat_id: str) -> None:
        with session_scope(self.session_factory) as session:
            tenders = TenderRepository(session).latest_sent(limit=10)
            await self.telegram.send_chat_text(chat_id, format_tender_list("Oxirgi yuborilgan tenderlar", tenders, now_tz(self.settings.tz)))

    async def _send_search(self, chat_id: str, query: str) -> None:
        if not query.strip():
            await self.telegram.send_chat_text(chat_id, escape_md("Namuna: /search MRI"))
            return
        with session_scope(self.session_factory) as session:
            tenders = TenderRepository(session).search_active(query, now_tz(self.settings.tz), limit=10)
            await self.telegram.send_chat_text(chat_id, format_tender_list(f"Qidiruv: {query}", tenders, now_tz(self.settings.tz)))

    async def _send_deadlines(self, chat_id: str) -> None:
        with session_scope(self.session_factory) as session:
            tenders = TenderRepository(session).deadline_due(now_tz(self.settings.tz), self.settings.reminder_days, limit=20)
            await self.telegram.send_chat_text(chat_id, format_tender_list("Yaqin deadline tenderlari", tenders, now_tz(self.settings.tz)))

    async def _send_category(self, chat_id: str, category: str) -> None:
        with session_scope(self.session_factory) as session:
            tenders = TenderRepository(session).active_by_category(category, now_tz(self.settings.tz), limit=10)
            await self.telegram.send_chat_text(chat_id, format_tender_list(category, tenders, now_tz(self.settings.tz)))

    async def _resend(self, chat_id: str, arg: str) -> None:
        tender_id = _safe_int(arg.strip())
        if tender_id is None:
            await self.telegram.send_chat_text(chat_id, escape_md("Namuna: /resend 123"))
            return
        with session_scope(self.session_factory) as session:
            repo = TenderRepository(session)
            tender = repo.get_tender(tender_id)
            if tender is None:
                await self.telegram.send_chat_text(chat_id, escape_md("Tender topilmadi."))
                return
            await self.telegram.send_chat_text(chat_id, format_full_tender(tender), tender_inline_keyboard(tender))
            repo.mark_sent(tender, "resend", chat_id, "sent")

    async def _record_action(
        self,
        chat_id: str,
        user_id: str,
        action: str,
        tender_id: int | None = None,
        value: str | None = None,
    ) -> None:
        with session_scope(self.session_factory) as session:
            TenderRepository(session).record_user_action(user_id, chat_id, action, tender_id=tender_id, value=value)

    async def _admin_denied(self, chat_id: str) -> None:
        await self.telegram.send_chat_text(chat_id, escape_md("Bu buyruq faqat admin uchun."))

    async def _test_sources_text(self) -> str:
        lines = ["Manbalar health-check:"]
        for parser in build_parsers(self.settings.sources_config_path):
            ok = await parser.health_check(self.http_client)
            lines.append(f"{'OK' if ok else 'FAIL'} - {parser.source_name} - {parser.base_url}")
        return escape_md("\n".join(lines))

    def _errors_text(self) -> str:
        with session_scope(self.session_factory) as session:
            runs = TenderRepository(session).failed_runs(limit=10)
        if not runs:
            return escape_md("Oxirgi xatoliklar topilmadi.")
        lines = ["Oxirgi xatoliklar:"]
        for run in runs:
            lines.append(f"{run.started_at:%d.%m %H:%M} {run.source_name}: {run.error_message or run.status}")
        return escape_md("\n".join(lines))

    def _sources_text(self) -> str:
        with session_scope(self.session_factory) as session:
            runs = TenderRepository(session).latest_runs(limit=200)
        latest_by_source = {}
        for run in runs:
            latest_by_source.setdefault(run.source_name, run)
        lines = ["Manbalar holati:"]
        for parser in build_parsers(self.settings.sources_config_path):
            run = latest_by_source.get(parser.source_name)
            if run is None:
                lines.append(f"WAIT - {parser.source_name} - hali tekshirilmagan")
            else:
                lines.append(f"{run.status.upper()} - {parser.source_name} - {run.started_at:%d.%m %H:%M}, found={run.records_found}")
        return escape_md("\n".join(lines))

    def _cleanup_text(self) -> str:
        now = now_tz(self.settings.tz)
        with session_scope(self.session_factory) as session:
            expired = session.scalar(select(func.count(Tender.id)).where(Tender.deadline.is_not(None), Tender.deadline < now)) or 0
        return escape_md(f"Cleanup xavfsiz rejimda: {expired} ta muddati o'tgan tender bor. Avtomatik o'chirish yoqilmagan.")

    def _categories_keyboard(self) -> dict[str, object]:
        rows = []
        active_categories = [category.value for category in Category if category != Category.NOT_RELEVANT]
        for index in range(0, len(active_categories), 2):
            rows.append(
                [
                    {"text": value, "callback_data": f"cat:{value}"}
                    for value in active_categories[index : index + 2]
                ]
            )
        return {"inline_keyboard": rows}


def _safe_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
