"""
delete_schedule 独立工具：删除日程。
"""

try:
    from typing_extensions import Annotated
except ImportError:
    from typing import Annotated

from .schedule_common import load_schedules, save_schedules, make_schedule_result


def delete_schedule(
    schedule_id: Annotated[str, "要删除的日程ID"],
) -> str:
    """
    删除指定的日程提醒。

    返回 JSON 字符串，结构示例：
    {
      "tool": "delete_schedule",
      "success": true,
      "data": { "deleted_schedule": { ... } }
    }
    """
    try:
        schedules = load_schedules()

        # 查找要删除的日程
        schedule_to_delete = None
        for schedule in schedules:
            if schedule["id"] == schedule_id:
                schedule_to_delete = schedule
                break

        if not schedule_to_delete:
            return make_schedule_result(
                "delete_schedule",
                False,
                error=(
                    f"未找到 ID 为 '{schedule_id}' 的日程。"
                    "请使用 list_schedules 工具查看现有日程的 ID。"
                ),
            )

        # 删除日程
        schedules = [s for s in schedules if s["id"] != schedule_id]
        save_schedules(schedules)

        return make_schedule_result(
            "delete_schedule",
            True,
            data={"deleted_schedule": schedule_to_delete},
            message="日程已成功删除。",
        )

    except Exception as e:
        return make_schedule_result(
            "delete_schedule",
            False,
            error=f"删除日程时发生错误: {str(e)}",
        )


try:
    from autogen_core.tools import FunctionTool

    delete_schedule_tool = FunctionTool(
        func=delete_schedule,
        name="delete_schedule",
        description="删除指定 ID 的日程（JSON 输出），用于取消不再需要的提醒。",
    )
except ImportError:
    delete_schedule_tool = None

