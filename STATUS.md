# 服务状态检查

## 快速检查命令

```bash
# 检查服务器是否运行
./check_server_status.sh

# 或者手动检查
ps aux | grep websocket_server.py | grep -v grep
lsof -ti:8765

# 查看服务器日志
tail -f server.log

# 测试连接
python3 quick_test.py
```

## 服务器管理

### 启动服务器
```bash
./start_all.sh
# 或
source venv/bin/activate
python3 websocket_server.py
```

### 停止服务器
```bash
# 如果使用 start_all.sh 启动
kill $(cat server.pid)

# 或手动停止
pkill -f websocket_server.py
```

### 重启服务器
```bash
./start_all.sh
```

## 常见问题

### 1. 连接失败 (1011 错误)
- 检查服务器是否运行: `ps aux | grep websocket_server.py`
- 查看服务器日志: `tail -f server.log`
- 检查端口占用: `lsof -ti:8765`

### 2. 前端一直重连
- 打开浏览器控制台 (F12) 查看详细日志
- 检查服务器日志中的错误信息
- 确保服务器正常启动

### 3. 响应内容格式异常
- 查看 `[EXTRACT]` 日志了解内容提取过程
- 检查 AutoGen 版本是否兼容

## 日志位置

- 服务器日志: `server.log`
- 浏览器日志: 打开开发者工具 (F12) -> Console

## 健康检查

服务器正常运行时应该看到：
- `[INIT] MultiAgentService initialized successfully`
- `WebSocket server is running on ws://localhost:8765`
- `[CONNECTION] Client connected` (当有客户端连接时)
