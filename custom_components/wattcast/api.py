"""Minimal async client for the Wattcast JSON API (https://wattcast.eu/api)."""
from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import REQUEST_TIMEOUT


class WattcastError(Exception):
    """The API could not be reached or answered with an error."""


class WattcastClient:
    def __init__(self, session: ClientSession, base_url: str, api_key: str | None = None) -> None:
        self._session = session
        self.base_url = base_url.rstrip("/")
        self._headers = {"X-API-Key": api_key} if api_key else {}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(f"{self.base_url}{path}", params=params, headers=self._headers) as r:
                    if r.status != 200:
                        raise WattcastError(f"{path}: HTTP {r.status}")
                    return await r.json()
        except (TimeoutError, ClientError) as err:
            raise WattcastError(f"{path}: {err}") from err

    async def status(self) -> dict:
        return await self._get("/v1/status")

    async def forecast(self, zone: str, resolution: str = "hour", hours: int = 192) -> dict:
        return await self._get("/v1/forecast", {"zone": zone, "resolution": resolution, "hours": hours})

    async def cheapest(self, zone: str, minutes: int, scope: str = "next24h", count: int = 3) -> dict:
        return await self._get("/v1/cheapest", {"zone": zone, "minutes": minutes, "count": count, "scope": scope})

    async def levels(self, zone: str, days: int = 30) -> dict:
        return await self._get("/v1/levels", {"zone": zone, "days": days})

    async def commentary(self, zone: str, lang: str = "en") -> dict | None:
        try:
            return await self._get("/v1/commentary", {"zone": zone, "lang": lang})
        except WattcastError as err:
            if "HTTP 404" in str(err):   # no outlook published for the zone yet
                return None
            raise
