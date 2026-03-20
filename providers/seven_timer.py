"""
7timer.info weather provider - free, no API key required.
Supports up to 8 days forecast.
API Documentation: http://www.7timer.info/doc.php
"""
import httpx
from datetime import datetime, date, timedelta
from typing import Optional
from .base import WeatherProvider, ProviderResult, WeatherNow, ForecastDay


class SevenTimerProvider(WeatherProvider):
    """Provider for 7timer.info API (free, no key required)."""
    
    BASE_URL = "https://www.7timer.info/bin/api.pl"
    
    # Weather code to condition mapping
    WEATHER_CODES = {
        "clear": "Clear sky",
        "cloudy": "Cloudy",
        "fog": "Fog",
        "haze": "Haze",
        "ishower": "Isolated showers",
        "lightrain": "Light rain",
        "lightsnow": "Light snow",
        "mcloudy": "Mostly cloudy",
        "oshower": "Occasional showers",
        "pcloudy": "Partly cloudy",
        "rain": "Rain",
        "rainsnow": "Rain and snow",
        "snow": "Snow",
        "ts": "Thunderstorm",
        "tshower": "Thundershowers",
        "wind": "Windy",
        "cloudyday": "Cloudy",
        "cloudynight": "Cloudy",
        "clearday": "Clear",
        "clearnight": "Clear",
        "pcloudyday": "Partly cloudy",
        "pcloudynight": "Partly cloudy",
        "mcloudyday": "Mostly cloudy",
        "mcloudynight": "Mostly cloudy",
        "lightrainday": "Light rain",
        "lightrainnight": "Light rain",
        "rainday": "Rain",
        "rainnight": "Rain",
        "snowday": "Snow",
        "snownight": "Snow",
        "tsday": "Thunderstorm",
        "tsnight": "Thunderstorm",
    }
    
    @property
    def name(self) -> str:
        return "seven_timer"
    
    @property
    def forecast_days(self) -> int:
        return 8
    
    async def fetch(self, lat: float, lon: float, timeout: float) -> ProviderResult:
        """Fetch weather data from 7timer.info."""
        
        params = {
            "lat": round(lat, 1),  # 7timer prefers rounded coordinates
            "lon": round(lon, 1),
            "product": "civil",  # 3-hourly data with detailed metrics
            "output": "json"
        }
        
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
        
        return self._parse(data)
    
    def _parse(self, data: dict) -> ProviderResult:
        """Parse 7timer API response into normalized schema."""
        fetched_at = datetime.utcnow()
        
        dataseries = data.get("dataseries", [])
        
        if not dataseries:
            return ProviderResult(
                provider_name=self.name,
                now=None,
                forecast=[]
            )
        
        # Get the first entry as "current" approximation
        first_entry = dataseries[0]
        now = WeatherNow(
            provider_name=self.name,
            fetched_at=fetched_at,
            temperature_c=first_entry.get("temp2m"),
            feels_like_c=None,  # Not provided
            humidity_pct=self._parse_humidity(first_entry.get("rh2m")),
            wind_speed_kmh=self._beaufort_to_kmh(first_entry.get("wind10m", {}).get("speed")),
            wind_direction_deg=self._direction_to_deg(first_entry.get("wind10m", {}).get("direction")),
            precipitation_mm=self._precip_amount_to_mm(first_entry.get("prec_amount")),
            pressure_hpa=None,  # Not provided
            visibility_km=None,  # Not provided
            uv_index=None,  # Not provided
            cloud_cover_pct=first_entry.get("cloudcover"),  # 0-9 scale, roughly oktaves
            condition=self.WEATHER_CODES.get(first_entry.get("weather"), "Unknown")
        )
        
        # Group by day (each entry is 3-hourly)
        days_data = {}
        
        for entry in dataseries:
            timepoint = entry.get("timepoint", 0)  # Hours from now
            day_offset = timepoint // 24
            
            if day_offset not in days_data:
                days_data[day_offset] = {
                    "entries": [],
                    "date": date.today() + timedelta(days=day_offset)
                }
            days_data[day_offset]["entries"].append(entry)
        
        # Process each day
        forecast = []
        
        for day_offset, day_info in sorted(days_data.items()):
            entries = day_info["entries"]
            
            temps = [e.get("temp2m") for e in entries if isinstance(e.get("temp2m"), (int, float))]
            humidities = [self._parse_humidity(e.get("rh2m")) for e in entries if e.get("rh2m")]
            wind_speeds = [self._beaufort_to_kmh(e.get("wind10m", {}).get("speed")) for e in entries]
            wind_dirs = [self._direction_to_deg(e.get("wind10m", {}).get("direction")) for e in entries]
            precips = [self._precip_amount_to_mm(e.get("prec_amount")) for e in entries]
            clouds = [e.get("cloudcover") for e in entries if e.get("cloudcover") is not None]
            conditions = [self.WEATHER_CODES.get(e.get("weather"), "Unknown") for e in entries]
            
            temp_max = max(temps) if temps else None
            temp_min = min(temps) if temps else None
            temp_avg = sum(temps) / len(temps) if temps else None
            humidity_avg = sum(humidities) / len(humidities) if humidities else None
            
            # Calculate average wind speed
            valid_wind_speeds = [w for w in wind_speeds if w is not None]
            avg_wind_speed = sum(valid_wind_speeds) / len(valid_wind_speeds) if valid_wind_speeds else None
            
            # Calculate circular mean for wind direction
            avg_wind_dir = None
            valid_wind_dirs = [d for d in wind_dirs if d is not None]
            if valid_wind_dirs:
                import math
                sin_sum = sum(math.sin(math.radians(d)) for d in valid_wind_dirs)
                cos_sum = sum(math.cos(math.radians(d)) for d in valid_wind_dirs)
                if sin_sum != 0 or cos_sum != 0:
                    avg_wind_dir = math.degrees(math.atan2(sin_sum, cos_sum)) % 360
            
            # Total precipitation
            total_precip = sum(p for p in precips if p is not None)
            
            # Average cloud cover
            avg_cloud = sum(clouds) / len(clouds) if clouds else None
            
            # Most common condition
            condition = max(set(conditions), key=conditions.count) if conditions else None
            
            forecast_day = ForecastDay(
                provider_name=self.name,
                date=day_info["date"],
                temp_max_c=temp_max,
                temp_min_c=temp_min,
                temp_avg_c=temp_avg,
                humidity_pct=humidity_avg,
                wind_speed_kmh=avg_wind_speed,
                wind_direction_deg=avg_wind_dir,
                precipitation_mm=total_precip if total_precip > 0 else None,
                uv_index=None,  # Not provided
                cloud_cover_pct=avg_cloud,
                condition=condition
            )
            forecast.append(forecast_day)
        
        return ProviderResult(
            provider_name=self.name,
            now=now,
            forecast=forecast
        )
    
    def _parse_humidity(self, rh: Optional[str]) -> Optional[float]:
        """Parse humidity string like '76%' to float."""
        if rh is None:
            return None
        try:
            return float(str(rh).replace('%', ''))
        except (ValueError, TypeError):
            return None
    
    def _precip_amount_to_mm(self, amount: Optional[int]) -> Optional[float]:
        """Convert 7timer precipitation amount to mm."""
        # 7timer uses: 0=none, 1=<1mm, 2=1-5mm, 3=5-10mm, 4=10-20mm, 5=>20mm
        if amount is None:
            return None
        mapping = {0: 0, 1: 0.5, 2: 3, 3: 7.5, 4: 15, 5: 25}
        return mapping.get(amount, 0)
    
    def _beaufort_to_kmh(self, beaufort: Optional[int]) -> Optional[float]:
        """Convert Beaufort scale to km/h."""
        if beaufort is None:
            return None
        
        # Beaufort scale to km/h ranges (using midpoint)
        beaufort_ranges = {
            0: 0.5,    # Calm: < 1 km/h
            1: 3.5,    # Light air: 1-5 km/h
            2: 10,     # Light breeze: 6-11 km/h
            3: 18.5,   # Gentle breeze: 12-19 km/h
            4: 28,     # Moderate breeze: 20-28 km/h
            5: 38.5,   # Fresh breeze: 29-38 km/h
            6: 50,     # Strong breeze: 39-49 km/h
            7: 61.5,   # Near gale: 51-62 km/h
            8: 74.5,   # Gale: 63-75 km/h
            9: 87.5,   # Strong gale: 76-87 km/h
            10: 101.5, # Storm: 88-102 km/h
            11: 115.5, # Violent storm: 103-117 km/h
            12: 125    # Hurricane: ≥ 118 km/h
        }
        return beaufort_ranges.get(beaufort, None)
    
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
