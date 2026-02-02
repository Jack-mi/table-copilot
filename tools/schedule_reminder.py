"""
日程提醒工具
用于创建、管理日程和闹钟提醒
"""

import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from typing_extensions import Annotated
except ImportError:
    from typing import Annotated


# 日程存储文件路径
SCHEDULE_FILE = os.path.join(os.path.dirname(__file__), "..", "schedules.json")


def _load_schedules() -> List[Dict[str, Any]]:
    """加载已保存的日程"""
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_schedules(schedules: List[Dict[str, Any]]) -> None:
    """保存日程到文件"""
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)


def _generate_id() -> str:
    """生成唯一 ID"""
    import uuid
    return str(uuid.uuid4())[:8]


def create_schedule(
    title: Annotated[str, "日程标题，简短描述日程内容"],
    datetime_str: Annotated[str, "日程时间，格式为 YYYY-MM-DD HH:MM，例如 2024-03-15 14:30"],
    description: Annotated[Optional[str], "日程详细描述（可选）"] = None,
    reminder_minutes: Annotated[int, "提前提醒的分钟数，默认为15分钟"] = 15,
    repeat: Annotated[Optional[str], "重复类型：once(一次)、daily(每天)、weekly(每周)、monthly(每月)，默认为once"] = "once",
) -> str:
    """
    创建一个新的日程提醒。
    
    当用户需要设置日程、闹钟、提醒或者计划某项活动时使用此工具。
    例如：
    - "明天下午3点提醒我开会"
    - "设置一个每周一上午9点的例会提醒"
    - "帮我建一个下周五的生日提醒"
    
    Args:
        title: 日程标题
        datetime_str: 日程时间，格式为 YYYY-MM-DD HH:MM
        description: 日程详细描述
        reminder_minutes: 提前提醒的分钟数
        repeat: 重复类型
    
    Returns:
        创建结果的描述信息
    """
    try:
        # 解析日期时间
        schedule_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
        
        # 检查时间是否已过
        if schedule_time < datetime.now() and repeat == "once":
            return f"错误：指定的时间 {datetime_str} 已经过去，请设置一个未来的时间。"
        
        # 验证重复类型
        valid_repeats = ["once", "daily", "weekly", "monthly"]
        if repeat not in valid_repeats:
            return f"错误：无效的重复类型 '{repeat}'。有效选项：{', '.join(valid_repeats)}"
        
        # 创建日程
        schedule_id = _generate_id()
        schedule = {
            "id": schedule_id,
            "title": title,
            "datetime": datetime_str,
            "description": description or "",
            "reminder_minutes": reminder_minutes,
            "repeat": repeat,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "active"
        }
        
        # 加载现有日程并添加新日程
        schedules = _load_schedules()
        schedules.append(schedule)
        _save_schedules(schedules)
        
        # 构建返回信息
        repeat_text = {
            "once": "单次",
            "daily": "每天",
            "weekly": "每周",
            "monthly": "每月"
        }.get(repeat, repeat)
        
        result = f"✅ 日程创建成功！\n"
        result += f"📋 ID: {schedule_id}\n"
        result += f"📝 标题: {title}\n"
        result += f"📅 时间: {datetime_str}\n"
        result += f"🔔 提前 {reminder_minutes} 分钟提醒\n"
        result += f"🔄 重复: {repeat_text}"
        
        if description:
            result += f"\n📄 描述: {description}"
        
        return result
        
    except ValueError as e:
        return f"错误：日期时间格式不正确。请使用格式 YYYY-MM-DD HH:MM，例如 2024-03-15 14:30。详细错误: {str(e)}"
    except Exception as e:
        return f"创建日程时发生错误: {str(e)}"


def list_schedules(
    status: Annotated[Optional[str], "筛选状态：all(全部)、active(活动)、completed(已完成)，默认为active"] = "active",
    limit: Annotated[int, "返回的最大日程数量，默认为10"] = 10,
) -> str:
    """
    列出现有的日程提醒。
    
    当用户想要查看自己的日程安排时使用此工具。
    例如：
    - "我有哪些日程"
    - "查看我的待办事项"
    - "显示所有提醒"
    
    Args:
        status: 筛选状态
        limit: 返回的最大数量
    
    Returns:
        日程列表的描述信息
    """
    try:
        schedules = _load_schedules()
        
        if not schedules:
            return "📭 当前没有任何日程。使用创建日程功能来添加新的提醒吧！"
        
        # 根据状态筛选
        if status != "all":
            schedules = [s for s in schedules if s.get("status") == status]
        
        if not schedules:
            return f"📭 没有找到状态为 '{status}' 的日程。"
        
        # 按时间排序
        schedules.sort(key=lambda x: x.get("datetime", ""))
        
        # 限制数量
        schedules = schedules[:limit]
        
        # 构建返回信息
        result = f"📅 日程列表（共 {len(schedules)} 项）：\n"
        result += "=" * 40 + "\n"
        
        repeat_text_map = {
            "once": "单次",
            "daily": "每天",
            "weekly": "每周",
            "monthly": "每月"
        }
        
        for i, schedule in enumerate(schedules, 1):
            repeat_text = repeat_text_map.get(schedule.get("repeat", "once"), schedule.get("repeat"))
            result += f"\n{i}. 【{schedule['title']}】\n"
            result += f"   🆔 ID: {schedule['id']}\n"
            result += f"   📅 时间: {schedule['datetime']}\n"
            result += f"   🔔 提前 {schedule.get('reminder_minutes', 15)} 分钟提醒\n"
            result += f"   🔄 重复: {repeat_text}\n"
            if schedule.get("description"):
                result += f"   📄 描述: {schedule['description']}\n"
        
        return result
        
    except Exception as e:
        return f"获取日程列表时发生错误: {str(e)}"


def delete_schedule(
    schedule_id: Annotated[str, "要删除的日程ID"],
) -> str:
    """
    删除指定的日程提醒。
    
    当用户想要取消或删除某个日程时使用此工具。
    例如：
    - "删除明天的会议提醒"
    - "取消ID为xxx的日程"
    
    Args:
        schedule_id: 日程ID
    
    Returns:
        删除结果的描述信息
    """
    try:
        schedules = _load_schedules()
        
        # 查找要删除的日程
        schedule_to_delete = None
        for schedule in schedules:
            if schedule["id"] == schedule_id:
                schedule_to_delete = schedule
                break
        
        if not schedule_to_delete:
            return f"❌ 未找到 ID 为 '{schedule_id}' 的日程。请使用列表功能查看现有日程的 ID。"
        
        # 删除日程
        schedules = [s for s in schedules if s["id"] != schedule_id]
        _save_schedules(schedules)
        
        return f"✅ 已成功删除日程：【{schedule_to_delete['title']}】（时间：{schedule_to_delete['datetime']}）"
        
    except Exception as e:
        return f"删除日程时发生错误: {str(e)}"


def update_schedule(
    schedule_id: Annotated[str, "要更新的日程ID"],
    title: Annotated[Optional[str], "新的日程标题（可选）"] = None,
    datetime_str: Annotated[Optional[str], "新的日程时间，格式为 YYYY-MM-DD HH:MM（可选）"] = None,
    description: Annotated[Optional[str], "新的日程描述（可选）"] = None,
    reminder_minutes: Annotated[Optional[int], "新的提前提醒分钟数（可选）"] = None,
    status: Annotated[Optional[str], "新的状态：active(活动)、completed(已完成)（可选）"] = None,
) -> str:
    """
    更新已有的日程提醒。
    
    当用户想要修改某个日程的信息时使用此工具。
    例如：
    - "把会议时间改到下午4点"
    - "更新日程标题"
    - "标记日程为已完成"
    
    Args:
        schedule_id: 日程ID
        title: 新标题
        datetime_str: 新时间
        description: 新描述
        reminder_minutes: 新的提醒时间
        status: 新状态
    
    Returns:
        更新结果的描述信息
    """
    try:
        schedules = _load_schedules()
        
        # 查找要更新的日程
        schedule_index = None
        for i, schedule in enumerate(schedules):
            if schedule["id"] == schedule_id:
                schedule_index = i
                break
        
        if schedule_index is None:
            return f"❌ 未找到 ID 为 '{schedule_id}' 的日程。请使用列表功能查看现有日程的 ID。"
        
        # 更新字段
        schedule = schedules[schedule_index]
        updated_fields = []
        
        if title is not None:
            schedule["title"] = title
            updated_fields.append(f"标题 -> {title}")
        
        if datetime_str is not None:
            try:
                datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                schedule["datetime"] = datetime_str
                updated_fields.append(f"时间 -> {datetime_str}")
            except ValueError:
                return "错误：日期时间格式不正确。请使用格式 YYYY-MM-DD HH:MM。"
        
        if description is not None:
            schedule["description"] = description
            updated_fields.append(f"描述已更新")
        
        if reminder_minutes is not None:
            schedule["reminder_minutes"] = reminder_minutes
            updated_fields.append(f"提醒时间 -> 提前{reminder_minutes}分钟")
        
        if status is not None:
            if status not in ["active", "completed"]:
                return "错误：无效的状态。有效选项：active, completed"
            schedule["status"] = status
            updated_fields.append(f"状态 -> {status}")
        
        if not updated_fields:
            return "⚠️ 没有提供需要更新的字段。"
        
        schedule["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        schedules[schedule_index] = schedule
        _save_schedules(schedules)
        
        result = f"✅ 日程更新成功！\n"
        result += f"📋 ID: {schedule_id}\n"
        result += f"📝 更新内容：\n"
        for field in updated_fields:
            result += f"   • {field}\n"
        
        return result
        
    except Exception as e:
        return f"更新日程时发生错误: {str(e)}"


# 尝试创建 FunctionTool 实例（需要 autogen_core）
try:
    from autogen_core.tools import FunctionTool
    
    # 创建日程工具
    create_schedule_tool = FunctionTool(
        func=create_schedule,
        name="create_schedule",
        description="""创建一个新的日程提醒。当用户需要设置日程、闹钟、提醒或者计划某项活动时使用此工具。
        
    使用场景示例：
    - "明天下午3点提醒我开会"
    - "设置一个每周一上午9点的例会提醒"  
    - "帮我建一个下周五的生日提醒"
    - "提醒我今天晚上8点吃药"

    参数说明：
    - title: 日程标题
    - datetime_str: 日程时间，格式为 YYYY-MM-DD HH:MM
    - description: 详细描述（可选）
    - reminder_minutes: 提前多少分钟提醒（默认15分钟）
    - repeat: 重复类型 once/daily/weekly/monthly（默认once）""",
    )

    # 列出日程工具
    list_schedules_tool = FunctionTool(
        func=list_schedules,
        name="list_schedules",
        description="""列出现有的日程提醒。当用户想要查看自己的日程安排时使用此工具。

    使用场景示例：
    - "我有哪些日程"
    - "查看我的待办事项"
    - "显示所有提醒"
    - "今天有什么安排"

    参数说明：
    - status: 筛选状态 all/active/completed（默认active）
    - limit: 返回的最大数量（默认10）""",
    )

    # 删除日程工具  
    delete_schedule_tool = FunctionTool(
        func=delete_schedule,
        name="delete_schedule",
        description="""删除指定的日程提醒。当用户想要取消或删除某个日程时使用此工具。

    使用场景示例：
    - "删除明天的会议提醒"
    - "取消ID为xxx的日程"
    - "移除那个提醒"

    参数说明：
    - schedule_id: 要删除的日程ID（可通过list_schedules获取）""",
    )

    # 更新日程工具
    update_schedule_tool = FunctionTool(
        func=update_schedule,
        name="update_schedule", 
        description="""更新已有的日程提醒。当用户想要修改某个日程的信息时使用此工具。

    使用场景示例：
    - "把会议时间改到下午4点"
    - "更新日程标题"
    - "标记日程为已完成"
    - "修改那个提醒的描述"

    参数说明：
    - schedule_id: 要更新的日程ID
    - title: 新标题（可选）
    - datetime_str: 新时间（可选）
    - description: 新描述（可选）
    - reminder_minutes: 新的提醒时间（可选）
    - status: 新状态 active/completed（可选）""",
    )

    # 导出主要工具（为了方便使用，提供一个组合工具）
    schedule_reminder_tool = create_schedule_tool

    # 所有日程相关工具列表
    schedule_tools = [
        create_schedule_tool,
        list_schedules_tool,
        delete_schedule_tool,
        update_schedule_tool,
    ]
    
    TOOLS_AVAILABLE = True

except ImportError:
    # 如果 autogen_core 不可用，设置为 None
    create_schedule_tool = None
    list_schedules_tool = None
    delete_schedule_tool = None
    update_schedule_tool = None
    schedule_reminder_tool = None
    schedule_tools = []
    TOOLS_AVAILABLE = False
