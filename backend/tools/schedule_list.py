"""
list_schedules 独立工具：列出日程。
"""

from typing import Optional

try:
    from typing_extensions import Annotated
except ImportError:
    from typing import Annotated

from .schedule_common import load_schedules, make_schedule_result


def list_schedules(
    status: Annotated[
        Optional[str], "筛选状态：all(全部)、active(活动)、completed(已完成)，默认为active"
    ] = "active",
    limit: Annotated[int, "返回的最大日程数量，默认为10"] = 10,
) -> str:
    """
    列出现有的日程提醒。

    返回 JSON 字符串，结构示例：
    {
      "tool": "list_schedules",
      "success": true,
      "data": { "schedules": [...], "status": "...", "limit": 10 }
    }
    """
    try:
        schedules = load_schedules()

        if not schedules:
            return make_schedule_result(
                "list_schedules",
                True,
                data={"schedules": [], "status": status, "limit": limit},
                message="当前没有任何日程。",
            )

        # 根据状态筛选
        if status != "all":
            schedules = [s for s in schedules if s.get("status") == status]

        if not schedules:
            return make_schedule_result(
                "list_schedules",
                True,
                data={"schedules": [], "status": status, "limit": limit},
                message=f"没有状态为 '{status}' 的日程。",
            )

        # 按时间排序
        schedules.sort(key=lambda x: x.get("datetime", ""))

        # 限制数量
        schedules = schedules[:limit]

        return make_schedule_result(
            "list_schedules",
            True,
            data={"schedules": schedules, "status": status, "limit": limit},
            message=f"共返回 {len(schedules)} 条日程。",
        )

    except Exception as e:
        return make_schedule_result(
            "list_schedules",
            False,
            error=f"获取日程列表时发生错误: {str(e)}",
        )


try:
    from autogen_core.tools import FunctionTool

    list_schedules_tool = FunctionTool(
        func=list_schedules,
        name="list_schedules",
        description="列出现有的日程提醒（JSON 输出），可按状态与数量筛选。",
    )
except ImportError:
    list_schedules_tool = None

