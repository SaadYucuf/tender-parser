from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping

import httpx

logger = logging.getLogger(__name__)


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
                    logger.warning("HTTP GET failed", extra={"url": url, "attempt": attempt, "error": str(exc)})
                    if attempt < self.retries:
                        await asyncio.sleep(self.backoff * attempt)
        raise RuntimeError(f"GET failed for {url}: {last_error}")

    async def post_json(self, url: str, data: Mapping[str, object]) -> dict[str, object]:
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for attempt in range(1, self.retries + 1):
                try:
                    response = await client.post(url, json=data)
                    response.raise_for_status()
                    return response.json()
                except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    logger.warning("HTTP POST failed", extra={"url": url, "attempt": attempt, "error": str(exc)})
                    if attempt < self.retries:
                        await asyncio.sleep(self.backoff * attempt)
        raise RuntimeError(f"POST failed for {url}: {last_error}")
