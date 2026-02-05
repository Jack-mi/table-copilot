"""
日程提醒工具聚合模块
（向后兼容：继续从这里导出 4 个独立工具及其 FunctionTool 和工具列表）
"""

from .schedule_create import create_schedule, create_schedule_tool
from .schedule_list import list_schedules, list_schedules_tool
from .schedule_delete import delete_schedule, delete_schedule_tool
from .schedule_update import update_schedule, update_schedule_tool

# 为了兼容原有接口，保留 schedule_reminder_tool 和 schedule_tools / TOOLS_AVAILABLE
schedule_reminder_tool = create_schedule_tool

schedule_tools = [
    tool
    for tool in [
        create_schedule_tool,
        list_schedules_tool,
        delete_schedule_tool,
        update_schedule_tool,
    ]
    if tool is not None
]

TOOLS_AVAILABLE = all(
    t is not None
    for t in [
        create_schedule_tool,
        list_schedules_tool,
        delete_schedule_tool,
        update_schedule_tool,
    ]
)

