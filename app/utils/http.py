from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Mapping

import httpx

logger = logging.getLogger(__name__)


def safe_url(url: str) -> str:
    return re.sub(r"(api\.telegram\.org/bot)[^/]+", r"\1<redacted>", url)


class HttpClient:
    def __init__(self, timeout: float, retries: int, backoff: float, user_agent: str = "MedTenderAI/1.0") -> None:
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.headers = {"User-Agent": user_agent, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}

    async def get_text(self, url: str, params: Mapping[str, str] | None = None) -> str:
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.headers) as client:
            for attempt in range(1, self.retries + 1):
                try:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    return response.text
                except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    logger.warning("HTTP GET failed", extra={"url": safe_url(url), "attempt": attempt, "error": str(exc)})
                    if attempt < self.retries:
                        await asyncio.sleep(self.backoff * attempt)
        raise RuntimeError(f"GET failed for {safe_url(url)}: {last_error}")

    async def post_json(self, url: str, data: Mapping[str, object]) -> object:
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for attempt in range(1, self.retries + 1):
                try:
                    response = await client.post(url, json=data)
                    response.raise_for_status()
                    return response.json()
                except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    error = _safe_error(exc)
                    logger.warning("HTTP POST failed", extra={"url": safe_url(url), "attempt": attempt, "error": error})
                    if attempt < self.retries:
                        await asyncio.sleep(self.backoff * attempt)
        raise RuntimeError(f"POST failed for {safe_url(url)}: {_safe_error(last_error)}")


def _safe_error(error: Exception | None) -> str:
    if error is None:
        return "unknown error"
    text = str(error)
    return safe_url(text)
