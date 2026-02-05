# WebSocket 测试指南

## ⚠️ 注意
**curl 不支持 WebSocket 协议**，WebSocket 是基于 HTTP 升级的持久连接协议，不能用 curl 直接测试。

## 推荐测试方法

### 方法1: 使用快速测试脚本（最简单）
```bash
python3 quick_test.py
```

### 方法2: 使用 Python 一行命令
```bash
python3 -c "
import asyncio
import json
import websockets

async def test():
    async with websockets.connect('ws://localhost:8765') as ws:
        print('连接成功:', await ws.recv())
        await ws.send(json.dumps({'type': 'message', 'content': '你好', 'session_id': 'test'}))
        print('状态:', await ws.recv())
        print('响应:', await ws.recv())

asyncio.run(test())
"
```

### 方法3: 使用 websocat（需要安装）
```bash
# 安装 websocat
brew install websocat  # macOS
# 或 cargo install websocat  # 需要 Rust

# 测试
echo '{"type":"message","content":"你好","session_id":"test"}' | websocat ws://localhost:8765
```

### 方法4: 使用 wscat（Node.js 工具）
```bash
# 安装
npm install -g wscat

# 测试
wscat -c ws://localhost:8765
# 然后输入: {"type":"message","content":"你好","session_id":"test"}
```

### 方法5: 使用完整的测试客户端
```bash
python3 test_client.py
```

## 消息格式

### 发送消息
```json
{
  "type": "message",
  "content": "你的消息内容",
  "session_id": "会话ID（可选）"
}
```

### 清除历史
```json
{
  "type": "clear_history",
  "session_id": "会话ID"
}
```

### 心跳检测
```json
{
  "type": "ping"
}
```

## 服务器响应格式

### 连接确认
```json
{
  "type": "connection",
  "status": "connected",
  "message": "Connected to AutoGen Multi-Agent Service"
}
```

### 处理状态
```json
{
  "type": "status",
  "status": "processing",
  "message": "Processing your message..."
}
```

### Agent 响应
```json
{
  "type": "response",
  "content": "Agent 的回复内容",
  "session_id": "会话ID"
}
```
