from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MedTender AI Agent"
    environment: Literal["dev", "prod", "test"] = "dev"
    tz: str = Field(default="Asia/Tashkent", alias="TZ")
    database_url: str = "sqlite:///./data/medtender.sqlite3"
    sources_config_path: str = "config/sources.yaml"
    monitoring_pause_file: str = "data/paused"
    log_level: str = "INFO"

    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")
    telegram_admin_ids: str | None = Field(default=None, alias="TELEGRAM_ADMIN_IDS")
    telegram_thread_id: int | None = Field(default=None, alias="TELEGRAM_THREAD_ID")
    telegram_parse_mode: str = "MarkdownV2"

    request_timeout_seconds: float = 25.0
    request_retries: int = 3
    request_backoff_seconds: float = 1.5
    max_download_bytes: int = 10 * 1024 * 1024
    relevance_threshold: int = 70
    reminder_days: int = 3
    dry_run: bool = False

    @field_validator("database_url")
    @classmethod
    def ensure_sqlite_parent(cls, value: str) -> str:
        if value.startswith("sqlite:///"):
            path = Path(value.removeprefix("sqlite:///"))
            if path.parent != Path("."):
                path.parent.mkdir(parents=True, exist_ok=True)
        return value

    @field_validator("telegram_thread_id", mode="before")
    @classmethod
    def blank_thread_id_as_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @property
    def admin_chat_ids(self) -> set[str]:
        values = {self.telegram_chat_id} if self.telegram_chat_id else set()
        if self.telegram_admin_ids:
            values.update(part.strip() for part in self.telegram_admin_ids.split(",") if part.strip())
        return values


@lru_cache
def get_settings() -> Settings:
    return Settings()
