"""多模型轮转管理 - 突破单模型速率限制

当主模型达到速率限制时，自动降级到备用模型。
"""

import asyncio
import logging
from typing import List, Optional, AsyncIterator, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ModelStatus:
    """跟踪单个模型的速率状态。"""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.rate_limited_until = datetime.min  # 被限速直到何时
        self.fail_count = 0  # 累计失败次数
        self.last_success = datetime.min  # 上次成功时间
        self.total_requests = 0  # 总请求数
        self.success_rate = 1.0  # 成功率

    def is_available(self) -> bool:
        """检查模型当前是否可用。"""
        return datetime.now() > self.rate_limited_until

    def mark_ratelimited(self, cooldown_seconds: int = 60):
        """标记模型被限速。"""
        self.rate_limited_until = datetime.now() + timedelta(seconds=cooldown_seconds)
        self.fail_count += 1
        logger.warning(
            f"Model {self.model_name} rate limited until {self.rate_limited_until.strftime('%H:%M:%S')}"
        )

    def mark_success(self):
        """标记模型请求成功。"""
        self.last_success = datetime.now()
        self.total_requests += 1

    def mark_failure(self):
        """标记模型请求失败（非429）。"""
        self.total_requests += 1


class ModelRotator:
    """多模型轮转管理器。

    维护多个模型的可用状态，在当前模型被限速时自动切换到备用模型。
    """

    def __init__(self, fallback_models: List[str]):
        self.fallback_models = fallback_models
        self.model_status = {
            model: ModelStatus(model) for model in fallback_models
        }
        self.current_index = 0  # 当前使用的模型索引

    def get_available_model(self) -> Optional[str]:
        """获取当前可用的最佳模型。"""
        # 优先检查当前索引的模型
        if self.model_status[self.fallback_models[self.current_index]].is_available():
            return self.fallback_models[self.current_index]

        # 轮询所有模型找可用的
        now = datetime.now()
        for i, model in enumerate(self.fallback_models):
            status = self.model_status[model]
            if status.is_available():
                self.current_index = i
                logger.info(f"切换到模型: {model} (索引 {i})")
                return model

        # 所有模型都被限速，返回 None
        logger.warning("所有模型均被限速，等待重置...")
        return None

    def get_all_available(self) -> List[str]:
        """获取所有当前可用的模型列表。"""
        return [
            model
            for model in self.fallback_models
            if self.model_status[model].is_available()
        ]

    def handle_rate_limit(self, model: str, cooldown: int = 60):
        """处理速率限制。"""
        if model in self.model_status:
            self.model_status[model].mark_ratelimited(cooldown)
            logger.info(
                f"模型 {model} 被限速，可用模型: {self.get_all_available()}"
            )

    def handle_success(self, model: str):
        """处理请求成功。"""
        if model in self.model_status:
            self.model_status[model].mark_success()

    def handle_failure(self, model: str):
        """处理请求失败（非限速）。"""
        if model in self.model_status:
            self.model_status[model].mark_failure()

    def get_stats(self) -> dict:
        """获取所有模型的状态统计。"""
        return {
            model: {
                "available": status.is_available(),
                "rate_limited_until": status.rate_limited_until.strftime("%H:%M:%S")
                if not status.is_available()
                else None,
                "fail_count": status.fail_count,
                "success_rate": status.success_rate,
            }
            for model, status in self.model_status.items()
        }

    def reset(self):
        """重置所有模型状态（用于测试）。"""
        for status in self.model_status.values():
            status.rate_limited_until = datetime.min
            status.fail_count = 0


class ModelRotationContext:
    """上下文管理器，用于处理流式响应中的模型切换。"""

    def __init__(
        self,
        rotator: ModelRotator,
        provider: Any,
        request: Any,
        input_tokens: int
    ):
        self.rotator = rotator
        self.provider = provider
        self.request = request
        self.input_tokens = input_tokens
        self.current_model = None
        self.retry_count = 0
        self.max_retries = 3  # 最多重试次数（模型切换）

    async def __aenter__(self):
        """获取可用模型。"""
        self.current_model = self.rotator.get_available_model()
        if not self.current_model:
            raise RuntimeError("所有模型均被限速，请稍后重试")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """处理异常和状态更新。"""
        if exc_type is not None:
            # 处理速率限制
            if "429" in str(exc_val) or "rate limit" in str(exc_val).lower():
                self.rotator.handle_rate_limit(self.current_model)
                # 尝试切换模型重试
                return False  # 不抑制异常，让调用方重试
            else:
                # 其他错误
                self.rotator.handle_failure(self.current_model)
        else:
            # 成功
            self.rotator.handle_success(self.current_model)
        return False

    def should_retry(self) -> bool:
        """判断是否应该重试（切换模型）。"""
        return self.retry_count < self.max_retries

    def next_model(self) -> str:
        """切换到下一个可用模型。"""
        self.retry_count += 1
        next_model = self.rotator.get_available_model()
        if next_model:
            logger.info(
                f"模型切换: {self.current_model} -> {next_model} "
                f"(重试 {self.retry_count}/{self.max_retries})"
            )
            self.current_model = next_model
        return next_model
