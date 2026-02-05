#!/bin/bash
# 启动 WebSocket 服务器脚本（开发模式）

# 脚本位于 scripts/，先回到项目根目录
cd "$(dirname "$0")/.."

source venv/bin/activate
# 确保使用正确的 Python 版本，作为 backend 包运行
python3 -m backend.websocket_server
