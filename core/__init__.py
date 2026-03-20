"""
Core modules for MeteoAvg.
"""
from core.geocoder import Geocoder, GeoResult, CityNotFoundError, AmbiguousCityError
from core.aggregator import Aggregator, stream_provider_results
from core.averager import (
    average_current,
    average_forecasts,
    averaged_now_to_dict,
    averaged_forecast_day_to_dict,
)

__all__ = [
    "Geocoder",
    "GeoResult",
    "CityNotFoundError",
    "AmbiguousCityError",
    "Aggregator",
    "stream_provider_results",
    "average_current",
    "average_forecasts",
    "averaged_now_to_dict",
    "averaged_forecast_day_to_dict",
]
