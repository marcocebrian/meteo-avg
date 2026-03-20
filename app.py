#!/usr/bin/env python3
"""
MeteoAvg - Multi-provider weather aggregator.

A local Python app that queries all available free weather APIs for a user-specified
city, normalizes their responses, averages overlapping fields, and displays results
in a local web dashboard with confidence scores and provider breakdown.

Usage:
    python app.py

Then enter a city name when prompted.
"""
import asyncio
import os
import sys
import webbrowser
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from providers import configure_providers, get_available_providers
from core.geocoder import (
    Geocoder,
    GeoResult,
    CityNotFoundError,
    AmbiguousCityError,
    GeocoderUnavailableError,
)
from web.server import app, set_city_info


def load_environment():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)

    # Configure providers with API keys from environment
    configure_providers(
        owm_api_key=os.getenv("OWM_API_KEY"),
        weatherapi_key=os.getenv("WEATHERAPI_KEY"),
        tomorrow_api_key=os.getenv("TOMORROW_API_KEY"),
        weatherbit_key=os.getenv("WEATHERBIT_KEY"),
    )


def get_settings():
    """Get application settings from environment."""
    return {
        "timeout": float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10")),
        "port": int(os.getenv("PORT", "8000")),
    }


def prompt_for_city() -> GeoResult:
    """
    Prompt user for a city name and resolve it to coordinates.

    Returns:
        GeoResult with coordinates and display name

    Raises:
        SystemExit on unrecoverable errors
    """
    geocoder = Geocoder()

    while True:
        city_input = input("\nEnter city name: ").strip()

        if not city_input:
            print("Please enter a city name.")
            continue

        try:
            # Try to geocode the city
            result = asyncio.run(geocoder.geocode(city_input))
            return result

        except CityNotFoundError as e:
            print(f"\nCity not found. Try a different spelling.")
            continue

        except AmbiguousCityError as e:
            # Show top 5 matches and let user pick
            print(geocoder.format_ambiguous_options(e.matches))

            while True:
                try:
                    choice = input("Enter number: ").strip()
                    idx = int(choice) - 1
                    if 0 <= idx < len(e.matches):
                        return e.matches[idx]
                    print(f"Please enter a number between 1 and {len(e.matches)}")
                except ValueError:
                    print("Please enter a valid number.")

        except GeocoderUnavailableError as e:
            print(f"\nGeocoding unavailable. Check your connection.")
            print(f"Error: {e}")
            sys.exit(1)


def find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """
    Find an available port starting from start_port.

    Args:
        start_port: Port to start checking from
        max_attempts: Maximum number of ports to try

    Returns:
        Available port number

    Raises:
        SystemExit if no port is available
    """
    import socket

    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue

    print(f"\nNo available ports found between {start_port} and {start_port + max_attempts - 1}")
    print("Close any applications using these ports and try again.")
    sys.exit(1)


def open_browser(url: str):
    """Open URL in default browser."""
    import threading
    import time

    def _open():
        time.sleep(1)  # Give server a moment to start
        webbrowser.open(url)

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def print_startup_info(city_result: GeoResult, available_providers: list):
    """Print startup information."""
    print("\n" + "=" * 60)
    print("  MeteoAvg - Multi-provider Weather Aggregator")
    print("=" * 60)
    print(f"\n  Location: {city_result.display_name}")
    print(f"  Coordinates: {city_result.lat:.4f}°, {city_result.lon:.4f}°")
    print(f"\n  Available providers ({len(available_providers)}):")
    for p in available_providers:
        key_status = "✓" if not p.requires_api_key else "🔑"
        print(f"    {key_status} {p.name.replace('_', ' ').title()} ({p.forecast_days} days)")
    print("\n" + "-" * 60)


def main():
    """Main entry point."""
    # Load environment and configure providers
    load_environment()

    # Get settings
    settings = get_settings()

    # Prompt for city
    print("\n🌤️  MeteoAvg - Weather Data Aggregator")
    print("-" * 40)

    city_result = prompt_for_city()

    # Get available providers
    available_providers = get_available_providers()

    if not available_providers:
        print("\nNo weather providers available!")
        print("Please check your .env file for API keys.")
        sys.exit(1)

    # Print startup info
    print_startup_info(city_result, available_providers)

    # Set city info in server
    set_city_info(
        city=city_result.display_name,
        lat=city_result.lat,
        lon=city_result.lon,
        display_name=city_result.display_name
    )

    # Find available port
    port = find_available_port(settings["port"])
    url = f"http://127.0.0.1:{port}"

    print(f"\n  Starting server at: {url}")
    print("  Press Ctrl+C to stop the server.\n")

    # Open browser
    open_browser(url)

    # Start server
    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False
        )
    except KeyboardInterrupt:
        print("\n\nServer stopped. Goodbye! 👋")


if __name__ == "__main__":
    main()
