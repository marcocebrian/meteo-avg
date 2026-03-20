"""
Tomorrow.io weather provider - requires API key.
Supports 5 days forecast.
API Documentation: https://docs.tomorrow.io/reference/api-introduction
"""
import httpx
from datetime import datetime, date
from typing import Optional
from .base import WeatherProvider, ProviderResult, WeatherNow, ForecastDay


class TomorrowIOProvider(WeatherProvider):
    """Provider for Tomorrow.io API (requires API key)."""
    
    BASE_URL = "https://api.tomorrow.io/v4/weather"
    
    # Weather code to condition mapping
    # https://docs.tomorrow.io/reference/data-layers-core#weather-code
    WEATHER_CODES = {
        0: "Unknown",
        1000: "Clear, Sunny",
        1001: "Cloudy",
        1100: "Mostly Clear",
        1101: "Partly Cloudy",
        1102: "Mostly Cloudy",
        2000: "Fog",
        2100: "Light Fog",
        3000: "Light Wind",
        3001: "Wind",
        3002: "Strong Wind",
        4000: "Light Drizzle",
        4001: "Drizzle",
        4200: "Light Rain",
        4201: "Heavy Rain",
        5000: "Light Snow",
        5001: "Flurries",
        5100: "Light Snow",
        5101: "Heavy Snow",
        6000: "Freezing Drizzle",
        6001: "Freezing Rain",
        6200: "Light Freezing Rain",
        6201: "Heavy Freezing Rain",
        7000: "Ice Pellets",
        7101: "Heavy Ice Pellets",
        7102: "Light Ice Pellets",
        8000: "Thunderstorm",
    }
    
    def __init__(self):
        self._api_key: Optional[str] = None
    
    @property
    def name(self) -> str:
        return "tomorrow_io"
    
    @property
    def requires_api_key(self) -> bool:
        return True
    
    @property
    def api_key(self) -> Optional[str]:
        return self._api_key
    
    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        self._api_key = value
    
    @property
    def forecast_days(self) -> int:
        return 5
    
    def is_available(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 0
    
    async def fetch(self, lat: float, lon: float, timeout: float) -> ProviderResult:
        """Fetch weather data from Tomorrow.io."""
        
        if not self.is_available():
            raise ValueError("Tomorrow.io API key not configured")
        
        location = f"{lat},{lon}"
        
        params = {
            "location": location,
            "apikey": self._api_key,
            "units": "metric",
            "timesteps": ["1d", "1h"],  # Daily and hourly
            "fields": [
                "temperature", "temperatureApparent", "humidity",
                "windSpeed", "windDirection", "precipitationIntensity",
                "pressureSeaLevel", "visibility", "uvIndex",
                "cloudCover", "weatherCode", "temperatureMax", "temperatureMin"
            ]
        }
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                f"{self.BASE_URL}/forecast",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
        
        return self._parse(data)
    
    def _parse(self, data: dict) -> ProviderResult:
        """Parse Tomorrow.io API response into normalized schema."""
        fetched_at = datetime.utcnow()
        
        timelines = data.get("timelines", {})
        
        # Parse current weather from hourly data (use first entry)
        now = None
        hourly = timelines.get("hourly", [])
        if hourly and len(hourly) > 0:
            first_hour = hourly[0].get("values", {})
            now = WeatherNow(
                provider_name=self.name,
                fetched_at=fetched_at,
                temperature_c=first_hour.get("temperature"),
                feels_like_c=first_hour.get("temperatureApparent"),
                humidity_pct=first_hour.get("humidity"),
                wind_speed_kmh=first_hour.get("windSpeed"),  # Already in km/h with metric units
                wind_direction_deg=first_hour.get("windDirection"),
                precipitation_mm=first_hour.get("precipitationIntensity"),
                pressure_hpa=first_hour.get("pressureSeaLevel"),
                visibility_km=first_hour.get("visibility"),
                uv_index=first_hour.get("uvIndex"),
                cloud_cover_pct=first_hour.get("cloudCover"),
                condition=self.WEATHER_CODES.get(first_hour.get("weatherCode"), "Unknown")
            )
        
        # Parse daily forecast
        forecast = []
        daily = timelines.get("daily", [])
        
        for day_entry in daily:
            try:
                values = day_entry.get("values", {})
                time_str = day_entry.get("time", "")
                
                # Parse date from ISO string
                forecast_date = date.fromisoformat(time_str.split("T")[0])
                
                forecast_day = ForecastDay(
                    provider_name=self.name,
                    date=forecast_date,
                    temp_max_c=values.get("temperatureMax"),
                    temp_min_c=values.get("temperatureMin"),
                    temp_avg_c=values.get("temperature"),
                    humidity_pct=values.get("humidity"),
                    wind_speed_kmh=values.get("windSpeed"),
                    wind_direction_deg=values.get("windDirection"),
                    precipitation_mm=values.get("precipitationIntensity"),
                    uv_index=values.get("uvIndex"),
                    cloud_cover_pct=values.get("cloudCover"),
                    condition=self.WEATHER_CODES.get(values.get("weatherCode"), "Unknown")
                )
                forecast.append(forecast_day)
            except (ValueError, KeyError):
                continue
        
        return ProviderResult(
            provider_name=self.name,
            now=now,
            forecast=forecast[:5]  # Limit to 5 days
        )
