"""NVIDIA NIM provider - optimized for streaming and memory safety."""

import logging
import os
import json
import uuid
from typing import Any, AsyncIterator, Optional

from openai import AsyncOpenAI
from openai import NotFoundError, RateLimitError as OpenAIRateLimitError

from .base import BaseProvider, ProviderConfig
from .utils import (
    SSEBuilder,
    map_stop_reason,
    ThinkTagParser,
    HeuristicToolParser,
    ContentType,
)
from .exceptions import APIError, RateLimitError
from .nvidia_mixins import (
    RequestBuilderMixin,
    ErrorMapperMixin,
    ResponseConverterMixin,
)
from .rate_limit import GlobalRateLimiter
from .model_rotator import ModelRotator

logger = logging.getLogger(__name__)


class NvidiaNimProvider(
    RequestBuilderMixin,
    ErrorMapperMixin,
    ResponseConverterMixin,
    BaseProvider,
):
    """NVIDIA NIM provider using official OpenAI client.

    Memory-safe implementation with proper resource cleanup.
    """

    def __init__(self, config: ProviderConfig, fallback_models: Optional[list] = None):
        super().__init__(config)
        self._api_key = config.api_key or os.getenv("NVIDIA_NIM_API_KEY", "")
        self._base_url = (
            config.base_url
            or os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
        ).rstrip("/")
        self._nim_params = self._load_nim_params()
        self._global_rate_limiter = GlobalRateLimiter.get_instance()

        # 初始化多模型轮转器
        if fallback_models:
            # 构建模型列表：主模型在前，备用模型在后
            primary_model = os.getenv("MODEL", "z-ai/glm4.7")
            all_models = [primary_model] + fallback_models
        else:
            all_models = [os.getenv("MODEL", "z-ai/glm4.7")]

        self._model_rotator = ModelRotator(all_models)

        # Create AsyncOpenAI client with connection limits
        # These settings help prevent memory buildup from accumulated connections
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            max_retries=2,
            timeout=300.0,
            # Connection pool limits to prevent unbounded connection growth
            http_client=None,  # Use default httpx client with built-in limits
        )

        logger.info(
            f"NvidiaNimProvider initialized: base_url={self._base_url}, "
            f"models={all_models}, "
            f"model_params={list(self._nim_params.keys())}"
        )

    async def stream_response(
        self, request: Any, input_tokens: int = 0
    ) -> AsyncIterator[str]:
        """Stream response in Anthropic SSE format with model rotation.

        Automatically switches to fallback models when rate limited.
        Memory-safe implementation with proper cleanup on client disconnect.
        """
        # Wait if globally rate limited
        waited_reactively = await self._global_rate_limiter.wait_if_blocked()

        message_id = f"msg_{uuid.uuid4().hex}"
        sse = SSEBuilder(message_id, request.model, input_tokens)

        if waited_reactively:
            error_msg = "⏱️ Rate limit active. Retrying..."
            logger.info(f"NIM_STREAM: {message_id} - reactive wait, notifying")
            yield sse.message_start()
            for event in sse.emit_error(error_msg):
                yield event
            return

        # 模型轮转重试循环
        max_model_retries = 3
        current_model = self._model_rotator.get_available_model()
        last_error = None

        for retry_count in range(max_model_retries):
            if not current_model:
                error_msg = "⚠️ All models rate limited. Please wait and try again."
                yield sse.message_start()
                for event in sse.emit_error(error_msg):
                    yield event
                return

            # 覆盖请求中的模型为当前选择的模型
            request.model = current_model
            body = self._build_request_body(request, stream=True)

            logger.info(
                f"NIM_STREAM: {message_id} - model={current_model} "
                f"(retry {retry_count + 1}/{max_model_retries}) "
                f"msgs={len(body.get('messages', []))} "
                f"tools={len(body.get('tools', []))}"
            )

            # Create parsers for this request
            think_parser = ThinkTagParser()
            heuristic_parser = HeuristicToolParser()

            # Emit message_start (仅第一次)
            if retry_count == 0:
                for event in sse.message_start():
                    yield event

            try:
                # 执行流式请求 - 内联实现以保持简单
                stream = await self._client.chat.completions.create(**body, stream=True)

                # 重置状态用于新尝试
                sse.blocks = type(sse.blocks)()  # 重新初始化 blocks
                finish_reason = None
                usage_info = None
                error_occurred = False

                async for chunk in stream:
                    if getattr(chunk, "usage", None):
                        usage_info = chunk.usage

                    if not chunk.choices:
                        continue

                    choice = chunk.choices[0]
                    delta = choice.delta

                    if choice.finish_reason:
                        finish_reason = choice.finish_reason

                    # Handle reasoning content
                    reasoning = getattr(delta, "reasoning_content", None)
                    if reasoning:
                        for event in sse.ensure_thinking_block():
                            yield event
                        yield sse.emit_thinking_delta(reasoning)

                    # Handle text content
                    if delta.content:
                        for part in think_parser.feed(delta.content):
                            if part.type == ContentType.THINKING:
                                for event in sse.ensure_thinking_block():
                                    yield event
                                yield sse.emit_thinking_delta(part.content)
                            else:
                                filtered_text, detected_tools = heuristic_parser.feed(part.content)

                                if filtered_text:
                                    for event in sse.ensure_text_block():
                                        yield event
                                    yield sse.emit_text_delta(filtered_text)

                                for tool_use in detected_tools:
                                    for event in sse.close_content_blocks():
                                        yield event

                                    block_idx = sse.blocks.allocate_index()
                                    yield sse.content_block_start(
                                        block_idx,
                                        "tool_use",
                                        id=tool_use["id"],
                                        name=tool_use["name"],
                                    )
                                    yield sse.content_block_delta(
                                        block_idx,
                                        "input_json_delta",
                                        json.dumps(tool_use["input"]),
                                    )
                                    yield sse.content_block_stop(block_idx)

                    # Handle native tool calls
                    if delta.tool_calls:
                        for event in sse.close_content_blocks():
                            yield event
                        for tc in delta.tool_calls:
                            tc_info = {
                                "index": tc.index,
                                "id": tc.id,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for event in self._process_tool_call(tc_info, sse, message_id):
                                yield event

                # 流完成 - 发送结束事件
                for event in self._finalize_stream(sse, finish_reason, usage_info, think_parser, heuristic_parser):
                    yield event

                # 成功完成，更新模型状态
                self._model_rotator.handle_success(current_model)
                logger.info(
                    f"NIM_STREAM: {message_id} - completed with model={current_model}"
                )
                return

            except (OpenAIRateLimitError, NotFoundError) as e:
                # 429 速率限制或 404 模型不可用
                last_error = e
                logger.warning(
                    f"NIM_STREAM: {message_id} - {current_model} failed: {type(e).__name__}"
                )

                # 标记当前模型不可用
                if isinstance(e, OpenAIRateLimitError):
                    self._model_rotator.handle_rate_limit(current_model)
                else:
                    self._model_rotator.handle_failure(current_model)

                # 切换到下一个可用模型
                current_model = self._model_rotator.get_available_model()

                # 如果还有可用模型，通知切换
                if current_model:
                    notification = (
                        f"🔄 Switching to model: {current_model} "
                        f"(previous model rate limited/unavailable)"
                    )
                    logger.info(f"NIM_STREAM: {message_id} - {notification}")

                    # 发送通知到客户端
                    for event in sse.emit_error(notification):
                        yield event
                else:
                    # 没有可用模型了
                    break

            except Exception as e:
                # 其他错误，不重试
                logger.error(f"NIM_STREAM: {message_id} - Unexpected error: {e}")
                last_error = e
                self._model_rotator.handle_failure(current_model)

                # 发送错误到客户端
                for event in sse.emit_error(str(e)):
                    yield event
                return

        # 所有模型都尝试失败
        error_msg = f"⚠️ All models exhausted. Last error: {last_error}"
        logger.error(f"NIM_STREAM: {message_id} - {error_msg}")
        for event in sse.emit_error(error_msg):
            yield event

    def _finalize_stream(self, sse, finish_reason, usage_info, think_parser, heuristic_parser):
        """Finalize stream by emitting remaining content and stop events."""
        # Flush remaining content from parsers
        remaining = think_parser.flush()
        if remaining:
            if remaining.type == ContentType.THINKING:
                for event in sse.ensure_thinking_block():
                    yield event
                yield sse.emit_thinking_delta(remaining.content)
            else:
                for event in sse.ensure_text_block():
                    yield event
                yield sse.emit_text_delta(remaining.content)

        for tool_use in heuristic_parser.flush():
            for event in sse.close_content_blocks():
                yield event

            block_idx = sse.blocks.allocate_index()
            yield sse.content_block_start(
                block_idx,
                "tool_use",
                id=tool_use["id"],
                name=tool_use["name"],
            )
            yield sse.content_block_delta(
                block_idx,
                "input_json_delta",
                json.dumps(tool_use["input"]),
            )
            yield sse.content_block_stop(block_idx)

        # Ensure at least one text block if no content/error occurred
        if sse.blocks.text_index == -1 and not sse.blocks.tool_indices:
            for event in sse.ensure_text_block():
                yield event
            yield sse.emit_text_delta(" ")

        # Close all blocks
        for event in sse.close_all_blocks():
            yield event

        # Send final events
        output_tokens = (
            usage_info.completion_tokens
            if usage_info and hasattr(usage_info, "completion_tokens")
            else sse.estimate_output_tokens()
        )
        yield sse.message_delta(map_stop_reason(finish_reason), output_tokens)
        yield sse.message_stop()
        yield sse.done()

    async def complete(self, request: Any) -> dict:
        """Make a non-streaming completion request."""
        await self._global_rate_limiter.wait_if_blocked()

        body = self._build_request_body(request, stream=False)
        logger.info(
            f"NIM_COMPLETE: model={body.get('model')} "
            f"msgs={len(body.get('messages', []))} "
            f"tools={len(body.get('tools', []))}"
        )

        try:
            response = await self._client.chat.completions.create(**body)
            return response.model_dump()
        except Exception as e:
            logger.error(f"NIM_ERROR: {type(e).__name__}: {e}")
            raise self._map_error(e)

    def _process_tool_call(self, tc: dict, sse: Any, request_id: str = None):
        """Process a single tool call delta and yield SSE events.

        Args:
            tc: Tool call delta info dict
            sse: SSEBuilder instance
            request_id: Request ID for logging (optional)
        """
        tc_index = tc.get("index", 0)
        if tc_index < 0:
            tc_index = len(sse.blocks.tool_indices)

        fn_delta = tc.get("function", {})
        if fn_delta.get("name") is not None:
            sse.blocks.tool_names[tc_index] = (
                sse.blocks.tool_names.get(tc_index, "") + fn_delta["name"]
            )

        if tc_index not in sse.blocks.tool_indices:
            name = sse.blocks.tool_names.get(tc_index, "")
            if name or tc.get("id"):
                tool_id = tc.get("id") or f"tool_{uuid.uuid4().hex}"
                yield sse.start_tool_block(tc_index, tool_id, name)
                sse.blocks.tool_started[tc_index] = True
        elif not sse.blocks.tool_started.get(tc_index) and sse.blocks.tool_names.get(
            tc_index
        ):
            tool_id = tc.get("id") or f"tool_{uuid.uuid4().hex}"
            name = sse.blocks.tool_names[tc_index]
            yield sse.start_tool_block(tc_index, tool_id, name)
            sse.blocks.tool_started[tc_index] = True

        args = fn_delta.get("arguments", "")
        if args:
            if not sse.blocks.tool_started.get(tc_index):
                tool_id = tc.get("id") or f"tool_{uuid.uuid4().hex}"
                name = sse.blocks.tool_names.get(tc_index, "tool_call") or "tool_call"

                yield sse.start_tool_block(tc_index, tool_id, name)
                sse.blocks.tool_started[tc_index] = True

            # INTERCEPTION: Force run_in_background=False for Task tool
            current_name = sse.blocks.tool_names.get(tc_index, "")
            if current_name == "Task":
                try:
                    args_json = json.loads(args)
                    if args_json.get("run_in_background") is not False:
                        if request_id:
                            logger.info(
                                f"NIM_INTERCEPT: {request_id} - "
                                f"forcing run_in_background=False for Task {tc.get('id', 'unknown')}"
                            )
                        args_json["run_in_background"] = False
                        args = json.dumps(args_json)
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(
                        f"NIM_INTERCEPT: Failed to parse/modify Task args: {e}"
                    )

            yield sse.emit_tool_delta(tc_index, args)

    async def close(self):
        """Explicitly close the provider and release resources.

        This should be called during application shutdown.
        """
        if hasattr(self, '_client') and self._client:
            await self._client.close()
            logger.info("NvidiaNimProvider: client closed")
