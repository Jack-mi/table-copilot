#!/bin/bash
# 启动前端客户端服务器

cd "$(dirname "$0")"

# 检查端口是否被占用
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 1
    else
        return 0
    fi
}

# 尝试不同的端口
PORT=3000
while ! check_port $PORT; do
    PORT=$((PORT + 1))
    if [ $PORT -gt 9999 ]; then
        echo "❌ 无法找到可用端口"
        exit 1
    fi
done

echo "🚀 启动前端服务器在端口 $PORT"
echo "📱 请在浏览器中打开: http://localhost:$PORT/client.html"
echo ""
echo "按 Ctrl+C 停止服务器"
echo ""

python3 -m http.server $PORT
