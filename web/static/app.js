/**
 * MeteoAvg Dashboard - Main Application
 * Handles SSE connection, data rendering, and unit conversion
 * Version: 2.0
 */

console.log('MeteoAvg app.js v2.0 loaded');

// State
let cityInfo = null;
let currentUnits = 'c';
let windUnits = 'kmh';
let eventSource = null;
let providerResults = [];
let averagedData = null;
let searchDebounceTimer = null;

// Weather icon mapping
const WEATHER_ICONS = {
    'clear': '☀️',
    'sunny': '☀️',
    'clear sky': '☀️',
    'mainly clear': '🌤️',
    'partly cloudy': '⛅',
    'cloudy': '☁️',
    'overcast': '☁️',
    'mostly cloudy': '🌥️',
    'fog': '🌫️',
    'mist': '🌫️',
    'haze': '🌫️',
    'drizzle': '🌦️',
    'light rain': '🌦️',
    'rain': '🌧️',
    'moderate rain': '🌧️',
    'heavy rain': '🌧️',
    'shower': '🌧️',
    'thunderstorm': '⛈️',
    'light snow': '🌨️',
    'snow': '❄️',
    'heavy snow': '❄️',
    'sleet': '🌨️',
    'wind': '💨',
    'unknown': '🌡️'
};

// Get weather icon from condition string
function getWeatherIcon(condition) {
    if (!condition) return WEATHER_ICONS['unknown'];
    const lower = condition.toLowerCase();
    for (const [key, icon] of Object.entries(WEATHER_ICONS)) {
        if (lower.includes(key)) return icon;
    }
    return WEATHER_ICONS['unknown'];
}

// Unit conversion functions
function celsiusToFahrenheit(c) {
    return c * 9 / 5 + 32;
}

function kmhToMph(kmh) {
    return kmh * 0.621371;
}

function formatTemp(tempC, withUnit = true) {
    if (tempC === null || tempC === undefined) return '--';
    const value = currentUnits === 'c' ? tempC : celsiusToFahrenheit(tempC);
    const unit = currentUnits === 'c' ? '°C' : '°F';
    return `${Math.round(value)}${withUnit ? unit : ''}`;
}

function formatSpeed(speedKmh, withUnit = true) {
    if (speedKmh === null || speedKmh === undefined) return '--';
    const value = windUnits === 'kmh' ? speedKmh : kmhToMph(speedKmh);
    const unit = windUnits === 'kmh' ? 'km/h' : 'mph';
    return `${Math.round(value)}${withUnit ? ' ' + unit : ''}`;
}

// Format date
function formatDate(dateStr) {
    const date = new Date(dateStr);
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    if (date.toDateString() === today.toDateString()) {
        return 'Today';
    } else if (date.toDateString() === tomorrow.toDateString()) {
        return 'Tomorrow';
    } else {
        return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    }
}

// Get confidence class
function getConfidenceClass(confidence) {
    return `confidence-${confidence}`;
}

// Get confidence indicator
function getConfidenceIndicator(n, confidence) {
    const emoji = confidence === 'high' ? '🟢' : confidence === 'medium' ? '🟡' : '🔴';
    return `<span class="${getConfidenceClass(confidence)}">${emoji} ${n} provider${n !== 1 ? 's' : ''}</span>`;
}

// Render current weather hero
function renderCurrentHero(data) {
    if (!data) return '';

    const temp = data.temperature_c;
    const feels = data.feels_like_c;
    const humidity = data.humidity_pct;
    const wind = data.wind_speed_kmh;
    const uv = data.uv_index;
    const precip = data.precipitation_mm;
    const condition = data.condition;

    return `
        <div class="metric-card main">
            <div class="icon">${getWeatherIcon(condition?.value)}</div>
            <div class="value">${formatTemp(temp?.value, false)}°</div>
            <div class="label">${condition?.value || 'Loading...'}</div>
            <div class="confidence">${getConfidenceIndicator(temp?.n || 0, temp?.confidence || 'low')}</div>
        </div>
        <div class="metric-card">
            <div class="icon">🌡️</div>
            <div class="value">${formatTemp(feels?.value)}</div>
            <div class="label">Feels Like</div>
            <div class="confidence ${getConfidenceClass(feels?.confidence || 'low')}">${feels?.n || 0} providers</div>
        </div>
        <div class="metric-card">
            <div class="icon">💧</div>
            <div class="value">${humidity?.value !== null ? Math.round(humidity.value) + '%' : '--'}</div>
            <div class="label">Humidity</div>
            <div class="confidence ${getConfidenceClass(humidity?.confidence || 'low')}">${humidity?.n || 0} providers</div>
        </div>
        <div class="metric-card">
            <div class="icon">💨</div>
            <div class="value">${formatSpeed(wind?.value)}</div>
            <div class="label">Wind</div>
            <div class="confidence ${getConfidenceClass(wind?.confidence || 'low')}">${wind?.n || 0} providers</div>
        </div>
        <div class="metric-card">
            <div class="icon">☀️</div>
            <div class="value">${uv?.value !== null ? Math.round(uv.value) : '--'}</div>
            <div class="label">UV Index</div>
            <div class="confidence ${getConfidenceClass(uv?.confidence || 'low')}">${uv?.n || 0} providers</div>
        </div>
        <div class="metric-card">
            <div class="icon">🌧️</div>
            <div class="value">${precip?.value !== null ? precip.value.toFixed(1) + ' mm' : '--'}</div>
            <div class="label">Precipitation</div>
            <div class="confidence ${getConfidenceClass(precip?.confidence || 'low')}">${precip?.n || 0} providers</div>
        </div>
    `;
}

// Render detailed metrics
function renderDetailedMetrics(data) {
    if (!data) return '';

    const metrics = [
        { key: 'pressure_hpa', label: 'Pressure', unit: ' hPa', format: v => Math.round(v) },
        { key: 'visibility_km', label: 'Visibility', unit: ' km', format: v => v.toFixed(1) },
        { key: 'cloud_cover_pct', label: 'Cloud Cover', unit: '%', format: v => Math.round(v) },
    ];

    let html = '';

    // Wind direction with compass
    const windDir = data.wind_direction_deg;
    if (windDir?.value !== null && windDir?.value !== undefined) {
        html += `
            <div class="metric-row">
                <span class="label">Wind Direction</span>
                <div class="value-container">
                    <div class="wind-compass">
                        <span class="direction n">N</span>
                        <span class="direction s">S</span>
                        <span class="direction e">E</span>
                        <span class="direction w">W</span>
                        <div class="arrow" style="transform: rotate(${windDir.value}deg)"></div>
                    </div>
                    <span class="value">${Math.round(windDir.value)}°</span>
                </div>
            </div>
        `;
    }

    for (const metric of metrics) {
        const field = data[metric.key];
        if (field && field.value !== null) {
            html += `
                <div class="metric-row">
                    <span class="label">${metric.label}</span>
                    <div class="value-container">
                        <span class="value">${metric.format(field.value)}${metric.unit}</span>
                        <span class="n-providers">${field.n} providers</span>
                        <div class="confidence-bar">
                            <div class="confidence-bar-fill ${field.confidence}" style="width: ${field.n >= 3 ? 100 : field.n >= 2 ? 66 : 33}%"></div>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    return html;
}

// Render forecast grid
function renderForecast(forecast) {
    if (!forecast || forecast.length === 0) return '<div class="empty-state">No forecast data available</div>';

    return forecast.map(day => {
        const isLowConfidence = day.temp_max_c?.n === 1 || day.temp_min_c?.n === 1;
        return `
            <div class="forecast-day ${isLowConfidence ? 'low-confidence' : ''}" onclick="showDayDetails('${day.date}')">
                <div class="date">${formatDate(day.date)}</div>
                <div class="icon">${getWeatherIcon(day.condition?.value)}</div>
                <div class="temps">
                    <span class="temp-high">${formatTemp(day.temp_max_c?.value, false)}</span>
                    <span class="temp-low"> / ${formatTemp(day.temp_min_c?.value, false)}</span>
                </div>
                ${day.precipitation_mm?.value ? `<div class="precip">💧 ${day.precipitation_mm.value.toFixed(1)} mm</div>` : ''}
                <div class="n-indicator">${day.temp_max_c?.n || 0} providers</div>
            </div>
        `;
    }).join('');
}

// Render provider list
function renderProviderList() {
    if (providerResults.length === 0) {
        return `
            <div class="empty-state">
                <div class="icon">📡</div>
                <div>Waiting for providers...</div>
            </div>
        `;
    }

    return providerResults.map(result => {
        if (result.status === 'error') {
            return `
                <div class="provider-card error">
                    <div class="provider-header">
                        <span class="provider-name">${result.provider.replace(/_/g, ' ')}</span>
                        <span class="provider-status error">✗ Error</span>
                    </div>
                    <div class="provider-details">${result.reason}</div>
                </div>
            `;
        }

        // Success case
        const fields = [];
        if (result.now) {
            const now = result.now;
            if (now.temperature_c !== null) fields.push(`Temp: ${now.temperature_c}°C`);
            if (now.humidity_pct !== null) fields.push(`Humidity: ${now.humidity_pct}%`);
            if (now.wind_speed_kmh !== null) fields.push(`Wind: ${now.wind_speed_kmh} km/h`);
            if (now.condition) fields.push(now.condition);
        }

        const forecastDays = result.forecast?.length || 0;
        const timestamp = result.now?.fetched_at ? new Date(result.now.fetched_at).toLocaleTimeString() : '';

        return `
            <div class="provider-card success">
                <div class="provider-header">
                    <span class="provider-name">${result.provider.replace(/_/g, ' ')}</span>
                    <span class="provider-status success">✓ Success</span>
                </div>
                <div class="provider-details">
                    ${fields.map(f => `<span class="field">${f}</span>`).join('')}
                    <br><br>
                    <small>Forecast: ${forecastDays} days | Fetched: ${timestamp}</small>
                </div>
            </div>
        `;
    }).join('');
}

// Show day details modal
function showDayDetails(dateStr) {
    if (!averagedData || !averagedData.forecast) return;

    const day = averagedData.forecast.find(d => d.date === dateStr);
    if (!day) return;

    const title = formatDate(dateStr);
    document.getElementById('day-details-title').textContent = title + ' Forecast Details';

    const metrics = [
        { key: 'temp_max_c', label: 'Max Temp', format: v => formatTemp(v) },
        { key: 'temp_min_c', label: 'Min Temp', format: v => formatTemp(v) },
        { key: 'temp_avg_c', label: 'Avg Temp', format: v => formatTemp(v) },
        { key: 'humidity_pct', label: 'Humidity', format: v => Math.round(v) + '%' },
        { key: 'wind_speed_kmh', label: 'Wind Speed', format: v => formatSpeed(v) },
        { key: 'precipitation_mm', label: 'Precipitation', format: v => v.toFixed(1) + ' mm' },
        { key: 'uv_index', label: 'UV Index', format: v => Math.round(v) },
        { key: 'cloud_cover_pct', label: 'Cloud Cover', format: v => Math.round(v) + '%' },
    ];

    let html = `
        <div style="text-align: center; margin-bottom: 20px;">
            <span style="font-size: 4rem;">${getWeatherIcon(day.condition?.value)}</span>
            <div style="font-size: 1.25rem; margin-top: 10px;">${day.condition?.value || 'Unknown'}</div>
        </div>
        <div class="metrics-grid">
    `;

    for (const metric of metrics) {
        const field = day[metric.key];
        if (field) {
            html += `
                <div class="metric-row">
                    <span class="label">${metric.label}</span>
                    <div class="value-container">
                        <span class="value">${field.value !== null ? metric.format(field.value) : '--'}</span>
                        <span class="n-providers">${getConfidenceIndicator(field.n, field.confidence)}</span>
                    </div>
                </div>
            `;
        }
    }

    html += '</div>';
    document.getElementById('day-details-body').innerHTML = html;
    document.getElementById('day-details').classList.add('active');
}

// Close day details modal
function closeDayDetails(event) {
    if (event && event.target !== document.getElementById('day-details')) return;
    document.getElementById('day-details').classList.remove('active');
}

// Update UI with averaged data
function updateUI(data) {
    console.log('updateUI called with:', data);
    averagedData = data;

    // Update current weather
    const heroHtml = renderCurrentHero(data.now);
    console.log('renderCurrentHero output length:', heroHtml.length);
    document.getElementById('current-hero').innerHTML = heroHtml;

    // Update detailed metrics
    document.getElementById('detailed-metrics').innerHTML = renderDetailedMetrics(data.now);

    // Update forecast
    document.getElementById('forecast-grid').innerHTML = renderForecast(data.forecast);

    // Update provider list
    document.getElementById('provider-list').innerHTML = renderProviderList();
}

// Update status
function updateStatus(loading, text) {
    const loadingEl = document.getElementById('status-loading');
    const textEl = document.getElementById('loading-text');
    const refreshIcon = document.getElementById('refresh-icon');

    if (loading) {
        loadingEl.style.display = 'flex';
        refreshIcon.innerHTML = '<span class="spinner">⏳</span>';
        document.querySelector('.refresh-btn').classList.add('loading');
    } else {
        loadingEl.style.display = 'none';
        refreshIcon.innerHTML = '🔄';
        document.querySelector('.refresh-btn').classList.remove('loading');
    }
    textEl.textContent = text;
}

// Update provider stats
function updateStats(total, success, failed) {
    const text = `${success}/${total} providers responded`;
    document.getElementById('stats-text').textContent = text;
}

// Update location display
function updateLocationDisplay() {
    if (cityInfo) {
        const locationEl = document.getElementById('location');
        locationEl.textContent = `${cityInfo.display_name} | ${cityInfo.lat.toFixed(4)}°, ${cityInfo.lon.toFixed(4)}°`;
        document.title = `MeteoAvg - ${cityInfo.display_name}`;
    }
}

// Connect to SSE endpoint
function connectSSE() {
    updateStatus(true, 'Connecting to weather providers...');
    providerResults = [];
    averagedData = null;

    // Clear current weather display
    document.getElementById('current-hero').innerHTML = '<div class="skeleton skeleton-metric"></div>'.repeat(6);
    document.getElementById('detailed-metrics').innerHTML = '<div class="skeleton skeleton-row"></div>'.repeat(4);
    document.getElementById('forecast-grid').innerHTML = '<div class="skeleton skeleton-metric"></div>'.repeat(5);
    document.getElementById('provider-list').innerHTML = `
        <div class="empty-state">
            <div class="icon">📡</div>
            <div>Waiting for providers...</div>
        </div>
    `;

    const url = `/api/weather?lat=${cityInfo.lat}&lon=${cityInfo.lon}`;

    eventSource = new EventSource(url);

    eventSource.addEventListener('provider_result', (event) => {
        const data = JSON.parse(event.data);
        providerResults.push(data);
    });

    eventSource.addEventListener('provider_error', (event) => {
        const data = JSON.parse(event.data);
        providerResults.push(data);
    });

    eventSource.addEventListener('averaged_update', (event) => {
        const data = JSON.parse(event.data);
        console.log('averaged_update received:', data);
        console.log('data.now:', data.now);
        console.log('data.now.temperature_c:', data.now?.temperature_c);
        updateUI(data);
        updateStatus(true, `Received data from ${data.provider_count} provider(s)...`);
    });

    eventSource.addEventListener('done', (event) => {
        const data = JSON.parse(event.data);
        updateStatus(false, 'All providers responded');
        updateStats(data.total_providers, data.successful, data.failed);
        eventSource.close();
    });

    eventSource.onerror = (error) => {
        console.error('SSE Error:', error);
        updateStatus(false, 'Connection error. Click refresh to retry.');
        if (eventSource) eventSource.close();
    };
}

// Refresh data
function refreshData() {
    if (eventSource) {
        eventSource.close();
    }
    connectSSE();
}

// Set temperature units
function setUnits(unit) {
    currentUnits = unit;
    document.querySelectorAll('.unit-toggle button[data-unit="c"], .unit-toggle button[data-unit="f"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.unit === unit);
    });
    if (averagedData) {
        updateUI(averagedData);
    }
}

// Set wind units
function setWindUnit(unit) {
    windUnits = unit;
    document.querySelectorAll('.unit-toggle button[data-unit="kmh"], .unit-toggle button[data-unit="mph"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.unit === unit);
    });
    if (averagedData) {
        updateUI(averagedData);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Get city info first, then connect SSE
    fetch('/api/city')
        .then(res => res.json())
        .then(info => {
            cityInfo = info;
            updateLocationDisplay();
            connectSSE();
        })
        .catch(err => {
            console.error('Failed to get city info:', err);
            updateStatus(false, 'Failed to get city info. Please restart the app.');
        });

    // Setup search input handlers
    const searchInput = document.getElementById('city-search');
    const searchResults = document.getElementById('search-results');

    // Handle Enter key
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            performSearch();
        }
    });

    // Debounced search on input
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchDebounceTimer);
        const query = e.target.value.trim();
        
        if (query.length >= 2) {
            searchDebounceTimer = setTimeout(() => performSearch(true), 500);
        } else {
            searchResults.classList.remove('active');
        }
    });

    // Close search results when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container')) {
            searchResults.classList.remove('active');
        }
    });
});

// Handle keyboard events for modal
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        closeDayDetails();
        document.getElementById('search-results').classList.remove('active');
    }
});

// ====== City Search Functions ======

async function performSearch(isAutoComplete = false) {
    const searchInput = document.getElementById('city-search');
    const searchBtn = document.getElementById('search-btn');
    const searchResults = document.getElementById('search-results');
    const query = searchInput.value.trim();

    if (!query) return;

    // Show loading state
    if (!isAutoComplete) {
        searchBtn.disabled = true;
        searchBtn.innerHTML = '⏳ Searching...';
    }
    searchResults.innerHTML = '<div class="search-loading">Searching...</div>';
    searchResults.classList.add('active');

    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();

        if (data.error) {
            searchResults.innerHTML = `<div class="search-error">Error: ${data.error}</div>`;
            return;
        }

        if (!data.cities || data.cities.length === 0) {
            searchResults.innerHTML = '<div class="search-error">No cities found. Try a different search.</div>';
            return;
        }

        // Render results
        searchResults.innerHTML = data.cities.map((city, idx) => `
            <div class="search-result-item" onclick="selectCity(${idx})">
                <div class="name">${city.name}</div>
                <div class="details">${city.admin1 ? city.admin1 + ', ' : ''}${city.country}</div>
                <div class="coords">${city.lat.toFixed(4)}°, ${city.lon.toFixed(4)}°</div>
            </div>
        `).join('');

        // Store cities for selection
        window._searchResults = data.cities;

    } catch (error) {
        console.error('Search error:', error);
        searchResults.innerHTML = '<div class="search-error">Search failed. Please try again.</div>';
    } finally {
        searchBtn.disabled = false;
        searchBtn.innerHTML = '🔍 Search';
    }
}

async function selectCity(index) {
    const cities = window._searchResults;
    if (!cities || !cities[index]) return;

    const city = cities[index];
    const searchResults = document.getElementById('search-results');
    const searchInput = document.getElementById('city-search');

    // Close search results
    searchResults.classList.remove('active');
    searchInput.value = '';

    // Update city info
    cityInfo = {
        city: city.name,
        lat: city.lat,
        lon: city.lon,
        display_name: city.display_name
    };

    // Save to server
    try {
        await fetch('/api/city', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cityInfo)
        });
    } catch (error) {
        console.error('Failed to save city:', error);
    }

    // Update display and reconnect SSE
    updateLocationDisplay();

    // Close existing SSE connection
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }

    // Connect to new location
    connectSSE();
}
