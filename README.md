# AutoGen Multi-Agent WebSocket Service

基于 [AutoGen](https://github.com/microsoft/autogen) 框架实现的 WebSocket 多 Agent 服务，支持多轮对话和工具调用。

## 项目简介

本项目实现了一个基于 AutoGen 框架的多 Agent WebSocket 服务，通过 OpenRouter API 使用 `moonshotai/kimi-k2.5` 模型。服务支持：

- ✅ 实时 WebSocket 通信
- ✅ 多轮对话上下文管理
- ✅ Markdown 格式回复渲染
- ✅ 代码语法高亮
- ✅ 会话历史管理
- ✅ 工具调用框架（已预留接口）

## 实现摘要

### 核心组件

1. **agent_service.py**: AutoGen 多 Agent 服务核心
   - 集成 OpenRouter API（使用 kimi-k2.5 模型）
   - 管理会话 Agent 实例和对话历史
   - 处理消息流并提取 assistant 回复

2. **websocket_server.py**: WebSocket 服务器
   - 处理客户端连接和消息路由
   - 支持多客户端并发
   - 错误处理和日志记录

3. **client.html**: 前端聊天界面
   - 实时 WebSocket 通信
   - Markdown 渲染（marked.js）
   - 代码高亮（highlight.js）
   - 自动重连机制

### 技术栈

- **后端**: Python 3.12+, AutoGen, WebSockets, OpenRouter API
- **前端**: HTML5, JavaScript, Marked.js, Highlight.js
- **模型**: moonshotai/kimi-k2.5 (通过 OpenRouter)

## 快速开始

### 1. 一键快速部署（推荐）

```bash
cd table-copilot

# 第一次运行或环境变化时执行（会自动创建 venv 并安装依赖）
chmod +x scripts/quick_start_server.sh
scripts/quick_start_server.sh
```

> 提示：脚本默认使用 `python3.12` 创建虚拟环境，如需自定义，可设置环境变量 `PYTHON_BIN`，例如：
> `PYTHON_BIN=python3.12 ./quick_start_server.sh`

### 2. 手动安装依赖（可选）

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量（必选）

推荐两种方式二选一：

- **方式 A：使用 OpenRouter + Kimi（推荐）**
  
```bash
export OPENROUTER_API_KEY=your_openrouter_key
export MODEL_NAME=moonshotai/kimi-k2.5        # 可选，默认即为该模型
export OPENROUTER_BASE_URL=https://openrouter.ai/api/v1  # 可选
```

- **方式 B：直接使用 OpenAI 官方接口**

```bash
export OPENAI_API_KEY=your_openai_key         # 或使用 OPENAI_KEY
export MODEL_NAME=gpt-4.1-mini                # 可选，覆盖默认模型
export OPENAI_BASE_URL=https://api.openai.com/v1  # 可选
```

> 也可以在项目根目录创建 `.env` 文件，内容示例：
>
> ```bash
> OPENROUTER_API_KEY=your_openrouter_key
> MODEL_NAME=moonshotai/kimi-k2.5
> ```

> 或使用 OpenAI：
>
> ```bash
> OPENAI_API_KEY=your_openai_key
> MODEL_NAME=gpt-4.1-mini
> ```
```

### 4. 启动服务

#### 方式一：使用启动脚本（推荐，配合一键脚本）

```bash
# 启动 WebSocket 服务器
scripts/start_all.sh

# 启动前端客户端服务器（新终端）
scripts/start_client.sh
```

#### 方式二：手动启动

```bash
# 启动 WebSocket 服务器
source venv/bin/activate
python3 -m backend.websocket_server

# 启动前端服务器（新终端）
python3 -m http.server 3000
```

### 4. 访问前端

浏览器打开：`http://localhost:3000/client.html`（或启动脚本显示的端口）

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
│       ├── todo_manager.py
│       └── ask_user_question.py
├── frontend/                 # 前端界面
│   ├── client.html           # Web 聊天界面
│   └── README_CLIENT.md      # 前端使用说明
├── scripts/                  # 启动与运维脚本
│   ├── start_all.sh          # 启动后端（含端口清理与日志）
│   ├── start_server.sh       # 仅启动后端 WebSocket 服务器
│   ├── start_client.sh       # 启动静态前端 HTTP 服务
│   ├── quick_start_server.sh # 一键创建 venv + 安装依赖 + 启动后端
│   ├── check_server_status.sh# 检查端口与连接状态
│   └── test_curl.sh          # 命令行 WebSocket 测试入口说明
├── tests/                    # 测试脚本
│   ├── quick_test.py         # 快速单轮对话测试
│   └── test_client.py        # 多轮对话与清理测试客户端
├── docs/                     # 文档与说明
│   ├── CURL_TEST.md
│   ├── LOG_LEVELS.md
│   ├── STATUS.md
│   └── TODO_IMPLEMENTATION_PLAN.md
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
