"""Config flow: happy path, connection error, duplicate zone, bad URL."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wattcast.const import CONF_API_KEY, CONF_BASE_URL, CONF_ZONE, DOMAIN

from .conftest import BASE, mock_api


async def test_user_flow_creates_entry(hass: HomeAssistant, aioclient_mock, frozen) -> None:
    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ZONE: "FI", CONF_BASE_URL: BASE + "/", CONF_API_KEY: " key1 "})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Wattcast FI"
    assert result["data"] == {CONF_ZONE: "FI", CONF_BASE_URL: BASE, CONF_API_KEY: "key1"}
    assert result["result"].unique_id == "FI@wattcast.eu"


async def test_user_flow_cannot_connect(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{BASE}/v1/status", status=503)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ZONE: "EE", CONF_BASE_URL: BASE})
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_not_wattcast_and_bad_url(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get("https://example.org/v1/status", json={"service": "other"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"],
                                                            {CONF_ZONE: "EE", CONF_BASE_URL: "https://example.org"})
    assert result["errors"] == {"base": "not_wattcast"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ZONE: "EE", CONF_BASE_URL: "wattcast"})
    assert result["errors"] == {"base_url": "invalid_url"}


async def test_duplicate_zone_aborts(hass: HomeAssistant, aioclient_mock) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id="EE@wattcast.eu", data={CONF_ZONE: "EE", CONF_BASE_URL: BASE}).add_to_hass(hass)
    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ZONE: "EE", CONF_BASE_URL: BASE})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"
