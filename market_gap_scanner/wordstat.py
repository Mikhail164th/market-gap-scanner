"""Yandex Wordstat API client via Direct API v4.

Implements the full Wordstat report lifecycle:
  1. CreateNewWordstatReport -- submit phrases for analysis
  2. GetWordstatReportList  -- poll until report is ready
  3. GetWordstatReport      -- retrieve keyword volumes
  4. DeleteWordstatReport   -- cleanup

Inspired by https://github.com/ne-coding/Yandex.Wordstat-parser (MIT License).
Modernized: httpx, async support, typed results, error handling.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://api.direct.yandex.com/json/v4/"
SANDBOX_URL = "https://api-sandbox.direct.yandex.ru/v4/json/"

POLL_INTERVAL = 3.0
POLL_TIMEOUT = 120.0
MAX_PHRASES_PER_REPORT = 10


@dataclass
class KeywordStat:
    """Single keyword with its search volume."""
    phrase: str
    shows: int


@dataclass
class WordstatResult:
    """Result for one queried phrase: related + associated keywords."""
    query: str
    related: list[KeywordStat]
    associated: list[KeywordStat]


class WordstatError(Exception):
    """Raised when Yandex Direct API returns an error."""
    def __init__(self, code: int, message: str, detail: str = ""):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(f"Wordstat API error {code}: {message}")


class WordstatClient:
    """Async client for Yandex Wordstat via Direct API v4."""

    def __init__(self, token: str, *, sandbox: bool = False, timeout: float = 30.0):
        self._token = token
        self._url = SANDBOX_URL if sandbox else API_URL
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def _call(self, method: str, param: Any = None) -> Any:
        payload: dict[str, Any] = {"method": method, "token": self._token}
        if param is not None:
            payload["param"] = param
        resp = await self._client.post(self._url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error_code" in data:
            raise WordstatError(data["error_code"], data.get("error_str", ""), data.get("error_detail", ""))
        return data.get("data")

    async def get_keyword_stats(self, phrases: list[str], geo: list[int] | None = None) -> list[WordstatResult]:
        results: list[WordstatResult] = []
        for i in range(0, len(phrases), MAX_PHRASES_PER_REPORT):
            batch = phrases[i : i + MAX_PHRASES_PER_REPORT]
            results.extend(await self._process_batch(batch, geo or []))
            if i + MAX_PHRASES_PER_REPORT < len(phrases):
                await asyncio.sleep(1.0)
        return results

    async def _process_batch(self, phrases: list[str], geo: list[int]) -> list[WordstatResult]:
        report_id = await self._call("CreateNewWordstatReport", {"Phrases": phrases, "GeoID": geo})
        logger.info("Created report %s for %d phrases", report_id, len(phrases))
        try:
            await self._wait_for_report(report_id)
            data = await self._call("GetWordstatReport", report_id)
            return self._parse_report(data)
        finally:
            try:
                await self._call("DeleteWordstatReport", report_id)
            except Exception as e:
                logger.warning("Failed to delete report %s: %s", report_id, e)

    async def _wait_for_report(self, report_id: int) -> None:
        elapsed = 0.0
        while elapsed < POLL_TIMEOUT:
            reports = await self._call("GetWordstatReportList")
            for r in reports:
                if r["ReportID"] == report_id and r["StatusReport"] == "Done":
                    return
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
        raise TimeoutError(f"Report {report_id} not ready after {POLL_TIMEOUT}s")

    @staticmethod
    def _parse_report(data: list[dict]) -> list[WordstatResult]:
        results = []
        for item in data:
            related = [KeywordStat(kw["Phrase"], kw["Shows"]) for kw in item.get("SearchedWith", [])]
            associated = [KeywordStat(kw["Phrase"], kw["Shows"]) for kw in item.get("SearchedAlso", [])]
            query = related[0].phrase if related else "unknown"
            results.append(WordstatResult(query=query, related=related, associated=associated))
        return results
