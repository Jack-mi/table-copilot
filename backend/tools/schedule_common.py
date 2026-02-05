"""
Schedule 工具的公共存储与返回格式封装。
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

# 日程存储文件路径（位于 backend/schedules.json）
SCHEDULE_FILE = os.path.join(os.path.dirname(__file__), "..", "schedules.json")


def load_schedules() -> List[Dict[str, Any]]:
    """加载已保存的日程列表。"""
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_schedules(schedules: List[Dict[str, Any]]) -> None:
    """保存日程列表到文件。"""
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)


def generate_schedule_id() -> str:
    """生成唯一日程 ID。"""
    import uuid

    return str(uuid.uuid4())[:8]


def make_schedule_result(
    tool: str,
    success: bool,
    data: Optional[Any] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
) -> str:
    """
    统一的 JSON 返回格式：
    {
      "tool": "<tool_name>",
      "success": true/false,
      "message": "<可选的人类可读描述>",
      "data": { ... 任意结构化数据 ... },
      "error": "<错误信息，仅在 success=false 时出现>"
    }
    """
    payload: Dict[str, Any] = {"tool": tool, "success": success}
    if message:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    if error:
        payload["error"] = error
    return json.dumps(payload, ensure_ascii=False)


__all__ = [
    "SCHEDULE_FILE",
    "datetime",
    "load_schedules",
    "save_schedules",
    "generate_schedule_id",
    "make_schedule_result",
]

