# Claude NIM Bridge

> Use NVIDIA's free NIM API (40 req/min) or Xiaomi MiMo as a drop-in replacement for Anthropic API with Claude Code

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg)]()

---

## Features

| Feature | Description |
|---------|-------------|
| 🚀 **Free API** | Use NVIDIA NIM free tier (40 req/min) or Xiaomi MiMo |
| 🔄 **Multi-Provider** | Switch between NVIDIA NIM and Xiaomi MiMo via config |
| 🔀 **Model Rotation** | Auto-rotate through 7+ fallback models when rate-limited (429) |
| ⚡ **Streaming Support** | Full Anthropic-style SSE streaming responses |
| 🎯 **Reasoning Models** | Support for thinking/reasoning model outputs |
| 🛡️ **Smart Optimization** | Intelligent skipping of quota checks and title generation requests |
| 📦 **Lightweight** | Pure proxy mode, minimal dependencies |

---

## Architecture

```
Claude Code ──[Anthropic API]──> Claude NIM Bridge (localhost:8082) ──[OpenAI API]──> NVIDIA NIM / Xiaomi MiMo
```

The bridge translates Anthropic Messages API format to OpenAI-compatible chat completions format, enabling Claude Code to work with any OpenAI-compatible backend.

---

## Quick Start

### 1. Get an API Key

**NVIDIA NIM** (free, 40 req/min):
Visit [build.nvidia.com/settings/api-keys](https://build.nvidia.com/settings/api-keys)

**Xiaomi MiMo** (optional alternative):
Get API key from [MiMo platform](https://api.xiaomimimo.com)

### 2. Install

```bash
git clone git@github.com:Aixxww/Claude-NIM-Bridge.git
cd Claude-NIM-Bridge

# Using uv (recommended)
uv venv && source .venv/bin/activate
uv pip install -e .

# Or using pip
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```env
# --- Provider Selection ---
PROVIDER=nvidia_nim          # "nvidia_nim" (default) or "mimo"

# --- NVIDIA NIM ---
NVIDIA_NIM_API_KEY=nvapi-your-key-here
MODEL=moonshotai/kimi-k2-thinking

# --- Xiaomi MiMo (if using mimo provider) ---
# PROVIDER=mimo
# MIMO_API_KEY=your-mimo-key
# MIMO_MODEL=mimo-v2.5-pro
```

### 4. Start

```bash
# Foreground
./cc-nim.sh start

# Or directly
uvicorn api.app:app --host 0.0.0.0 --port 8082
```

### 5. Use with Claude Code

```bash
ANTHROPIC_AUTH_TOKEN=ccnim ANTHROPIC_BASE_URL=http://localhost:8082 claude
```

Or add to `~/.claude/settings.json`:

```json
{
  "apiBase": "http://localhost:8082",
  "apiKey": "ccnim"
}
```

---

## Multi-Provider Support

### NVIDIA NIM (Default)

The primary provider using NVIDIA's free NIM API. Supports 100+ models including reasoning models.

```env
PROVIDER=nvidia_nim
NVIDIA_NIM_API_KEY=nvapi-xxx
MODEL=moonshotai/kimi-k2-thinking
```

### Xiaomi MiMo

Xiaomi's MiMo model via OpenAI-compatible API. Extends the NIM provider with MiMo-specific defaults.

```env
PROVIDER=mimo
MIMO_API_KEY=your-key
MIMO_MODEL=mimo-v2.5-pro
```

---

## Model Rotation

When a model hits its rate limit (HTTP 429), the bridge automatically rotates to the next available model. Configure fallback models:

```env
MODEL=moonshotai/kimi-k2-thinking
MODEL_FALLBACK=moonshotai/kimi-k2.5,z-ai/glm4.7,minimaxai/minimax-m2.1
```

Rotation order: Primary MODEL -> FALLBACK[0] -> FALLBACK[1] -> ... -> back to primary.

---

## Service Management

All-in-one management script:

```bash
./cc-nim.sh start      # Start service
./cc-nim.sh stop       # Stop service
./cc-nim.sh restart    # Restart
./cc-nim.sh status     # Check status
./cc-nim.sh logs       # View logs
./cc-nim.sh install    # Install as auto-start service
./cc-nim.sh uninstall  # Remove auto-start service
```

### Auto-start

| Platform | Method | Notes |
|----------|--------|-------|
| **macOS** | LaunchAgent | No additional requirements |
| **Linux** | systemd | Requires sudo for install/uninstall |

Health check:

```bash
curl http://localhost:8082/health
```

---

## Available Models

View full list: [build.nvidia.com/explore/discover](https://build.nvidia.com/explore/discover)

| Model ID | Type | Description |
|----------|------|-------------|
| `moonshotai/kimi-k2-thinking` | Reasoning | Strong reasoning, default choice |
| `moonshotai/kimi-k2.5` | General | Balanced performance |
| `z-ai/glm4.7` | Chinese | Optimized for Chinese content |
| `minimaxai/minimax-m2.1` | Efficient | Fast response for simple tasks |

Refresh model cache:

```bash
curl "https://integrate.api.nvidia.com/v1/models" -H "Authorization: Bearer $NVIDIA_NIM_API_KEY" > nvidia_nim_models.json
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/messages` | POST | Create message (streaming/non-streaming) |
| `/v1/messages/count_tokens` | POST | Count tokens |
| `/health` | GET | Health check |
| `/` | GET | Service info |

---

## Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `PROVIDER` | Backend provider (`nvidia_nim` or `mimo`) | `nvidia_nim` |
| `MODEL` | Primary model ID | `moonshotai/kimi-k2-thinking` |
| `MODEL_FALLBACK` | Comma-separated fallback models | *(empty)* |
| `NVIDIA_NIM_API_KEY` | NVIDIA API key | *(required for nvidia_nim)* |
| `MIMO_API_KEY` | MiMo API key | *(required for mimo)* |
| `MIMO_MODEL` | MiMo model ID | `mimo-v2.5-pro` |
| `NVIDIA_NIM_RATE_LIMIT` | Rate limit per window | `40` |
| `NVIDIA_NIM_RATE_WINDOW` | Rate window in seconds | `60` |
| `FAST_PREFIX_DETECTION` | Enable prefix detection | `true` |
| `ENABLE_NETWORK_PROBE_MOCK` | Enable network probe mock | `true` |
| `ENABLE_TITLE_GENERATION_SKIP` | Skip title generation requests | `true` |
| `NVIDIA_NIM_MAX_TOKENS` | Max output tokens | `81920` |
| `NVIDIA_NIM_REASONING_EFFORT` | Reasoning effort level | `high` |

See `.env.example` for full configuration reference.

---

## Python SDK Usage

```python
import anthropic

client = anthropic.Anthropic(
    api_key="ccnim",
    base_url="http://localhost:8082"
)

response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)

print(response.content[0].text)
```

---

## Project Structure

```
Claude-NIM-Bridge/
├── cc-nim.sh                      # Unified management script
├── server.py                      # Uvicorn entry point
├── pyproject.toml                 # Project config (v2.2.0)
├── .env.example                   # Environment template
├── LICENSE                        # MIT
│
├── api/                           # FastAPI application
│   ├── app.py                     # App factory, lifespan, error handlers
│   ├── routes.py                  # /v1/messages, /health endpoints
│   ├── models.py                  # Pydantic request/response models
│   ├── dependencies.py            # DI — provider & settings singletons
│   └── request_utils.py           # Quota check, title gen, prefix detection
│
├── providers/                     # LLM provider implementations
│   ├── base.py                    # BaseProvider abstract class
│   ├── nvidia_nim.py              # NVIDIA NIM provider (OpenAI SDK)
│   ├── nvidia_mixins.py           # NIM-specific mixins
│   ├── mimo.py                    # Xiaomi MiMo provider
│   ├── model_utils.py             # Model name mapping/rotation
│   ├── model_rotator.py           # Multi-model rotation logic
│   ├── rate_limit.py              # Async rate limiter
│   ├── exceptions.py              # Custom exceptions
│   ├── logging_utils.py           # Compact request logging
│   └── utils/
│       ├── sse_builder.py         # SSE streaming builder
│       ├── message_converter.py   # Anthropic <-> OpenAI format conversion
│       ├── think_parser.py        # Thinking tag parser
│       └── heuristic_tool_parser.py  # Tool call parser
│
├── config/
│   └── settings.py                # Pydantic Settings from .env
│
└── tests/                         # Test suite
```

---

## Troubleshooting

### Port Already in Use

```bash
lsof -i :8082
./cc-nim.sh stop
```

### Rate Limited (429)

The bridge auto-rotates models. If all models are rate-limited, add more fallbacks:

```env
MODEL_FALLBACK=moonshotai/kimi-k2.5,z-ai/glm4.7,minimaxai/minimax-m2.1,nvidia/nemotron-3-8b-chat
```

### Request Failed

```bash
# Check logs
./cc-nim.sh logs

# Verify API key
curl https://integrate.api.nvidia.com/v1/models   -H "Authorization: Bearer $NVIDIA_NIM_API_KEY"

# Health check
curl http://localhost:8082/health
```

---

## Comparison

| Feature | Anthropic Official | Claude NIM Bridge |
|---------|-------------------|-------------------|
| Cost | Pay-per-use | Free |
| Rate Limit | Depends on plan | 40 req/min (rotatable) |
| Model Selection | Claude 3/4 Series | 100+ NIM models / MiMo |
| Streaming | ✅ | ✅ |
| Tool Use | ✅ | ✅ (heuristic parsing) |
| Thinking | ✅ | ✅ |

---

## License

MIT License - See [LICENSE](LICENSE) file
