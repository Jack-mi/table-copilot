"""
AutoGen Multi-Agent Service
提供多 agent 对话服务，支持多轮对话和工具调用
"""
import asyncio
import json
import logging
from typing import Dict, Optional, List
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
import os
from dotenv import load_dotenv

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


class MultiAgentService:
    """多 Agent 服务类，管理对话状态和 agent 交互"""
    
    def __init__(self):
        """初始化服务，创建 agent 和运行时"""
        # OpenRouter API 配置
        # 优先使用 OPENROUTER_API_KEY 环境变量，如果没有则使用默认的 OpenRouter API_KEY
        # 注意：不使用 OPENAI_API_KEY，因为它可能是其他服务的 key
        self.api_key = (
            os.getenv("OPENROUTER_API_KEY") or 
            "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"
        )
        logger.info(f"Using OpenRouter API key: {self.api_key[:30]}...")
        
        # OpenRouter 配置
        base_url = "https://openrouter.ai/api/v1"
        # OpenRouter 模型格式：provider/model-name
        openrouter_model = os.getenv("MODEL_NAME", "moonshotai/kimi-k2.5")  # OpenRouter 模型名
        
        logger.info(f"Using OpenRouter with model: {openrouter_model}")
        logger.info(f"Base URL: {base_url}")
        
        # 创建客户端（OpenRouter 兼容 OpenAI API 格式）
        from openai import OpenAI
        # 创建 OpenAI 客户端（支持 base_url）
        # OpenRouter 需要额外的 HTTP 头
        # 临时清除环境变量，确保使用我们指定的 API key
        old_openai_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            default_headers = {
                "HTTP-Referer": "https://github.com/microsoft/autogen",  # 可选，用于跟踪
                "X-Title": "AutoGen Multi-Agent Service"  # 可选，用于跟踪
            }
            openai_client = OpenAI(
                api_key=self.api_key,
                base_url=base_url,
                default_headers=default_headers
            )
            logger.info(f"Created OpenAI client with API key: {self.api_key[:30]}...")
            logger.info(f"Verified client API key: {openai_client.api_key[:30]}...")
        finally:
            # 恢复环境变量
            if old_openai_key:
                os.environ["OPENAI_API_KEY"] = old_openai_key
        
        # 创建 AutoGen 客户端
        # 使用标准模型名（gpt-4o-mini），然后通过替换客户端来使用 OpenRouter
        # 这样可以在请求时使用 OpenRouter 的模型名
        # 临时设置环境变量，确保使用正确的 API key
        old_openai_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = self.api_key
        try:
            self.model_client = OpenAIChatCompletionClient(
                model="gpt-4o-mini",  # 使用标准模型名，避免 model_info 问题
                api_key=self.api_key
            )
        finally:
            # 恢复原来的环境变量
            if old_openai_key:
                os.environ["OPENAI_API_KEY"] = old_openai_key
            elif "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]
        
        # 存储 OpenRouter 模型名
        self.openrouter_model = openrouter_model
        
        # 替换内部客户端以使用 OpenRouter（这样会使用正确的 base_url 和 headers）
        if hasattr(self.model_client, '_client'):
            # 在替换之前，保存原始的 openai_client.chat.completions.create 方法
            original_create_method = openai_client.chat.completions.create
            
            # 替换 _client
            self.model_client._client = openai_client
            logger.info("Set _client attribute to use OpenRouter")
            logger.info(f"OpenRouter client API key: {openai_client.api_key[:30]}...")
            
            # 创建包装函数，使用保存的原始方法
            # AutoGen 的 create 方法使用 asyncio.ensure_future，期望协程
            # 但 OpenAI 同步客户端返回同步结果，所以我们需要在线程池中执行
            async def wrapped_chat_create(*args, **kwargs):
                # 确保使用 OpenRouter 模型名
                if 'model' not in kwargs:
                    kwargs['model'] = self.openrouter_model
                elif kwargs.get('model') != self.openrouter_model:
                    kwargs['model'] = self.openrouter_model
                # 在线程池中执行同步调用
                import asyncio
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: original_create_method(*args, **kwargs)
                )
            
            # 替换方法
            self.model_client._client.chat.completions.create = wrapped_chat_create
            logger.info("Wrapped chat.completions.create to use OpenRouter model name and client")
        elif hasattr(self.model_client, 'client'):
            self.model_client.client = openai_client
            logger.info("Set client attribute to use OpenRouter")
        else:
            logger.warning("Could not find client attribute")
        
        # 存储每个会话的 agent 实例和对话历史
        self.session_agents: Dict[str, AssistantAgent] = {}
        self.conversation_history: Dict[str, List] = {}
    
    def get_or_create_agent(self, session_id: str) -> AssistantAgent:
        """获取或创建会话的 agent 实例"""
        if session_id not in self.session_agents:
            logger.info(f"[AGENT] Creating new agent for session {session_id}")
            self.session_agents[session_id] = AssistantAgent(
                name="assistant",
                model_client=self.model_client,
                system_message=f"You are Kimi, an AI assistant developed by Moonshot AI. You are using the {self.openrouter_model} model. Always identify yourself as Kimi when asked about your identity. You can help users with various tasks. When you need to use tools, you can call them appropriately.",
                tools=[],  # 暂时不添加工具，只跑通流程
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
    
    async def process_message(self, session_id: str, user_message: str) -> str:
        """
        处理用户消息并返回 agent 响应
        
        Args:
            session_id: 会话 ID，用于维护多轮对话
            user_message: 用户消息
            
        Returns:
            agent 的响应文本
        """
        import time
        start_time = time.time()
        
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
                    logger.debug(f"[STREAM] Received message #{message_count}: {type(message).__name__}")
                    if hasattr(message, 'content'):
                        logger.debug(f"[STREAM] Message content preview: {str(message.content)[:100]}...")
            except Exception as stream_error:
                logger.error(f"[STREAM] Error in agent.run_stream: {str(stream_error)}", exc_info=True)
                raise
            
            logger.info(f"[STREAM] Stream completed, received {len(messages)} messages")
            
            # 提取 assistant 的回复内容
            response_text = ""
            
            if messages:
                # 从后往前查找 assistant 的 TextMessage
                # 通常最后一条是 TaskResult，倒数第二条是 assistant 的回复
                assistant_message = None
                
                # 方法1：查找 source='assistant' 的 TextMessage
                for msg in reversed(messages):
                    # 检查是否是 TextMessage 且 source 是 assistant
                    if hasattr(msg, 'source') and msg.source == 'assistant':
                        if hasattr(msg, 'content'):
                            assistant_message = msg
                            logger.debug(f"[EXTRACT] Found assistant message with source='assistant'")
                            break
                
                # 方法2：如果没找到，查找包含 assistant 回复的 TextMessage（通常倒数第二条）
                if assistant_message is None and len(messages) >= 2:
                    # 从后往前查找，跳过 TaskResult
                    for msg in reversed(messages[:-1]):  # 排除最后一条（通常是 TaskResult）
                        if hasattr(msg, 'content') and hasattr(msg, 'source'):
                            if msg.source == 'assistant':
                                assistant_message = msg
                                logger.debug(f"[EXTRACT] Found assistant message (method 2)")
                                break
                
                # 方法3：如果还是没找到，尝试从 TaskResult 中提取
                if assistant_message is None:
                    last_message = messages[-1]
                    logger.debug(f"[EXTRACT] Last message is {type(last_message).__name__}, attempting to extract from TaskResult")
                    
                    # 检查是否是 TaskResult，包含 messages 属性
                    if hasattr(last_message, 'messages'):
                        # 从 messages 列表中查找 assistant 的回复
                        for msg in reversed(last_message.messages):
                            if hasattr(msg, 'source') and msg.source == 'assistant':
                                if hasattr(msg, 'content'):
                                    assistant_message = msg
                                    logger.debug(f"[EXTRACT] Found assistant message in TaskResult.messages")
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
                return response_text
            else:
                logger.warning(f"[ERROR] No messages received from agent for session {session_id}")
                return "I apologize, but I couldn't generate a response."
                
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[ERROR] Error processing message for session {session_id} after {elapsed_time:.2f}s: {str(e)}", exc_info=True)
            logger.error(f"[ERROR] Exception type: {type(e).__name__}")
            return f"Error: {str(e)}"
    
    def clear_history(self, session_id: str):
        """清除指定会话的历史记录和 agent"""
        if session_id in self.conversation_history:
            del self.conversation_history[session_id]
        if session_id in self.session_agents:
            del self.session_agents[session_id]
        logger.info(f"Cleared history and agent for session {session_id}")
