"""
Open-Meteo weather provider - free, no API key required.
Supports up to 16 days forecast.
API Documentation: https://open-meteo.com/en/docs
"""
import httpx
from datetime import datetime, date
from typing import Optional
from .base import WeatherProvider, ProviderResult, WeatherNow, ForecastDay


class OpenMeteoProvider(WeatherProvider):
    """Provider for Open-Meteo API (free, no key required)."""
    
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    
    @property
    def name(self) -> str:
        return "open_meteo"
    
    @property
    def forecast_days(self) -> int:
        return 16
    
    async def fetch(self, lat: float, lon: float, timeout: float) -> ProviderResult:
        """Fetch weather data from Open-Meteo."""
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,pressure_msl,wind_speed_10m,wind_direction_10m,cloud_cover,visibility",
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant,uv_index_max,cloud_cover_mean",
            "timezone": "auto",
            "forecast_days": 16
        }
        
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
        
        return self._parse(data)
    
    def _parse(self, data: dict) -> ProviderResult:
        """Parse Open-Meteo API response into normalized schema."""
        fetched_at = datetime.utcnow()
        
        # Parse current weather
        now = None
        if "current" in data:
            current = data["current"]
            now = WeatherNow(
                provider_name=self.name,
                fetched_at=fetched_at,
                temperature_c=current.get("temperature_2m"),
                feels_like_c=current.get("apparent_temperature"),
                humidity_pct=current.get("relative_humidity_2m"),
                wind_speed_kmh=current.get("wind_speed_10m"),
                wind_direction_deg=current.get("wind_direction_10m"),
                precipitation_mm=current.get("precipitation"),
                pressure_hpa=current.get("pressure_msl"),
                visibility_km=current.get("visibility", 10) / 1000 if current.get("visibility") else None,
                cloud_cover_pct=current.get("cloud_cover"),
                uv_index=None,  # Current UV not available in current endpoint
                condition=self._get_condition_from_code(current.get("weather_code", 0))
            )
        
        # Parse daily forecast
        forecast = []
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        
        for i, d in enumerate(dates):
            try:
                forecast_day = ForecastDay(
                    provider_name=self.name,
                    date=date.fromisoformat(d),
                    temp_max_c=self._get_list_value(daily.get("temperature_2m_max"), i),
                    temp_min_c=self._get_list_value(daily.get("temperature_2m_min"), i),
                    temp_avg_c=self._get_list_value(daily.get("temperature_2m_mean"), i),
                    precipitation_mm=self._get_list_value(daily.get("precipitation_sum"), i),
                    wind_speed_kmh=self._get_list_value(daily.get("wind_speed_10m_max"), i),
                    wind_direction_deg=self._get_list_value(daily.get("wind_direction_10m_dominant"), i),
                    uv_index=self._get_list_value(daily.get("uv_index_max"), i),
                    cloud_cover_pct=self._get_list_value(daily.get("cloud_cover_mean"), i),
                    humidity_pct=None,  # Daily humidity not available
                    condition=None  # Daily weather code not in standard params
                )
                forecast.append(forecast_day)
            except (ValueError, IndexError):
                continue
        
        return ProviderResult(
            provider_name=self.name,
            now=now,
            forecast=forecast
        )
    
    def _get_list_value(self, lst: Optional[list], index: int) -> Optional[float]:
        """Safely get a value from a list."""
        if lst is None or index >= len(lst):
            return None
        val = lst[index]
        return val if val is not None else None
    
    def _get_condition_from_code(self, code: int) -> str:
        """Convert WMO weather code to condition string."""
        # WMO Weather interpretation codes (WW)
        # https://open-meteo.com/en/docs
        conditions = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Light freezing drizzle",
            57: "Dense freezing drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail"
        }
        return conditions.get(code, "Unknown")
