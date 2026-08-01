from __future__ import annotations

import argparse
import asyncio
import logging

from app.config import get_settings
from app.parsers import build_parsers
from app.repositories.database import init_db, session_scope
from app.repositories.tenders import TenderRepository
from app.services.monitor import MonitorService
from app.services.telegram import TelegramClient, format_new_tender
from app.utils.dates import now_tz
from app.utils.http import HttpClient
from app.utils.logging import configure_logging


logger = logging.getLogger(__name__)


async def cmd_run(args) -> None:
    settings = get_settings()
    session_factory = init_db(settings)
    service = MonitorService(settings, session_factory)
    summary = await service.run_once(send_report=not args.no_report)
    print(summary)


async def cmd_test_sources(args) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    client = HttpClient(settings.request_timeout_seconds, settings.request_retries, settings.request_backoff_seconds)
    for parser in build_parsers():
        try:
            records = await parser.fetch(client)
            print(f"{parser.source_name}: success, {len(records)} records")
        except Exception as exc:
            print(f"{parser.source_name}: failed, {exc}")


async def cmd_test_telegram(args) -> None:
    settings = get_settings()
    client = TelegramClient(
        settings,
        HttpClient(settings.request_timeout_seconds, settings.request_retries, settings.request_backoff_seconds),
    )
    await client.send_test()
    print("Telegram test completed")


async def cmd_resend(args) -> None:
    settings = get_settings()
    session_factory = init_db(settings)
    client = TelegramClient(
        settings,
        HttpClient(settings.request_timeout_seconds, settings.request_retries, settings.request_backoff_seconds),
    )
    now = now_tz(settings.tz)
    with session_scope(session_factory) as session:
        repo = TenderRepository(session)
        from app.models.db import Tender

        tender = session.get(Tender, args.tender_id)
        if tender is None:
            raise SystemExit(f"Tender not found: {args.tender_id}")
        await client.send_text(format_new_tender(tender, now))
        repo.mark_sent(tender, "resend", settings.telegram_chat_id, "sent")
    print(f"Resent tender {args.tender_id}")


def cmd_report(args) -> None:
    settings = get_settings()
    session_factory = init_db(settings)
    with session_scope(session_factory) as session:
        repo = TenderRepository(session)
        for run in repo.latest_runs(limit=args.limit):
            print(
                f"{run.started_at} {run.source_name}: {run.status}, found={run.records_found}, "
                f"new={run.new_records}, updated={run.updated_records}, dup={run.duplicate_records}, error={run.error_message or '-'}"
            )


def cmd_cleanup(args) -> None:
    settings = get_settings()
    init_db(settings)
    print("Cleanup hook ready. SQLite VACUUM/old notification pruning can be added by retention policy.")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.main")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--no-report", action="store_true")
    sub.add_parser("test-sources")
    sub.add_parser("test-telegram")
    resend = sub.add_parser("resend")
    resend.add_argument("--tender-id", type=int, required=True)
    report = sub.add_parser("report")
    report.add_argument("--limit", type=int, default=20)
    sub.add_parser("cleanup")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    if args.command == "run":
        asyncio.run(cmd_run(args))
    elif args.command == "test-sources":
        asyncio.run(cmd_test_sources(args))
    elif args.command == "test-telegram":
        asyncio.run(cmd_test_telegram(args))
    elif args.command == "resend":
        asyncio.run(cmd_resend(args))
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "cleanup":
        cmd_cleanup(args)


if __name__ == "__main__":
    main()
