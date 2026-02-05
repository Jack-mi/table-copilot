# 日志级别说明

## 日志配置

项目使用 Python 的 `logging` 模块，日志级别从低到高：
- DEBUG: 详细的调试信息
- INFO: 一般信息
- WARNING: 警告信息
- ERROR: 错误信息
- CRITICAL: 严重错误

## 如何查看日志

### 1. WebSocket 服务器日志
启动服务器时会自动输出到控制台：
```bash
python3 websocket_server.py
```

### 2. Agent 服务日志
Agent 服务的日志会输出到控制台，包含：
- 消息处理过程
- API 调用详情
- 错误信息

### 3. 前端客户端日志
打开浏览器开发者工具（F12），在 Console 标签页查看：
- 连接状态
- 消息收发
- 错误信息

## 日志格式

```
2026-02-01 12:00:00 - websocket_server - INFO - [websocket_server.py:45] - [CONNECTION] Client connected: 127.0.0.1:12345
```

格式：`时间 - 模块名 - 级别 - [文件名:行号] - 消息`

## 调试技巧

### 查看详细日志
修改日志级别为 DEBUG：
```python
logging.basicConfig(level=logging.DEBUG)
```

### 查看特定模块日志
```python
logging.getLogger('agent_service').setLevel(logging.DEBUG)
```

### 保存日志到文件
```python
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)
```

## 常见问题排查

1. **连接失败**: 查看 `[CONNECTION]` 和 `[ERROR]` 日志
2. **消息处理失败**: 查看 `[AGENT]` 和 `[STREAM]` 日志
3. **响应异常**: 查看 `[EXTRACT]` 和 `[RESPONSE]` 日志
4. **前端问题**: 查看浏览器控制台的日志
