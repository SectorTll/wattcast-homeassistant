# Wattcast for Home Assistant

Nord Pool day-ahead electricity prices and a **7-day probabilistic forecast** for **Estonia, Finland, Latvia and
Lithuania** (bidding zones EE, FI, LV, LT) from [wattcast.eu](https://wattcast.eu), as Home Assistant entities.
Prices are exchange prices in **ct/kWh without VAT, network fees or supplier margin**.

## Install

1. HACS → Integrations → ⋮ → *Custom repositories* → add `https://github.com/SectorTll/wattcast-hacs` (type
   *Integration*), then install **Wattcast** and restart Home Assistant.
2. Settings → Devices & services → *Add integration* → **Wattcast** → pick the bidding zone. One entry per zone.
   The API base URL and the optional API key are only needed for a self-hosted Wattcast or a higher rate limit.

Manual install: copy `custom_components/wattcast` into your `config/custom_components/` and restart.

## Entities (one device per zone, e.g. *Wattcast EE*)

| Entity | State | Attributes |
|---|---|---|
| `sensor.wattcast_ee_price` | current 15-minute price, ct/kWh | `eur_mwh`, `slot_start`, `level` |
| `sensor.wattcast_ee_price_hour` | current hour (mean of its quarters), ct/kWh | `next_hour_ct_kwh`, `next_hour_known`, `level` |
| `sensor.wattcast_ee_today_average` / `_tomorrow_average` | day average, ct/kWh | `basis` = `settled` or `forecast`, `min_ct_kwh`, `min_hour`, `max_ct_kwh`, `max_hour` |
| `sensor.wattcast_ee_cheapest_1h` / `_2h` / `_3h` | start of the cheapest window in the next 24 h (timestamp) | `ends_at`, `avg_ct_kwh`, `known` (settled vs forecast), `windows` (top 3) |
| `sensor.wattcast_ee_price_level` | `cheap` / `normal` / `high` / `expensive` | thresholds `p25_ct_kwh`, `p50_ct_kwh`, `p75_ct_kwh` of the last 30 days |
| `sensor.wattcast_ee_forecast` | when the forecast was issued (timestamp) | `hours` = `[[local ISO start, EUR/MWh], …]` settled + forecast p50 for ~8 days; `forecast` = list of `{start, k, p10, p50, p90}` in ct/kWh; `known_until`; `backtest_mae_eur_mwh`; `adjustments` (expert corrections from the daily outlook) |
| `sensor.wattcast_ee_outlook` | title of the written daily outlook | `markdown`, `language`, `generated_at` |
| `binary_sensor.wattcast_ee_cheap_now` | on when the current hour is below the 30-day p25 | `price_ct_kwh`, `threshold_ct_kwh` |
| `binary_sensor.wattcast_ee_tomorrow_published` | on once Nord Pool has published tomorrow (about 14:00 EET) | `settled_hours`, `known_until` |

The `hours` attribute has the same shape as a Nord Pool hourly cache (`[[iso_local, EUR/MWh], ...]`), so existing
templates and AppDaemon apps that read such a list can be pointed at the forecast without changing their parsing.

Polling: prices and cheapest windows every 15 minutes, the 30-day levels and the outlook once an hour. The public API
allows 60 requests per minute per IP; one zone uses about six per 15 minutes.

## Examples

Start the water heater in the cheapest 2-hour window of the next 24 hours:

```yaml
automation:
  - alias: Boiler in the cheapest 2 h
    triggers:
      - trigger: time
        at: sensor.wattcast_ee_cheapest_2h
    actions:
      - action: switch.turn_on
        target: { entity_id: switch.boiler }
      - delay: "02:00:00"
      - action: switch.turn_off
        target: { entity_id: switch.boiler }
```

Charge the car only while the price is in the cheapest quarter of the last 30 days:

```yaml
automation:
  - alias: EV charging when cheap
    triggers:
      - trigger: state
        entity_id: binary_sensor.wattcast_ee_cheap_now
    actions:
      - action: "switch.turn_{{ 'on' if is_state('binary_sensor.wattcast_ee_cheap_now', 'on') else 'off' }}"
        target: { entity_id: switch.charger }
```

A price chart with the p10–p90 band (apexcharts-card):

```yaml
type: custom:apexcharts-card
graph_span: 3d
span: { start: day }
series:
  - entity: sensor.wattcast_ee_forecast
    name: p50
    data_generator: |
      return entity.attributes.forecast.map(x => [new Date(x.start).getTime(), x.p50]);
  - entity: sensor.wattcast_ee_forecast
    name: p90
    type: area
    data_generator: |
      return entity.attributes.forecast.map(x => [new Date(x.start).getTime(), x.p90]);
```

## Recorder

The `forecast` sensor carries ~200 rows of attributes and changes about once an hour. If you keep a long recorder
history, exclude its attributes or the entity:

```yaml
recorder:
  exclude:
    entities:
      - sensor.wattcast_ee_forecast
      - sensor.wattcast_ee_outlook
```

## Attribution

Prices: Elering (Nord Pool day-ahead). Weather: Open-Meteo.com (CC BY 4.0). Forecast: Wattcast, unofficial and
informational, no guarantee.
