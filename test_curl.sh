#!/bin/bash
# WebSocket 测试脚本
# 注意：curl 不支持 WebSocket，这里提供几种测试方法

echo "WebSocket 不能用 curl 直接测试，以下是几种测试方法："
echo ""
echo "方法1: 使用 Python 测试脚本（推荐）"
echo "python3 test_client.py"
echo ""
echo "方法2: 使用 websocat (需要安装: brew install websocat)"
echo "websocat ws://localhost:8765"
echo ""
echo "方法3: 使用 wscat (需要安装: npm install -g wscat)"
echo "wscat -c ws://localhost:8765"
echo ""
echo "方法4: 使用 Python 交互式测试"
echo "python3 -c \"import asyncio, json, websockets; asyncio.run((lambda: websockets.connect('ws://localhost:8765'))())()\""
echo ""

# 提供一个简单的 Python 一行命令测试
echo "快速测试命令："
echo "python3 -c \"
import asyncio
import json
import websockets

async def test():
    async with websockets.connect('ws://localhost:8765') as ws:
        # 接收连接消息
        response = await ws.recv()
        print('连接成功:', response)
        
        # 发送测试消息
        await ws.send(json.dumps({
            'type': 'message',
            'content': '你好',
            'session_id': 'test_curl'
        }))
        
        # 接收状态
        status = await ws.recv()
        print('状态:', status)
        
        # 接收响应
        result = await ws.recv()
        print('响应:', result)

asyncio.run(test())
\""
