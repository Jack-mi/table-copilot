"""
Simple schedule notifier service.

定期扫描 backend/schedules.json，在到达提醒时间时触发
macOS / Windows 系统通知。
"""

import asyncio
import json
import logging
import os
import platform
import subprocess
from datetime import datetime, timedelta
from typing import Any, Dict, List

from .tools.schedule_common import SCHEDULE_FILE, load_schedules, save_schedules

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 30


def _escape_osascript_text(text: str) -> str:
    """对 AppleScript 里的字符串做简单转义（目前只处理双引号）。"""
    return text.replace('"', '\\"')


def _send_macos_notification(title: str, message: str) -> None:
    """Use AppleScript to show a notification on macOS, 带详细日志。"""
    safe_title = _escape_osascript_text(title)
    safe_message = _escape_osascript_text(message)
    script = f'display notification "{safe_message}" with title "{safe_title}"'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.warning(
                "[NOTIFY] macOS osascript notification failed: "
                f"code={result.returncode}, stderr={result.stderr!r}"
            )
        else:
            logger.info("[NOTIFY] macOS osascript notification executed successfully")
    except Exception as e:
        logger.warning(f"[NOTIFY] macOS notification crashed: {e}")


def _send_plyer_notification(title: str, message: str) -> None:
    """Try to use plyer for cross-platform notifications."""
    try:
        from plyer import notification

        notification.notify(title=title, message=message, timeout=10)
    except Exception as e:
        logger.warning(f"[NOTIFY] plyer notification failed: {e}")


def send_system_notification(title: str, message: str) -> None:
    """
    发送系统级通知：
    - macOS: 优先使用 plyer，失败则回退到 osascript
    - Windows: 使用 plyer（需要系统支持）
    - 其他平台: 打日志，不抛异常
    """
    os_name = platform.system().lower()
    logger.info(f"[NOTIFY] Sending notification on {os_name}: {title} - {message}")

    if os_name == "darwin":
        # macOS 上直接使用 AppleScript，更稳定，也避免 plyer 依赖 pyobjus
        _send_macos_notification(title, message)
    elif os_name == "windows":
        _send_plyer_notification(title, message)
    else:
        # 其他平台暂时只记录日志
        logger.info(f"[NOTIFY] {title}: {message}")


def _ensure_notified_flag(schedules: List[Dict[str, Any]]) -> None:
    """确保每个 schedule 至少有 notified 字段。"""
    for sched in schedules:
        if "notified" not in sched:
            sched["notified"] = False


async def schedule_notifier_loop() -> None:
    """Main loop: periodically check schedules and fire notifications."""
    logger.info(f"[NOTIFIER] Using schedule file: {SCHEDULE_FILE}")

    while True:
        try:
            schedules = load_schedules()
            _ensure_notified_flag(schedules)

            now = datetime.now()
            changed = False

            for sched in schedules:
                try:
                    if sched.get("status") != "active":
                        continue

                    if sched.get("notified"):
                        continue

                    dt_str = sched.get("datetime")
                    if not dt_str:
                        continue

                    schedule_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                    reminder_minutes = int(sched.get("reminder_minutes", 15))
                    reminder_time = schedule_time - timedelta(minutes=reminder_minutes)

                    # 如果当前时间已经超过提醒时间，就触发一次通知
                    if now >= reminder_time:
                        title = f"日程提醒：{sched.get('title', '无标题')}"
                        desc = sched.get("description") or ""
                        msg = f"{dt_str}（提前 {reminder_minutes} 分钟提醒）"
                        if desc:
                            msg += f" - {desc}"

                        send_system_notification(title, msg)
                        sched["notified"] = True
                        sched["notified_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
                        changed = True
                        logger.info(f"[NOTIFIER] Fired notification for schedule {sched.get('id')}")
                except Exception as e:
                    logger.warning(f"[NOTIFIER] Error processing schedule {sched.get('id')}: {e}")

            if changed:
                save_schedules(schedules)

        except Exception as e:
            logger.error(f"[NOTIFIER] Error in notifier loop: {e}", exc_info=True)

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("[NOTIFIER] Schedule notifier starting...")

    # 如果 schedules.json 不存在，创建一个空文件
    if not os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

    try:
        asyncio.run(schedule_notifier_loop())
    except KeyboardInterrupt:
        logger.info("[NOTIFIER] Schedule notifier stopped by user")


if __name__ == "__main__":
    main()

