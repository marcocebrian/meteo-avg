"""
FastAPI server for MeteoAvg dashboard.
Serves the HTML dashboard and provides SSE endpoint for weather data.
"""
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from core.aggregator import stream_provider_results
from core.averager import (
    average_current,
    average_forecasts,
    averaged_now_to_dict,
    averaged_forecast_day_to_dict,
)
from core.geocoder import Geocoder, GeocoderError
from providers.base import ProviderResult, WeatherNow, ForecastDay


# Create FastAPI app
app = FastAPI(title="MeteoAvg", docs_url=None, redoc_url=None)

# Get the web directory path
WEB_DIR = Path(__file__).parent

# Mount static files
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

# Templates
templates = Jinja2Templates(directory=WEB_DIR / "templates")


# Store for city info (set by app.py at startup or via search)
_city_info: dict = {}
_geocoder = Geocoder()


def set_city_info(city: str, lat: float, lon: float, display_name: str):
    """Set city info for the dashboard."""
    global _city_info
    _city_info = {
        "city": city,
        "lat": lat,
        "lon": lon,
        "display_name": display_name
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main dashboard page."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            **_city_info
        }
    )


@app.get("/api/city")
async def get_city():
    """Get current city info."""
    return _city_info


@app.get("/api/search")
async def search_city(
    q: str = Query(..., description="City name to search for"),
    count: int = Query(5, description="Maximum number of results")
):
    """
    Search for cities by name.
    
    Returns a list of matching cities with coordinates for user selection.
    """
    params = {
        "name": q,
        "count": count,
        "language": "en",
        "format": "json"
    }
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(_geocoder.GEOCODING_URL, params=params)
            response.raise_for_status()
            data = response.json()
        
        results = data.get("results", [])
        
        cities = []
        for r in results:
            # Build display name: City, Admin1, Country
            parts = [r.get("name", "")]
            if r.get("admin1"):
                parts.append(r["admin1"])
            if r.get("country"):
                parts.append(r["country"])
            display_name = ", ".join(parts)
            
            cities.append({
                "name": r.get("name", ""),
                "lat": r.get("latitude"),
                "lon": r.get("longitude"),
                "display_name": display_name,
                "country": r.get("country", ""),
                "admin1": r.get("admin1")
            })
        
        return {"cities": cities, "query": q}
    
    except httpx.TimeoutException:
        return {"error": "Geocoding service timed out", "cities": []}
    except httpx.HTTPStatusError as e:
        return {"error": f"Geocoding service error: {e.response.status_code}", "cities": []}
    except Exception as e:
        return {"error": str(e), "cities": []}


@app.post("/api/city")
async def set_city(request: Request):
    """Set the current city for weather data."""
    global _city_info
    data = await request.json()
    
    _city_info = {
        "city": data.get("name", ""),
        "lat": data.get("lat"),
        "lon": data.get("lon"),
        "display_name": data.get("display_name", "")
    }
    
    return {"success": True, **_city_info}


@app.get("/api/weather")
async def get_weather(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    timeout: float = Query(10.0, description="Request timeout in seconds")
):
    """
    Stream weather data via Server-Sent Events (SSE).
    
    Events:
    - provider_result: Emitted when a provider successfully returns data
    - provider_error: Emitted when a provider fails
    - averaged_update: Emitted after each provider with running average
    - done: Emitted when all providers have responded
    """
    
    async def event_generator():
        results: list[ProviderResult] = []
        errors: list[dict] = []
        
        async for data in stream_provider_results(lat, lon, timeout):
            event_type = data["type"]
            
            if event_type == "provider_result":
                # Reconstruct WeatherNow from dict
                now = None
                if data.get("now"):
                    now = WeatherNow(**data["now"])
                
                # Reconstruct ForecastDay list from dict
                forecast = []
                for f in data.get("forecast", []):
                    forecast.append(ForecastDay(**f))
                
                # Store result for averaging
                result = ProviderResult(
                    provider_name=data["provider"],
                    now=now,
                    forecast=forecast
                )
                results.append(result)
                
                # Send provider result event
                yield f"event: provider_result\ndata: {json.dumps(data)}\n\n"
                
                # Compute and send running average
                averaged_now = average_current(results)
                averaged_forecast = average_forecasts(results)
                
                averaged_data = {
                    "provider_count": len(results),
                    "now": averaged_now_to_dict(averaged_now),
                    "forecast": [averaged_forecast_day_to_dict(d) for d in averaged_forecast]
                }
                yield f"event: averaged_update\ndata: {json.dumps(averaged_data)}\n\n"
                
            elif event_type == "provider_error":
                errors.append(data)
                yield f"event: provider_error\ndata: {json.dumps(data)}\n\n"
        
        # Send done event
        done_data = {
            "total_providers": len(results) + len(errors),
            "successful": len(results),
            "failed": len(errors)
        }
        yield f"event: done\ndata: {json.dumps(done_data)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
