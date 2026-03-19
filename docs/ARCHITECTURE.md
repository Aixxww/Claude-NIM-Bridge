# Architecture

## Overview

Claude NIM Bridge is a lightweight proxy service that converts Anthropic API requests to NVIDIA NIM format, enabling free usage of NVIDIA's LLM models.

## System Architecture

```
┌─────────────────┐
│   Claude Code   │
│  (Client App)   │
└────────┬────────┘
         │ Anthropic API
         │ (GET/POST)
         ▼
┌─────────────────────────────────┐
│   Claude NIM Bridge             │
│   ┌─────────────────────────┐   │
│   │   FastAPI Application   │   │
│   │   ┌─────────────────┐   │   │
│   │   │  Request Router │   │   │
│   │   │  (routes.py)    │   │   │
│   │   └────────┬────────┘   │   │
│   │            │             │   │
│   │   ┌────────▼────────┐   │   │
│   │   │  Optimizations  │   │   │
│   │   │  - Quota skips  │   │   │
│   │   │  - Prefix detect│   │   │
│   │   │  - Title skip   │   │   │
│   │   └────────┬────────┘   │   │
│   │            │             │   │
│   │   ┌────────▼────────┐   │   │
│   │   │  Format Conv.   │   │   │
│   │   └────────┬────────┘   │   │
│   │            │             │   │
│   │   ┌────────▼────────┐   │   │
│   │   │  NvidiaNimProv. │   │   │
│   │   │  (AsyncOpenAI)  │   │   │
│   │   └────────┬────────┘   │   │
│   └────────────┼─────────────┘   │
                │                 │
                │ OpenAI Format   │
                ▼                 │
┌─────────────────────────────────┤
│   NVIDIA NIM API               │
│   (Free Tier - 40 req/min)     │
└─────────────────────────────────┘
```

## Project Structure

```
claude-nim-bridge/
├── api/                       # FastAPI application layer
│   ├── app.py                # App factory and lifespan
│   ├── routes.py             # API route handlers
│   ├── models.py             # Pydantic data models
│   ├── dependencies.py       # Dependency injection
│   └── request_utils.py      # Request optimization utilities
├── providers/                 # LLM provider implementations
│   ├── nvidia_nim.py         # NVIDIA NIM provider
│   ├── nvidia_mixins.py      # NIM provider mixins
│   ├── base.py               # Base provider interface
│   ├── model_utils.py        # Model name normalization
│   ├── rate_limit.py         # Global rate limiting
│   ├── exceptions.py         # Provider exceptions
│   ├── logging_utils.py      # Logging utilities
│   └── utils/                # Utility modules
│       ├── sse_builder.py    # SSE stream builder
│       ├── message_converter.py  # Format conversion
│       ├── think_parser.py   # Thinking tag parser
│       └── heuristic_tool_parser.py  # Tool call parser
├── config/                    # Configuration
│   └── settings.py           # Pydantic settings
├── tests/                     # Test suite
│   ├── conftest.py           # Test fixtures
│   ├── test_*.py             # Test modules
├── docs/                      # Documentation
│   └── ARCHITECTURE.md       # This file
├── manage.sh                  # Cross-platform service manager
├── run.sh                     # Quick start script
├── server.py                  # Uvicorn entry point
├── pyproject.toml            # Project configuration
├── .env.example              # Environment template
├── claude-nim-bridge.service.example  # systemd service
└── com.claude-nim-bridge.plist.example # LaunchAgent
```

## Core Components

### 1. Request Router (`api/routes.py`)

Handles incoming HTTP requests:
- `/v1/messages` - Main chat endpoint (streaming/non-streaming)
- `/v1/messages/count_tokens` - Token counting
- `/health` - Health check
- `/` - Service info

### 2. Provider Interface (`providers/base.py`)

Abstract base class for LLM providers:
```python
class BaseProvider(ABC):
    @abstractmethod
    async def complete(self, request) -> dict: pass

    @abstractmethod
    async def stream_response(self, request, input_tokens) -> AsyncIterator[str]: pass
```

### 3. NVIDIA NIM Provider (`providers/nvidia_nim.py`)

Implements the provider interface using the official OpenAI Python SDK:
- AsyncOpenAI client for HTTP communication
- Automatic format conversion (Anthropic → OpenAI → Anthropic)
- Streaming response handling with SSE
- Native tool call support
- Thinking/reasoning content extraction

### 4. Rate Limiting (`providers/rate_limit.py`)

Dual-layer rate limiting:
- Proactive: Token bucket before API calls
- Reactive: Global block on 429 errors

### 5. Format Conversion

Two-way conversion between Anthropic and OpenAI formats:
- Messages, tools, system prompts
- Thinking/reasoning blocks
- Tool calls and results

## Request Flow

### Non-Streaming Request

```
Client → FastAPI → Route Handler → Validation
       → Provider → Format Conv. → OpenAI SDK
       → NVIDIA API → Response → Format Conv.
       → Client
```

### Streaming Request

```
Client → FastAPI → Route Handler → Validation
       → Provider → Format Conv. → OpenAI SDK (Stream)
       └─ SSE Parser → SSE Builder → Event Stream
       → Client (SSE)
```

## Optimizations

### Smart Request Skipping

| Optimization | Trigger | Action |
|--------------|---------|--------|
| Quota Check | `max_tokens=1` + "quota" keyword | Return mock response |
| Title Generation | "write a 5-10 word title" phrase | Return mock title |
| Prefix Detection | `<policy_spec>` + `Command:` | Return command prefix |

### Memory Safety

- Proper async resource cleanup (`client.close()`)
- Try-finally blocks for streaming
- Local parser instances (garbage collected)

## Cross-Platform Service Management

### macOS (LaunchAgent)

```bash
./manage.sh install  # Creates ~/Library/LaunchAgents/
```

### Linux (systemd)

```bash
./manage.sh install  # Creates /etc/systemd/system/
```

## Configuration

Environment-based configuration using Pydantic Settings:
- `.env` file for local overrides
- Type-safe validation
- Default values for all settings

## Testing

Full test coverage with pytest:
- Unit tests for utilities
- Integration tests for API
- Mock-based provider tests

110 tests, all passing.
