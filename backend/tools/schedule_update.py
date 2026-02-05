"""
update_schedule 独立工具：更新日程信息。
"""

from typing import Optional, List

try:
    from typing_extensions import Annotated
except ImportError:
    from typing import Annotated

from .schedule_common import datetime, load_schedules, save_schedules, make_schedule_result


def update_schedule(
    schedule_id: Annotated[str, "要更新的日程ID"],
    title: Annotated[Optional[str], "新的日程标题（可选）"] = None,
    datetime_str: Annotated[
        Optional[str], "新的日程时间，格式为 YYYY-MM-DD HH:MM（可选）"
    ] = None,
    description: Annotated[Optional[str], "新的日程描述（可选）"] = None,
    reminder_minutes: Annotated[Optional[int], "新的提前提醒分钟数（可选）"] = None,
    status: Annotated[Optional[str], "新的状态：active(活动)、completed(已完成)（可选）"] = None,
) -> str:
    """
    更新已有的日程提醒。

    返回 JSON 字符串，结构示例：
    {
      "tool": "update_schedule",
      "success": true,
      "data": { "schedule": { ... }, "updated_fields": [...] }
    }
    """
    try:
        schedules = load_schedules()

        # 查找要更新的日程
        schedule_index = None
        for i, schedule in enumerate(schedules):
            if schedule["id"] == schedule_id:
                schedule_index = i
                break

        if schedule_index is None:
            return make_schedule_result(
                "update_schedule",
                False,
                error=(
                    f"未找到 ID 为 '{schedule_id}' 的日程。"
                    "请使用 list_schedules 工具查看现有日程的 ID。"
                ),
            )

        # 更新字段
        schedule = schedules[schedule_index]
        updated_fields: List[str] = []

        if title is not None:
            schedule["title"] = title
            updated_fields.append(f"title -> {title}")

        if datetime_str is not None:
            try:
                datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                schedule["datetime"] = datetime_str
                updated_fields.append(f"datetime -> {datetime_str}")
            except ValueError:
                return make_schedule_result(
                    "update_schedule",
                    False,
                    error="日期时间格式不正确。请使用格式 YYYY-MM-DD HH:MM。",
                )

        if description is not None:
            schedule["description"] = description
            updated_fields.append("description -> <updated>")

        if reminder_minutes is not None:
            schedule["reminder_minutes"] = reminder_minutes
            updated_fields.append(f"reminder_minutes -> {reminder_minutes}")

        if status is not None:
            if status not in ["active", "completed"]:
                return make_schedule_result(
                    "update_schedule",
                    False,
                    error="无效的状态。有效选项：active, completed",
                )
            schedule["status"] = status
            updated_fields.append(f"status -> {status}")

        if not updated_fields:
            return make_schedule_result(
                "update_schedule",
                False,
                error="没有提供需要更新的字段。",
            )

        schedule["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        schedules[schedule_index] = schedule
        save_schedules(schedules)

        return make_schedule_result(
            "update_schedule",
            True,
            data={"schedule": schedule, "updated_fields": updated_fields},
            message="日程更新成功",
        )

    except Exception as e:
        return make_schedule_result(
            "update_schedule",
            False,
            error=f"更新日程时发生错误: {str(e)}",
        )


try:
    from autogen_core.tools import FunctionTool

    update_schedule_tool = FunctionTool(
        func=update_schedule,
        name="update_schedule",
        description="更新已有日程的信息（JSON 输出），包括标题、时间、描述、提醒时间以及状态。",
    )
except ImportError:
    update_schedule_tool = None

