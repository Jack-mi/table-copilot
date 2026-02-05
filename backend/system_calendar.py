"""
系统日历集成（目前优先支持 macOS 的 Calendar.app）。

设计原则：
- 不影响主业务：同步失败不会让工具报错，只做 best-effort。
- 尽量少依赖第三方库：macOS 直接使用系统自带的 AppleScript（osascript）。

环境变量：
- TABLE_COPILOT_CALENDAR（可选）：指定要写入的日历名称，例如「工作」。
  如果不设置，则使用 Calendar.app 的第一个日历。
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _escape_ics_text(text: str) -> str:
    """简单转义 ICS 文本字段。"""
    # 参考 RFC 5545：逗号、分号和反斜杠需要转义，换行需要折行。
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _add_event_macos(
    title: str,
    start: datetime,
    duration_minutes: int,
    notes: str,
    calendar_name: Optional[str] = None,  # 保留参数以便未来按日历名路由，目前未使用
) -> None:
    """
    在 macOS 上通过生成 .ics 文件并用 `open` 命令交给系统处理。

    这样可以：
    - 由系统默认日历应用（通常是 Calendar.app）接管导入逻辑
    - 用户能直观看到“添加到哪一个日历”，权限问题也交给系统处理
    """
    try:
        uid = str(uuid.uuid4())

        # 使用本地时间写 DTSTART/DTEND，Calendar 会按本地时区解析
        dtstart = start.strftime("%Y%m%dT%H%M%S")
        dtend = (start + timedelta(minutes=duration_minutes)).strftime("%Y%m%dT%H%M%S")

        now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        ics_title = _escape_ics_text(title)
        ics_desc = _escape_ics_text(notes or "")

        ics_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//TableCopilot//EN",
            "CALSCALE:GREGORIAN",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{ics_title}",
            f"DESCRIPTION:{ics_desc}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
        ics_content = "\n".join(ics_lines)

        tmp_dir = tempfile.gettempdir()
        ics_path = os.path.join(tmp_dir, f"table_copilot_{uid}.ics")

        with open(ics_path, "w", encoding="utf-8") as f:
            f.write(ics_content)

        logger.info("[CAL] Created temporary ICS file at %s", ics_path)

        # 交给系统默认日历应用打开
        result = subprocess.run(
            ["open", ics_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.warning(
                "[CAL] Failed to open ICS with default app: code=%s, stderr=%r",
                result.returncode,
                result.stderr,
            )
        else:
            logger.info("[CAL] Opened ICS with default calendar app successfully")
    except Exception as e:
        logger.warning("[CAL] macOS Calendar ICS integration crashed: %s", e)


def sync_schedule_to_system_calendar(schedule: Dict[str, Any]) -> None:
    """
    将内部日程同步到系统日历。

    - macOS: 创建 Calendar.app 事件
    - 其他平台: 目前仅打日志，不做实际操作
    """
    os_name = platform.system().lower()
    if os_name != "darwin":
        logger.info("[CAL] System calendar integration not implemented for OS=%s", os_name)
        return

    dt_str = schedule.get("datetime")
    if not dt_str:
        logger.info(
            "[CAL] Schedule has no datetime, skip calendar sync: id=%s",
            schedule.get("id"),
        )
        return

    try:
        start = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    except Exception as e:
        logger.warning(
            "[CAL] Failed to parse schedule datetime %r for id=%s: %s",
            dt_str,
            schedule.get("id"),
            e,
        )
        return

    try:
        duration_minutes = int(schedule.get("duration_minutes") or 30)
    except Exception:
        duration_minutes = 30

    title = str(schedule.get("title") or "无标题日程")
    desc = str(schedule.get("description") or "")
    calendar_name = os.getenv("TABLE_COPILOT_CALENDAR", "") or None

    _add_event_macos(
        title=title,
        start=start,
        duration_minutes=duration_minutes,
        notes=desc,
        calendar_name=calendar_name,
    )


__all__ = ["sync_schedule_to_system_calendar"]

