"""Constants for the Wattcast integration."""
from datetime import timedelta

DOMAIN = "wattcast"

CONF_ZONE = "zone"
CONF_BASE_URL = "base_url"
CONF_API_KEY = "api_key"

DEFAULT_BASE_URL = "https://wattcast.eu"
ZONES = ["EE", "FI", "LV", "LT"]
ZONE_TZ = {"EE": "Europe/Tallinn", "FI": "Europe/Helsinki", "LV": "Europe/Riga", "LT": "Europe/Vilnius"}

UPDATE_INTERVAL = timedelta(minutes=15)      # prices and cheapest windows
SLOW_INTERVAL = timedelta(hours=1)           # 30-day levels and the written outlook
REQUEST_TIMEOUT = 60

# cheapest non-overlapping windows exposed as timestamp sensors (minutes)
WINDOWS = {"cheapest_1h": 60, "cheapest_2h": 120, "cheapest_3h": 180}
WINDOW_SCOPE = "next24h"

LEVELS = ["cheap", "normal", "high", "expensive"]
LEVEL_DAYS = 30

ATTRIBUTION = "Prices: Elering (Nord Pool). Weather: Open-Meteo.com (CC BY 4.0). Forecast: Wattcast, unofficial."
MANUFACTURER = "Wattcast"
