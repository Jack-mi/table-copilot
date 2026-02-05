"""
Backend package for the Table Copilot project.

包含：
- WebSocket 服务入口 (`websocket_server.py`)
- 多 Agent 服务与工具注册 (`agent_service.py`)
- 工具集合 (`tools/`)
- 配置文件 (`config/`)
"""

__all__ = [
    "agent_service",
    "websocket_server",
    "tools",
    "config",
]

