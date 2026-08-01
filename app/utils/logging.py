from __future__ import annotations

import logging
import sys


class SecretFilter(logging.Filter):
    secret_words = ("token", "password", "cookie", "authorization", "secret")

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        if "api.telegram.org/bot" in message:
            return False
        return not any(word in message for word in self.secret_words)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(SecretFilter())
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=[handler], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
