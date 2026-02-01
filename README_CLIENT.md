# 前端客户端使用说明

## 启动前端页面

### 方法1: 使用 Python HTTP 服务器（推荐）

```bash
# 在项目目录下运行（使用 3000 端口）
python3 -m http.server 3000

# 然后在浏览器中打开
open http://localhost:3000/client.html
```

### 方法2: 直接用浏览器打开

```bash
# macOS
open client.html

# Linux
xdg-open client.html

# Windows
start client.html
```

### 方法3: 使用其他 HTTP 服务器

```bash
# 使用 Node.js http-server
npx http-server -p 3000

# 使用 PHP
php -S localhost:3000
```

## 功能说明

1. **自动连接**: 页面加载后自动连接到 WebSocket 服务器
2. **实时对话**: 在输入框中输入消息，按 Enter 或点击发送按钮
3. **消息显示**: 
   - 用户消息显示在右侧（紫色）
   - AI 回复显示在左侧（白色）
   - 系统消息显示在中间（黄色）
4. **状态指示**: 顶部显示连接状态（绿色=已连接，红色=未连接）
5. **清空历史**: 点击"清空"按钮清除对话历史
6. **自动重连**: 连接断开后会自动尝试重连

## 注意事项

1. **确保 WebSocket 服务器已启动**: 先运行 `python3 websocket_server.py`
2. **端口配置**: 默认 WebSocket 服务器在 `ws://localhost:8765`
3. **跨域问题**: 如果遇到跨域问题，确保使用 HTTP 服务器访问，而不是直接用 `file://` 协议

## 自定义配置

如果需要修改 WebSocket 地址，编辑 `client.html` 中的这一行：

```javascript
const wsUrl = 'ws://localhost:8765';
```

改为你的服务器地址即可。
