"""
Base provider class and Pydantic models for weather data normalization.
"""
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


class WeatherNow(BaseModel):
    """Current weather conditions from a single provider."""
    provider_name: str
    fetched_at: datetime
    temperature_c: Optional[float] = None
    feels_like_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    precipitation_mm: Optional[float] = None
    pressure_hpa: Optional[float] = None
    visibility_km: Optional[float] = None
    uv_index: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    condition: Optional[str] = None


class ForecastDay(BaseModel):
    """Forecast for a single day from a single provider."""
    provider_name: str
    date: date
    temp_max_c: Optional[float] = None
    temp_min_c: Optional[float] = None
    temp_avg_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    precipitation_mm: Optional[float] = None
    uv_index: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    condition: Optional[str] = None


class ProviderResult(BaseModel):
    """Complete result from a single provider."""
    provider_name: str
    now: Optional[WeatherNow] = None
    forecast: list[ForecastDay] = Field(default_factory=list)


class ProviderError(BaseModel):
    """Error information from a failed provider."""
    provider_name: str
    reason: str


class WeatherProvider(ABC):
    """Abstract base class for weather providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this provider."""
        pass
    
    @property
    def requires_api_key(self) -> bool:
        """Whether this provider requires an API key."""
        return False
    
    @property
    def api_key(self) -> Optional[str]:
        """The API key for this provider, if required."""
        return None
    
    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        """Set the API key for this provider."""
        pass
    
    @property
    @abstractmethod
    def forecast_days(self) -> int:
        """Maximum number of forecast days this provider supports."""
        pass
    
    def is_available(self) -> bool:
        """Check if this provider is available (has required keys, etc.)."""
        return True
    
    @abstractmethod
    async def fetch(self, lat: float, lon: float, timeout: float) -> ProviderResult:
        """
        Fetch weather data for the given coordinates.
        
        Args:
            lat: Latitude
            lon: Longitude
            timeout: Request timeout in seconds
            
        Returns:
            ProviderResult with current conditions and forecast
            
        Raises:
            ProviderError on failure
        """
        pass
