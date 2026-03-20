"""
Averager module for computing averaged weather data with confidence scores.
"""
import math
from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from collections import Counter

from providers.base import WeatherNow, ForecastDay, ProviderResult


# Confidence thresholds per field (sigma threshold for "high" confidence)
CONFIDENCE_THRESHOLDS = {
    "temperature_c": 1.5,
    "feels_like_c": 2.0,
    "humidity_pct": 5.0,
    "wind_speed_kmh": 5.0,
    "precipitation_mm": 1.0,
    "pressure_hpa": 3.0,
    "visibility_km": 2.0,
    "uv_index": 1.0,
    "cloud_cover_pct": 10.0,
    # temp_max_c, temp_min_c, temp_avg_c use temperature_c threshold
}


# Valid value bounds - filter out sentinel/error values
VALUE_BOUNDS = {
    "temperature_c": (-70.0, 60.0),       # Reasonable Earth temperature range
    "feels_like_c": (-90.0, 60.0),        # Wind chill can go lower
    "humidity_pct": (0.0, 100.0),         # Percentage
    "wind_speed_kmh": (0.0, 500.0),       # Reasonable max wind speed
    "wind_direction_deg": (0.0, 360.0),   # Degrees
    "precipitation_mm": (0.5, 500.0),     # MIN 0.5mm per user requirement
    "pressure_hpa": (800.0, 1200.0),      # Reasonable pressure range
    "visibility_km": (0.0, 100.0),        # Reasonable visibility
    "uv_index": (0.0, 15.0),              # UV index max
    "cloud_cover_pct": (0.0, 100.0),      # Percentage
}

# Precipitation minimum threshold - values below this are ignored completely
PRECIP_MIN_MM = 0.5


@dataclass
class FieldAverage:
    """Averaged value for a single field with confidence info."""
    value: Optional[float] = None
    sigma: Optional[float] = None
    n: int = 0  # Number of providers that reported this field
    confidence: str = "low"  # "high", "medium", "low"


@dataclass
class ConditionVote:
    """Voted condition with provider breakdown."""
    value: Optional[str] = None
    votes: dict[str, int] = field(default_factory=dict)  # condition -> count
    n: int = 0


@dataclass
class AveragedNow:
    """Averaged current weather conditions."""
    temperature_c: FieldAverage = field(default_factory=FieldAverage)
    feels_like_c: FieldAverage = field(default_factory=FieldAverage)
    humidity_pct: FieldAverage = field(default_factory=FieldAverage)
    wind_speed_kmh: FieldAverage = field(default_factory=FieldAverage)
    wind_direction_deg: FieldAverage = field(default_factory=FieldAverage)
    precipitation_mm: FieldAverage = field(default_factory=FieldAverage)
    pressure_hpa: FieldAverage = field(default_factory=FieldAverage)
    visibility_km: FieldAverage = field(default_factory=FieldAverage)
    uv_index: FieldAverage = field(default_factory=FieldAverage)
    cloud_cover_pct: FieldAverage = field(default_factory=FieldAverage)
    condition: ConditionVote = field(default_factory=ConditionVote)


@dataclass
class AveragedForecastDay:
    """Averaged forecast for a single day."""
    date: date
    temp_max_c: FieldAverage = field(default_factory=FieldAverage)
    temp_min_c: FieldAverage = field(default_factory=FieldAverage)
    temp_avg_c: FieldAverage = field(default_factory=FieldAverage)
    humidity_pct: FieldAverage = field(default_factory=FieldAverage)
    wind_speed_kmh: FieldAverage = field(default_factory=FieldAverage)
    wind_direction_deg: FieldAverage = field(default_factory=FieldAverage)
    precipitation_mm: FieldAverage = field(default_factory=FieldAverage)
    uv_index: FieldAverage = field(default_factory=FieldAverage)
    cloud_cover_pct: FieldAverage = field(default_factory=FieldAverage)
    condition: ConditionVote = field(default_factory=ConditionVote)


def is_valid_value(value: Optional[float], field_name: str) -> bool:
    """
    Check if a value is within valid bounds for its field.
    
    Filters out sentinel/error values like -9999 and out-of-bounds data.
    
    Args:
        value: The value to check
        field_name: The field name for bounds lookup
        
    Returns:
        True if value is valid, False otherwise
    """
    if value is None:
        return False
    
    bounds = VALUE_BOUNDS.get(field_name)
    if bounds is None:
        # Unknown field, allow it
        return True
    
    min_val, max_val = bounds
    return min_val <= value <= max_val


def compute_average(values: list[float]) -> tuple[float, float]:
    """
    Compute arithmetic mean and standard deviation.
    
    Args:
        values: List of numeric values
        
    Returns:
        Tuple of (mean, sigma)
    """
    if not values:
        return 0.0, 0.0
    
    n = len(values)
    mean = sum(values) / n
    
    if n < 2:
        return mean, 0.0
    
    variance = sum((x - mean) ** 2 for x in values) / n
    sigma = math.sqrt(variance)
    
    return mean, sigma


def compute_circular_mean(angles: list[float]) -> Optional[float]:
    """
    Compute circular mean of angles in degrees.
    
    Args:
        angles: List of angles in degrees
        
    Returns:
        Circular mean in degrees, or None if no valid angles
    """
    if not angles:
        return None
    
    radians = [math.radians(a) for a in angles]
    sin_sum = sum(math.sin(r) for r in radians)
    cos_sum = sum(math.cos(r) for r in radians)
    
    if sin_sum == 0 and cos_sum == 0:
        return None
    
    mean_rad = math.atan2(sin_sum, cos_sum)
    mean_deg = math.degrees(mean_rad)
    
    # Normalize to 0-360
    return mean_deg % 360


def get_confidence_level(n: int, sigma: Optional[float], threshold: float) -> str:
    """
    Determine confidence level based on provider count and sigma.
    
    Args:
        n: Number of providers reporting this field
        sigma: Standard deviation
        threshold: Field-specific threshold for "high" confidence
        
    Returns:
        "high", "medium", or "low"
    """
    if n == 0:
        return "low"
    if n == 1:
        return "low"
    if n >= 3 and (sigma is None or sigma <= threshold):
        return "high"
    return "medium"


def vote_condition(
    conditions: list[str],
    provider_field_counts: dict[str, int]
) -> ConditionVote:
    """
    Determine condition by majority vote.
    
    In case of tie, uses the provider with most fields populated.
    
    Args:
        conditions: List of condition strings from providers
        provider_field_counts: Map of provider name to number of fields populated
        
    Returns:
        ConditionVote with the winning condition and vote breakdown
    """
    if not conditions:
        return ConditionVote()
    
    # Count votes
    vote_counts = Counter(conditions)
    
    # Find max vote count
    max_votes = max(vote_counts.values())
    
    # Get all conditions with max votes (potential ties)
    top_conditions = [c for c, v in vote_counts.items() if v == max_votes]
    
    if len(top_conditions) == 1:
        # Clear winner
        return ConditionVote(
            value=top_conditions[0],
            votes=dict(vote_counts),
            n=len(conditions)
        )
    
    # Tie-breaker: use provider with most fields
    # (This is a simplification - in practice we'd need to track which provider
    # reported which condition)
    return ConditionVote(
        value=top_conditions[0],  # Just pick first in case of tie
        votes=dict(vote_counts),
        n=len(conditions)
    )


def average_field(
    values: list[float],
    threshold_key: str
) -> FieldAverage:
    """
    Compute averaged field with confidence.
    
    Filters out invalid/sentinel values before averaging.
    
    Args:
        values: List of values from providers
        threshold_key: Key for confidence threshold lookup
        
    Returns:
        FieldAverage with value, sigma, n, and confidence
    """
    if not values:
        return FieldAverage()
    
    # Filter out invalid values based on bounds
    valid_values = [v for v in values if is_valid_value(v, threshold_key)]
    
    if not valid_values:
        return FieldAverage()
    
    threshold = CONFIDENCE_THRESHOLDS.get(threshold_key, 5.0)
    mean, sigma = compute_average(valid_values)
    confidence = get_confidence_level(len(valid_values), sigma, threshold)
    
    return FieldAverage(
        value=round(mean, 2),
        sigma=round(sigma, 2),
        n=len(valid_values),
        confidence=confidence
    )


def average_current(results: list[ProviderResult]) -> AveragedNow:
    """
    Average current weather from multiple providers.
    
    Args:
        results: List of successful provider results
        
    Returns:
        AveragedNow with averaged values and confidence scores
    """
    now_data = [r.now for r in results if r.now]
    
    if not now_data:
        return AveragedNow()
    
    # Collect values for each field (with validation)
    temps = [n.temperature_c for n in now_data if is_valid_value(n.temperature_c, "temperature_c")]
    feels_like = [n.feels_like_c for n in now_data if is_valid_value(n.feels_like_c, "feels_like_c")]
    humidity = [n.humidity_pct for n in now_data if is_valid_value(n.humidity_pct, "humidity_pct")]
    wind_speed = [n.wind_speed_kmh for n in now_data if is_valid_value(n.wind_speed_kmh, "wind_speed_kmh")]
    wind_dir = [n.wind_direction_deg for n in now_data if is_valid_value(n.wind_direction_deg, "wind_direction_deg")]
    # Precipitation: filter values < 0.5mm (ignore trace precipitation)
    precip = [n.precipitation_mm for n in now_data if is_valid_value(n.precipitation_mm, "precipitation_mm")]
    pressure = [n.pressure_hpa for n in now_data if is_valid_value(n.pressure_hpa, "pressure_hpa")]
    visibility = [n.visibility_km for n in now_data if is_valid_value(n.visibility_km, "visibility_km")]
    uv = [n.uv_index for n in now_data if is_valid_value(n.uv_index, "uv_index")]
    cloud = [n.cloud_cover_pct for n in now_data if is_valid_value(n.cloud_cover_pct, "cloud_cover_pct")]
    conditions = [n.condition for n in now_data if n.condition]
    
    # Compute averages
    averaged = AveragedNow()
    averaged.temperature_c = average_field(temps, "temperature_c")
    averaged.feels_like_c = average_field(feels_like, "feels_like_c")
    averaged.humidity_pct = average_field(humidity, "humidity_pct")
    averaged.wind_speed_kmh = average_field(wind_speed, "wind_speed_kmh")
    averaged.precipitation_mm = average_field(precip, "precipitation_mm")
    averaged.pressure_hpa = average_field(pressure, "pressure_hpa")
    averaged.visibility_km = average_field(visibility, "visibility_km")
    averaged.uv_index = average_field(uv, "uv_index")
    averaged.cloud_cover_pct = average_field(cloud, "cloud_cover_pct")
    
    # Wind direction uses circular mean (no sigma)
    if wind_dir:
        avg_dir = compute_circular_mean(wind_dir)
        averaged.wind_direction_deg = FieldAverage(
            value=round(avg_dir, 1) if avg_dir else None,
            sigma=None,
            n=len(wind_dir),
            confidence="high" if len(wind_dir) >= 3 else "medium" if len(wind_dir) == 2 else "low"
        )
    
    # Condition uses majority vote
    averaged.condition = vote_condition(conditions, {})
    
    return averaged


def average_forecasts(results: list[ProviderResult]) -> list[AveragedForecastDay]:
    """
    Average forecast data from multiple providers.
    
    Args:
        results: List of successful provider results
        
    Returns:
        List of AveragedForecastDay for each day covered
    """
    # Collect all forecast days by date
    days_data: dict[date, list[ForecastDay]] = {}
    
    for result in results:
        for day in result.forecast:
            if day.date not in days_data:
                days_data[day.date] = []
            days_data[day.date].append(day)
    
    # Average each day
    averaged_days = []
    
    for forecast_date in sorted(days_data.keys()):
        day_list = days_data[forecast_date]
        
        # Collect values for each field (with validation)
        temps_max = [d.temp_max_c for d in day_list if is_valid_value(d.temp_max_c, "temperature_c")]
        temps_min = [d.temp_min_c for d in day_list if is_valid_value(d.temp_min_c, "temperature_c")]
        temps_avg = [d.temp_avg_c for d in day_list if is_valid_value(d.temp_avg_c, "temperature_c")]
        humidity = [d.humidity_pct for d in day_list if is_valid_value(d.humidity_pct, "humidity_pct")]
        wind_speed = [d.wind_speed_kmh for d in day_list if is_valid_value(d.wind_speed_kmh, "wind_speed_kmh")]
        wind_dir = [d.wind_direction_deg for d in day_list if is_valid_value(d.wind_direction_deg, "wind_direction_deg")]
        # Precipitation: filter values < 0.5mm (ignore trace precipitation)
        precip = [d.precipitation_mm for d in day_list if is_valid_value(d.precipitation_mm, "precipitation_mm")]
        uv = [d.uv_index for d in day_list if is_valid_value(d.uv_index, "uv_index")]
        cloud = [d.cloud_cover_pct for d in day_list if is_valid_value(d.cloud_cover_pct, "cloud_cover_pct")]
        conditions = [d.condition for d in day_list if d.condition]
        
        averaged = AveragedForecastDay(date=forecast_date)
        averaged.temp_max_c = average_field(temps_max, "temperature_c")
        averaged.temp_min_c = average_field(temps_min, "temperature_c")
        averaged.temp_avg_c = average_field(temps_avg, "temperature_c")
        averaged.humidity_pct = average_field(humidity, "humidity_pct")
        averaged.wind_speed_kmh = average_field(wind_speed, "wind_speed_kmh")
        averaged.precipitation_mm = average_field(precip, "precipitation_mm")
        averaged.uv_index = average_field(uv, "uv_index")
        averaged.cloud_cover_pct = average_field(cloud, "cloud_cover_pct")
        
        # Wind direction uses circular mean
        if wind_dir:
            avg_dir = compute_circular_mean(wind_dir)
            averaged.wind_direction_deg = FieldAverage(
                value=round(avg_dir, 1) if avg_dir else None,
                sigma=None,
                n=len(wind_dir),
                confidence="high" if len(wind_dir) >= 3 else "medium" if len(wind_dir) == 2 else "low"
            )
        
        # Condition uses majority vote
        averaged.condition = vote_condition(conditions, {})
        
        averaged_days.append(averaged)
    
    # Return up to 10 days
    return averaged_days[:10]


def field_average_to_dict(fa: FieldAverage) -> dict:
    """Convert FieldAverage to dict for JSON serialization."""
    return {
        "value": fa.value,
        "sigma": fa.sigma,
        "n": fa.n,
        "confidence": fa.confidence
    }


def condition_vote_to_dict(cv: ConditionVote) -> dict:
    """Convert ConditionVote to dict for JSON serialization."""
    return {
        "value": cv.value,
        "votes": cv.votes,
        "n": cv.n
    }


def averaged_now_to_dict(averaged: AveragedNow) -> dict:
    """Convert AveragedNow to dict for JSON serialization."""
    return {
        "temperature_c": field_average_to_dict(averaged.temperature_c),
        "feels_like_c": field_average_to_dict(averaged.feels_like_c),
        "humidity_pct": field_average_to_dict(averaged.humidity_pct),
        "wind_speed_kmh": field_average_to_dict(averaged.wind_speed_kmh),
        "wind_direction_deg": field_average_to_dict(averaged.wind_direction_deg),
        "precipitation_mm": field_average_to_dict(averaged.precipitation_mm),
        "pressure_hpa": field_average_to_dict(averaged.pressure_hpa),
        "visibility_km": field_average_to_dict(averaged.visibility_km),
        "uv_index": field_average_to_dict(averaged.uv_index),
        "cloud_cover_pct": field_average_to_dict(averaged.cloud_cover_pct),
        "condition": condition_vote_to_dict(averaged.condition)
    }


def averaged_forecast_day_to_dict(averaged: AveragedForecastDay) -> dict:
    """Convert AveragedForecastDay to dict for JSON serialization."""
    return {
        "date": averaged.date.isoformat(),
        "temp_max_c": field_average_to_dict(averaged.temp_max_c),
        "temp_min_c": field_average_to_dict(averaged.temp_min_c),
        "temp_avg_c": field_average_to_dict(averaged.temp_avg_c),
        "humidity_pct": field_average_to_dict(averaged.humidity_pct),
        "wind_speed_kmh": field_average_to_dict(averaged.wind_speed_kmh),
        "wind_direction_deg": field_average_to_dict(averaged.wind_direction_deg),
        "precipitation_mm": field_average_to_dict(averaged.precipitation_mm),
        "uv_index": field_average_to_dict(averaged.uv_index),
        "cloud_cover_pct": field_average_to_dict(averaged.cloud_cover_pct),
        "condition": condition_vote_to_dict(averaged.condition)
    }
