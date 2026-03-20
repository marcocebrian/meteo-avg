"""
Geocoder module for resolving city names to coordinates.
Uses Open-Meteo's free geocoding API.
"""
import httpx
from dataclasses import dataclass
from typing import Optional


@dataclass
class GeoResult:
    """Result from geocoding a city name."""
    lat: float
    lon: float
    display_name: str
    country: str
    admin1: Optional[str] = None  # State/Province/Region


class GeocoderError(Exception):
    """Exception raised when geocoding fails."""
    pass


class CityNotFoundError(GeocoderError):
    """Exception raised when a city cannot be found."""
    pass


class AmbiguousCityError(GeocoderError):
    """Exception raised when multiple cities match the query."""
    
    def __init__(self, matches: list[GeoResult]):
        self.matches = matches
        super().__init__(f"Multiple cities found: {[m.display_name for m in matches]}")


class GeocoderUnavailableError(GeocoderError):
    """Exception raised when the geocoding service is unavailable."""
    pass


class Geocoder:
    """Geocoder using Open-Meteo's free geocoding API."""
    
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
    
    async def geocode(self, city_name: str) -> GeoResult:
        """
        Resolve a city name to coordinates.
        
        Args:
            city_name: Name of the city to geocode
            
        Returns:
            GeoResult with coordinates and display name
            
        Raises:
            CityNotFoundError: If the city cannot be found
            AmbiguousCityError: If multiple cities match (returns top 5)
            GeocoderUnavailableError: If the geocoding service is unavailable
        """
        params = {
            "name": city_name,
            "count": 5,
            "language": "en",
            "format": "json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.GEOCODING_URL, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            raise GeocoderUnavailableError("Geocoding service timed out")
        except httpx.HTTPStatusError as e:
            raise GeocoderUnavailableError(f"Geocoding service error: {e.response.status_code}")
        except httpx.RequestError as e:
            raise GeocoderUnavailableError(f"Geocoding service unavailable: {e}")
        
        results = data.get("results", [])
        
        if not results:
            raise CityNotFoundError(f"City '{city_name}' not found. Try a different spelling.")
        
        # Convert results to GeoResult objects
        geo_results = []
        for r in results:
            # Build display name: City, Admin1, Country
            parts = [r.get("name", "")]
            if r.get("admin1"):
                parts.append(r["admin1"])
            if r.get("country"):
                parts.append(r["country"])
            display_name = ", ".join(parts)
            
            geo_results.append(GeoResult(
                lat=r.get("latitude"),
                lon=r.get("longitude"),
                display_name=display_name,
                country=r.get("country", ""),
                admin1=r.get("admin1")
            ))
        
        # If multiple results, check for exact match
        city_lower = city_name.lower().strip()
        exact_matches = [g for g in geo_results if g.display_name.lower().startswith(city_lower)]
        
        # If exactly one match starts with the city name, return it
        if len(exact_matches) == 1:
            return exact_matches[0]
        
        # If multiple matches start with the city name, prefer the first one
        # (Open-Meteo returns results sorted by relevance)
        if len(exact_matches) > 1:
            # Check if the first result is clearly the main city (population heuristic)
            # Usually the most relevant result is listed first
            return exact_matches[0]
        
        # If multiple results (and no match starts with city name), return all for user selection
        if len(geo_results) > 1:
            raise AmbiguousCityError(geo_results)
        
        return geo_results[0]
    
    def format_ambiguous_options(self, matches: list[GeoResult]) -> str:
        """
        Format ambiguous city matches for display.
        
        Args:
            matches: List of GeoResult objects
            
        Returns:
            Formatted string for user display
        """
        lines = ["Multiple cities found. Please select one:"]
        for i, match in enumerate(matches, 1):
            lines.append(f"  {i}. {match.display_name}")
        lines.append(f"  Enter number (1-{len(matches)}): ")
        return "\n".join(lines)
