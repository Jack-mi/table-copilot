"""
AutoGen Multi-Agent Service
提供多 agent 对话服务，支持多轮对话和工具调用
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Optional, List, Callable, Awaitable, Any
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
import os
from dotenv import load_dotenv

# 导入工具集合（位于 backend.tools 包内）
from .tools.schedule_reminder import (
    create_schedule,
    list_schedules,
    delete_schedule,
    update_schedule,
    schedule_tools,
    TOOLS_AVAILABLE as SCHEDULE_TOOLS_AVAILABLE,
)
from .tools.ask_user_question import (
    ask_user_question,
    ask_user_question_tool,
    ASK_USER_TOOLS_AVAILABLE,
)

load_dotenv()

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# run_stream 流式事件与 chunk 分类（chunk_type）对应关系：
# - llm: 模型思考/推理/正文（ThoughtEvent、message.thought、ModelClientStreamingChunkEvent、TextMessage）
# - tool: 工具调用请求或结果（ToolCallRequestEvent、ToolCallExecutionEvent、ToolCallSummaryMessage）
# 前端可根据 chunk_type 做筛选、样式或日志区分。
#
# ReAct / reflect_on_tool_use 说明（AutoGen AssistantAgent）：
# - 每轮 ReAct：LLM 可能返回思考/正文或 tool_calls；工具执行后会把结果加入上下文并再次调用 LLM。
# - 设计上「结束节点」应为模型的总结回复（对工具结果的总结），不是工具调用本身。
# - 若 reflect_on_tool_use=True，工具循环结束后会再做一次模型推理（tool_choice="none"），
#   并 yield Response(chat_message=TextMessage(...))，BaseChatAgent.run_stream 会将其拆成
#   yield chat_message 再 yield TaskResult，故我们能在 messages 里拿到该 TextMessage。
# - 若 reflect_on_tool_use=False，则用 _summarize_tool_use 生成 ToolCallSummaryMessage 作为结束。
# - 未拿到最终模型回复的常见原因：(1) reflect 推理抛错（如 "Reflect on tool use produced no valid
#   text response"）；(2) 提取逻辑只认 source='assistant' 而 agent name 不同；(3) 流中最后一条
#   被误判。此处用多种回退方式提取，并在无任何正文时用工具成功 message 拼一段摘要。
def _stream_chunk_type(msg_type: str) -> str:
    if msg_type in ("ThoughtEvent", "ModelClientStreamingChunkEvent", "TextMessage"):
        return "llm"
    if msg_type in ("ToolCallRequestEvent", "ToolCallExecutionEvent", "ToolCallSummaryMessage"):
        return "tool"
    return "other"

# 为 HTTP 请求设置日志级别（减少噪音）
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)


def patch_kimi_reasoning():
    """
    Patch OpenAI 客户端以支持 Kimi 的 reasoning 字段。
    Kimi 返回 'reasoning' 字段，而 AutoGen 期望 'reasoning_content'。
    这个 patch 在消息的 model_extra 中添加 reasoning_content 以兼容 AutoGen。
    """
    try:
        from openai.types.chat.chat_completion import Choice
        from openai.types.chat.chat_completion_message import ChatCompletionMessage
        
        # 保存原始的 __init__
        original_message_init = ChatCompletionMessage.__init__
        
        def patched_message_init(self, **data):
            # 调用原始初始化
            original_message_init(self, **data)
            
            # 如果有 reasoning 但没有 reasoning_content，复制一份
            if hasattr(self, 'model_extra') and self.model_extra:
                reasoning = self.model_extra.get('reasoning')
                if reasoning and not self.model_extra.get('reasoning_content'):
                    # 添加 reasoning_content 以兼容 AutoGen
                    self.model_extra['reasoning_content'] = reasoning
        
        ChatCompletionMessage.__init__ = patched_message_init
        logger.info("[PATCH] Kimi reasoning compatibility patch applied")
        
    except Exception as e:
        logger.warning(f"[PATCH] Failed to apply Kimi reasoning patch: {e}")


# 应用 patch
patch_kimi_reasoning()


def load_system_prompt_template() -> str:
    """
    从配置文件中加载 system prompt 模板。
    如果读取失败，回退到一个简单的内置提示。
    """
    base_dir = os.path.dirname(__file__)
    config_path = os.path.join(base_dir, "config", "system_prompt.txt")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            template = f.read()
            if template.strip():
                logger.info(f"[CONFIG] Loaded system prompt template from {config_path}")
                return template
    except Exception as e:
        logger.warning(f"[CONFIG] Failed to load system prompt template: {e}")

    # 回退到一个简化版的内置提示（不会包含具体工具细节）
    fallback = (
        "You are Kimi, a workday schedule management expert. "
        "You help users manage calendars, tasks and reminders using the available tools."
    )
    logger.warning("[CONFIG] Using fallback built-in system prompt template")
    return fallback


class MultiAgentService:
    """多 Agent 服务类，管理对话状态和 agent 交互"""
    
    def __init__(self):
        """初始化服务，创建 agent 和运行时"""
        # 模型 / API 配置：统一走 OpenRouter，不再直接请求 OpenAI
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        fallback_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
        # 兜底：若 fallback_key 以 sk-or- 开头，视为 OpenRouter key
        if openrouter_key:
            self.api_key = openrouter_key
        elif fallback_key and fallback_key.startswith("sk-or-"):
            self.api_key = fallback_key
        else:
            raise ValueError("请设置 OPENROUTER_API_KEY 环境变量（OpenRouter 的 key 以 sk-or- 开头）")

        self.provider = "openrouter"
        self.model_name = os.getenv("MODEL_NAME", "moonshotai/kimi-k2.5")
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        
        logger.info(f"Using provider: {self.provider}")
        logger.info(f"Using model: {self.model_name}")
        logger.info(f"Base URL: {base_url}")
        
        # 创建 AutoGen 客户端
        self.model_client = OpenAIChatCompletionClient(
            model=self.model_name,
            api_key=self.api_key,
            base_url=base_url,
            model_info={
                "vision": False,
                "function_calling": True,
                "json_output": True,
                "family": "unknown",
            }
        )
        logger.info("Model client created successfully")
        
        # 存储每个会话的 agent 实例和对话历史
        self.session_agents: Dict[str, AssistantAgent] = {}
        self.conversation_history: Dict[str, List] = {}
        # 加载系统提示模板（只读一次）
        self.system_prompt_template: str = load_system_prompt_template()

    def _build_system_prompt(self) -> str:
        """根据模板和当前上下文构建最终的 system prompt。"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        prompt = self.system_prompt_template.replace("{{MODEL_NAME}}", self.model_name)
        prompt = prompt.replace("{{CURRENT_TIME}}", current_time)
        return prompt
    
    def get_or_create_agent(self, session_id: str) -> AssistantAgent:
        """获取或创建会话的 agent 实例"""
        if session_id not in self.session_agents:
            logger.info(f"[AGENT] Creating new agent for session {session_id}")
            
            # 根据 FunctionTool 是否可用选择工具列表
            # 如果 autogen_core.tools 可用，使用 FunctionTool 包装的工具
            # 否则直接使用原始函数（autogen-agentchat 支持 Callable 类型的工具）
            agent_tools = []

            # 日程类工具
            if SCHEDULE_TOOLS_AVAILABLE and schedule_tools:
                agent_tools.extend(schedule_tools)
                logger.info(f"[AGENT] Using schedule FunctionTools: {len(schedule_tools)} tools")
            else:
                agent_tools.extend([create_schedule, list_schedules, delete_schedule, update_schedule])
                logger.info("[AGENT] Using raw schedule functions as tools")

            # 用户澄清问题工具（askUserQuestion）
            if ASK_USER_TOOLS_AVAILABLE and ask_user_question_tool:
                agent_tools.append(ask_user_question_tool)
                logger.info("[AGENT] Using askUserQuestion FunctionTool")
            else:
                agent_tools.append(ask_user_question)
                logger.info("[AGENT] Using raw ask_user_question function as tool")
            
            # 每轮对话使用 ReAct loop：模型可多次调用 tool，直到本轮不再发起 tool 才结束并返回最终回复
            self.session_agents[session_id] = AssistantAgent(
                name="assistant",
                model_client=self.model_client,
                system_message=self._build_system_prompt(),
                tools=agent_tools,
                max_tool_iterations=10,      # 单轮内最多 10 次 tool 调用，防止死循环
                reflect_on_tool_use=True,    # 每次 tool 结果后让模型再推理，决定继续 call tool 或产出最终文本
            )
            logger.debug(f"[AGENT] Agent created successfully for session {session_id}")
            logger.debug(f"[AGENT] Total active sessions: {len(self.session_agents)}")
        else:
            logger.debug(f"[AGENT] Reusing existing agent for session {session_id}")
        return self.session_agents[session_id]
    
    def get_or_create_history(self, session_id: str) -> List:
        """获取或创建会话历史"""
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []
        return self.conversation_history[session_id]
    
    async def process_message(
        self,
        session_id: str,
        user_message: str,
        stream_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Dict:
        """
        处理用户消息并返回 agent 响应。
        
        语义约定（与具体是否用 Kimi 等模型无关）：
        - 每轮中可能有多轮「模型 → 调用 tool → 执行 → 回填」的循环，但**结束节点一定是大模型对 tool 的总结回复**，而不是工具调用本身。
        - 即：工具调用是中间步骤，最终展示给用户的 content 必须是模型的那段总结性文本。
        - 该约定由 ReAct/框架保证（如 reflect_on_tool_use）；此处从 stream 中提取的即是这段「最终模型回复」。
        
        Args:
            session_id: 会话 ID，用于维护多轮对话
            user_message: 用户消息
            stream_callback: 可选，流式事件回调（thought/tool_call/llm_chunk），事件中带 chunk_type（llm/tool）
            
        Returns:
            包含 content、thoughts、tool_calls 的字典
        """
        import time
        start_time = time.time()
        
        # 初始化响应结构
        result = {
            "content": "",
            "thoughts": [],      # 思考过程
            "tool_calls": [],    # 工具调用
        }
        
        try:
            logger.info(f"[PROCESS] Processing message for session {session_id}")
            logger.debug(f"[PROCESS] Message length: {len(user_message)} chars")
            logger.debug(f"[PROCESS] Message content: {user_message[:200]}...")
            
            # 获取会话的 agent 和历史
            agent = self.get_or_create_agent(session_id)
            history = self.get_or_create_history(session_id)
            logger.debug(f"[SESSION] Session {session_id} has {len(history)} history entries")
            
            # 本轮的 ReAct loop 由 AutoGen 在 agent.run_stream 内部实现：
            # 循环：模型输出 → 若含 tool_calls 则执行并回写结果 → 模型再推理 → 直到本轮无 tool 调用则 break，得到最终文本
            messages = []
            message_count = 0
            logger.info(f"[AGENT] Starting agent.run_stream (ReAct loop) for session {session_id}")
            
            try:
                async for message in agent.run_stream(task=user_message):
                    messages.append(message)
                    message_count += 1
                    msg_type = type(message).__name__
                    logger.info(f"[STREAM] Received message #{message_count}: {msg_type}")
                    
                    # 提取思考过程（AutoGen 官方类型：autogen_agentchat.messages.ThoughtEvent）
                    if msg_type == "ThoughtEvent":
                        if hasattr(message, 'content') and message.content:
                            thought_item = {
                                "content": message.content,
                                "source": getattr(message, 'source', 'assistant')
                            }
                            result["thoughts"].append(thought_item)
                            logger.info(f"[THOUGHT] Captured ThoughtEvent: {message.content[:100]}...")
                            # 流式回传思考过程（分类为 llm）
                            if stream_callback is not None:
                                try:
                                    await stream_callback(
                                        {
                                            "type": "thought",
                                            "chunk_type": "llm",
                                            "thought": thought_item,
                                        }
                                    )
                                except Exception as cb_err:
                                    logger.warning(f"[STREAM_CALLBACK] Error sending thought event: {cb_err}")
                    
                    # LLM 逐 token 流式输出（若模型客户端支持）
                    elif msg_type == "ModelClientStreamingChunkEvent":
                        chunk_content = getattr(message, "content", None) or getattr(message, "chunk", None) or getattr(message, "delta", "")
                        if chunk_content and stream_callback is not None:
                            try:
                                await stream_callback(
                                    {
                                        "type": "llm_chunk",
                                        "chunk_type": "llm",
                                        "delta": chunk_content if isinstance(chunk_content, str) else str(chunk_content),
                                    }
                                )
                            except Exception as cb_err:
                                logger.warning(f"[STREAM_CALLBACK] Error sending llm_chunk: {cb_err}")
                    
                    # 提取工具调用请求 (ToolCallRequestEvent)
                    elif msg_type == "ToolCallRequestEvent":
                        if hasattr(message, 'content'):
                            for call in message.content:
                                tool_call = {
                                    "id": getattr(call, 'id', ''),
                                    "name": getattr(call, 'name', ''),
                                    "arguments": getattr(call, 'arguments', '{}'),
                                    "status": "pending"
                                }
                                result["tool_calls"].append(tool_call)
                                logger.info(f"[TOOL_CALL] Tool request: {tool_call['name']}({tool_call['arguments'][:50]}...)")
                                # 流式回传工具调用请求（分类为 tool）
                                if stream_callback is not None:
                                    try:
                                        await stream_callback(
                                            {
                                                "type": "tool_call",
                                                "chunk_type": "tool",
                                                "phase": "request",
                                                "tool_call": tool_call,
                                            }
                                        )
                                    except Exception as cb_err:
                                        logger.warning(f"[STREAM_CALLBACK] Error sending tool call request: {cb_err}")
                    
                    # 提取工具调用结果 (ToolCallExecutionEvent)
                    elif msg_type == "ToolCallExecutionEvent":
                        if hasattr(message, 'content'):
                            for exec_result in message.content:
                                call_id = getattr(exec_result, 'call_id', '')
                                # 更新对应的工具调用状态
                                for tc in result["tool_calls"]:
                                    if tc["id"] == call_id:
                                        tc["result"] = getattr(exec_result, 'content', '')
                                        tc["is_error"] = getattr(exec_result, 'is_error', False)
                                        tc["status"] = "error" if tc["is_error"] else "completed"
                                        logger.info(f"[TOOL_RESULT] Tool {tc['name']} completed: {tc['result'][:100]}...")
                                        # 流式回传工具调用结果（分类为 tool）
                                        if stream_callback is not None:
                                            try:
                                                await stream_callback(
                                                    {
                                                        "type": "tool_call",
                                                        "chunk_type": "tool",
                                                        "phase": "result",
                                                        "tool_call": tc,
                                                    }
                                                )
                                            except Exception as cb_err:
                                                logger.warning(f"[STREAM_CALLBACK] Error sending tool call result: {cb_err}")
                                        break
                    
                    # 从 ToolCallSummaryMessage 中提取工具调用信息（备用方案）
                    elif msg_type == "ToolCallSummaryMessage":
                        if hasattr(message, 'tool_calls') and message.tool_calls:
                            for call in message.tool_calls:
                                # 检查是否已存在
                                call_id = getattr(call, 'id', '')
                                existing = any(tc['id'] == call_id for tc in result["tool_calls"])
                                if not existing:
                                    tool_call = {
                                        "id": call_id,
                                        "name": getattr(call, 'name', ''),
                                        "arguments": getattr(call, 'arguments', '{}'),
                                        "status": "pending"
                                    }
                                    result["tool_calls"].append(tool_call)
                                    # 流式回传工具调用摘要（当作 request 处理，分类为 tool）
                                    if stream_callback is not None:
                                        try:
                                            await stream_callback(
                                                {
                                                    "type": "tool_call",
                                                    "chunk_type": "tool",
                                                    "phase": "request",
                                                    "tool_call": tool_call,
                                                }
                                            )
                                        except Exception as cb_err:
                                            logger.warning(f"[STREAM_CALLBACK] Error sending tool call summary request: {cb_err}")
                        
                        if hasattr(message, 'results') and message.results:
                            for exec_result in message.results:
                                call_id = getattr(exec_result, 'call_id', '')
                                for tc in result["tool_calls"]:
                                    if tc["id"] == call_id:
                                        tc["result"] = getattr(exec_result, 'content', '')
                                        tc["is_error"] = getattr(exec_result, 'is_error', False)
                                        tc["status"] = "error" if tc["is_error"] else "completed"
                                        # 流式回传工具调用结果摘要（分类为 tool）
                                        if stream_callback is not None:
                                            try:
                                                await stream_callback(
                                                    {
                                                        "type": "tool_call",
                                                        "chunk_type": "tool",
                                                        "phase": "result",
                                                        "tool_call": tc,
                                                    }
                                                )
                                            except Exception as cb_err:
                                                logger.warning(f"[STREAM_CALLBACK] Error sending tool call summary result: {cb_err}")
                                        break
                        
                        logger.info(f"[TOOL_SUMMARY] Extracted from ToolCallSummaryMessage: {len(result['tool_calls'])} tool calls")
                    
                    # 检查是否有 thought 属性（某些版本的 autogen 可能会添加）
                    if hasattr(message, 'thought') and message.thought:
                        thought_item = {
                            "content": message.thought,
                            "source": getattr(message, 'source', 'assistant')
                        }
                        result["thoughts"].append(thought_item)
                        logger.info(f"[THOUGHT] Captured from message.thought: {message.thought[:100]}...")
                        # 流式回传思考过程（message.thought 字段，分类为 llm）
                        if stream_callback is not None:
                            try:
                                await stream_callback(
                                    {
                                        "type": "thought",
                                        "chunk_type": "llm",
                                        "thought": thought_item,
                                    }
                                )
                            except Exception as cb_err:
                                logger.warning(f"[STREAM_CALLBACK] Error sending thought(thought field) event: {cb_err}")
            except Exception as stream_error:
                logger.error(f"[STREAM] Error in agent.run_stream: {str(stream_error)}", exc_info=True)
                raise
            
            logger.info(f"[STREAM] Stream completed, received {len(messages)} messages")
            logger.info(f"[STREAM] Collected {len(result['thoughts'])} thoughts, {len(result['tool_calls'])} tool calls")
            
            # 结束节点一定是大模型的回复（对 tool 的总结），不是工具调用。从 stream 中提取该最终模型回复作为 content。
            response_text = ""
            
            if messages:
                # 从后往前查找 assistant 的 TextMessage（即模型在 tool 执行后的总结回复）
                assistant_message = None
                
                # 方法1：查找 source='assistant' 的 TextMessage
                for msg in reversed(messages):
                    msg_type = type(msg).__name__
                    # 检查是否是 TextMessage 且 source 是 assistant
                    if hasattr(msg, 'source') and msg.source == 'assistant':
                        # 排除事件类型，只要消息类型
                        if msg_type in ['TextMessage', 'ToolCallSummaryMessage']:
                            if hasattr(msg, 'content'):
                                assistant_message = msg
                                logger.debug(f"[EXTRACT] Found assistant message with source='assistant', type={msg_type}")
                                break
                
                # 方法2：如果没找到，查找包含 assistant 回复的 TextMessage（通常倒数第二条）
                if assistant_message is None and len(messages) >= 2:
                    # 从后往前查找，跳过 TaskResult
                    for msg in reversed(messages[:-1]):  # 排除最后一条（通常是 TaskResult）
                        msg_type = type(msg).__name__
                        if hasattr(msg, 'content') and hasattr(msg, 'source'):
                            if msg.source == 'assistant' and msg_type in ['TextMessage', 'ToolCallSummaryMessage']:
                                assistant_message = msg
                                logger.debug(f"[EXTRACT] Found assistant message (method 2), type={msg_type}")
                                break
                
                # 方法3：如果还是没找到，尝试从 TaskResult 中提取
                if assistant_message is None:
                    last_message = messages[-1]
                    logger.debug(f"[EXTRACT] Last message is {type(last_message).__name__}, attempting to extract from TaskResult")
                    
                    # 检查是否是 TaskResult，包含 messages 属性
                    if hasattr(last_message, 'messages'):
                        # 从 messages 列表中查找 assistant 的回复
                        for msg in reversed(last_message.messages):
                            msg_type = type(msg).__name__
                            if hasattr(msg, 'source') and msg.source == 'assistant':
                                if hasattr(msg, 'content') and msg_type in ['TextMessage', 'ToolCallSummaryMessage']:
                                    assistant_message = msg
                                    logger.debug(f"[EXTRACT] Found assistant message in TaskResult.messages, type={msg_type}")
                                    break
                
                # 方法4：最后一条非 TaskResult 的 TextMessage/ToolCallSummaryMessage（兼容 agent 名或 reflect 形态）
                if assistant_message is None:
                    for msg in reversed(messages):
                        msg_type = type(msg).__name__
                        if msg_type == 'TaskResult':
                            continue
                        if msg_type in ['TextMessage', 'ToolCallSummaryMessage'] and hasattr(msg, 'content'):
                            content = msg.content
                            if content and (isinstance(content, str) and content.strip()):
                                assistant_message = msg
                                logger.debug(f"[EXTRACT] Found last non-TaskResult message (method 4), type={msg_type}, source={getattr(msg, 'source', 'N/A')}")
                                break
                
                # 提取内容
                if assistant_message is not None:
                    if hasattr(assistant_message, 'content'):
                        content = assistant_message.content
                        if isinstance(content, str):
                            response_text = content
                        else:
                            response_text = str(content)
                        logger.debug(f"[EXTRACT] Extracted assistant response: {len(response_text)} chars")
                    else:
                        logger.warning(f"[EXTRACT] Assistant message found but no content attribute")
                else:
                    # 如果还是找不到，使用旧的逻辑作为后备
                    logger.warning(f"[EXTRACT] Could not find assistant message, using fallback")
                    last_message = messages[-1]
                    if hasattr(last_message, 'content'):
                        content = last_message.content
                        if isinstance(content, str):
                            response_text = content
                        else:
                            response_text = str(content)
                    elif hasattr(last_message, 'text'):
                        response_text = last_message.text
                    else:
                        response_text = str(last_message)
                
                if not response_text or len(response_text.strip()) == 0:
                    logger.warning(f"[EXTRACT] No assistant text found in stream (messages: {len(messages)})")
                    msg_info = [f"{type(m).__name__}(source={getattr(m, 'source', 'N/A')})" for m in messages]
                    logger.debug(f"[EXTRACT] All messages: {msg_info}")
                    # 按理结束节点应为模型总结；未提取到时为降级：用工具返回的 message 拼一段摘要
                    success_tools = [tc for tc in result.get("tool_calls", []) if tc.get("status") == "completed"]
                    if success_tools:
                        parts = []
                        for tc in success_tools:
                            name = tc.get("name") or "tool"
                            try:
                                raw = tc.get("result") or ""
                                parsed = json.loads(raw) if isinstance(raw, str) else raw
                                if isinstance(parsed, dict) and parsed.get("success") and parsed.get("message"):
                                    parts.append(parsed.get("message"))
                                elif name == "create_schedule":
                                    parts.append("已创建日程。")
                                else:
                                    parts.append(f"已执行 {name}。")
                            except Exception:
                                parts.append(f"已执行 {name}。")
                        response_text = " ".join(parts) if parts else "操作已完成。"
                    else:
                        response_text = "I apologize, but I couldn't generate a response."

                # 通用规则：如果某些工具的返回中包含结构化的 markdown（如澄清问题），
                # 则将这些 markdown 追加到最终回答后面，避免只出现一句「请选择一个选项」而看不到完整内容。
                # 注意：askUserQuestion 的提问内容通常已由模型在回复中写出，不再追加以免重复显示两遍。
                try:
                    extra_markdowns = []
                    _skip_markdown_tools = ("askUserQuestion", "ask_user_question")
                    for tc in result.get("tool_calls", []):
                        if tc.get("status") != "completed":
                            continue
                        if (tc.get("name") or "").strip() in _skip_markdown_tools:
                            continue
                        raw_result = tc.get("result")
                        if not raw_result:
                            continue
                        try:
                            parsed = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
                        except Exception:
                            continue
                        if not isinstance(parsed, dict) or not parsed.get("success"):
                            continue
                        data = parsed.get("data") or parsed
                        markdown = None
                        if isinstance(data, dict):
                            # 约定：工具若希望其 markdown 直接展示给用户，可放在 data["markdown"]
                            markdown = data.get("markdown")
                        if isinstance(markdown, str) and markdown.strip():
                            extra_markdowns.append(markdown.strip())

                    if extra_markdowns:
                        # 将这些 markdown 附加到模型回答后面（通用，不限定具体工具名）
                        extra_block = "\n\n".join(extra_markdowns)
                        if response_text:
                            response_text = response_text.rstrip() + "\n\n" + extra_block
                        else:
                            response_text = extra_block
                except Exception as e:
                    logger.warning(f"[POSTPROCESS] Failed to inject tool markdown into answer: {e}")

                result["content"] = response_text

                # 保存到历史记录
                history.append({
                    "role": "user",
                    "content": user_message
                })
                history.append({
                    "role": "assistant",
                    "content": response_text
                })
                
                elapsed_time = time.time() - start_time
                logger.info(f"[SUCCESS] Response generated in {elapsed_time:.2f}s, length: {len(response_text)} chars")
                logger.debug(f"[SUCCESS] Response preview: {response_text[:200]}...")
                return result
            else:
                logger.warning(f"[ERROR] No messages received from agent for session {session_id}")
                result["content"] = "I apologize, but I couldn't generate a response."
                return result
                
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[ERROR] Error processing message for session {session_id} after {elapsed_time:.2f}s: {str(e)}", exc_info=True)
            logger.error(f"[ERROR] Exception type: {type(e).__name__}")
            result["content"] = f"Error: {str(e)}"
            return result
    
    def clear_history(self, session_id: str):
        """清除指定会话的历史记录和 agent"""
        if session_id in self.conversation_history:
            del self.conversation_history[session_id]
        if session_id in self.session_agents:
            del self.session_agents[session_id]
        logger.info(f"Cleared history and agent for session {session_id}")
