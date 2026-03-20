"""Dependency injection for FastAPI - memory-safe implementation."""

import logging
from typing import Optional
from config.settings import Settings, get_settings as _get_settings, NVIDIA_NIM_BASE_URL
from providers.base import ProviderConfig
from providers.nvidia_nim import NvidiaNimProvider

logger = logging.getLogger(__name__)

# Global provider instance (singleton)
_provider: Optional[NvidiaNimProvider] = None


def get_settings() -> Settings:
    """Get application settings via dependency injection."""
    return _get_settings()


def get_provider() -> NvidiaNimProvider:
    """Get or create the NvidiaNimProvider instance.

    Uses singleton pattern to ensure only one client exists per application.
    Includes model rotation support for handling rate limits.
    """
    global _provider
    if _provider is None:
        settings = get_settings()
        config = ProviderConfig(
            api_key=settings.nvidia_nim_api_key,
            base_url=NVIDIA_NIM_BASE_URL,
            rate_limit=settings.nvidia_nim_rate_limit,
            rate_window=settings.nvidia_nim_rate_window,
        )
        _provider = NvidiaNimProvider(
            config,
            fallback_models=settings.model_fallback
        )
        logger.info(
            f"Provider singleton created with {len(settings.model_fallback)} fallback models"
        )
    return _provider


async def cleanup_provider():
    """Cleanup provider resources.

    Called during application shutdown to properly close connections
    and prevent connection leaks.
    """
    global _provider
    if _provider:
        try:
            await _provider.close()
        except Exception as e:
            logger.error(f"Error during provider cleanup: {e}")
        finally:
            _provider = None
            logger.info("Provider cleanup completed")
