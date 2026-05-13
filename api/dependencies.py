"""Dependency injection for FastAPI - memory-safe implementation."""

import logging
from typing import Union
from config.settings import (
    Settings,
    get_settings as _get_settings,
    NVIDIA_NIM_BASE_URL,
    MIMO_BASE_URL_DEFAULT,
)
from providers.base import ProviderConfig
from providers.nvidia_nim import NvidiaNimProvider
from providers.mimo import MimoProvider

logger = logging.getLogger(__name__)

# Global provider instance (singleton)
_provider: Union[NvidiaNimProvider, MimoProvider, None] = None


def get_settings() -> Settings:
    """Get application settings via dependency injection."""
    return _get_settings()


def get_provider() -> Union[NvidiaNimProvider, MimoProvider]:
    """Get or create the provider instance based on PROVIDER setting.

    Uses singleton pattern to ensure only one client exists per application.
    Provider selection controlled by the PROVIDER env var:
      - "nvidia_nim" (default): NVIDIA NIM provider
      - "mimo": Xiaomi MiMo provider
    """
    global _provider
    if _provider is None:
        settings = get_settings()

        if settings.provider == "mimo":
            _provider = _create_mimo_provider(settings)
        else:
            _provider = _create_nvidia_provider(settings)

    return _provider


def _create_nvidia_provider(settings: Settings) -> NvidiaNimProvider:
    """Create NVIDIA NIM provider with model rotation."""
    config = ProviderConfig(
        api_key=settings.nvidia_nim_api_key,
        base_url=NVIDIA_NIM_BASE_URL,
        rate_limit=settings.nvidia_nim_rate_limit,
        rate_window=settings.nvidia_nim_rate_window,
    )
    provider = NvidiaNimProvider(
        config,
        fallback_models=settings.model_fallback,
    )
    logger.info(
        f"Provider: nvidia_nim | {len(settings.model_fallback)} fallback models"
    )
    return provider


def _create_mimo_provider(settings: Settings) -> MimoProvider:
    """Create Xiaomi MiMo provider."""
    config = ProviderConfig(
        api_key=settings.mimo_api_key,
        base_url=settings.mimo_base_url or MIMO_BASE_URL_DEFAULT,
        rate_limit=settings.nvidia_nim_rate_limit,
        rate_window=settings.nvidia_nim_rate_window,
    )
    provider = MimoProvider(config)
    logger.info(
        f"Provider: mimo | base_url={settings.mimo_base_url} | "
        f"model={settings.mimo_model}"
    )
    return provider


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
