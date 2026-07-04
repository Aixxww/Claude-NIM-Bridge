"""Centralized configuration using Pydantic Settings."""

import json
from functools import lru_cache
from typing import Annotated, Optional, Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

# Fixed base URL for NVIDIA NIM
NVIDIA_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Fixed base URL for Xiaomi MiMo (OpenAI-compatible)
MIMO_BASE_URL_DEFAULT = "https://api.xiaomimimo.com/v1"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ==================== Provider Selection ====================
    # "nvidia_nim" or "mimo" — determines which provider to use
    provider: Literal["nvidia_nim", "mimo"] = "nvidia_nim"

    # ==================== NVIDIA NIM Config ====================
    nvidia_nim_api_key: str = ""

    # ==================== Xiaomi MiMo Config ====================
    mimo_api_key: str = ""
    mimo_base_url: str = MIMO_BASE_URL_DEFAULT
    mimo_model: str = "mimo-v2.5-pro"

    # ==================== Model ====================
    # 支持多模型轮转以突破单模型速率限制
    # 优先级从高到低：主模型 → 备用1 → 备用2...
    model: str = "moonshotai/kimi-k2.6"
    model_fallback: Annotated[list[str], NoDecode] = [
        "minimaxai/minimax-m3",
        "deepseek-ai/deepseek-v4-flash",
        "deepseek-ai/deepseek-v4-pro",
        "qwen/qwen3.5-122b-a10b",
        "qwen/qwen3.5-397b-a17b",
        "mistralai/mistral-large-3-675b-instruct-2512",
        "openai/gpt-oss-120b",
    ]

    # ==================== Rate Limiting ====================
    nvidia_nim_rate_limit: int = 40
    nvidia_nim_rate_window: int = 60

    # ==================== Fast Prefix Detection ====================
    fast_prefix_detection: bool = True

    # ==================== Logging ====================
    log_full_payloads: bool = False

    # ==================== Optimizations ====================
    enable_network_probe_mock: bool = True
    enable_title_generation_skip: bool = True

    # ==================== NIM Core Parameters ====================
    nvidia_nim_temperature: float = 1.0
    nvidia_nim_top_p: float = 1.0
    nvidia_nim_top_k: int = -1
    nvidia_nim_max_tokens: int = 16384
    nvidia_nim_presence_penalty: float = 0.0
    nvidia_nim_frequency_penalty: float = 0.0

    # ==================== NIM Advanced Parameters ====================
    nvidia_nim_min_p: float = 0.0
    nvidia_nim_repetition_penalty: float = 1.0
    nvidia_nim_seed: Optional[int] = 42
    nvidia_nim_stop: Optional[str] = None

    # ==================== NIM Flag Parameters ====================
    nvidia_nim_parallel_tool_calls: bool = True
    nvidia_nim_return_tokens_as_token_ids: bool = False
    nvidia_nim_include_stop_str_in_output: bool = False
    nvidia_nim_ignore_eos: bool = False

    nvidia_nim_min_tokens: int = 0
    nvidia_nim_chat_template: str = ""
    nvidia_nim_request_id: str = ""

    # ==================== Thinking/Reasoning Parameters ====================
    nvidia_nim_reasoning_effort: str = "high"
    nvidia_nim_include_reasoning: bool = True

    # ==================== Server ====================
    host: str = "0.0.0.0"
    port: int = 8082

    # Handle empty strings for optional int fields
    @field_validator("nvidia_nim_seed", mode="before")
    @classmethod
    def parse_optional_int(cls, v):
        if v == "" or v is None:
            return None
        return int(v)

    # Handle empty strings for optional string fields
    @field_validator("nvidia_nim_stop", mode="before")
    @classmethod
    def parse_optional_str(cls, v):
        if v == "":
            return None
        return v

    @field_validator("model_fallback", mode="before")
    @classmethod
    def parse_model_fallback(cls, v):
        """Accept JSON lists or comma-separated MODEL_FALLBACK values."""
        if v is None or v == "":
            return []
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            return [model.strip() for model in v.split(",") if model.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
