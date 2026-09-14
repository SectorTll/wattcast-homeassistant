"""Shared fixtures: auto-enable custom integrations, a deterministic clock and canned API responses."""
from __future__ import annotations

import datetime as dt

import pytest

NOW = dt.datetime(2026, 9, 15, 10, 30, tzinfo=dt.timezone.utc)   # 13:30 Tallinn, tomorrow (16.09) not published yet
BASE = "https://wattcast.eu"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def frozen(freezer):
    freezer.move_to(NOW)
    return NOW


def _ts(t: dt.datetime) -> int:
    return int(t.timestamp())


def _iso(t: dt.datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def api_payloads(now: dt.datetime = NOW) -> dict[str, dict]:
    """Settled prices from local midnight (14.09 21:00Z) to end of 15.09 local (15.09 21:00Z); forecast after that."""
    day0 = dt.datetime(2026, 9, 14, 21, 0, tzinfo=dt.timezone.utc)
    last_known = dt.datetime(2026, 9, 15, 20, 45, tzinfo=dt.timezone.utc)
    known_h, known_q, fc_h, fc_q = [], [], [], []
    for i in range(24):
        t = day0 + dt.timedelta(hours=i)
        price = 40.0 + i * 5.0          # 4.0 .. 15.5 ct: hour 13 UTC (index 16) = 120 EUR/MWh
        known_h.append({"ts": _ts(t), "startsAt": _iso(t), "eurMwh": price, "ctKwh": round(price / 10, 3)})
        for q in range(4):
            tq = t + dt.timedelta(minutes=15 * q)
            pq = price + (q - 1.5) * 4
            known_q.append({"ts": _ts(tq), "startsAt": _iso(tq), "eurMwh": pq, "ctKwh": round(pq / 10, 3)})
    for i in range(1, 7 * 24 + 1):
        t = last_known + dt.timedelta(minutes=15) + dt.timedelta(hours=i - 1)
        k = 1 + (i - 1) // 24
        p50 = 60.0 + (i % 24) * 2
        fc_h.append({"ts": _ts(t), "startsAt": _iso(t), "k": k, "p10": p50 - 30, "p50": p50, "p90": p50 + 40,
                     "p50CtKwh": round(p50 / 10, 3)})
    for i in range(1, 2 * 96 + 1):
        t = last_known + dt.timedelta(minutes=15 * i)
        p50 = 60.0 + ((i // 4) % 24) * 2
        fc_q.append({"ts": _ts(t), "startsAt": _iso(t), "k": 1 + (i - 1) // 96, "p10": p50 - 30, "p50": p50, "p90": p50 + 40,
                     "p50CtKwh": round(p50 / 10, 3)})
    made = _ts(now - dt.timedelta(minutes=5))
    fc_common = {"zone": "EE", "currency": "EUR", "unit": "EUR/MWh", "now": _ts(now), "madeAt": made,
                 "madeAtIso": _iso(now - dt.timedelta(minutes=5)), "lastKnownTs": _ts(last_known),
                 "lastKnownIso": _iso(last_known), "adjustments": None, "modelTrainedAt": "2026-09-14T11:41:17+00:00",
                 "backtestMae": {"1": 27.2, "2": 27.9}, "attribution": "test"}
    w0 = day0 + dt.timedelta(hours=26)   # tomorrow 02:00 local, inside the forecast
    cheap = {"zone": "EE", "scope": "next24h", "minutes": 120, "windows": [
        {"startsAt": _iso(w0), "endsAt": _iso(w0 + dt.timedelta(hours=2)), "ts": _ts(w0), "avgEurMwh": 62.0,
         "avgCtKwh": 6.2, "known": False},
        {"startsAt": _iso(day0 + dt.timedelta(hours=14)), "endsAt": _iso(day0 + dt.timedelta(hours=16)),
         "ts": _ts(day0 + dt.timedelta(hours=14)), "avgEurMwh": 112.5, "avgCtKwh": 11.25, "known": True}],
        "attribution": "test"}
    return {
        "hour": {**fc_common, "resolution": "hour", "known": known_h, "forecast": fc_h},
        "15min": {**fc_common, "resolution": "15min", "known": known_q, "forecast": fc_q},
        "cheapest": cheap,
        "levels": {"zone": "EE", "days": 30, "unit": "EUR/MWh", "n": 720, "from": "2026-08-16T00:00:00Z",
                   "to": "2026-09-15T09:00:00Z", "mean": 80.0, "quantiles": {"p25": 45.0, "p50": 80.0, "p75": 130.0},
                   "attribution": "test"},
        "commentary": {"zone": "EE", "lang": "en", "requestedLang": "en", "languages": ["et", "en"],
                       "generatedAt": "2026-09-15T08:00:00Z", "validUntil": "2026-09-16T08:00:00Z",
                       "model": "test", "title": "Windy week, cheap nights", "markdown": "Prices fall from Wednesday.",
                       "fileUpdatedAt": "2026-09-15T08:00:29Z", "attribution": "test"},
        "status": {"service": "wattcast", "version": "0.1.0", "zones": {}},
    }


def mock_api(aioclient_mock, base: str = BASE, payloads: dict | None = None) -> None:
    p = payloads or api_payloads()
    aioclient_mock.get(f"{base}/v1/status", json=p["status"])
    aioclient_mock.get(f"{base}/v1/forecast", side_effect=lambda method, url, data: _forecast_response(method, url, data, p))
    aioclient_mock.get(f"{base}/v1/cheapest", json=p["cheapest"])
    aioclient_mock.get(f"{base}/v1/levels", json=p["levels"])
    aioclient_mock.get(f"{base}/v1/commentary", json=p["commentary"])


async def _forecast_response(method, url, data, p):
    from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse

    res = str(url.query.get("resolution", "hour"))
    return AiohttpClientMockResponse("GET", url, json=p["15min" if res == "15min" else "hour"])
