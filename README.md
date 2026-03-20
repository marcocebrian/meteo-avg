# MeteoAvg - Multi-Provider Weather Aggregator

A local Python application that queries multiple free weather APIs for a user-specified city, normalizes their responses into a shared schema, averages overlapping fields, and displays results in a local web dashboard with confidence scores and provider breakdown.

## Features

- **Multi-provider aggregation**: Queries up to 7 weather APIs simultaneously
- **Always-on providers** (no API key required):
  - Open-Meteo (16-day forecast)
  - wttr.in (3-day forecast)
  - 7timer.info (8-day forecast)
- **API key providers** (optional):
  - OpenWeatherMap (5-day forecast)
  - WeatherAPI.com (14-day forecast)
  - Tomorrow.io (5-day forecast)
  - Weatherbit.io (16-day forecast)
- **Smart averaging**: Arithmetic mean for numeric fields, circular mean for wind direction, majority vote for conditions
- **Confidence scoring**: Per-field confidence based on provider count and data variance
- **Real-time dashboard**: SSE-powered live updates as providers respond
- **Unit conversion**: Toggle between °C/°F and km/h/mph

## Installation

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root (optional):

```env
# API Keys (optional — providers activate when key is present)
OWM_API_KEY=your_openweathermap_key
WEATHERAPI_KEY=your_weatherapi_key
TOMORROW_API_KEY=your_tomorrow_io_key
WEATHERBIT_KEY=your_weatherbit_key

# Settings
REQUEST_TIMEOUT_SECONDS=10
PORT=8000
```

## Usage

```bash
# Activate virtual environment first
source venv/bin/activate

# Run the application
python app.py
```

The app will prompt for a city name, then start a local web server and open the dashboard in your browser.

### Example

```
Enter city name: Kuala Lumpur

============================================================
  MeteoAvg - Multi-provider Weather Aggregator
============================================================

  Location: Kuala Lumpur, Malaysia
  Coordinates: 3.1390°, 101.6869°

  Available providers (3):
    ✓ Open Meteo (16 days)
    ✓ Wttr In (3 days)
    ✓ Seven Timer (8 days)

------------------------------------------------------------

  Starting server at: http://127.0.0.1:8000
  Press Ctrl+C to stop the server.
```

## Architecture

```
meteo-avg/
├── app.py                  # Entry point
├── .env                    # Optional API keys
├── requirements.txt
├── providers/
│   ├── __init__.py         # Provider registry
│   ├── base.py             # Abstract WeatherProvider class
│   ├── open_meteo.py       # No key required
│   ├── wttr_in.py          # No key required
│   ├── seven_timer.py      # No key required
│   ├── openweathermap.py   # Requires OWM_API_KEY
│   ├── weatherapi.py       # Requires WEATHERAPI_KEY
│   ├── tomorrow_io.py      # Requires TOMORROW_API_KEY
│   └── weatherbit.py       # Requires WEATHERBIT_KEY
├── core/
│   ├── geocoder.py         # City name → coordinates
│   ├── aggregator.py       # Parallel provider fetching
│   └── averager.py         # Averaging + confidence scoring
└── web/
    ├── server.py           # FastAPI + SSE endpoint
    ├── static/
    │   └── app.js          # Dashboard JS
    └── templates/
        └── index.html      # Dashboard HTML
```

## Adding a New Provider

1. Create a new file in `providers/` (e.g., `my_provider.py`)
2. Inherit from `WeatherProvider` and implement `fetch()` and `parse()` methods
3. Add the provider to `ALL_PROVIDERS` list in `providers/__init__.py`

## Data Schema

### Current Conditions

| Field | Type | Description |
|-------|------|-------------|
| temperature_c | float | Temperature in Celsius |
| feels_like_c | float | Apparent temperature |
| humidity_pct | float | Relative humidity percentage |
| wind_speed_kmh | float | Wind speed in km/h |
| wind_direction_deg | float | Wind direction in degrees |
| precipitation_mm | float | Precipitation in mm |
| pressure_hpa | float | Atmospheric pressure in hPa |
| visibility_km | float | Visibility in kilometers |
| uv_index | float | UV index |
| cloud_cover_pct | float | Cloud coverage percentage |
| condition | str | Weather condition description |

### Confidence Levels

| Level | Criteria |
|-------|----------|
| 🟢 High | 3+ providers AND σ ≤ threshold |
| 🟡 Medium | 2 providers OR σ > threshold |
| 🔴 Low | Only 1 provider reported |

## Security

- Server binds to `127.0.0.1` only (not accessible from network)
- API keys never transmitted to browser
- Add `.env` to `.gitignore`

## License

MIT License
