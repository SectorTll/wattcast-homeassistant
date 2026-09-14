"""Sensors: current prices, day averages, cheapest windows, price level, forecast series, written outlook."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WattcastConfigEntry
from .const import ATTRIBUTION, DOMAIN, LEVELS, MANUFACTURER, WINDOWS
from .coordinator import WattcastCoordinator

CT_KWH = "ct/kWh"


async def async_setup_entry(hass: HomeAssistant, entry: WattcastConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    c = entry.runtime_data
    entities: list[SensorEntity] = [
        PriceSensor(c, entry), PriceHourSensor(c, entry),
        DayAverageSensor(c, entry, "today_average", 0), DayAverageSensor(c, entry, "tomorrow_average", 1),
        PriceLevelSensor(c, entry), ForecastSensor(c, entry), OutlookSensor(c, entry),
    ]
    entities += [CheapestWindowSensor(c, entry, key) for key in WINDOWS]
    async_add_entities(entities)


class WattcastEntity(CoordinatorEntity[WattcastCoordinator]):
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: WattcastCoordinator, entry: WattcastConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=f"Wattcast {coordinator.zone}",
                                            manufacturer=MANUFACTURER, model="Electricity price forecast",
                                            configuration_url=f"{coordinator.client.base_url}/{coordinator.zone.lower()}")

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


class PriceSensor(WattcastEntity, SensorEntity):
    """Current 15-minute exchange price."""
    _attr_native_unit_of_measurement = CT_KWH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:flash"

    def __init__(self, c, e):
        super().__init__(c, e, "price")

    @property
    def native_value(self) -> float | None:
        s = self.coordinator.current_quarter()
        return s["ctKwh"] if s else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self.coordinator.current_quarter()
        return {"eur_mwh": s["eurMwh"] if s else None, "slot_start": s["startsAt"] if s else None, "resolution": "15min",
                "level": self.coordinator.level_of(s["ctKwh"] if s else None)}


class PriceHourSensor(WattcastEntity, SensorEntity):
    """Current hour (mean of its four quarters), next hour as attribute."""
    _attr_native_unit_of_measurement = CT_KWH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:flash-outline"

    def __init__(self, c, e):
        super().__init__(c, e, "price_hour")

    @property
    def native_value(self) -> float | None:
        s = self.coordinator.current_hour()
        return s["ctKwh"] if s else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self.coordinator.current_hour()
        nxt = self.coordinator.hour_at(1)
        return {"eur_mwh": s["eurMwh"] if s else None, "hour_start": s["startsAt"] if s else None,
                "next_hour_ct_kwh": nxt["ct_kwh"] if nxt else None, "next_hour_known": nxt["known"] if nxt else None,
                "level": self.coordinator.level_of(s["ctKwh"] if s else None)}


class DayAverageSensor(WattcastEntity, SensorEntity):
    _attr_native_unit_of_measurement = CT_KWH
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:calendar-today"

    def __init__(self, c, e, key: str, offset: int):
        super().__init__(c, e, key)
        self._offset = offset
        if offset:
            self._attr_icon = "mdi:calendar-arrow-right"

    @property
    def native_value(self) -> float | None:
        d = self.coordinator.day_stats(self._offset)
        return d["avg"] if d else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.day_stats(self._offset) or {}
        return {"basis": d.get("basis"), "min_ct_kwh": d.get("min"), "min_hour": d.get("min_hour"),
                "max_ct_kwh": d.get("max"), "max_hour": d.get("max_hour"), "settled_hours": d.get("settled_hours")}


class CheapestWindowSensor(WattcastEntity, SensorEntity):
    """Start of the cheapest window of the given length within the next 24 h (settled prices, then forecast)."""
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, c, e, key: str):
        super().__init__(c, e, key)
        self._key = key

    def _windows(self) -> list[dict]:
        return (self.coordinator.data.cheapest.get(self._key) or {}).get("windows", [])

    @property
    def native_value(self) -> datetime | None:
        w = self._windows()
        return datetime.fromtimestamp(w[0]["ts"], timezone.utc) if w else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        w = self._windows()
        first = w[0] if w else {}
        return {"minutes": WINDOWS[self._key], "ends_at": first.get("endsAt"), "avg_ct_kwh": first.get("avgCtKwh"),
                "known": first.get("known"), "windows": [{"starts_at": x["startsAt"], "ends_at": x["endsAt"],
                                                          "avg_ct_kwh": x["avgCtKwh"], "known": x["known"]} for x in w]}


class PriceLevelSensor(WattcastEntity, SensorEntity):
    """cheap / normal / high / expensive: the current hour against the 30-day quartiles."""
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = LEVELS
    _attr_icon = "mdi:speedometer"

    def __init__(self, c, e):
        super().__init__(c, e, "price_level")

    @property
    def native_value(self) -> str | None:
        s = self.coordinator.current_hour()
        return self.coordinator.level_of(s["ctKwh"] if s else None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        th = self.coordinator.thresholds() or {}
        return {"p25_ct_kwh": th.get("p25"), "p50_ct_kwh": th.get("p50"), "p75_ct_kwh": th.get("p75"),
                "mean_ct_kwh": th.get("mean"), "window_days": th.get("days")}


class ForecastSensor(WattcastEntity, SensorEntity):
    """When the forecast was issued; the series live in the attributes (hourly, ct/kWh and EUR/MWh)."""
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:chart-bell-curve-cumulative"

    def __init__(self, c, e):
        super().__init__(c, e, "forecast")

    @property
    def native_value(self) -> datetime | None:
        ts = self.coordinator.data.hourly.get("madeAt")
        return datetime.fromtimestamp(ts, timezone.utc) if ts else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        h = self.coordinator.data.hourly
        return {"unit": "EUR/MWh", "hours": self.coordinator.hours_series(),
                "known_until": h.get("lastKnownIso"),
                "forecast": [{"start": x["startsAt"], "k": x["k"], "p10": round(x["p10"] / 10, 3), "p50": x["p50CtKwh"],
                              "p90": round(x["p90"] / 10, 3)} for x in h.get("forecast", [])],
                "forecast_unit": CT_KWH, "backtest_mae_eur_mwh": h.get("backtestMae"),
                "adjustments": (h.get("adjustments") or {}).get("entries")}


class OutlookSensor(WattcastEntity, SensorEntity):
    """Title of the written daily outlook; the Markdown body is an attribute."""
    _attr_icon = "mdi:text-box-outline"

    def __init__(self, c, e):
        super().__init__(c, e, "outlook")

    @property
    def native_value(self) -> str | None:
        cm = self.coordinator.data.commentary
        return (cm.get("title") or "")[:255] or None if cm else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        cm = self.coordinator.data.commentary or {}
        return {"markdown": cm.get("markdown"), "language": cm.get("lang"), "generated_at": cm.get("generatedAt"),
                "valid_until": cm.get("validUntil")}
