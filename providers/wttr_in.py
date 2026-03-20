"""
wttr.in weather provider - free, no API key required.
Supports 3 days forecast.
API Documentation: https://github.com/chubin/wttr.in
"""
import httpx
from datetime import datetime, date
from typing import Optional
from .base import WeatherProvider, ProviderResult, WeatherNow, ForecastDay


class WttrInProvider(WeatherProvider):
    """Provider for wttr.in API (free, no key required)."""
    
    BASE_URL = "https://wttr.in"
    
    @property
    def name(self) -> str:
        return "wttr_in"
    
    @property
    def forecast_days(self) -> int:
        return 3
    
    async def fetch(self, lat: float, lon: float, timeout: float) -> ProviderResult:
        """Fetch weather data from wttr.in."""
        
        # wttr.in accepts coordinates as "lat,lon"
        location = f"{lat},{lon}"
        url = f"{self.BASE_URL}/{location}"
        
        params = {
            "format": "j1",  # JSON format
            "lang": "en"
        }
        
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        return self._parse(data)
    
    def _parse(self, data: dict) -> ProviderResult:
        """Parse wttr.in API response into normalized schema."""
        fetched_at = datetime.utcnow()
        
        # Parse current weather
        now = None
        if "current_condition" in data and data["current_condition"]:
            current = data["current_condition"][0]
            
            # Parse visibility - could be in km or miles
            vis_km = current.get("visibility")
            if vis_km:
                vis_km = float(vis_km)
            else:
                vis_mi = current.get("visibilityMiles")
                if vis_mi:
                    vis_km = float(vis_mi) * 1.60934
            
            # Parse pressure - could be in hPa or inches
            pressure = current.get("pressure")
            if pressure:
                pressure = float(pressure)
            else:
                pressure_in = current.get("pressureInches")
                if pressure_in:
                    pressure = float(pressure_in) * 33.8639
            
            now = WeatherNow(
                provider_name=self.name,
                fetched_at=fetched_at,
                temperature_c=self._safe_float(current.get("temp_C")),
                feels_like_c=self._safe_float(current.get("FeelsLikeC")),
                humidity_pct=self._safe_float(current.get("humidity")),
                wind_speed_kmh=self._safe_float(current.get("windspeedKmph")),
                wind_direction_deg=self._safe_float(current.get("winddirDegree")),
                precipitation_mm=self._safe_float(current.get("precipMM")),
                pressure_hpa=pressure,
                visibility_km=vis_km,
                uv_index=self._safe_float(current.get("uvIndex")),
                cloud_cover_pct=self._safe_float(current.get("cloudcover")),
                condition=current.get("weatherDesc", [{}])[0].get("value", "Unknown") if current.get("weatherDesc") else None
            )
        
        # Parse 3-day forecast
        forecast = []
        weather_data = data.get("weather", [])
        
        for day_data in weather_data:
            try:
                # Get hourly data for more detailed metrics
                hourly = day_data.get("hourly", [])
                avg_humidity = None
                avg_wind = None
                avg_wind_dir = None
                total_precip = 0.0
                avg_cloud = None
                
                if hourly:
                    humidities = [self._safe_float(h.get("humidity")) for h in hourly if h.get("humidity")]
                    winds = [self._safe_float(h.get("windspeedKmph")) for h in hourly if h.get("windspeedKmph")]
                    wind_dirs = [self._safe_float(h.get("winddirDegree")) for h in hourly if h.get("winddirDegree")]
                    precips = [self._safe_float(h.get("precipMM")) for h in hourly if h.get("precipMM")]
                    clouds = [self._safe_float(h.get("cloudcover")) for h in hourly if h.get("cloudcover")]
                    
                    if humidities:
                        avg_humidity = sum(humidities) / len(humidities)
                    if winds:
                        avg_wind = sum(winds) / len(winds)
                    if wind_dirs:
                        # Circular mean for wind direction
                        import math
                        sin_sum = sum(math.sin(math.radians(d)) for d in wind_dirs if d is not None)
                        cos_sum = sum(math.cos(math.radians(d)) for d in wind_dirs if d is not None)
                        if sin_sum != 0 or cos_sum != 0:
                            avg_wind_dir = math.degrees(math.atan2(sin_sum, cos_sum)) % 360
                    if precips:
                        total_precip = sum(precips)
                    if clouds:
                        avg_cloud = sum(clouds) / len(clouds)
                
                forecast_day = ForecastDay(
                    provider_name=self.name,
                    date=date.fromisoformat(day_data["date"]),
                    temp_max_c=self._safe_float(day_data.get("maxtempC")),
                    temp_min_c=self._safe_float(day_data.get("mintempC")),
                    temp_avg_c=self._safe_float(day_data.get("avgtempC")),
                    humidity_pct=avg_humidity,
                    wind_speed_kmh=avg_wind,
                    wind_direction_deg=avg_wind_dir,
                    precipitation_mm=total_precip if total_precip > 0 else None,
                    uv_index=self._safe_float(day_data.get("uvIndex")),
                    cloud_cover_pct=avg_cloud,
                    condition=day_data.get("hourly", [{}])[0].get("weatherDesc", [{}])[0].get("value") if hourly else None
                )
                forecast.append(forecast_day)
            except (ValueError, KeyError, IndexError):
                continue
        
        return ProviderResult(
            provider_name=self.name,
            now=now,
            forecast=forecast
        )
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
