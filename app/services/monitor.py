from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.models.db import SourceRun
from app.models.schemas import Category
from app.parsers import build_parsers
from app.repositories.database import session_scope
from app.repositories.tenders import TenderRepository
from app.services.classifier import TenderClassifier
from app.services.deadline_checker import DeadlineChecker
from app.services.deduplicator import Deduplicator
from app.services.telegram import (
    TelegramClient,
    format_daily_report,
    format_new_tender,
    format_reminder,
    format_update,
    reminder_inline_keyboard,
    report_inline_keyboard,
    tender_inline_keyboard,
)
from app.utils.dates import now_tz
from app.utils.http import HttpClient

logger = logging.getLogger(__name__)


@dataclass
class RunSummary:
    sources_checked: int = 0
    found: int = 0
    new_active: int = 0
    updated: int = 0
    reminders: int = 0
    duplicates: int = 0
    skipped: int = 0
    failed_sources: list[str] = field(default_factory=list)
    source_links: list[tuple[str, str]] = field(default_factory=list)
    source_statuses: list[dict[str, object]] = field(default_factory=list)

    def stats(self) -> dict[str, int]:
        return {
            "sources_checked": self.sources_checked,
            "found": self.found,
            "new_active": self.new_active,
            "updated": self.updated,
            "reminders": self.reminders,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
        }


class MonitorService:
    def __init__(self, settings: Settings, session_factory: sessionmaker) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.http_client = HttpClient(
            timeout=settings.request_timeout_seconds,
            retries=settings.request_retries,
            backoff=settings.request_backoff_seconds,
        )
        self.telegram = TelegramClient(settings, self.http_client)
        self.classifier = TenderClassifier()
        self.deduplicator = Deduplicator()
        self.deadlines = DeadlineChecker()

    async def run_once(self, send_report: bool = True, force: bool = False) -> RunSummary:
        summary = RunSummary()
        started = now_tz(self.settings.tz)
        if not force and Path(self.settings.monitoring_pause_file).exists():
            logger.info("monitoring skipped because pause file exists")
            if send_report:
                await self.telegram.send_text("Monitoring vaqtincha to'xtatilgan\\. Qayta yoqish uchun /resume buyrug'ini yuboring\\.")
            return summary
        logger.info("monitoring started")
        for parser in build_parsers(self.settings.sources_config_path):
            summary.sources_checked += 1
            summary.source_links.append((parser.source_name, getattr(parser, "base_url", "")))
            source_started = now_tz(self.settings.tz)
            run_id: int | None = None
            with session_scope(self.session_factory) as session:
                source_run = SourceRun(source_name=parser.source_name, started_at=source_started, status="running")
                session.add(source_run)
                session.flush()
                run_id = source_run.id
            try:
                logger.info("checking source %s", parser.source_name)
                records = await parser.fetch(self.http_client)
                source_new, source_updated, source_duplicates = await self._process_records(records)
                summary.found += len(records)
                summary.new_active += source_new
                summary.updated += source_updated
                summary.duplicates += source_duplicates
                summary.source_statuses.append(
                    {"name": parser.source_name, "url": getattr(parser, "base_url", ""), "status": "success", "found": len(records)}
                )
                with session_scope(self.session_factory) as session:
                    source_run = session.get(SourceRun, run_id)
                    assert source_run is not None
                    source_run.finished_at = now_tz(self.settings.tz)
                    source_run.records_found = len(records)
                    source_run.new_records = source_new
                    source_run.updated_records = source_updated
                    source_run.duplicate_records = source_duplicates
                    source_run.status = "success"
            except Exception as exc:
                logger.exception("source failed: %s", parser.source_name)
                summary.failed_sources.append(f"{parser.source_name}: {exc}")
                summary.source_statuses.append(
                    {"name": parser.source_name, "url": getattr(parser, "base_url", ""), "status": "failed", "found": 0, "error": str(exc)}
                )
                with session_scope(self.session_factory) as session:
                    source_run = session.get(SourceRun, run_id)
                    assert source_run is not None
                    source_run.finished_at = now_tz(self.settings.tz)
                    source_run.status = "failed"
                    source_run.error_message = str(exc)

        summary.reminders = await self._send_deadline_reminders()
        if send_report:
            await self.telegram.send_text(
                format_daily_report(summary.stats(), summary.failed_sources, summary.source_links, summary.source_statuses),
                reply_markup=report_inline_keyboard(),
                parse_mode=None,
            )
        elapsed = (now_tz(self.settings.tz) - started).total_seconds()
        logger.info("monitoring finished in %.2fs", elapsed)
        return summary

    async def _process_records(self, records) -> tuple[int, int, int]:
        source_new = 0
        source_updated = 0
        source_duplicates = 0
        now = now_tz(self.settings.tz)
        for record in records:
            record = self.classifier.classify(record)
            if record.category == Category.NOT_RELEVANT or record.relevance_score < self.settings.relevance_threshold:
                continue
            if not self.deadlines.is_active_record(record.deadline, record.status, now):
                continue
            record = self.deduplicator.enrich(record)
            with session_scope(self.session_factory) as session:
                repo = TenderRepository(session)
                result = repo.upsert(record, now)
                if result.status == "new":
                    source_new += 1
                    await self._notify(repo, result.tender, "new", format_new_tender(result.tender, now), tender_inline_keyboard(result.tender))
                elif result.status == "updated":
                    source_updated += 1
                    await self._notify(
                        repo,
                        result.tender,
                        "updated",
                        format_update(result.tender, result.changed_fields),
                        tender_inline_keyboard(result.tender),
                    )
                else:
                    source_duplicates += 1
        return source_new, source_updated, source_duplicates

    async def _send_deadline_reminders(self) -> int:
        now = now_tz(self.settings.tz)
        sent = 0
        with session_scope(self.session_factory) as session:
            repo = TenderRepository(session)
            for tender in repo.active_tenders(now, self.settings.reminder_days):
                notification_type = f"deadline_{tender.deadline.date().isoformat()}" if tender.deadline else "deadline"
                if not self.deadlines.reminder_due(tender, now, self.settings.reminder_days):
                    continue
                if repo.was_notification_sent(tender.id, notification_type):
                    continue
                await self._notify(repo, tender, notification_type, format_reminder(tender, now), reminder_inline_keyboard(tender))
                sent += 1
        return sent

    async def _notify(
        self,
        repo: TenderRepository,
        tender,
        notification_type: str,
        text: str,
        reply_markup: dict[str, object] | None = None,
    ) -> None:
        if self.settings.dry_run:
            repo.mark_sent(tender, notification_type, self.settings.telegram_chat_id, "dry-run")
            logger.info("dry-run notification %s for tender %s", notification_type, tender.id)
            return
        try:
            await self.telegram.send_text(text, reply_markup=reply_markup)
            repo.mark_sent(tender, notification_type, self.settings.telegram_chat_id, "sent")
        except Exception as exc:
            repo.mark_sent(tender, notification_type, self.settings.telegram_chat_id, "failed", str(exc))
            logger.exception("telegram notification failed")
