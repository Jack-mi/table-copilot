#!/bin/bash
# 一键初始化虚拟环境并启动 AutoGen WebSocket 服务

set -e

# 脚本位于 scripts/，先回到项目根目录
cd "$(dirname "$0")/.."

echo "🚀 Quick start backend server"
echo ""

# 可通过环境变量自定义 Python，可选：PYTHON_BIN=python3.12 ./quick_start_server.sh
PYTHON_BIN="${PYTHON_BIN:-python3.12}"

echo "🧪 Using Python binary: ${PYTHON_BIN}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "❌ 未找到 Python 可执行文件：${PYTHON_BIN}"
  echo "   请先安装对应版本的 Python，或通过环境变量 PYTHON_BIN 指定，例如："
  echo "   PYTHON_BIN=python3 ./quick_start_server.sh"
  exit 1
fi

# 创建或复用虚拟环境
if [ ! -d "venv" ]; then
  echo "📦 创建虚拟环境 venv..."
  "${PYTHON_BIN}" -m venv venv
  echo "✅ 虚拟环境创建完成"
fi

echo "📥 安装 / 更新依赖..."
source venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt -i https://pypi.org/simple/

echo "🔑 检查 API Key..."
if [ -z "${OPENROUTER_API_KEY}" ]; then
  if [ -f ".env" ]; then
    echo "ℹ️ 未在当前 shell 检测到 OPENROUTER_API_KEY，但检测到 .env 文件，服务启动时将通过 python-dotenv 加载。"
  else
    echo "❌ 未检测到 OPENROUTER_API_KEY，且不存在 .env 文件"
    echo "   请设置 OPENROUTER_API_KEY（OpenRouter key 以 sk-or- 开头），或在项目根目录创建 .env 文件。"
    exit 1
  fi
fi

echo "📡 启动 WebSocket 服务器..."
chmod +x scripts/start_all.sh
scripts/start_all.sh

