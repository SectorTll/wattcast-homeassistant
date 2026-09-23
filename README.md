# Wattcast for Home Assistant

Nord Pool day-ahead electricity prices and a **7-day probabilistic forecast** for **Estonia, Finland, Latvia and
Lithuania** (bidding zones EE, FI, LV, LT) from [wattcast.eu](https://wattcast.eu), as Home Assistant entities.
Prices are exchange prices in **ct/kWh without VAT, network fees or supplier margin**.

## Start here

**[Installation guide and EV charging workflow →](https://wattcast.eu/home-assistant)**

See the daily price trend, choose a charging day, then refine the hours once market prices are published.
The guide includes HACS installation steps and a basic dashboard card. Car or charger control uses its own
compatible Home Assistant integration; forecasts can change and do not guarantee savings.

[English](https://wattcast.eu/home-assistant) · [Eesti](https://wattcast.eu/home-assistant/et) ·
[Suomi](https://wattcast.eu/home-assistant/fi) · [Latviešu](https://wattcast.eu/home-assistant/lv) ·
[Lietuvių](https://wattcast.eu/home-assistant/lt) · [Русский](https://wattcast.eu/home-assistant/ru)

## Install

1. HACS → Integrations → ⋮ → *Custom repositories* → add `https://github.com/SectorTll/wattcast-homeassistant` (type
   *Integration*), then install **Wattcast** and restart Home Assistant.
2. Settings → Devices & services → *Add integration* → **Wattcast** → pick the bidding zone. One entry per zone.
   The API base URL and the optional API key are only needed for a self-hosted Wattcast or a higher rate limit.

Manual install: copy `custom_components/wattcast` into your `config/custom_components/` and restart.

## Entities (one device per zone, e.g. *Wattcast EE*)

| Entity | State | Attributes |
|---|---|---|
| `sensor.wattcast_ee_price` | current 15-minute price, ct/kWh | `eur_mwh`, `slot_start`, `level`, `raw_today` / `raw_tomorrow` = 15-minute `[{start, value}]` (ct/kWh), `raw_today_known` / `raw_tomorrow_known` |
| `sensor.wattcast_ee_price_hour` | current hour (mean of its quarters), ct/kWh | `next_hour_ct_kwh`, `next_hour_known`, `level`, `raw_today` / `raw_tomorrow` = hourly `[{start, end, value}]` (ct/kWh, Nord Pool shape), `today` / `tomorrow` = plain price arrays, `raw_today_known` / `raw_tomorrow_known` |
| `sensor.wattcast_ee_today_average` / `_tomorrow_average` | day average, ct/kWh | `basis` = `settled` or `forecast`, `min_ct_kwh`, `min_hour`, `max_ct_kwh`, `max_hour` |
| `sensor.wattcast_ee_cheapest_1h` / `_2h` / `_3h` | start of the cheapest window in the next 24 h (timestamp) | `ends_at`, `avg_ct_kwh`, `known` (settled vs forecast), `windows` (top 3) |
| `sensor.wattcast_ee_price_level` | `cheap` / `normal` / `high` / `expensive` | thresholds `p25_ct_kwh`, `p50_ct_kwh`, `p75_ct_kwh` of the last 30 days |
| `sensor.wattcast_ee_forecast` | when the forecast was issued (timestamp) | `forecast` = the 7-day hourly band, list of `{start, k, p10, p50, p90}` in ct/kWh; `known_until`; `backtest_mae_eur_mwh`; `adjustments` (expert corrections from the daily outlook) |
| `sensor.wattcast_ee_outlook` | title of the written daily outlook | `markdown`, `language`, `generated_at` |
| `binary_sensor.wattcast_ee_cheap_now` | on when the current hour is below the 30-day p25 | `price_ct_kwh`, `threshold_ct_kwh` |
| `binary_sensor.wattcast_ee_tomorrow_published` | on once Nord Pool has published tomorrow (about 14:00 EET) | `settled_hours`, `known_until` |

The `raw_today` / `raw_tomorrow` attributes on the price sensors use the Nord Pool shape (`[{start, end, value}]`), so
existing cards, blueprints and templates that read Nord Pool's `raw_today` work unchanged. Hourly arrays live on
`sensor.wattcast_ee_price_hour`, 15-minute arrays (compact `{start, value}`) on `sensor.wattcast_ee_price`; the full
7-day band is on `sensor.wattcast_ee_forecast`. Each entity's attributes stay under Home Assistant's 16 KB limit.

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

Some entities carry list attributes. The `forecast` and `outlook` sensors change hourly, and the 15-minute
`sensor.wattcast_ee_price` carries a 96-point `raw_today` that changes every 15 minutes — exclude these from the
recorder if you keep a long history (`sensor.wattcast_ee_price_hour` stays recorded and gives hourly statistics):

```yaml
recorder:
  exclude:
    entities:
      - sensor.wattcast_ee_forecast
      - sensor.wattcast_ee_outlook
      - sensor.wattcast_ee_price
```

## Attribution

Prices: Elering (Nord Pool day-ahead). Weather: Open-Meteo.com (CC BY 4.0). Forecast: Wattcast, unofficial and
informational, no guarantee.
