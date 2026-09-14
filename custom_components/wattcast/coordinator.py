"""Polls the Wattcast API and derives the values the entities show."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import WattcastClient, WattcastError
from .const import DOMAIN, LEVEL_DAYS, LEVELS, SLOW_INTERVAL, UPDATE_INTERVAL, WINDOW_SCOPE, WINDOWS, ZONE_TZ

_LOGGER = logging.getLogger(__name__)


@dataclass
class WattcastData:
    hourly: dict                       # /v1/forecast resolution=hour: known + forecast
    quarter: dict                      # /v1/forecast resolution=15min (2 days)
    cheapest: dict[str, dict]          # key from WINDOWS -> /v1/cheapest response
    levels: dict | None = None         # /v1/levels (30 d quartiles)
    commentary: dict | None = None     # /v1/commentary
    slow_fetched: float = 0.0          # epoch of the last levels/commentary fetch
    fetched: float = field(default_factory=time.time)


class WattcastCoordinator(DataUpdateCoordinator[WattcastData]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: WattcastClient, zone: str) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} {zone}", update_interval=UPDATE_INTERVAL)
        self.client = client
        self.zone = zone
        self.tz = ZoneInfo(ZONE_TZ.get(zone, "UTC"))

    async def _async_update_data(self) -> WattcastData:
        z = self.zone
        prev = self.data
        try:
            hourly = await self.client.forecast(z, "hour", 192)
            quarter = await self.client.forecast(z, "15min", 48)
            cheapest = {key: await self.client.cheapest(z, minutes, WINDOW_SCOPE) for key, minutes in WINDOWS.items()}
            levels, commentary, slow_at = (prev.levels, prev.commentary, prev.slow_fetched) if prev else (None, None, 0.0)
            if time.time() - slow_at >= SLOW_INTERVAL.total_seconds():
                levels = await self.client.levels(z, LEVEL_DAYS)
                lang = (self.hass.config.language or "en").split("-")[0]
                commentary = await self.client.commentary(z, lang)
                slow_at = time.time()
        except WattcastError as err:
            raise UpdateFailed(str(err)) from err
        return WattcastData(hourly=hourly, quarter=quarter, cheapest=cheapest, levels=levels,
                            commentary=commentary, slow_fetched=slow_at)

    # ---------- derived values (all times UTC epoch seconds, prices ct/kWh unless stated) ----------
    @staticmethod
    def _slot(items: list[dict], ts: int, length: int) -> dict | None:
        for it in items:
            if it["ts"] <= ts < it["ts"] + length:
                return it
        return None

    def now_ts(self) -> int:
        return int(dt_util.utcnow().timestamp())

    def current_quarter(self) -> dict | None:
        return self._slot(self.data.quarter.get("known", []), self.now_ts(), 900)

    def current_hour(self) -> dict | None:
        return self._slot(self.data.hourly.get("known", []), self.now_ts(), 3600)

    def hour_at(self, offset_hours: int) -> dict | None:
        """Settled hour if published, else the forecast p50 for that hour (flagged)."""
        ts = self.now_ts() + offset_hours * 3600
        s = self._slot(self.data.hourly.get("known", []), ts, 3600)
        if s:
            return {"ct_kwh": s["ctKwh"], "starts_at": s["startsAt"], "known": True}
        f = self._slot(self.data.hourly.get("forecast", []), ts, 3600)
        if f:
            return {"ct_kwh": f["p50CtKwh"], "starts_at": f["startsAt"], "known": False}
        return None

    def local_day_bounds(self, day_offset: int) -> tuple[int, int]:
        day = datetime.now(self.tz).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)
        return int(day.timestamp()), int((day + timedelta(days=1)).timestamp())

    def day_stats(self, day_offset: int) -> dict | None:
        """avg / min / max of a local day: settled hours if (nearly) the whole day is published, else settled +
        forecast p50 (basis says which)."""
        t0, t1 = self.local_day_bounds(day_offset)
        known = [x for x in self.data.hourly.get("known", []) if t0 <= x["ts"] < t1]
        fc = [x for x in self.data.hourly.get("forecast", []) if t0 <= x["ts"] < t1]
        rows = [(x["ts"], x["ctKwh"]) for x in known]
        basis = "settled"
        if len(known) < 20:
            rows += [(x["ts"], x["p50CtKwh"]) for x in fc]
            basis = "forecast" if fc else "settled"
        if not rows:
            return None
        prices = [p for _, p in rows]
        lo, hi = min(rows, key=lambda r: r[1]), max(rows, key=lambda r: r[1])
        return {"avg": round(sum(prices) / len(prices), 3), "min": lo[1], "max": hi[1],
                "min_hour": datetime.fromtimestamp(lo[0], self.tz).hour, "max_hour": datetime.fromtimestamp(hi[0], self.tz).hour,
                "basis": basis, "hours": len(rows), "settled_hours": len(known)}

    def thresholds(self) -> dict | None:
        """30-day quartiles in ct/kWh."""
        lv = self.data.levels
        if not lv or "quantiles" not in lv:
            return None
        q = lv["quantiles"]
        return {"p25": round(q["p25"] / 10, 3), "p50": round(q["p50"] / 10, 3), "p75": round(q["p75"] / 10, 3),
                "mean": round(lv.get("mean", 0) / 10, 3), "days": lv.get("days"), "from": lv.get("from"), "to": lv.get("to")}

    def level_of(self, ct_kwh: float | None) -> str | None:
        th = self.thresholds()
        if th is None or ct_kwh is None:
            return None
        if ct_kwh < th["p25"]:
            return LEVELS[0]
        if ct_kwh < th["p50"]:
            return LEVELS[1]
        if ct_kwh < th["p75"]:
            return LEVELS[2]
        return LEVELS[3]

    def raw_series(self, step: int, day_offset: int, compact: bool = False) -> tuple[list[dict], bool]:
        """One local day at the given resolution, Nord Pool `raw_today` shape: [{start, end, value}] in ct/kWh
        (end omitted when compact). Settled price where published, else the forecast p50. Returns (rows, all_known)."""
        src = self.data.hourly if step == 3600 else self.data.quarter
        t0, t1 = self.local_day_bounds(day_offset)
        pts: dict[int, tuple[float, bool]] = {}
        for x in src.get("known", []):
            if t0 <= x["ts"] < t1:
                pts[x["ts"]] = (x["ctKwh"], True)
        for x in src.get("forecast", []):
            if t0 <= x["ts"] < t1 and x["ts"] not in pts:
                pts[x["ts"]] = (x["p50CtKwh"], False)
        rows, all_known = [], True
        for ts in sorted(pts):
            val, known = pts[ts]
            all_known = all_known and known
            e = {"start": datetime.fromtimestamp(ts, self.tz).isoformat(), "value": val}
            if not compact:
                e["end"] = datetime.fromtimestamp(ts + step, self.tz).isoformat()
            rows.append(e)
        return rows, all_known

    def day_prices(self, step: int, day_offset: int) -> list[float]:
        """Plain price list for a local day (Nord Pool `today` / `tomorrow` shape)."""
        return [r["value"] for r in self.raw_series(step, day_offset, compact=True)[0]]

