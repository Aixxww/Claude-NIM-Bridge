"""Xiaomi MiMo provider - OpenAI-compatible API.

MiMo uses the same OpenAI-compatible protocol as NVIDIA NIM,
so this provider extends NvidiaNimProvider with MiMo-specific defaults.
"""

import logging
import os

from .base import BaseProvider, ProviderConfig
from .nvidia_nim import NvidiaNimProvider

logger = logging.getLogger(__name__)


class MimoProvider(NvidiaNimProvider):
    """Xiaomi MiMo provider using OpenAI-compatible API.

    Inherits all streaming, tool call, and response conversion logic
    from NvidiaNimProvider. Only overrides initialization to use
    MiMo-specific base_url, api_key, and model defaults.
    """

    def __init__(self, config: ProviderConfig, fallback_models: list | None = None):
        # Override base_url and api_key with MiMo defaults
        self._mimo_api_key = config.api_key or os.getenv("MIMO_API_KEY", "")
        self._mimo_base_url = (
            config.base_url
            or os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
        ).rstrip("/")

        # Build a new config with MiMo credentials for the parent
        mimo_config = ProviderConfig(
            api_key=self._mimo_api_key,
            base_url=self._mimo_base_url,
            rate_limit=config.rate_limit,
            rate_window=config.rate_window,
        )

        # Use MiMo model as primary
        mimo_model = os.getenv("MIMO_MODEL", "mimo-v2.5-pro")

        # Temporarily set MODEL env var so parent picks up MiMo model
        old_model = os.environ.get("MODEL")
        os.environ["MODEL"] = mimo_model

        super().__init__(mimo_config, fallback_models=fallback_models)

        # Restore original MODEL env var
        if old_model is not None:
            os.environ["MODEL"] = old_model
        else:
            os.environ.pop("MODEL", None)

        logger.info(
            f"MimoProvider initialized: base_url={self._mimo_base_url}, "
            f"model={mimo_model}"
        )
