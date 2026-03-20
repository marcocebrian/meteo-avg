"""
Weatherbit.io weather provider - requires API key.
Supports 16 days forecast.
API Documentation: https://www.weatherbit.io/api
"""
import httpx
from datetime import datetime, date
from typing import Optional
from .base import WeatherProvider, ProviderResult, WeatherNow, ForecastDay


class WeatherbitProvider(WeatherProvider):
    """Provider for Weatherbit.io API (requires API key)."""
    
    BASE_URL = "https://api.weatherbit.io/v2.0"
    
    # Weather code to condition mapping
    # https://www.weatherbit.io/api/codes
    WEATHER_CODES = {
        200: "Thunderstorm with light rain",
        201: "Thunderstorm with rain",
        202: "Thunderstorm with heavy rain",
        230: "Thunderstorm with light drizzle",
        231: "Thunderstorm with drizzle",
        232: "Thunderstorm with heavy drizzle",
        233: "Thunderstorm",
        300: "Light drizzle",
        301: "Drizzle",
        302: "Heavy drizzle",
        500: "Light rain",
        501: "Moderate rain",
        502: "Heavy rain",
        511: "Freezing rain",
        520: "Light shower rain",
        521: "Shower rain",
        522: "Heavy shower rain",
        600: "Light snow",
        601: "Snow",
        602: "Heavy snow",
        610: "Mix snow/rain",
        611: "Sleet",
        612: "Heavy sleet",
        621: "Snow shower",
        622: "Heavy snow shower",
        623: "Flurries",
        700: "Mist",
        711: "Smoke",
        721: "Haze",
        731: "Sand/dust",
        741: "Fog",
        751: "Freezing fog",
        800: "Clear sky",
        801: "Few clouds",
        802: "Scattered clouds",
        803: "Broken clouds",
        804: "Overcast clouds",
        900: "Unknown precipitation",
    }
    
    def __init__(self):
        self._api_key: Optional[str] = None
    
    @property
    def name(self) -> str:
        return "weatherbit"
    
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
        return 16
    
    def is_available(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 0
    
    async def fetch(self, lat: float, lon: float, timeout: float) -> ProviderResult:
        """Fetch weather data from Weatherbit.io."""
        
        if not self.is_available():
            raise ValueError("Weatherbit API key not configured")
        
        params = {
            "lat": lat,
            "lon": lon,
            "key": self._api_key,
            "units": "M",  # Metric (Celsius, km/h, mm)
            "days": 16
        }
        
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # Fetch current weather
            current_response = await client.get(
                f"{self.BASE_URL}/current",
                params=params
            )
            current_response.raise_for_status()
            current_data = current_response.json()
            
            # Fetch 16-day forecast
            forecast_response = await client.get(
                f"{self.BASE_URL}/forecast/daily",
                params=params
            )
            forecast_response.raise_for_status()
            forecast_data = forecast_response.json()
        
        return self._parse(current_data, forecast_data)
    
    def _parse(self, current_data: dict, forecast_data: dict) -> ProviderResult:
        """Parse Weatherbit API response into normalized schema."""
        fetched_at = datetime.utcnow()
        
        # Parse current weather
        now = None
        if "data" in current_data and current_data["data"]:
            current = current_data["data"][0]
            weather = current.get("weather", {})
            
            now = WeatherNow(
                provider_name=self.name,
                fetched_at=fetched_at,
                temperature_c=current.get("temp"),
                feels_like_c=current.get("app_temp"),
                humidity_pct=current.get("rh"),
                wind_speed_kmh=current.get("wind_spd"),
                wind_direction_deg=current.get("wind_dir"),
                precipitation_mm=current.get("precip"),
                pressure_hpa=current.get("pres"),
                visibility_km=current.get("vis"),
                uv_index=current.get("uv"),
                cloud_cover_pct=current.get("clouds"),
                condition=weather.get("description")
            )
        
        # Parse forecast
        forecast = []
        for day_data in forecast_data.get("data", []):
            try:
                weather = day_data.get("weather", {})
                
                forecast_day = ForecastDay(
                    provider_name=self.name,
                    date=date.fromisoformat(day_data["valid_date"]),
                    temp_max_c=day_data.get("max_temp"),
                    temp_min_c=day_data.get("min_temp"),
                    temp_avg_c=day_data.get("temp"),
                    humidity_pct=day_data.get("rh"),
                    wind_speed_kmh=day_data.get("wind_spd"),
                    wind_direction_deg=day_data.get("wind_dir"),
                    precipitation_mm=day_data.get("precip"),
                    uv_index=day_data.get("uv"),
                    cloud_cover_pct=day_data.get("clouds"),
                    condition=weather.get("description")
                )
                forecast.append(forecast_day)
            except (ValueError, KeyError):
                continue
        
        return ProviderResult(
            provider_name=self.name,
            now=now,
            forecast=forecast
        )
