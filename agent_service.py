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

# 导入日程提醒工具
from tools.schedule_reminder import (
    create_schedule,
    list_schedules,
    delete_schedule,
    update_schedule,
    schedule_tools,
    TOOLS_AVAILABLE,
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


class MultiAgentService:
    """多 Agent 服务类，管理对话状态和 agent 交互"""
    
    def __init__(self):
        """初始化服务，创建 agent 和运行时"""
        # OpenRouter API 配置
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        
        if not self.api_key:
            raise ValueError("请设置 OPENROUTER_API_KEY 环境变量")
        
        self.model_name = os.getenv("MODEL_NAME", "moonshotai/kimi-k2.5")
        base_url = "https://openrouter.ai/api/v1"
        
        logger.info(f"Using OpenRouter API key: {self.api_key[:20]}...")
        logger.info(f"Using model: {self.model_name}")
        logger.info(f"Base URL: {base_url}")
        
        # 创建 AutoGen 客户端，使用 OpenRouter
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
        logger.info("OpenRouter client created successfully")
        
        # 存储每个会话的 agent 实例和对话历史
        self.session_agents: Dict[str, AssistantAgent] = {}
        self.conversation_history: Dict[str, List] = {}
    
    def get_or_create_agent(self, session_id: str) -> AssistantAgent:
        """获取或创建会话的 agent 实例"""
        if session_id not in self.session_agents:
            logger.info(f"[AGENT] Creating new agent for session {session_id}")
            
            # 根据 FunctionTool 是否可用选择工具列表
            # 如果 autogen_core.tools 可用，使用 FunctionTool 包装的工具
            # 否则直接使用原始函数（autogen-agentchat 支持 Callable 类型的工具）
            if TOOLS_AVAILABLE and schedule_tools:
                agent_tools = schedule_tools
                logger.info(f"[AGENT] Using FunctionTool wrapped tools: {len(agent_tools)} tools")
            else:
                # 直接使用原始函数作为工具
                agent_tools = [create_schedule, list_schedules, delete_schedule, update_schedule]
                logger.info(f"[AGENT] Using raw functions as tools: {len(agent_tools)} tools")
            
            self.session_agents[session_id] = AssistantAgent(
                name="assistant",
                model_client=self.model_client,
                system_message=f"""You are Kimi, a helpful AI assistant. You are using the {self.model_name} model.
You can help users with various tasks. 

你有以下工具可以使用：
1. create_schedule - 创建日程提醒。当用户需要设置日程、闹钟、提醒或计划活动时使用。
   参数：title(标题), datetime_str(时间，格式YYYY-MM-DD HH:MM), description(描述，可选), reminder_minutes(提前提醒分钟数，默认15), repeat(重复类型once/daily/weekly/monthly，默认once)
2. list_schedules - 查看日程列表。当用户想查看自己的日程安排时使用。
   参数：status(状态筛选all/active/completed，默认active), limit(数量限制，默认10)
3. delete_schedule - 删除日程。当用户想取消或删除某个日程时使用。
   参数：schedule_id(日程ID)
4. update_schedule - 更新日程。当用户想修改已有日程信息时使用。
   参数：schedule_id(日程ID), title(新标题，可选), datetime_str(新时间，可选), description(新描述，可选), reminder_minutes(新提醒时间，可选), status(新状态active/completed，可选)

When users mention scheduling, reminders, alarms, or planning activities, use the appropriate schedule tools.
日期时间格式为 YYYY-MM-DD HH:MM，例如 2024-03-15 14:30。
当前时间是 {datetime.now().strftime('%Y-%m-%d %H:%M')}。""",
                tools=agent_tools,  # 添加日程提醒工具
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
