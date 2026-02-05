"""
create_schedule 独立工具：创建日程 / 提醒 / 闹钟，并尝试同步到系统日历（如 macOS Calendar）。
"""

from typing import Optional
import logging

try:
    from typing_extensions import Annotated
except ImportError:
    from typing import Annotated

from .schedule_common import (
    datetime,
    load_schedules,
    save_schedules,
    generate_schedule_id,
    make_schedule_result,
)

from ..system_calendar import sync_schedule_to_system_calendar


logger = logging.getLogger(__name__)


def create_schedule(
    title: Annotated[str, "日程标题，简短描述日程内容"],
    datetime_str: Annotated[str, "日程时间，格式为 YYYY-MM-DD HH:MM，例如 2024-03-15 14:30"],
    description: Annotated[Optional[str], "日程详细描述（可选）"] = None,
    reminder_minutes: Annotated[int, "提前提醒的分钟数，默认为15分钟"] = 15,
    repeat: Annotated[
        Optional[str],
        "重复类型：once(一次)、daily(每天)、weekly(每周)、monthly(每月)，默认为once",
    ] = "once",
) -> str:
    """
    创建一个新的日程提醒。

    返回 JSON 字符串，结构示例：
    {
      "tool": "create_schedule",
      "success": true,
      "data": { "schedule": { ... } },
      "message": "日程创建成功"
    }
    """
    try:
        # 解析日期时间
        schedule_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")

        # 检查时间是否已过
        if schedule_time < datetime.now() and repeat == "once":
            return make_schedule_result(
                "create_schedule",
                False,
                error=f"指定的时间 {datetime_str} 已经过去，请设置一个未来的时间。",
            )

        # 验证重复类型
        valid_repeats = ["once", "daily", "weekly", "monthly"]
        if repeat not in valid_repeats:
            return make_schedule_result(
                "create_schedule",
                False,
                error=f"无效的重复类型 '{repeat}'。有效选项：{', '.join(valid_repeats)}",
            )

        # 创建日程
        schedule_id = generate_schedule_id()
        schedule = {
            "id": schedule_id,
            "title": title,
            "datetime": datetime_str,
            "description": description or "",
            "reminder_minutes": reminder_minutes,
            "repeat": repeat,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "active",
        }

        # 加载现有日程并添加新日程
        schedules = load_schedules()
        schedules.append(schedule)
        save_schedules(schedules)

        # 尝试同步到系统日历（比如 macOS Calendar），失败不影响主流程
        try:
            sync_schedule_to_system_calendar(schedule)
        except Exception as e:
            logger.warning(
                "[CAL] Failed to sync schedule %s to system calendar: %s",
                schedule_id,
                e,
            )

        return make_schedule_result(
            "create_schedule",
            True,
            data={"schedule": schedule},
            message="日程创建成功",
        )

    except ValueError as e:
        return make_schedule_result(
            "create_schedule",
            False,
            error=(
                "日期时间格式不正确。请使用格式 YYYY-MM-DD HH:MM，例如 2024-03-15 14:30。"
                f" 详细错误: {str(e)}"
            ),
        )
    except Exception as e:
        return make_schedule_result(
            "create_schedule",
            False,
            error=f"创建日程时发生错误: {str(e)}",
        )


try:
    from autogen_core.tools import FunctionTool

    create_schedule_tool = FunctionTool(
        func=create_schedule,
        name="create_schedule",
        description="创建一个新的日程提醒（JSON 输出），用于设置会议、提醒、闹钟等。",
    )
except ImportError:
    create_schedule_tool = None

