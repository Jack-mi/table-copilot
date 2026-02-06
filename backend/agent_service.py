"""
AutoGen Multi-Agent Service
提供多 agent 对话服务，支持多轮对话和工具调用
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Optional, List
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
            
            self.session_agents[session_id] = AssistantAgent(
                name="assistant",
                model_client=self.model_client,
                system_message=self._build_system_prompt(),
                tools=agent_tools,
                # ReAct 循环：持续执行 tool 直到模型返回文本（无 tool 调用）为止
                max_tool_iterations=10,      # 最多 10 轮 tool 调用，达到后强制进入 reflect
                reflect_on_tool_use=True,    # 工具调用后做一次推理，生成最终自然语言回复
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
    
    async def process_message(self, session_id: str, user_message: str) -> Dict:
        """
        处理用户消息并返回 agent 响应
        
        Args:
            session_id: 会话 ID，用于维护多轮对话
            user_message: 用户消息
            
        Returns:
            包含响应信息的字典，包括：
            - content: 最终响应文本
            - thoughts: 思考过程列表
            - tool_calls: 工具调用列表
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
            
            # 使用 agent 处理消息
            # 收集所有消息
            messages = []
            message_count = 0
            logger.info(f"[AGENT] Starting agent.run_stream for session {session_id}")
            
            try:
                async for message in agent.run_stream(task=user_message):
                    messages.append(message)
                    message_count += 1
                    msg_type = type(message).__name__
                    logger.info(f"[STREAM] Received message #{message_count}: {msg_type}")
                    
                    # 提取思考过程 (ThoughtEvent)
                    if msg_type == "ThoughtEvent":
                        if hasattr(message, 'content') and message.content:
                            result["thoughts"].append({
                                "content": message.content,
                                "source": getattr(message, 'source', 'assistant')
                            })
                            logger.info(f"[THOUGHT] Captured ThoughtEvent: {message.content[:100]}...")
                    
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
                        
                        if hasattr(message, 'results') and message.results:
                            for exec_result in message.results:
                                call_id = getattr(exec_result, 'call_id', '')
                                for tc in result["tool_calls"]:
                                    if tc["id"] == call_id:
                                        tc["result"] = getattr(exec_result, 'content', '')
                                        tc["is_error"] = getattr(exec_result, 'is_error', False)
                                        tc["status"] = "error" if tc["is_error"] else "completed"
                                        break
                        
                        logger.info(f"[TOOL_SUMMARY] Extracted from ToolCallSummaryMessage: {len(result['tool_calls'])} tool calls")
                    
                    # 检查是否有 thought 属性（某些版本的 autogen 可能会添加）
                    if hasattr(message, 'thought') and message.thought:
                        result["thoughts"].append({
                            "content": message.thought,
                            "source": getattr(message, 'source', 'assistant')
                        })
                        logger.info(f"[THOUGHT] Captured from message.thought: {message.thought[:100]}...")
            except Exception as stream_error:
                logger.error(f"[STREAM] Error in agent.run_stream: {str(stream_error)}", exc_info=True)
                raise
            
            logger.info(f"[STREAM] Stream completed, received {len(messages)} messages")
            logger.info(f"[STREAM] Collected {len(result['thoughts'])} thoughts, {len(result['tool_calls'])} tool calls")
            
            # 提取 assistant 的回复内容
            response_text = ""
            
            if messages:
                # 从后往前查找 assistant 的 TextMessage
                # 通常最后一条是 TaskResult，倒数第二条是 assistant 的回复
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
                    logger.error(f"[EXTRACT] Empty response extracted!")
                    msg_info = [f"{type(m).__name__}(source={getattr(m, 'source', 'N/A')})" for m in messages]
                    logger.error(f"[EXTRACT] All messages: {msg_info}")
                    response_text = "I apologize, but I couldn't generate a response."
                
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
