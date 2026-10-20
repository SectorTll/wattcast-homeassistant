"""Wattcast: Nord Pool day-ahead prices and a 7-day forecast for EE / FI / LV / LT in Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import WattcastClient
from .const import CONF_API_KEY, CONF_BASE_URL, CONF_ZONE, DEFAULT_BASE_URL, ZONE_TZ
from .coordinator import WattcastCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type WattcastConfigEntry = ConfigEntry[WattcastCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: WattcastConfigEntry) -> bool:
    zone = entry.data[CONF_ZONE]
    time_zone = await dt_util.async_get_time_zone(ZONE_TZ[zone])
    if time_zone is None:
        raise ConfigEntryNotReady(f"Unable to load time zone {ZONE_TZ[zone]}")

    client = WattcastClient(async_get_clientsession(hass), entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
                            entry.data.get(CONF_API_KEY) or None)
    coordinator = WattcastCoordinator(hass, entry, client, zone, time_zone)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WattcastConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
