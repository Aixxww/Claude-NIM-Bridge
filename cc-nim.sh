#!/bin/bash
# ==========================================
# Claude NIM Bridge - 统一管理脚本
# ==========================================
# 功能: 一键安装/启动/停止/管理服务
# 平台: macOS (LaunchAgent) / Linux (systemd)
# ==========================================

set -e
cd "$(dirname "$0")"

# 项目配置
PROJECT_NAME="claude-nim-bridge"
PORT=8082
PYTHON_BIN=".venv/bin/python"
PID_FILE="service.pid"
LOG_FILE="service.log"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info()    { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error()   { echo -e "${RED}❌ $1${NC}"; }

# 检测操作系统
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    LAUNCH_AGENT="com.claude-nim-bridge"
    LAUNCH_AGENT_PATH="$HOME/Library/LaunchAgents/$LAUNCH_AGENT.plist"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    SERVICE_NAME="claude-nim-bridge"
    SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
else
    OS="unknown"
    print_warning "未知系统类型，使用基础命令"
fi

# 检查服务是否运行
is_running() {
    if [ "$OS" == "linux" ]; then
        systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null
        return $?
    else
        ps aux | grep "uvicorn.*server:app" | grep -v grep > /dev/null
        return $?
    fi
}

# 加载环境变量
load_env() {
    if [ -f .env ]; then
        set -a && source .env && set +a
        print_success "环境变量已加载"
    else
        print_warning ".env 文件未找到"
        if [ "$1" != "status" ] && [ "$1" != "stop" ]; then
            print_info "从示例文件创建 .env..."
            cp .env.example .env 2>/dev/null || true
            print_warning "请编辑 .env 文件并设置 NVIDIA_NIM_API_KEY"
        fi
    fi
}

# 停止服务
stop_service() {
    if ! is_running; then
        print_info "服务未运行"
        return 0
    fi

    print_info "停止 $PROJECT_NAME..."

    if [ "$OS" == "linux" ]; then
        sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        print_success "服务已停止 (systemd)"
    else
        PIDS=$(ps aux | grep "uvicorn.*server:app" | grep -v grep | awk '{print $2}')
        if [ -n "$PIDS" ]; then
            kill $PIDS 2>/dev/null
            sleep 2

            REMAINING=$(ps aux | grep "uvicorn.*server:app" | grep -v grep | awk '{print $2}')
            [ -n "$REMAINING" ] && kill -9 $REMAINING 2>/dev/null
            print_success "服务已停止"
        fi
    fi

    rm -f $PID_FILE 2>/dev/null

    # 检查端口
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "端口 $PORT 仍被占用"
    else
        print_success "端口 $PORT 已释放"
    fi
}

# 启动服务
start_service() {
    if is_running; then
        print_warning "服务已在运行"
        return 0
    fi

    load_env start

    print_info "启动 $PROJECT_NAME..."

    if [ "$OS" == "linux" ]; then
        sudo systemctl start "$SERVICE_NAME" 2>/dev/null || \
            nohup .venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port $PORT --log-level info > $LOG_FILE 2>&1 &
    else
        nohup .venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port $PORT --log-level info > $LOG_FILE 2>&1 &
        local pid=$!
        echo $pid > $PID_FILE
        sleep 2
    fi

    if ps -p ${PID:-$(cat $PID_FILE 2>/dev/null)} > /dev/null 2>&1 || is_running; then
        print_success "服务已启动 (PID: $(cat $PID_FILE 2>/dev/null || echo 'systemd'))"

        # 验证服务响应
        sleep 2
        if curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
            print_success "API 响应正常"
        fi
    else
        print_error "服务启动失败"
        cat $LOG_FILE 2>/dev/null
        return 1
    fi
}

# 重启服务
restart_service() {
    print_info "重启 $PROJECT_NAME..."
    stop_service
    sleep 1
    start_service
}

# 查看状态
show_status() {
    echo ""
    echo "==============================================="
    echo "  $PROJECT_NAME - 状态"
    echo "==============================================="
    echo "  OS: $OS | Port: $PORT"
    echo "==============================================="
    echo ""

    if [ "$OS" == "linux" ]; then
        sudo systemctl status "$SERVICE_NAME" --no-pager -l 2>/dev/null || print_error "systemd 服务未配置"
    else
        PIDS=$(ps aux | grep "uvicorn.*server:app" | grep -v grep)
        if [ -n "$PIDS" ]; then
            print_success "服务正在运行:"
            echo "$PIDS"
            echo ""

            [ -f "$PID_FILE" ] && echo "  PID: $(cat $PID_FILE)"

            if curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
                print_success "API: $(curl -s http://localhost:$PORT/health)"
            fi

            [ -f "$LAUNCH_AGENT_PATH" ] && print_info "LaunchAgent: 已配置"
        else
            print_error "服务未运行"
        fi
    fi
    echo ""
}

# 查看日志
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        print_info "查看日志 (Ctrl+C 退出):"
        tail -f "$LOG_FILE"
    else
        print_error "日志文件未找到: $LOG_FILE"
    fi
}

# 前台运行
run_foreground() {
    load_env run

    print_info "前台启动服务 (Ctrl+C 停止)..."
    print_info "Port: $PORT"
    echo ""

    export HTTP_PROXY HTTPS_PROXY
    python3 server.py
}

# 一键安装
install() {
    echo "======================================"
    echo "  Claude NIM Bridge - 安装"
    echo "======================================"
    echo ""

    # 1. 检查虚拟环境
    if [ ! -d ".venv" ]; then
        print_info "创建虚拟环境..."
        uv venv
        print_success "虚拟环境已创建"
    fi

    # 2. 安装依赖
    print_info "安装依赖..."
    uv pip install -e .
    print_success "依赖安装完成"
    echo ""

    # 3. 配置环境变量
    if [ ! -f ".env" ]; then
        print_info "创建配置文件..."
        cp .env.example .env 2>/dev/null || echo "# NVIDIA_NIM_API_KEY=your_key_here" > .env
        print_warning "请编辑 .env 文件，设置 NVIDIA_NIM_API_KEY"
    else
        load_env install
    fi
    echo ""

    # 4. 停止旧服务
    print_info "停止旧服务..."
    stop_service 2>/dev/null || true
    echo ""

    # 5. 安装系统服务
    if [ "$OS" == "macos" ]; then
        print_info "配置 macOS LaunchAgent..."

        PROJECT_DIR=$(pwd)
        CURRENT_USER=$(whoami)

        mkdir -p "$HOME/Library/LaunchAgents"

        # 创建 LaunchAgent
        cat > "$LAUNCH_AGENT_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude-nim-bridge</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/.venv/bin/python</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>server:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>$PORT</string>
        <string>--log-level</string>
        <string>info</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/service.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/service.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

        launchctl unload "$LAUNCH_AGENT_PATH" 2>/dev/null || true
        sleep 1

        if launchctl load "$LAUNCH_AGENT_PATH" 2>/dev/null; then
            print_success "LaunchAgent 已配置"
        fi

        launchctl start "$LAUNCH_AGENT" 2>/dev/null || start_service

    elif [ "$OS" == "linux" ]; then
        print_info "配置 systemd 服务..."

        PROJECT_DIR=$(pwd)
        CURRENT_USER=$(whoami)

        [ -f ".env" ] && set -a && source .env && set +a

        sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Claude NIM Bridge - Anthropic to NVIDIA NIM Proxy
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port $PORT --log-level info
Restart=on-failure
RestartSec=5
StartLimitInterval=0

Environment="PYTHONPATH=$PROJECT_DIR"
Environment="NVIDIA_NIM_API_KEY=${NVIDIA_NIM_API_KEY:-}"

[Install]
WantedBy=multi-user.target
EOF

        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE_NAME" 2>/dev/null
        sudo systemctl start "$SERVICE_NAME"
        print_success "systemd 服务已配置"
    fi

    echo ""

    # 6. 验证服务
    sleep 3
    show_status

    echo ""
    echo "======================================"
    echo "  ✅ 安装完成！"
    echo "======================================"
    echo ""
    echo "🔧 管理命令:"
    echo "  状态:   ./cc-nim.sh status"
    echo "  日志:   ./cc-nim.sh logs"
    echo "  重启:   ./cc-nim.sh restart"
    echo "  停止:   ./cc-nim.sh stop"
    echo "  前台:   ./cc-nim.sh run"
    echo ""
    echo "⚙️ Claude Code 配置:"
    echo "  export ANTHROPIC_AUTH_TOKEN=ccnim"
    echo "  export ANTHROPIC_BASE_URL=http://localhost:$PORT"
    echo "  claude"
    echo ""
}

# 卸载服务
uninstall() {
    print_info "卸载服务..."

    stop_service

    if [ "$OS" == "macos" ] && [ -f "$LAUNCH_AGENT_PATH" ]; then
        launchctl unload "$LAUNCH_AGENT_PATH" 2>/dev/null || true
        rm -f "$LAUNCH_AGENT_PATH"
        print_success "LaunchAgent 已移除"
    elif [ "$OS" == "linux" ]; then
        sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        sudo systemctl disable "$SERVICE_NAME" 2>/dev/null || true
        sudo rm -f "$SERVICE_FILE"
        sudo systemctl daemon-reload 2>/dev/null
        print_success "systemd 服务已移除"
    fi

    print_success "卸载完成"
}

# ==========================================
# 主命令分发器
# ==========================================

case "$1" in
    install|setup)
        install
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    run|foreground)
        run_foreground
        ;;
    uninstall|remove)
        uninstall
        ;;
    *)
        echo "Claude NIM Bridge - 统一管理脚本"
        echo ""
        echo "用法: ./cc-nim.sh <命令>"
        echo ""
        echo "命令:"
        echo "  install    - 一键安装（依赖 + 系统服务）"
        echo "  start      - 启动服务（后台）"
        echo "  stop       - 停止服务"
        echo "  restart    - 重启服务"
        echo "  status     - 查看状态"
        echo "  logs       - 查看日志（实时）"
        echo "  run        - 前台运行（调试用）"
        echo "  uninstall  - 卸载系统服务"
        echo ""
        echo "示例:"
        echo "  ./cc-nim.sh install     # 首次安装"
        echo "  ./cc-nim.sh status      # 查看状态"
        echo "  ./cc-nim.sh start       # 启动服务"
        echo "  ./cc-nim.sh logs        # 查看日志"
        echo ""
        ;;
esac
