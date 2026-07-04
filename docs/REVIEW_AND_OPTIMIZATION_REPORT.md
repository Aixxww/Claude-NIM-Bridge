# Claude NIM Bridge 审验与迭代优化报告

日期：2026-07-05

## 1. 产品定位

Claude NIM Bridge 的核心作用是把 Claude Code 发出的 Anthropic Messages API 请求转换为 OpenAI-compatible 请求，并转发到 NVIDIA NIM 或 Xiaomi MiMo。它的产品价值不是做一个通用聊天网关，而是为 Claude Code 提供一个低摩擦、可本地运行、可模型轮转的替代后端。

当前产品定位清晰：

- 对 Claude Code 暴露 Anthropic-compatible `/v1/messages` 和 `/v1/messages/count_tokens`。
- 对上游使用 OpenAI-compatible Chat Completions。
- 通过模型映射把 Claude 模型名统一映射到配置的 NIM/MiMo 模型。
- 通过本地优化拦截 Claude Code 的探测、标题生成、前缀检测等低价值请求。
- 通过 fallback 模型轮转降低 429、404、410 对使用流程的影响。

## 2. 架构链路

请求主链路：

1. `api.routes.create_message` 接收 Anthropic Messages 请求。
2. `api.models.MessagesRequest` 做模型名归一化。
3. `api.dependencies.get_provider` 创建并缓存 provider 单例。
4. `providers.nvidia_mixins.RequestBuilderMixin` 将 Anthropic 请求转换为 OpenAI-compatible 请求体。
5. `providers.nvidia_nim.NvidiaNimProvider` 执行 streaming 或 non-streaming 上游请求。
6. `providers.utils.sse_builder.SSEBuilder` 将 OpenAI streaming chunk 转回 Anthropic SSE。
7. `providers.nvidia_mixins.ResponseConverterMixin` 将 non-streaming response 转为 Anthropic 响应。

设计优点：

- provider 抽象边界基本清楚，NVIDIA NIM 与 MiMo 共享大部分 OpenAI-compatible 逻辑。
- 请求优化逻辑集中在 route 层，provider 层主要负责协议转换和上游交互。
- SSEBuilder 把 Anthropic 事件格式集中封装，降低流式响应拼接复杂度。
- ModelRotator 独立维护模型状态，便于扩展 fallback 策略。

主要设计风险：

- Provider 初始化时直接读取部分环境变量，而不是完全依赖 `Settings` 注入；长期会造成配置来源分裂。
- Streaming 分支承担了模型轮转、tool call、thinking parser、heuristic tool parser、SSE 生命周期等多种职责，后续复杂度还会继续上升。
- `ModelRotationContext` 当前未被主链路使用，属于遗留抽象，容易误导维护者。

## 3. 关键问题审验

### 3.1 NVIDIA 参数兼容性

之前请求体会注入 `reasoning_split`，NVIDIA GLM-5.2 返回 400：

```text
Unsupported parameter(s): `reasoning_split`
```

已优化：

- 不再默认向 NVIDIA 发送 `thinking` / `reasoning_split` 扩展参数。
- 即使客户端通过 `extra_body` 传入 `reasoning_split`，也会过滤。
- 保留对上游返回 `reasoning_content` 和 `<think>` 标签的解析。

### 3.2 已下线模型处理

`z-ai/glm5` 已在 2026-05-18 下线，NVIDIA 返回 410。当前代码已将 404/410 纳入不可用模型处理，并切换 fallback。

已优化：

- 默认主模型和文档更新为当前 `/models` 中存在的 `z-ai/glm-5.2`。
- fallback 更新为当前模型列表中的可用候选。
- 410 回归测试已覆盖。

### 3.3 Streaming SSE 生命周期

审验发现模型切换时，代理曾把“Switching to model”作为正文 content block 发给 Claude Code。这个信息是代理内部状态，不应污染用户响应；更重要的是，后续成功重试会重新初始化 block 状态，可能造成同一条 SSE 消息内 content block index 重复。

已优化：

- 模型切换改为只写日志，不再作为正文 SSE 发送。
- 移除成功上游请求前不必要的 `sse.blocks` 重置。
- 新增统一 `_emit_error_stream`，确保错误路径也发出完整 Anthropic SSE 生命周期：
  - `message_start`
  - `content_block_start`
  - `content_block_delta`
  - `content_block_stop`
  - `message_delta`
  - `message_stop`
  - `[DONE]`

### 3.4 GLM-5.2 官方参数对齐

参考 NVIDIA GLM-5.2 官方示例，当前配置应优先使用：

- `temperature=1`
- `top_p=1`
- `max_tokens=16384`
- `seed=42`
- `stream=true`

已优化：

- `.env` 与 `.env.example` 对齐 GLM-5.2 官方示例。
- `NVIDIA_NIM_SEED` 现在会实际转发给 OpenAI-compatible request。
- `NVIDIA_NIM_MAX_TOKENS` 作为输出上限生效，避免 Claude Code 请求超过当前模型推荐输出上限。
- 清理示例配置中当前未转发、容易误导的 NIM 参数。

### 3.5 Tool Choice 支持

GLM-5.2 官方模型卡标注支持 tool calling。Claude Code 会依赖工具调用质量。原逻辑已支持 tools schema 和 tool call delta，但未显式转换 Anthropic `tool_choice`。

已优化：

- 新增 `AnthropicToOpenAIConverter.convert_tool_choice`。
- 支持映射：
  - Anthropic `auto` -> OpenAI `auto`
  - Anthropic `none` -> OpenAI `none`
  - Anthropic `any` -> OpenAI `required`
  - Anthropic `tool` -> OpenAI function tool choice

## 4. 本次已实施优化

代码层：

- `providers/nvidia_nim.py`
  - 静默模型切换，避免污染 Claude Code 输出。
  - 完整化 streaming 错误 SSE 生命周期。
  - 移除不必要的 content block 状态重置。
  - 支持 404/410 不可用模型轮转。

- `providers/nvidia_mixins.py`
  - 过滤 `reasoning_split`。
  - 转发 `NVIDIA_NIM_SEED`。
  - 用 `NVIDIA_NIM_MAX_TOKENS` 作为 `max_tokens` 上限。
  - 转发 OpenAI-compatible `tool_choice`。

- `providers/utils/message_converter.py`
  - 新增 `tool_choice` 转换。
  - 跳过 message 列表中的 system role，避免与 Anthropic `system` 字段重复。

- `config/settings.py`
  - `MODEL_FALLBACK` 支持逗号分隔字符串和 JSON list。
  - 使用 `NoDecode` 避免 pydantic-settings 在 validator 前强制 JSON 解码失败。
  - 默认 max tokens 与 seed 对齐 GLM-5.2 示例。

配置与文档：

- `.env.example`
  - 主模型更新为 `z-ai/glm-5.2`。
  - fallback 更新为当前 NVIDIA `/models` 返回的可用模型。
  - NIM 参数精简到实际转发且适配 GLM-5.2 的字段。

- `README.md`
  - 更新模型示例、fallback 示例、配置表。

- `claude-nim-bridge.service.example`
  - 更新 MODEL 与 MODEL_FALLBACK。

- `com.claude-nim-bridge.plist.example`
  - 更新 MODEL 与 MODEL_FALLBACK。

测试层：

- 新增 `reasoning_split` 过滤测试。
- 新增 GLM 默认参数转发测试。
- 新增 `tool_choice` 转换测试。
- 新增 410 模型轮转测试。
- 新增模型耗尽时 SSE 完整收尾测试。

## 5. 验证结果

全量测试通过：

```bash
.venv/bin/pytest
```

结果：

```text
115 passed
```

服务健康检查通过：

```bash
curl http://localhost:8082/health
```

结果：

```json
{"status":"healthy"}
```

当前实际解析配置：

```text
MODEL=z-ai/glm-5.2
FALLBACK_COUNT=7
MAX_TOKENS=16384
SEED=42
```

## 6. 后续迭代建议

优先级 P0：

- 将 provider 内部环境变量读取统一迁移到 `Settings`，避免配置来源分裂。
- 给 streaming SSE 增加端到端快照测试，覆盖 text、thinking、tool call、error、model rotation 五类流。
- 对 `.env` 中的密钥配置增加文档警告，避免用户误提交真实 key。

优先级 P1：

- 清理 `ModelRotationContext` 这类未接入主链路的遗留抽象。
- 给 `/health` 增加可选 verbose 模式，例如返回 provider、model、fallback count，但默认继续保持轻量。
- 为 model rotator 增加更明确的状态指标：当前模型、不可用模型、冷却剩余秒数。
- 对 fallback 模型做启动时校验：如果本地 `nvidia_nim_models.json` 存在，可提示配置中不存在的模型。

优先级 P2：

- 增加 OpenAI-compatible structured output / response_format 的透传策略。
- 为不同模型维护 profile，例如 GLM、Qwen、Mistral、DeepSeek 分别配置推荐 `temperature/top_p/max_tokens/tool_choice`。
- 增加简单管理端点或 CLI：查看当前模型状态、重置不可用模型、热加载 fallback。

## 7. 结论

当前项目已经具备可用的 Claude Code -> NVIDIA NIM/MiMo 桥接能力。经过本次迭代后，GLM-5.2 参数适配、模型下线处理、fallback 稳定性、tool choice 兼容性和 streaming 错误收尾都有明显改善。

下一阶段最值得投入的是配置收敛和 streaming 端到端测试。只要这两块补齐，项目会从“能跑的代理”进一步稳定为“可长期使用和迭代的 Claude Code 后端适配层”。
