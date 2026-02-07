# AutoGen Multi-Agent WebSocket Service

基于 [AutoGen](https://github.com/microsoft/autogen) 的 WebSocket 多 Agent 服务，支持多轮对话、工具调用（日程/澄清提问）与流式回复。

## 功能概览

- 实时 WebSocket 通信与流式回复展示
- 多轮对话与会话历史（按 session 隔离）
- 日程工具：创建/列表/更新/删除日程；日程提醒服务
- 澄清提问工具：向用户发起单选/多选等
- 前端仅展示最终回复（思考过程与工具调用不在界面展示，仅控制台可查）

## 启动方式

### 环境要求

- Python 3.12+（推荐）
- 配置 OpenRouter API Key：在项目根目录创建 `.env`，或 `export OPENROUTER_API_KEY=sk-or-...`

### 一键启动后端（推荐）

```bash
cd table-copilot
chmod +x scripts/quick_start_server.sh
scripts/quick_start_server.sh
```

脚本会：创建/复用 `venv`、安装依赖、启动 **WebSocket 服务**（`ws://localhost:8765`）和 **日程通知服务**。  
自定义 Python 可设置：`PYTHON_BIN=python3.12 scripts/quick_start_server.sh`。

### 启动前端（另开终端）

```bash
scripts/start_client.sh
```

按提示在浏览器打开 `http://localhost:<端口>/client.html`（默认从 3000 起找可用端口）。

### 仅手动启动

```bash
# 后端
source venv/bin/activate
pip install -r requirements.txt   # 首次
scripts/start_all.sh               # 或: python3 -m backend.websocket_server（仅 WebSocket）

# 前端（新终端）
cd frontend && python3 -m http.server 3000
# 访问 http://localhost:3000/client.html
```

## 测试流程

### 1. 检查服务器状态

```bash
# 检查服务器进程和端口
scripts/check_server_status.sh
```

### 2. 使用前端界面测试

1. 打开 `http://localhost:3000/client.html`
2. 等待连接成功（右上角显示"已连接"）
3. 发送测试消息，如："who are u"
4. 验证回复是否正确识别为 Kimi
5. 测试 Markdown 格式（代码块、列表等）

### 3. 使用命令行测试

```bash
# Python 测试脚本
source venv/bin/activate
python3 tests/quick_test.py
```

### 4. 使用 WebSocket 命令行工具测试（参考 docs/CURL_TEST.md）

```bash
# 需要安装 websocat
websocat ws://localhost:8765
```

## 项目结构

```
table-copilot/
├── backend/                  # 后端代码与工具
│   ├── __init__.py
│   ├── agent_service.py      # 多 Agent 服务核心（含工具注册）
│   ├── websocket_server.py   # WebSocket 服务器入口
│   ├── check_server.py       # 服务器健康检查脚本（Python）
│   ├── schedules.json        # 日程数据存储
│   ├── config/
│   │   └── system_prompt.txt # 系统提示词配置
│   └── tools/                # 可调用工具集合
│       ├── __init__.py
│       ├── schedule_reminder.py
│       ├── schedule_common.py
│       ├── schedule_create.py
│       ├── schedule_list.py
│       ├── schedule_update.py
│       ├── schedule_delete.py
│       └── ask_user_question.py
├── frontend/                 # 前端界面
│   ├── client.html           # Web 聊天界面
│   └── README_CLIENT.md      # 前端使用说明
├── scripts/                  # 启动与运维脚本
│   ├── start_all.sh          # 启动后端 WebSocket + 日程通知
│   ├── start_server.sh       # 仅启动 WebSocket
│   ├── start_client.sh       # 启动前端静态服务（frontend/）
│   ├── quick_start_server.sh # 一键 venv + 依赖 + 启动后端
│   ├── check_server_status.sh# 检查端口与进程
│   └── test_curl.sh          # WebSocket 测试说明
├── tests/
│   ├── quick_test.py
│   └── test_client.py
├── docs/
│   ├── CURL_TEST.md
│   ├── LOG_LEVELS.md
│   └── STATUS.md
├── requirements.txt          # Python 依赖
└── README.md                 # 项目说明（本文件）
```

## WebSocket 消息格式

### 客户端发送

```json
{
  "type": "message",
  "content": "用户消息",
  "session_id": "会话ID（可选）"
}
```

### 服务器响应

```json
{
  "type": "response",
  "content": "AI 回复内容（支持 Markdown）",
  "session_id": "会话ID"
}
```

更多消息格式请参考代码注释或 `CURL_TEST.md`。

## 功能特性

- **多轮对话**: 通过 `session_id` 维护对话上下文
- **Markdown 渲染**: 支持代码块、列表、表格等格式
- **代码高亮**: 自动识别代码语言并高亮
- **自动重连**: 前端支持断线自动重连（最多5次）
- **错误处理**: 完善的错误处理和日志记录

## 注意事项

- 服务器默认监听 `localhost:8765`
- 前端默认端口从 3000 开始自动查找可用端口
- 每个会话（session_id）维护独立的对话历史和 Agent 实例
- 确保网络可以访问 OpenRouter API

## 许可证

本项目基于 AutoGen 框架，遵循相应的开源许可证。
