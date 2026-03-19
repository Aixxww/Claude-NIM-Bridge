# Claude NIM Bridge

> Use NVIDIA's free NIM API (40 req/min) as a drop-in replacement for Anthropic API with Claude Code

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg)]()

---

## Features

| Feature | Description |
|---------|-------------|
| 🚀 **Free API** | Use NVIDIA NIM free tier (40 req/min) |
| 🔄 **API Proxy** | Translation from Anthropic API format to NVIDIA NIM format |
| ⚡ **Streaming Support** | Full support for Anthropic-style streaming responses |
| 🎯 **Reasoning Models** | Support for thinking/reasoning model outputs |
| 🛡️ **Smart Optimization** | Intelligent skipping of quota checks and title generation requests |
| 📦 **Lightweight** | Pure proxy mode, minimal dependencies |

---

## Quick Start

### 1. Get NVIDIA API Key

Visit [build.nvidia.com/settings/api-keys](https://build.nvidia.com/settings/api-keys) to get your free API key.

### 2. Install Dependencies

```bash
cd /path/to/claude-nim-bridge

# Using uv (recommended)
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -e .

# Or using pip
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` file:

```env
NVIDIA_NIM_API_KEY=nvapi-your-key
MODEL=moonshotai/kimi-k2-thinking
```

### 4. Start the Service

```bash
# Direct start
uvicorn api.app:app --host 0.0.0.0 --port 8082

# Or use script
./run.sh
```

### 5. Use Claude Code

```bash
ANTHROPIC_AUTH_TOKEN=ccnim \
ANTHROPIC_BASE_URL=http://localhost:8082 \
claude
```

Or configure in `~/.claude/settings.json`:

```json
{
  "apiBase": "http://localhost:8082",
  "apiKey": "ccnim"
}
```

---

## Service Management

### Unified Management Script

```bash
cd /path/to/claude-nim-bridge

# Start
./manage.sh start

# Stop
./manage.sh stop

# Restart
./manage.sh restart

# Status
./manage.sh status

# Logs
./manage.sh logs

# Install with auto-start
./manage.sh install

# Uninstall
./manage.sh uninstall
```

### Platform Support

| Platform | Auto-start Method | Requirements |
|----------|------------------|--------------|
| **macOS** | LaunchAgent | No additional requirements |
| **Linux** | systemd | Requires sudo for install/uninstall |

### Quick Commands

```bash
# Start background service
./start_service.sh      # macOS/Linux
./run.sh                # Foreground

# Quick health check
curl http://localhost:8082/health
```

---

## Available Models

View full list at [build.nvidia.com/explore/discover](https://build.nvidia.com/explore/discover)

Recommended models:

| Model ID | Type | Description |
|----------|------|-------------|
| `moonshotai/kimi-k2-thinking` | Reasoning | Strong reasoning capability, default choice |
| `moonshotai/kimi-k2.5` | General | Balanced performance |
| `z-ai/glm4.7` | Chinese optimized | Optimized for Chinese content |
| `minimaxai/minimax-m2.1` | Efficient | Fast response for simple tasks |

Update model list:

```bash
curl "https://integrate.api.nvidia.com/v1/models" > nvidia_nim_models.json
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

## Project Structure

```
claude-nim-bridge/
├── manage.sh              # Main management script
├── start_service.sh       # Start script
├── stop_service.sh        # Stop script
├── run.sh                 # Run script
├── server.py              # Uvicorn entry point
├── api/                   # FastAPI application
│   ├── app.py            # App configuration
│   ├── routes.py         # API routes
│   ├── models.py         # Pydantic models
│   ├── dependencies.py   # Dependency injection
│   └── request_utils.py  # Request utilities
├── providers/             # Provider implementations
│   ├── nvidia_nim.py     # NVIDIA NIM provider
│   ├── nvidia_mixins.py  # NIM provider mixins
│   ├── model_utils.py    # Model name utilities
│   ├── rate_limit.py     # Rate limiting
│   ├── exceptions.py     # Provider exceptions
│   └── utils/            # Utility modules
│       ├── sse_builder.py       # SSE streaming
│       ├── message_converter.py # Format conversion
│       ├── think_parser.py      # Thinking tag parser
│       └── heuristic_tool_parser.py # Tool call parser
├── config/                # Configuration
│   └── settings.py       # Pydantic settings
├── tests/                 # Tests
├── .env                   # Environment variables (create this)
├── .env.example           # Environment variables template
├── claude-nim-bridge.service.example  # systemd service file
├── com.claude-nim-bridge.plist.example # LaunchAgent file
└── pyproject.toml         # Project configuration
```

---

## Configuration

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `NVIDIA_NIM_API_KEY` | NVIDIA API Key | - | Yes |
| `MODEL` | Default model ID | `moonshotai/kimi-k2-thinking` | No |
| `NVIDIA_NIM_RATE_LIMIT` | Rate limit per window | `40` | No |
| `NVIDIA_NIM_RATE_WINDOW` | Rate window in seconds | `60` | No |
| `FAST_PREFIX_DETECTION` | Enable prefix detection | `true` | No |
| `ENABLE_NETWORK_PROBE_MOCK` | Enable network probe mock | `true` | No |
| `ENABLE_TITLE_GENERATION_SKIP` | Skip title generation | `true` | No |

For full configuration reference, see `.env.example`.

---

## Troubleshooting

### Port Already Occupied

```bash
# Check process using the port
lsof -i :8082

# Stop service
./stop_service.sh
```

### Request Failed

```bash
# View logs
tail -f service.log

# Verify API Key
curl https://integrate.api.nvidia.com/v1/models \
  -H "Authorization: Bearer $NVIDIA_NIM_API_KEY"
```

For troubleshooting details, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

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
        {"role": "user", "content": "Hello, please introduce yourself"}
    ]
)

print(response.content[0].text)
```

---

## Auto-start Setup

### macOS (LaunchAgent)

```bash
# Install and configure
./manage.sh install

# Manual setup
cp com.claude-nim-bridge.plist.example ~/Library/LaunchAgents/com.claude-nim-bridge.plist
# Edit the plist file with your settings
launchctl load ~/Library/LaunchAgents/com.claude-nim-bridge.plist
launchctl start com.claude-nim-bridge

# Uninstall
./manage.sh uninstall
```

### Linux (systemd)

```bash
# Install and configure
sudo ./manage.sh install

# Manual setup
sudo cp claude-nim-bridge.service.example /etc/systemd/system/claude-nim-bridge.service
# Edit the service file with your paths and API key
sudo systemctl daemon-reload
sudo systemctl enable claude-nim-bridge
sudo systemctl start claude-nim-bridge

# View logs
sudo journalctl -u claude-nim-bridge -f

# Uninstall
sudo ./manage.sh uninstall
```

---

## Comparison

| Feature | Anthropic Official | Claude NIM Bridge |
|---------|-------------------|-------------------|
| Cost | Pay-per-use | Free |
| Rate Limit | Depends on plan | 40 req/min |
| Model Selection | Claude 3/4 Series | NVIDIA NIM Platform |
| Streaming | ✅ | ✅ |

---

## Documentation

For detailed documentation, see the [docs](docs) directory:

- **[Architecture](docs/ARCHITECTURE.md)** - System architecture and design
- **[API Reference](docs/API.md)** - Complete API documentation
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

---

## Other Languages

- [中文文档 (Chinese)](README_CN.md)

---

## License

MIT License - See [LICENSE](LICENSE) file
