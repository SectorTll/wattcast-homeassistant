"""Integration setup loads the bidding zone's time zone asynchronously."""
from __future__ import annotations

import asyncio
from os import stat
from unittest.mock import patch
from zoneinfo import ZoneInfo

from aiozoneinfo import CachedZoneInfo
import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wattcast.const import CONF_BASE_URL, CONF_ZONE, DOMAIN, ZONE_TZ

from .conftest import BASE, mock_api


@pytest.mark.parametrize("zone", ZONE_TZ)
async def test_setup_time_zone(hass: HomeAssistant, aioclient_mock, frozen, zone: str) -> None:
    """An uncached bidding zone loads outside the loop and keeps local day boundaries."""
    await hass.config.async_set_time_zone("America/New_York")
    mock_api(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=f"{zone}@wattcast.eu", title=f"Wattcast {zone}",
        data={CONF_ZONE: zone, CONF_BASE_URL: BASE},
    )
    entry.add_to_hass(hass)
    ZoneInfo.clear_cache(only_keys=[ZONE_TZ[zone]])
    CachedZoneInfo.clear_cache(only_keys=[ZONE_TZ[zone]])

    checked_zone_files = []

    def check_file_stat(path, *args, **kwargs):
        if str(path).endswith(f"/{ZONE_TZ[zone]}"):
            with pytest.raises(RuntimeError, match="no running event loop"):
                asyncio.get_running_loop()
            checked_zone_files.append(path)
        return stat(path, *args, **kwargs)

    with patch("os.stat", side_effect=check_file_stat):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert checked_zone_files

    assert entry.runtime_data.tz.key == ZONE_TZ[zone]
    start, end = entry.runtime_data.local_day_bounds(0)
    assert start == 1789419600  # 2026-09-15 00:00 in each supported bidding zone
    assert end - start == 24 * 3600
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_unavailable_time_zone_retries_setup(hass: HomeAssistant, aioclient_mock) -> None:
    """A missing time zone must not silently switch price calculations to local time."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="EE@wattcast.eu",
        data={CONF_ZONE: "EE", CONF_BASE_URL: BASE},
    )
    entry.add_to_hass(hass)

    with patch("custom_components.wattcast.dt_util.async_get_time_zone", return_value=None):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state.name == "SETUP_RETRY"
    assert aioclient_mock.call_count == 0
