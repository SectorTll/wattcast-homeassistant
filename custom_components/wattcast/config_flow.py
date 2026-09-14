"""Config flow: pick a bidding zone, optionally another API base URL and an API key."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (SelectSelector, SelectSelectorConfig, SelectSelectorMode, TextSelector,
                                            TextSelectorConfig, TextSelectorType)

from .api import WattcastClient, WattcastError
from .const import CONF_API_KEY, CONF_BASE_URL, CONF_ZONE, DEFAULT_BASE_URL, DOMAIN, ZONES

SCHEMA = vol.Schema({
    vol.Required(CONF_ZONE, default="EE"): SelectSelector(
        SelectSelectorConfig(options=ZONES, mode=SelectSelectorMode.DROPDOWN, translation_key="zone")),
    vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
    vol.Optional(CONF_API_KEY): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
})


class WattcastConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            base = user_input[CONF_BASE_URL].strip().rstrip("/")
            zone = user_input[CONF_ZONE]
            parsed = urlparse(base)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                errors["base_url"] = "invalid_url"
            else:
                await self.async_set_unique_id(f"{zone}@{parsed.netloc.lower()}")
                self._abort_if_unique_id_configured()
                client = WattcastClient(async_get_clientsession(self.hass), base, user_input.get(CONF_API_KEY) or None)
                try:
                    status = await client.status()
                    if status.get("service") != "wattcast":
                        errors["base"] = "not_wattcast"
                except WattcastError:
                    errors["base"] = "cannot_connect"
            if not errors:
                data = {CONF_ZONE: zone, CONF_BASE_URL: base}
                if user_input.get(CONF_API_KEY):
                    data[CONF_API_KEY] = user_input[CONF_API_KEY].strip()
                return self.async_create_entry(title=f"Wattcast {zone}", data=data)
        return self.async_show_form(step_id="user", data_schema=self.add_suggested_values_to_schema(SCHEMA, user_input),
                                    errors=errors)
