"""
OpenWeatherMap weather provider - requires API key.
Supports 5 days forecast.
API Documentation: https://openweathermap.org/api
"""
import httpx
from datetime import datetime, date
from typing import Optional
from .base import WeatherProvider, ProviderResult, WeatherNow, ForecastDay


class OpenWeatherMapProvider(WeatherProvider):
    """Provider for OpenWeatherMap API (requires API key)."""
    
    BASE_URL = "https://api.openweathermap.org/data/2.5"
    
    # Weather condition codes to description
    # https://openweathermap.org/weather-conditions
    CONDITION_CODES = {
        200: "Thunderstorm with light rain",
        201: "Thunderstorm with rain",
        202: "Thunderstorm with heavy rain",
        210: "Light thunderstorm",
        211: "Thunderstorm",
        212: "Heavy thunderstorm",
        221: "Ragged thunderstorm",
        230: "Thunderstorm with light drizzle",
        231: "Thunderstorm with drizzle",
        232: "Thunderstorm with heavy drizzle",
        300: "Light intensity drizzle",
        301: "Drizzle",
        302: "Heavy intensity drizzle",
        310: "Light intensity drizzle rain",
        311: "Drizzle rain",
        312: "Heavy intensity drizzle rain",
        313: "Shower rain and drizzle",
        314: "Heavy shower rain and drizzle",
        321: "Shower drizzle",
        500: "Light rain",
        501: "Moderate rain",
        502: "Heavy intensity rain",
        503: "Very heavy rain",
        504: "Extreme rain",
        511: "Freezing rain",
        520: "Light intensity shower rain",
        521: "Shower rain",
        522: "Heavy intensity shower rain",
        531: "Ragged shower rain",
        600: "Light snow",
        601: "Snow",
        602: "Heavy snow",
        611: "Sleet",
        612: "Light shower sleet",
        613: "Shower sleet",
        615: "Light rain and snow",
        616: "Rain and snow",
        620: "Light shower snow",
        621: "Shower snow",
        622: "Heavy shower snow",
        701: "Mist",
        711: "Smoke",
        721: "Haze",
        731: "Sand/dust whirls",
        741: "Fog",
        751: "Sand",
        761: "Dust",
        762: "Volcanic ash",
        771: "Squalls",
        781: "Tornado",
        800: "Clear sky",
        801: "Few clouds",
        802: "Scattered clouds",
        803: "Broken clouds",
        804: "Overcast clouds",
    }
    
    def __init__(self):
        self._api_key: Optional[str] = None
    
    @property
    def name(self) -> str:
        return "openweathermap"
    
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
        """Fetch weather data from OpenWeatherMap."""
        
        if not self.is_available():
            raise ValueError("OpenWeatherMap API key not configured")
        
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # Fetch current weather
            current_params = {
                "lat": lat,
                "lon": lon,
                "appid": self._api_key,
                "units": "metric"
            }
            current_response = await client.get(
                f"{self.BASE_URL}/weather",
                params=current_params
            )
            current_response.raise_for_status()
            current_data = current_response.json()
            
            # Fetch 5-day forecast (3-hour intervals)
            forecast_params = {
                "lat": lat,
                "lon": lon,
                "appid": self._api_key,
                "units": "metric"
            }
            forecast_response = await client.get(
                f"{self.BASE_URL}/forecast",
                params=forecast_params
            )
            forecast_response.raise_for_status()
            forecast_data = forecast_response.json()
        
        return self._parse(current_data, forecast_data)
    
    def _parse(self, current_data: dict, forecast_data: dict) -> ProviderResult:
        """Parse OpenWeatherMap API response into normalized schema."""
        fetched_at = datetime.utcnow()
        
        # Parse current weather
        now = None
        if current_data:
            main = current_data.get("main", {})
            wind = current_data.get("wind", {})
            clouds = current_data.get("clouds", {})
            rain = current_data.get("rain", {})
            snow = current_data.get("snow", {})
            visibility = current_data.get("visibility")
            weather = current_data.get("weather", [{}])[0] if current_data.get("weather") else {}
            
            # Precipitation (rain + snow in last hour)
            precip_mm = rain.get("1h", 0) + snow.get("1h", 0)
            
            now = WeatherNow(
                provider_name=self.name,
                fetched_at=fetched_at,
                temperature_c=main.get("temp"),
                feels_like_c=main.get("feels_like"),
                humidity_pct=main.get("humidity"),
                wind_speed_kmh=wind.get("speed", 0) * 3.6,  # m/s to km/h
                wind_direction_deg=wind.get("deg"),
                precipitation_mm=precip_mm if precip_mm > 0 else None,
                pressure_hpa=main.get("pressure"),
                visibility_km=visibility / 1000 if visibility else None,
                uv_index=None,  # Not in current weather endpoint
                cloud_cover_pct=clouds.get("all"),
                condition=self.CONDITION_CODES.get(weather.get("id"), weather.get("description", "Unknown"))
            )
        
        # Parse forecast (aggregate 3-hour data into daily)
        forecast = []
        daily_data = {}
        
        for entry in forecast_data.get("list", []):
            dt = datetime.fromtimestamp(entry.get("dt", 0))
            date_key = dt.date()
            
            if date_key not in daily_data:
                daily_data[date_key] = {
                    "temps": [],
                    "humidity": [],
                    "wind_speed": [],
                    "wind_dir": [],
                    "precip": [],
                    "clouds": [],
                    "conditions": []
                }
            
            main = entry.get("main", {})
            wind = entry.get("wind", {})
            clouds = entry.get("clouds", {})
            rain = entry.get("rain", {})
            snow = entry.get("snow", {})
            weather = entry.get("weather", [{}])[0] if entry.get("weather") else {}
            
            daily_data[date_key]["temps"].append(main.get("temp"))
            daily_data[date_key]["humidity"].append(main.get("humidity"))
            daily_data[date_key]["wind_speed"].append(wind.get("speed", 0) * 3.6)
            daily_data[date_key]["wind_dir"].append(wind.get("deg"))
            daily_data[date_key]["precip"].append(rain.get("3h", 0) + snow.get("3h", 0))
            daily_data[date_key]["clouds"].append(clouds.get("all"))
            daily_data[date_key]["conditions"].append(self.CONDITION_CODES.get(weather.get("id"), weather.get("description")))
        
        for forecast_date, data in sorted(daily_data.items()):
            temps = [t for t in data["temps"] if t is not None]
            humidities = [h for h in data["humidity"] if h is not None]
            wind_speeds = [w for w in data["wind_speed"] if w is not None]
            wind_dirs = [d for d in data["wind_dir"] if d is not None]
            precips = [p for p in data["precip"] if p is not None]
            clouds = [c for c in data["clouds"] if c is not None]
            conditions = [c for c in data["conditions"] if c]
            
            # Circular mean for wind direction
            avg_wind_dir = None
            if wind_dirs:
                import math
                sin_sum = sum(math.sin(math.radians(d)) for d in wind_dirs)
                cos_sum = sum(math.cos(math.radians(d)) for d in wind_dirs)
                if sin_sum != 0 or cos_sum != 0:
                    avg_wind_dir = math.degrees(math.atan2(sin_sum, cos_sum)) % 360
            
            # Most common condition
            condition = max(set(conditions), key=conditions.count) if conditions else None
            
            forecast_day = ForecastDay(
                provider_name=self.name,
                date=forecast_date,
                temp_max_c=max(temps) if temps else None,
                temp_min_c=min(temps) if temps else None,
                temp_avg_c=sum(temps) / len(temps) if temps else None,
                humidity_pct=sum(humidities) / len(humidities) if humidities else None,
                wind_speed_kmh=sum(wind_speeds) / len(wind_speeds) if wind_speeds else None,
                wind_direction_deg=avg_wind_dir,
                precipitation_mm=sum(precips) if precips and sum(precips) > 0 else None,
                uv_index=None,  # Not provided in free tier
                cloud_cover_pct=sum(clouds) / len(clouds) if clouds else None,
                condition=condition
            )
            forecast.append(forecast_day)
        
        return ProviderResult(
            provider_name=self.name,
            now=now,
            forecast=forecast[:5]  # Limit to 5 days
        )
