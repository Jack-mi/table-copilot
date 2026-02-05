#!/bin/bash
# 启动所有服务（后端 WebSocket + 日程通知）

# 脚本位于 scripts/，先回到项目根目录
cd "$(dirname "$0")/.."

echo "🚀 启动 AutoGen WebSocket 服务 & 日程通知服务"
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

source venv/bin/activate

# 停止旧进程
if [ -f "server.pid" ]; then
    OLD_PID=$(cat server.pid)
    if kill -0 $OLD_PID 2>/dev/null; then
        echo "🛑 停止旧服务器进程 (PID: $OLD_PID)"
        kill $OLD_PID 2>/dev/null
        sleep 1
    fi
fi

# 清理端口
lsof -ti:8765 | xargs kill -9 2>/dev/null || true

# 启动 WebSocket 服务器（以 backend 包形式运行）
echo "📡 启动 WebSocket 服务器..."
./venv/bin/python3 -m backend.websocket_server > server.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > server.pid

# 启动日程通知服务
echo "⏰ 启动日程通知服务..."
./venv/bin/python3 -m backend.schedule_notifier > schedule_notifier.log 2>&1 &
NOTIFIER_PID=$!
echo $NOTIFIER_PID > schedule_notifier.pid

sleep 2

# 检查服务器是否启动成功
if kill -0 $SERVER_PID 2>/dev/null; then
    echo "✅ 服务器启动成功 (PID: $SERVER_PID)"
    echo "⏰ 日程通知服务已启动 (PID: $NOTIFIER_PID)"
    echo "📝 WebSocket 日志文件: server.log"
    echo "📝 通知服务日志文件: schedule_notifier.log"
    echo "🌐 WebSocket 地址: ws://localhost:8765"
    echo ""
    echo "查看 WebSocket 日志: tail -f server.log"
    echo "查看通知服务日志: tail -f schedule_notifier.log"
    echo "停止服务器: kill $SERVER_PID && kill $NOTIFIER_PID"
    echo ""
    tail -10 server.log
else
    echo "❌ 服务器启动失败，查看 server.log 了解详情"
    tail -20 server.log
    exit 1
fi
