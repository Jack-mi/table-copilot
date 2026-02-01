#!/bin/bash
# 启动 WebSocket 服务器脚本

cd "$(dirname "$0")"
source venv/bin/activate
# 确保使用正确的 Python 版本
python3 websocket_server.py
