"""
Aggregator module for fetching weather data from multiple providers in parallel.
"""
import asyncio
from datetime import datetime
from typing import AsyncGenerator
from providers import (
    WeatherProvider,
    ProviderResult,
    ProviderError,
    get_available_providers,
)


class Aggregator:
    """Aggregates weather data from multiple providers."""
    
    def __init__(
        self,
        providers: list[WeatherProvider] | None = None,
        timeout: float = 10.0
    ):
        """
        Initialize the aggregator.
        
        Args:
            providers: List of providers to use. If None, uses all available providers.
            timeout: Request timeout in seconds
        """
        self.providers = providers or get_available_providers()
        self.timeout = timeout
    
    async def fetch_all(
        self,
        lat: float,
        lon: float
    ) -> AsyncGenerator[ProviderResult | ProviderError, None]:
        """
        Fetch weather data from all providers in parallel.
        
        Yields results as they complete (for SSE streaming).
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Yields:
            ProviderResult for successful fetches, ProviderError for failures
        """
        # Create tasks for all providers
        tasks = {
            provider.name: asyncio.create_task(
                self._fetch_provider(provider, lat, lon)
            )
            for provider in self.providers
        }
        
        # Yield results as they complete
        pending = set(tasks.keys())
        
        while pending:
            done, _ = await asyncio.wait(
                [tasks[name] for name in pending],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in done:
                # Find which provider this task belongs to
                for name, t in tasks.items():
                    if t == task:
                        pending.discard(name)
                        try:
                            result = task.result()
                            yield result
                        except Exception as e:
                            yield ProviderError(
                                provider_name=name,
                                reason=str(e)
                            )
                        break
    
    async def fetch_all_wait(
        self,
        lat: float,
        lon: float
    ) -> tuple[list[ProviderResult], list[ProviderError]]:
        """
        Fetch weather data from all providers and wait for all to complete.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Tuple of (successful results, errors)
        """
        results: list[ProviderResult] = []
        errors: list[ProviderError] = []
        
        async for result in self.fetch_all(lat, lon):
            if isinstance(result, ProviderResult):
                results.append(result)
            else:
                errors.append(result)
        
        return results, errors
    
    async def _fetch_provider(
        self,
        provider: WeatherProvider,
        lat: float,
        lon: float
    ) -> ProviderResult:
        """
        Fetch weather data from a single provider.
        
        Args:
            provider: Weather provider instance
            lat: Latitude
            lon: Longitude
            
        Returns:
            ProviderResult
            
        Raises:
            Exception on failure
        """
        return await provider.fetch(lat, lon, self.timeout)


async def stream_provider_results(
    lat: float,
    lon: float,
    timeout: float = 10.0
) -> AsyncGenerator[dict, None]:
    """
    Stream provider results for SSE.
    
    Args:
        lat: Latitude
        lon: Longitude
        timeout: Request timeout in seconds
        
    Yields:
        Dict with provider name, status, and data or error
    """
    aggregator = Aggregator(timeout=timeout)
    
    async for result in aggregator.fetch_all(lat, lon):
        if isinstance(result, ProviderResult):
            yield {
                "type": "provider_result",
                "provider": result.provider_name,
                "status": "ok",
                "now": result.now.model_dump(mode='json') if result.now else None,
                "forecast": [f.model_dump(mode='json') for f in result.forecast]
            }
        else:
            yield {
                "type": "provider_error",
                "provider": result.provider_name,
                "status": "error",
                "reason": result.reason
            }
