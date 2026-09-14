"""Entities from canned API data at a frozen moment (15.09.2026 13:30 Tallinn, tomorrow not yet published)."""
from __future__ import annotations

import datetime as dt

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wattcast.const import CONF_BASE_URL, CONF_ZONE, DOMAIN

from .conftest import BASE, NOW, api_payloads, mock_api


async def _setup(hass: HomeAssistant, aioclient_mock, payloads=None) -> MockConfigEntry:
    mock_api(aioclient_mock, payloads=payloads)
    entry = MockConfigEntry(domain=DOMAIN, unique_id="EE@wattcast.eu", title="Wattcast EE",
                            data={CONF_ZONE: "EE", CONF_BASE_URL: BASE})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_prices_now(hass: HomeAssistant, aioclient_mock, frozen) -> None:
    await _setup(hass, aioclient_mock)
    # 10:30Z = hour index 13 since local midnight (21:00Z) -> 40 + 13*5 = 105 EUR/MWh; quarter 2 of that hour = +2
    hour = hass.states.get("sensor.wattcast_ee_price_hour")
    assert hour.state == "10.5" and hour.attributes["level"] == "high"        # 105 EUR/MWh between p50 80 and p75 130
    assert hour.attributes["next_hour_ct_kwh"] == 11.0 and hour.attributes["next_hour_known"] is True
    quarter = hass.states.get("sensor.wattcast_ee_price")
    assert quarter.state == "10.7" and quarter.attributes["resolution"] == "15min"
    assert hass.states.get("sensor.wattcast_ee_price_level").state == "high"
    assert hass.states.get("binary_sensor.wattcast_ee_cheap_now").state == "off"


async def test_day_averages_and_tomorrow_flag(hass: HomeAssistant, aioclient_mock, frozen) -> None:
    await _setup(hass, aioclient_mock)
    today = hass.states.get("sensor.wattcast_ee_today_average")
    assert today.attributes["basis"] == "settled" and today.attributes["settled_hours"] == 24
    assert float(today.state) == round(sum(4.0 + i * 0.5 for i in range(24)) / 24, 3)
    assert today.attributes["min_hour"] == 0 and today.attributes["max_hour"] == 23
    tomorrow = hass.states.get("sensor.wattcast_ee_tomorrow_average")
    assert tomorrow.attributes["basis"] == "forecast" and tomorrow.attributes["settled_hours"] == 0
    assert hass.states.get("binary_sensor.wattcast_ee_tomorrow_published").state == "off"


async def test_cheapest_windows_forecast_and_outlook(hass: HomeAssistant, aioclient_mock, frozen) -> None:
    await _setup(hass, aioclient_mock)
    w = hass.states.get("sensor.wattcast_ee_cheapest_2_h")
    assert w.state == "2026-09-15T23:00:00+00:00"        # tomorrow 02:00 local, from the forecast
    assert w.attributes["known"] is False and w.attributes["minutes"] == 120 and len(w.attributes["windows"]) == 2
    assert hass.states.get("sensor.wattcast_ee_cheapest_1_h").attributes["minutes"] == 60
    f = hass.states.get("sensor.wattcast_ee_forecast")
    assert f.state == (NOW - dt.timedelta(minutes=5)).isoformat()
    hours = f.attributes["hours"]
    assert len(hours) == 24 + 7 * 24 and hours[0] == ["2026-09-15T00:00:00+03:00", 40.0] and hours[24][1] == 62.0
    assert f.attributes["forecast"][0] == {"start": "2026-09-15T21:00:00Z", "k": 1, "p10": 3.2, "p50": 6.2, "p90": 10.2}
    assert f.attributes["known_until"] == "2026-09-15T20:45:00Z"
    o = hass.states.get("sensor.wattcast_ee_outlook")
    assert o.state == "Windy week, cheap nights" and o.attributes["markdown"] == "Prices fall from Wednesday."
    lvl = hass.states.get("sensor.wattcast_ee_price_level")
    assert lvl.attributes["p25_ct_kwh"] == 4.5 and lvl.attributes["p75_ct_kwh"] == 13.0


async def test_no_outlook_yet_and_unload(hass: HomeAssistant, aioclient_mock, frozen) -> None:
    aioclient_mock.get(f"{BASE}/v1/commentary", status=404)   # registered first: takes precedence for this URL
    p = api_payloads()
    entry = await _setup(hass, aioclient_mock, payloads=p)
    assert hass.states.get("sensor.wattcast_ee_outlook").state == "unknown"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.wattcast_ee_price").state == "unavailable"


async def test_api_down_marks_setup_retry(hass: HomeAssistant, aioclient_mock, frozen) -> None:
    aioclient_mock.get(f"{BASE}/v1/forecast", status=500)
    entry = MockConfigEntry(domain=DOMAIN, unique_id="EE@wattcast.eu", data={CONF_ZONE: "EE", CONF_BASE_URL: BASE})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state.name == "SETUP_RETRY"
