# API Reference

## Overview

Claude NIM Bridge provides an Anthropic-compatible API for NVIDIA NIM models.

**Base URL:** `http://localhost:8082`

**Authentication:** Use any API key (e.g., `ccnim`)

---

## Endpoints

### POST /v1/messages

Create a new message (streaming or non-streaming).

#### Request Headers

```http
Content-Type: application/json
x-api-key: ccnim
anthropic-version: 2023-06-01
```

#### Request Body

```json
{
  "model": "claude-opus-4-6",
  "max_tokens": 1024,
  "messages": [
    {"role": "user", "content": "Hello, how are you?"}
  ],
  "stream": false,
  "temperature": 1.0,
  "top_p": 1.0,
  "stop_sequences": ["STOP"],
  "system": "You are a helpful assistant.",
  "tools": [
    {
      "name": "calculator",
      "description": "Perform calculations",
      "input_schema": {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"]
      }
    }
  ],
  "thinking": {"enabled": true}
}
```

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | Model name (will be mapped to NIM model) |
| `max_tokens` | integer | Yes | Maximum tokens to generate |
| `messages` | array of Message | Yes | Conversation messages |
| `stream` | boolean | No | Enable streaming (default: false) |
| `temperature` | float | No | Sampling temperature (0-1, default: 1.0) |
| `top_p` | float | No | Nucleus sampling threshold (default: 1.0) |
| `top_k` | integer | No | Top-k sampling threshold |
| `stop_sequences` | array | No | Stop sequences |
| `system` | string or array | No | System prompt |
| `tools` | array of Tool | No | Tool definitions |
| `thinking` | object | No | Thinking configuration |

#### Message Object

```typescript
interface Message {
  role: "user" | "assistant";
  content: string | ContentBlock[];
}
```

#### Content Blocks

```typescript
type ContentBlock =
  | { type: "text"; text: string }
  | { type: "image"; source: ImageSource }
  | { type: "tool_use"; id: string; name: string; input: object }
  | { type: "tool_result"; tool_use_id: string; content: string | array }
  | { type: "thinking"; thinking: string };
```

#### Response (Non-Streaming)

```json
{
  "id": "msg_1234567890",
  "type": "message",
  "role": "assistant",
  "model": "moonshotai/kimi-k2-thinking",
  "content": [
    {"type": "thinking", "thinking": "Let me think..."},
    {"type": "text", "text": "Hello! I'm doing well, thank you."}
  ],
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 10,
    "output_tokens": 25,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0
  }
}
```

#### Response (Streaming)

Server-Sent Events (SSE) format:

```
event: message_start
data: {"type":"message_start","message":{"id":"msg_123","type":"message","role":"assistant","content":[]}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"thinking"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"Let me think..."}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: content_block_start
data: {"type":"content_block_start","index":1,"content_block":{"type":"text"}}

event: content_block_delta
data: {"type":"content_block_delta","index":1,"delta":{"type":"text_delta","text":"Hello!"}}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":5}}

event: message_stop
data: {"type":"message_stop"}
```

#### Stop Reasons

| Value | Description |
|-------|-------------|
| `end_turn` | Model naturally finished |
| `max_tokens` | Reached max_tokens limit |
| `stop_sequence` | Hit a stop sequence |
| `tool_use` | Model initiated a tool use |

---

### POST /v1/messages/count_tokens

Count tokens for a request without generating a response.

#### Request Body

Same as `/v1/messages` but without `max_tokens`.

#### Response

```json
{
  "input_tokens": 42
}
```

---

### GET /health

Health check endpoint.

#### Response

```json
{
  "status": "ok",
  "service": "Claude NIM Bridge",
  "version": "2.2.0",
  "provider": "NVIDIA NIM",
  "model": "moonshotai/kimi-k2-thinking"
}
```

---

### GET /

Service information.

#### Response

```json
{
  "name": "Claude NIM Bridge",
  "version": "2.2.0",
  "description": "Anthropic API compatible proxy for NVIDIA NIM",
  "docs": "https://github.com/Aixxww/Claude-NIM-Bridge",
  "endpoints": {
    "messages": "/v1/messages",
    "count_tokens": "/v1/messages/count_tokens",
    "health": "/health"
  }
}
```

---

## Model Mapping

All Claude model names are mapped to the configured NIM model.

| Input Model | Mapped To |
|-------------|-----------|
| `claude-opus-4-6` | Configured MODEL (default: `moonshotai/kimi-k2-thinking`) |
| `claude-sonnet-4-6` | Configured MODEL |
| `claude-haiku-4-6` | Configured MODEL |
| `anthropic/claude-3-opus` | Configured MODEL |
| Any Claude name | Configured MODEL |
| Other names | Passed through unchanged |

---

## Error Responses

All errors follow Anthropic's error format:

```json
{
  "type": "error",
  "error": {
    "type": "api_error",
    "message": "Error description here"
  }
}
```

### Error Types

| Type | HTTP Code | Description |
|------|-----------|-------------|
| `validation_error` | 400 | Invalid request parameters |
| `authentication_error` | 401 | Authentication failed |
| `permission_error` | 403 | Insufficient permissions |
| `not_found_error` | 404 | Resource not found |
| `rate_limit_error` | 429 | Rate limit exceeded |
| `api_error` | 500 | Internal server error |

---

## Examples

### cURL (Non-Streaming)

```bash
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: ccnim" \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### cURL (Streaming)

```bash
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: ccnim" \
  -N \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 100,
    "stream": true,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Python (anthropic SDK)

```python
import anthropic

client = anthropic.Anthropic(
    api_key="ccnim",
    base_url="http://localhost:8082"
)

response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}]
)

print(response.content[0].text)
```

### JavaScript (anthropic SDK)

```javascript
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic({
  apiKey: 'ccnim',
  baseURL: 'http://localhost:8082',
  dangerouslyAllowBrowser: true
});

const message = await client.messages.create({
  model: 'claude-opus-4-6',
  max_tokens: 1024,
  messages: [{ role: 'user', content: 'Hello!' }]
});

console.log(message.content[0].text);
```

---

## Rate Limits

NVIDIA NIM free tier:
- **Rate:** 40 requests per minute
- **Window:** 60 seconds

The bridge proactively throttles requests to stay within limits and reactively blocks all requests temporarily if a 429 error is received.
