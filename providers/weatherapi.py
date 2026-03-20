"""
WeatherAPI.com weather provider - requires API key.
Supports 14 days forecast.
API Documentation: https://www.weatherapi.com/docs/
"""
import httpx
from datetime import datetime, date
from typing import Optional
from .base import WeatherProvider, ProviderResult, WeatherNow, ForecastDay


class WeatherAPIProvider(WeatherProvider):
    """Provider for WeatherAPI.com (requires API key)."""
    
    BASE_URL = "https://api.weatherapi.com/v1"
    
    def __init__(self):
        self._api_key: Optional[str] = None
    
    @property
    def name(self) -> str:
        return "weatherapi"
    
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
        return 14
    
    def is_available(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 0
    
    async def fetch(self, lat: float, lon: float, timeout: float) -> ProviderResult:
        """Fetch weather data from WeatherAPI.com."""
        
        if not self.is_available():
            raise ValueError("WeatherAPI key not configured")
        
        # WeatherAPI accepts coordinates as "lat,lon"
        location = f"{lat},{lon}"
        
        params = {
            "key": self._api_key,
            "q": location,
            "days": 14,
            "aqi": "no",
            "alerts": "no"
        }
        
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                f"{self.BASE_URL}/forecast.json",
                params=params
            )
            response.raise_for_status()
            data = response.json()
        
        return self._parse(data)
    
    def _parse(self, data: dict) -> ProviderResult:
        """Parse WeatherAPI response into normalized schema."""
        fetched_at = datetime.utcnow()
        
        # Parse current weather
        now = None
        if "current" in data:
            current = data["current"]
            
            # Parse wind direction (comes as string like "N", "NE", etc.)
            wind_dir_deg = self._direction_to_deg(current.get("wind_dir"))
            
            now = WeatherNow(
                provider_name=self.name,
                fetched_at=fetched_at,
                temperature_c=current.get("temp_c"),
                feels_like_c=current.get("feelslike_c"),
                humidity_pct=current.get("humidity"),
                wind_speed_kmh=current.get("wind_kph"),
                wind_direction_deg=wind_dir_deg,
                precipitation_mm=current.get("precip_mm"),
                pressure_hpa=current.get("pressure_mb"),
                visibility_km=current.get("vis_km"),
                uv_index=current.get("uv"),
                cloud_cover_pct=current.get("cloud"),
                condition=current.get("condition", {}).get("text")
            )
        
        # Parse forecast
        forecast = []
        forecast_data = data.get("forecast", {}).get("forecastday", [])
        
        for day_data in forecast_data:
            try:
                day = day_data.get("day", {})
                
                forecast_day = ForecastDay(
                    provider_name=self.name,
                    date=date.fromisoformat(day_data.get("date")),
                    temp_max_c=day.get("maxtemp_c"),
                    temp_min_c=day.get("mintemp_c"),
                    temp_avg_c=day.get("avgtemp_c"),
                    humidity_pct=day.get("avghumidity"),
                    wind_speed_kmh=day.get("maxwind_kph"),
                    wind_direction_deg=None,  # Not provided in daily summary
                    precipitation_mm=day.get("totalprecip_mm"),
                    uv_index=day.get("uv"),
                    cloud_cover_pct=None,  # Not directly provided
                    condition=day.get("condition", {}).get("text")
                )
                forecast.append(forecast_day)
            except (ValueError, KeyError):
                continue
        
        return ProviderResult(
            provider_name=self.name,
            now=now,
            forecast=forecast
        )
    
    def _direction_to_deg(self, direction: Optional[str]) -> Optional[float]:
        """Convert wind direction string to degrees."""
        if direction is None:
            return None
        
        directions = {
            "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
            "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
            "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
            "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5
        }
        return directions.get(direction.upper(), None)
