"""Weather integration via Open-Meteo (no API key required).

Docs: https://open-meteo.com/en/docs
Needs: WEATHER_LAT, WEATHER_LON (defaults provided), optional WEATHER_UNITS.
This card works out of the box without any secrets.
"""
import requests

from .base import Integration

API_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes -> short text. e-ink: text beats icons.
WMO = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Heavy showers",
    85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm + hail", 99: "Thunderstorm + hail",
}


class WeatherIntegration(Integration):
    name = "weather"

    def __init__(self, env, cache_ttl=300):
        super().__init__(env, cache_ttl)
        self.lat = env.get("WEATHER_LAT", "").strip()
        self.lon = env.get("WEATHER_LON", "").strip()
        self.label = env.get("WEATHER_LABEL", "").strip()
        units = env.get("WEATHER_UNITS", "fahrenheit").strip().lower()
        self.temp_unit = "fahrenheit" if units.startswith("f") else "celsius"
        self.unit_symbol = "F" if self.temp_unit == "fahrenheit" else "C"

    def is_configured(self):
        return bool(self.lat and self.lon)

    def fetch_real(self):
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "temperature_unit": self.temp_unit,
            "current": "temperature_2m,apparent_temperature,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,weather_code",
            "timezone": "auto",
            "forecast_days": 3,
        }
        resp = requests.get(API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        cur = data.get("current", {})
        daily = data.get("daily", {})

        forecast = []
        days = daily.get("time", [])
        for i, day in enumerate(days):
            forecast.append(
                {
                    "day": _weekday(day),
                    "high": round(daily["temperature_2m_max"][i]),
                    "low": round(daily["temperature_2m_min"][i]),
                    "desc": WMO.get(daily["weather_code"][i], "--"),
                }
            )

        return {
            "label": self.label or "Weather",
            "temp": round(cur.get("temperature_2m", 0)),
            "feels": round(cur.get("apparent_temperature", 0)),
            "desc": WMO.get(cur.get("weather_code"), "--"),
            "unit": self.unit_symbol,
            "forecast": forecast,
        }

    def mock(self):
        return {
            "label": "Set WEATHER_LAT/LON",
            "temp": 72,
            "feels": 70,
            "desc": "Partly cloudy",
            "unit": "F",
            "forecast": [
                {"day": "Today", "high": 75, "low": 60, "desc": "Clear"},
                {"day": "Tue", "high": 73, "low": 58, "desc": "Rain"},
                {"day": "Wed", "high": 68, "low": 55, "desc": "Cloudy"},
            ],
        }


def _weekday(iso_date: str) -> str:
    import datetime as _dt
    try:
        d = _dt.date.fromisoformat(iso_date)
    except ValueError:
        return iso_date
    if d == _dt.date.today():
        return "Today"
    return d.strftime("%a")
