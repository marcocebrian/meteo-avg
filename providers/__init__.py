"""
Provider registry for MeteoAvg.

Providers are registered explicitly in this file.
To add a new provider:
1. Create a new file in this directory (e.g., my_provider.py)
2. Import and add it to the ALL_PROVIDERS list below
"""
from typing import Optional
from .base import WeatherProvider, ProviderResult, ProviderError
from .open_meteo import OpenMeteoProvider
from .wttr_in import WttrInProvider
from .seven_timer import SevenTimerProvider
from .openweathermap import OpenWeatherMapProvider
from .weatherapi import WeatherAPIProvider
from .tomorrow_io import TomorrowIOProvider
from .weatherbit import WeatherbitProvider

__all__ = [
    "WeatherProvider",
    "ProviderResult", 
    "ProviderError",
    "ALL_PROVIDERS",
    "configure_providers",
    "get_available_providers",
]

# Provider instances
ALL_PROVIDERS = [
    OpenMeteoProvider(),
    WttrInProvider(),
    SevenTimerProvider(),
    OpenWeatherMapProvider(),
    WeatherAPIProvider(),
    TomorrowIOProvider(),
    WeatherbitProvider(),
]


def configure_providers(
    owm_api_key: Optional[str] = None,
    weatherapi_key: Optional[str] = None,
    tomorrow_api_key: Optional[str] = None,
    weatherbit_key: Optional[str] = None,
) -> None:
    """
    Configure API keys for providers that require them.
    
    Args:
        owm_api_key: OpenWeatherMap API key
        weatherapi_key: WeatherAPI.com API key
        tomorrow_api_key: Tomorrow.io API key
        weatherbit_key: Weatherbit.io API key
    """
    for provider in ALL_PROVIDERS:
        if provider.name == "openweathermap" and owm_api_key:
            provider.api_key = owm_api_key
        elif provider.name == "weatherapi" and weatherapi_key:
            provider.api_key = weatherapi_key
        elif provider.name == "tomorrow_io" and tomorrow_api_key:
            provider.api_key = tomorrow_api_key
        elif provider.name == "weatherbit" and weatherbit_key:
            provider.api_key = weatherbit_key


def get_available_providers() -> list[WeatherProvider]:
    """
    Get list of providers that are available (have required API keys).
    
    Returns:
        List of available WeatherProvider instances
    """
    return [p for p in ALL_PROVIDERS if p.is_available()]


def get_provider_by_name(name: str) -> Optional[WeatherProvider]:
    """
    Get a provider by its name.
    
    Args:
        name: Provider name (e.g., "open_meteo")
        
    Returns:
        WeatherProvider instance or None if not found
    """
    for provider in ALL_PROVIDERS:
        if provider.name == name:
            return provider
    return None
