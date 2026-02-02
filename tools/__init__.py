"""
Table Copilot Tools
提供各种工具供 Agent 调用
"""

from .schedule_reminder import (
    # FunctionTool 实例（如果 autogen_core 可用）
    schedule_reminder_tool,
    schedule_tools,
    create_schedule_tool,
    list_schedules_tool,
    delete_schedule_tool,
    update_schedule_tool,
    # 原始函数（始终可用）
    create_schedule,
    list_schedules,
    delete_schedule,
    update_schedule,
    # 可用性标志
    TOOLS_AVAILABLE,
)

__all__ = [
    # FunctionTool 实例
    "schedule_reminder_tool",
    "schedule_tools",
    "create_schedule_tool",
    "list_schedules_tool",
    "delete_schedule_tool",
    "update_schedule_tool",
    # 原始函数
    "create_schedule",
    "list_schedules", 
    "delete_schedule",
    "update_schedule",
    # 可用性标志
    "TOOLS_AVAILABLE",
]
