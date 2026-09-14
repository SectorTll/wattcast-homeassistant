"""Wattcast: Nord Pool day-ahead prices and a 7-day forecast for EE / FI / LV / LT in Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WattcastClient
from .const import CONF_API_KEY, CONF_BASE_URL, CONF_ZONE, DEFAULT_BASE_URL
from .coordinator import WattcastCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type WattcastConfigEntry = ConfigEntry[WattcastCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: WattcastConfigEntry) -> bool:
    client = WattcastClient(async_get_clientsession(hass), entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
                            entry.data.get(CONF_API_KEY) or None)
    coordinator = WattcastCoordinator(hass, entry, client, entry.data[CONF_ZONE])
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WattcastConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
