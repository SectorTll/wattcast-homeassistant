"""Binary sensors: cheap now (current hour below the 30-day p25), tomorrow's prices published."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WattcastConfigEntry
from .sensor import WattcastEntity


async def async_setup_entry(hass: HomeAssistant, entry: WattcastConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    c = entry.runtime_data
    async_add_entities([CheapNowSensor(c, entry), TomorrowPublishedSensor(c, entry)])


class CheapNowSensor(WattcastEntity, BinarySensorEntity):
    _attr_icon = "mdi:cash-check"

    def __init__(self, c, e):
        super().__init__(c, e, "cheap_now")

    @property
    def is_on(self) -> bool | None:
        s = self.coordinator.current_hour()
        level = self.coordinator.level_of(s["ctKwh"] if s else None)
        return None if level is None else level == "cheap"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self.coordinator.current_hour()
        th = self.coordinator.thresholds() or {}
        return {"price_ct_kwh": s["ctKwh"] if s else None, "threshold_ct_kwh": th.get("p25")}


class TomorrowPublishedSensor(WattcastEntity, BinarySensorEntity):
    _attr_icon = "mdi:calendar-check"

    def __init__(self, c, e):
        super().__init__(c, e, "tomorrow_published")

    @property
    def is_on(self) -> bool:
        d = self.coordinator.day_stats(1)
        return bool(d and d["basis"] == "settled")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.day_stats(1) or {}
        return {"settled_hours": d.get("settled_hours"), "known_until": self.coordinator.data.hourly.get("lastKnownIso")}
