# Claude NIM Bridge

> 使用 NVIDIA 的免费 NIM API（40 请求/分钟）替代 Anthropic API 运行 Claude Code

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg)]()

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 🚀 **免费 API** | 使用 NVIDIA NIM 免费套餐（40 请求/分钟） |
| 🔄 **API 代理** | 将 Anthropic API 请求转换为 NVIDIA NIM 格式 |
| ⚡ **流式支持** | 完整支持 Anthropic 格式的流式响应 |
| 🎯 **推理模型** | 支持带思维链输出的推理模型 |
| 🛡️ **智能优化** | 智能跳过配额检查和标题生成请求 |
| 📦 **精简设计** | 纯代理模式，极简依赖 |

---

## 快速开始

### 1. 获取 NVIDIA API 密钥

访问 [build.nvidia.com/settings/api-keys](https://build.nvidia.com/settings/api-keys) 获取免费 API 密钥。

### 2. 安装依赖

```bash
cd /path/to/claude-nim-bridge

# 使用 uv（推荐）
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -e .

# 或使用 pip
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
NVIDIA_NIM_API_KEY=nvapi-your-key
MODEL=moonshotai/kimi-k2-thinking
```

### 4. 启动服务

```bash
# 直接启动
uvicorn api.app:app --host 0.0.0.0 --port 8082

# 或使用脚本
./run.sh
```

### 5. 使用 Claude Code

```bash
ANTHROPIC_AUTH_TOKEN=ccnim \
ANTHROPIC_BASE_URL=http://localhost:8082 \
claude
```

或在 `~/.claude/settings.json` 中配置：

```json
{
  "apiBase": "http://localhost:8082",
  "apiKey": "ccnim"
}
```

---

## 服务管理

### 统一管理脚本

```bash
cd /path/to/claude-nim-bridge

# 启动
./manage.sh start

# 停止
./manage.sh stop

# 重启
./manage.sh restart

# 状态
./manage.sh status

# 日志
./manage.sh logs

# 安装并配置开机自启
./manage.sh install

# 卸载
./manage.sh uninstall
```

### 平台支持

| 平台 | 开机自启方式 | 要求 |
|------|------------|------|
| **macOS** | LaunchAgent | 无额外要求 |
| **Linux** | systemd | 安装/卸载需要 sudo |

### 快速命令

```bash
# 启动后台服务
./start_service.sh      # macOS/Linux
./run.sh                # 前台运行

# 快速健康检查
curl http://localhost:8082/health
```

---

## 可用模型

查看完整列表: [build.nvidia.com/explore/discover](https://build.nvidia.com/explore/discover)

推荐模型：

| 模型 ID | 类型 | 说明 |
|---------|------|------|
| `moonshotai/kimi-k2-thinking` | 推理模型 | 强大的推理能力，默认选择 |
| `moonshotai/kimi-k2.5` | 通用模型 | 平衡的性能与速度 |
| `z-ai/glm4.7` | 中文优化 | 针对中文内容优化 |
| `minimaxai/minimax-m2.1` | 高效模型 | 快速响应，适合简单任务 |

更新模型列表：

```bash
curl "https://integrate.api.nvidia.com/v1/models" > nvidia_nim_models.json
```

---

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/messages` | POST | 发送消息（流式/非流式） |
| `/v1/messages/count_tokens` | POST | 计算 Token 数量 |
| `/health` | GET | 健康检查 |
| `/` | GET | 服务信息 |

---

## 项目结构

```
claude-nim-bridge/
├── manage.sh              # 主管理脚本
├── start_service.sh       # 启动脚本
├── stop_service.sh        # 停止脚本
├── run.sh                 # 运行脚本
├── server.py              # uvicorn 入口
├── api/                   # FastAPI 应用
│   ├── app.py            # 应用配置
│   ├── routes.py         # API 路由
│   ├── models.py         # Pydantic 模型
│   ├── dependencies.py   # 依赖注入
│   └── request_utils.py  # 请求工具
├── providers/             # 提供商实现
│   ├── nvidia_nim.py     # NVIDIA NIM 提供商
│   ├── nvidia_mixins.py  # NIM 提供商混入
│   ├── model_utils.py    # 模型名称工具
│   ├── rate_limit.py     # 速率限制
│   ├── exceptions.py     # 提供商异常
│   └── utils/            # 工具模块
│       ├── sse_builder.py       # SSE 流式
│       ├── message_converter.py # 格式转换
│       ├── think_parser.py      # 思维标签解析
│       └── heuristic_tool_parser.py # 工具调用解析
├── config/                # 配置
│   └── settings.py       # Pydantic 配置
├── tests/                 # 测试
├── .env                   # 环境变量（需创建）
├── .env.example           # 环境变量示例
├── claude-nim-bridge.service.example  # systemd 服务文件
├── com.claude-nim-bridge.plist.example # LaunchAgent 文件
└── pyproject.toml         # 项目配置
```

---

## 配置参数

| 参数 | 说明 | 默认值 | 必需 |
|------|------|--------|------|
| `NVIDIA_NIM_API_KEY` | NVIDIA API 密钥 | - | 是 |
| `MODEL` | 默认模型 ID | `moonshotai/kimi-k2-thinking` | 否 |
| `NVIDIA_NIM_RATE_LIMIT` | 每时间窗口请求限制 | `40` | 否 |
| `NVIDIA_NIM_RATE_WINDOW` | 时间窗口（秒）| `60` | 否 |
| `FAST_PREFIX_DETECTION` | 启用前缀检测 | `true` | 否 |
| `ENABLE_NETWORK_PROBE_MOCK` | 启用网络探测模拟 | `true` | 否 |
| `ENABLE_TITLE_GENERATION_SKIP` | 跳过标题生成 | `true` | 否 |

完整配置参考请参见 `.env.example`。

---

## 故障排查

### 端口被占用

```bash
# 查看占用端口的进程
lsof -i :8082

# 停止服务
./stop_service.sh
```

### 请求失败

```bash
# 查看日志
tail -f service.log

# 验证 API 密钥
curl https://integrate.api.nvidia.com/v1/models \
  -H "Authorization: Bearer $NVIDIA_NIM_API_KEY"
```

更多故障排查详情，请查看日志文件或运行 `./manage.sh status`。

---

## Python SDK 使用

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
        {"role": "user", "content": "你好，请介绍一下自己"}
    ]
)

print(response.content[0].text)
```

---

## 开机自启配置

### macOS (LaunchAgent)

```bash
# 安装并配置
./manage.sh install

# 手动设置
cp com.claude-nim-bridge.plist.example ~/Library/LaunchAgents/com.claude-nim-bridge.plist
# 编辑 plist 文件填入配置
launchctl load ~/Library/LaunchAgents/com.claude-nim-bridge.plist
launchctl start com.claude-nim-bridge

# 卸载
./manage.sh uninstall
```

### Linux (systemd)

```bash
# 安装并配置
sudo ./manage.sh install

# 手动设置
sudo cp claude-nim-bridge.service.example /etc/systemd/system/claude-nim-bridge.service
# 编辑服务文件填入路径和密钥
sudo systemctl daemon-reload
sudo systemctl enable claude-nim-bridge
sudo systemctl start claude-nim-bridge

# 查看日志
sudo journalctl -u claude-nim-bridge -f

# 卸载
sudo ./manage.sh uninstall
```

---

## 对比

| 特性 | Anthropic 官方 API | Claude NIM Bridge |
|------|-------------------|-------------------|
| 费用 | 按使用收费 | 完全免费 |
| 速率限制 | 取决于套餐 | 40 req/min |
| 模型选择 | Claude 3/4 系列 | NVIDIA NIM 平台模型 |
| 流式响应 | ✅ | ✅ |

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 其他语言

- [English Documentation](README.md)
