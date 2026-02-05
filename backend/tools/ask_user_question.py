"""
AskUserQuestion 工具
用于在用户需求不清晰时，向用户发起结构化澄清问题。

输入 / 输出统一采用 JSON 结构，以便上游/下游统一处理。
"""

import json
from typing import List, Optional, Dict, Any

try:
    from typing_extensions import Annotated
except ImportError:
    from typing import Annotated


def _make_result(
    success: bool,
    data: Optional[Any] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
) -> str:
    """
    统一 JSON 返回格式：
    {
      "tool": "askUserQuestion",
      "success": true/false,
      "message": "<可选的人类可读描述>",
      "data": { ... 问题结构 ... },
      "error": "<错误信息，仅在 success=false 时出现>"
    }
    """
    payload: Dict[str, Any] = {"tool": "askUserQuestion", "success": success}
    if message:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    if error:
        payload["error"] = error
    return json.dumps(payload, ensure_ascii=False)


def ask_user_question(
    question: Annotated[str, "要向用户提出的自然语言问题，要求简洁具体"],
    question_type: Annotated[
        str,
        "问题类型：single_choice(单选)、multi_choice(多选)、boolean(是/否判断)",
    ] = "single_choice",
    options: Annotated[
        Optional[List[str]],
        "候选选项列表。对于 single_choice / multi_choice 必填，boolean 可留空。",
    ] = None,
) -> str:
    """
    向用户发起一个结构化澄清问题。

    返回值为 JSON 字符串，示例：
    {
      "tool": "askUserQuestion",
      "success": true,
      "data": {
        "question": "...",
        "question_type": "single_choice",
        "options": ["选项1", "选项2"],
        "markdown": "...用于直接展示给用户的问题文案..."
      }
    }
    """
    qt = (question_type or "").strip().lower()
    valid_types = {"single_choice", "multi_choice", "boolean"}

    if qt not in valid_types:
        return _make_result(
            False,
            error=f"不支持的问题类型 '{question_type}'，请使用 single_choice / multi_choice / boolean。",
        )

    # 处理选项
    opts: List[str] = options or []
    if qt in {"single_choice", "multi_choice"}:
        # 单选/多选必须有至少两个候选项
        cleaned = [o.strip() for o in opts if isinstance(o, str) and o.strip()]
        if len(cleaned) < 2:
            return _make_result(
                False,
                error="single_choice / multi_choice 类型必须提供至少 2 个非空选项。",
            )
        opts = cleaned

    # 生成选项展示（带 A/B/C... 标签）
    def _format_options(option_list: List[str]) -> str:
        labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        lines: List[str] = []
        for idx, text in enumerate(option_list):
            label = labels[idx] if idx < len(labels) else f"选项{idx + 1}"
            lines.append(f"- {label}. {text}")
        return "\n".join(lines)

    # 根据类型生成用户提示
    if qt == "boolean":
        hint = "请回答：是 / 否（也可以用 yes/no、对/错 等同义表达）。"
        options_block = ""
    elif qt == "single_choice":
        hint = "这是一个单选题，请选择**一个**最符合你想法的选项，并回复对应的字母。"
        options_block = _format_options(opts)
    else:  # multi_choice
        hint = "这是一个多选题，可以选择**一个或多个**选项，并回复对应字母组合，例如：A,C。"
        options_block = _format_options(opts)

    # 构造 Markdown 展示文案
    lines: List[str] = []
    lines.append("❓ 为了更准确地帮你规划和管理日程，我需要先确认一个问题：")
    lines.append("")
    lines.append(f"**问题类型**：{qt}")
    lines.append("")
    lines.append(f"**问题内容**：{question}")
    lines.append("")

    if options_block:
        lines.append("**可选项：**")
        lines.append("")
        lines.append(options_block)
        lines.append("")

    lines.append(hint)
    lines.append("")
    lines.append("回答示例：`A` 或 `A,C` 或 `是`。")

    markdown = "\n".join(lines)

    data = {
        "question": question,
        "question_type": qt,
        "options": opts,
        "markdown": markdown,
    }

    return _make_result(True, data=data, message="已生成澄清问题")


# 尝试创建 FunctionTool 实例（需要 autogen_core）
try:
    from autogen_core.tools import FunctionTool

    ask_user_question_tool = FunctionTool(
        func=ask_user_question,
        name="askUserQuestion",
        description="""
向用户发起结构化的澄清问题（单选 / 多选 / 判断），用于在需求模糊时主动确认用户意图。

输入参数：
- question: string，自然语言问题内容；
- question_type: string，single_choice / multi_choice / boolean；
- options: string[]，选项列表（single_choice / multi_choice 必填，boolean 可选）。

输出为 JSON 字符串：
{
  "tool": "askUserQuestion",
  "success": true,
  "data": {
    "question": "...",
    "question_type": "single_choice",
    "options": ["...", "..."],
    "markdown": "...可直接展示给用户的问题文案..."
  }
}
""".strip(),
    )

    ASK_USER_TOOLS_AVAILABLE = True

except ImportError:
    # 如果 autogen_core 不可用，退化为普通函数工具
    ask_user_question_tool = None
    ASK_USER_TOOLS_AVAILABLE = False


