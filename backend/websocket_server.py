"""
WebSocket 服务器，提供多 agent 服务的 WebSocket 接口
"""
import asyncio
import json
import logging
from typing import Dict

import websockets
from websockets.server import WebSocketServerProtocol

from .agent_service import MultiAgentService

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 为 WebSocket 相关模块设置详细日志
logging.getLogger('websockets').setLevel(logging.WARNING)  # 减少 websockets 库的噪音


class WebSocketAgentServer:
    """WebSocket 服务器，处理客户端连接和消息"""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        """
        初始化 WebSocket 服务器
        
        Args:
            host: 服务器主机地址
            port: 服务器端口
        """
        self.host = host
        self.port = port
        try:
            logger.info("[INIT] Initializing MultiAgentService...")
            self.agent_service = MultiAgentService()
            logger.info("[INIT] MultiAgentService initialized successfully")
        except Exception as e:
            logger.error(f"[INIT] Failed to initialize MultiAgentService: {str(e)}", exc_info=True)
            raise
        self.connected_clients: Dict[str, WebSocketServerProtocol] = {}
    
    async def handle_client(self, websocket):
        """
        处理客户端连接
        
        Args:
            websocket: WebSocket 连接对象
            path: 连接路径
        """
        # 获取客户端信息
        try:
            remote_addr = websocket.remote_address
            client_id = f"{remote_addr[0] if remote_addr else 'unknown'}:{remote_addr[1] if remote_addr else 'unknown'}"
        except:
            client_id = "unknown"
        
        session_id = None
        
        try:
            logger.info(f"[CONNECTION] Client connected: {client_id}")
            try:
                logger.debug(f"[CONNECTION] WebSocket headers: {dict(websocket.request_headers)}")
            except:
                pass
            self.connected_clients[client_id] = websocket
            
            # 发送连接成功消息
            try:
                logger.debug(f"[CONNECTION] Preparing to send connection message to {client_id}")
                connection_msg = {
                    "type": "connection",
                    "status": "connected",
                    "message": "Connected to AutoGen Multi-Agent Service"
                }
                await self.send_message(websocket, connection_msg)
                logger.info(f"[CONNECTION] Connection message sent successfully to {client_id}")
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"[CONNECTION] Connection closed before sending message to {client_id}")
                return
            except Exception as send_err:
                logger.error(f"[CONNECTION] Failed to send connection message to {client_id}: {str(send_err)}", exc_info=True)
                # 不抛出异常，让连接继续
                try:
                    await websocket.close(code=1011, reason=f"Server error: {str(send_err)[:100]}")
                except:
                    pass
                return
            
            # 处理消息循环
            async for message in websocket:
                try:
                    # 解析 JSON 消息
                    logger.debug(f"[MESSAGE] Raw message from {client_id}: {message[:200]}...")
                    data = json.loads(message)
                    logger.info(f"[MESSAGE] Received from {client_id}: type={data.get('type')}, session_id={data.get('session_id', 'N/A')}")
                    logger.debug(f"[MESSAGE] Full message data: {json.dumps(data, ensure_ascii=False, indent=2)}")
                    
                    # 处理不同类型的消息
                    msg_type = data.get("type", "message")
                    
                    if msg_type == "message":
                        # 处理用户消息
                        user_message = data.get("content", "")
                        session_id = data.get("session_id", client_id)
                        
                        logger.info(f"[PROCESS] Processing message for session {session_id}, length: {len(user_message)} chars")
                        logger.debug(f"[PROCESS] Message content: {user_message[:100]}...")
                        
                        if not user_message:
                            logger.warning(f"[ERROR] Empty message from {client_id}")
                            await self.send_message(websocket, {
                                "type": "error",
                                "message": "Message content is required"
                            })
                            continue
                        
                        # 发送处理中状态
                        logger.debug(f"[STATUS] Sending processing status to {client_id}")
                        await self.send_message(websocket, {
                            "type": "status",
                            "status": "processing",
                            "message": "Processing your message..."
                        })
                        
                        # 处理消息并获取响应
                        try:
                            import time
                            start_time = time.time()
                            logger.info(f"[AGENT] Calling agent_service.process_message for session {session_id}")
                            response_data = await self.agent_service.process_message(
                                session_id, user_message
                            )
                            elapsed_time = time.time() - start_time
                            
                            # 响应数据现在是一个字典，包含 content, thoughts, tool_calls
                            response_content = response_data.get("content", "")
                            thoughts = response_data.get("thoughts", [])
                            tool_calls = response_data.get("tool_calls", [])
                            
                            logger.info(f"[AGENT] Agent response received in {elapsed_time:.2f}s")
                            logger.info(f"[AGENT] Content length: {len(response_content)} chars, thoughts: {len(thoughts)}, tool_calls: {len(tool_calls)}")
                            logger.debug(f"[AGENT] Response preview: {response_content[:200]}...")
                        except Exception as agent_error:
                            logger.error(f"[AGENT] Error processing message: {str(agent_error)}", exc_info=True)
                            await self.send_message(websocket, {
                                "type": "error",
                                "message": f"Agent processing error: {str(agent_error)}"
                            })
                            continue
                        
                        # 发送响应（包含思考过程和工具调用）
                        logger.debug(f"[RESPONSE] Sending response to {client_id}")
                        await self.send_message(websocket, {
                            "type": "response",
                            "content": response_content,
                            "thoughts": thoughts,
                            "tool_calls": tool_calls,
                            "session_id": session_id
                        })
                        logger.info(f"[RESPONSE] Response sent successfully to {client_id}")
                    
                    elif msg_type == "clear_history":
                        # 清除历史记录
                        session_id = data.get("session_id", client_id)
                        self.agent_service.clear_history(session_id)
                        await self.send_message(websocket, {
                            "type": "status",
                            "status": "success",
                            "message": f"History cleared for session {session_id}"
                        })
                    
                    elif msg_type == "ping":
                        # 心跳检测
                        await self.send_message(websocket, {
                            "type": "pong"
                        })
                    
                    else:
                        await self.send_message(websocket, {
                            "type": "error",
                            "message": f"Unknown message type: {msg_type}"
                        })
                
                except json.JSONDecodeError as json_err:
                    logger.error(f"[ERROR] JSON decode error from {client_id}: {str(json_err)}")
                    logger.debug(f"[ERROR] Invalid JSON content: {message[:500]}")
                    await self.send_message(websocket, {
                        "type": "error",
                        "message": f"Invalid JSON format: {str(json_err)}"
                    })
                except Exception as e:
                    logger.error(f"[ERROR] Unexpected error handling message from {client_id}: {str(e)}", exc_info=True)
                    await self.send_message(websocket, {
                        "type": "error",
                        "message": f"Error processing message: {str(e)}"
                    })
        
        except websockets.exceptions.ConnectionClosed as close_err:
            logger.info(f"[DISCONNECT] Client disconnected: {client_id}, code: {close_err.code}, reason: {close_err.reason}")
        except Exception as e:
            logger.error(f"[ERROR] Error in client handler for {client_id}: {str(e)}", exc_info=True)
            # 尝试关闭连接
            try:
                if websocket and websocket.open:
                    await websocket.close(code=1011, reason=f"Handler error: {str(e)[:100]}")
            except:
                pass
        finally:
            # 清理连接
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]
                logger.debug(f"[CLEANUP] Removed {client_id} from connected clients")
            logger.info(f"[CLEANUP] Client {client_id} cleaned up, remaining clients: {len(self.connected_clients)}")
    
    async def send_message(self, websocket: WebSocketServerProtocol, message: Dict):
        """
        发送消息到客户端
        
        Args:
            websocket: WebSocket 连接对象
            message: 要发送的消息字典
        """
        try:
            message_str = json.dumps(message, ensure_ascii=False)
            logger.debug(f"[SEND] Sending message type: {message.get('type')}, size: {len(message_str)} bytes")
            await websocket.send(message_str)
            logger.debug(f"[SEND] Message sent successfully")
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"[SEND] Connection closed while sending message")
        except Exception as e:
            logger.error(f"[SEND] Error sending message: {str(e)}", exc_info=True)
            raise
    
    async def start(self):
        """启动 WebSocket 服务器"""
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")
        async with websockets.serve(self.handle_client, self.host, self.port):
            logger.info(f"WebSocket server is running on ws://{self.host}:{self.port}")
            await asyncio.Future()  # 保持服务器运行


def main():
    """主函数，启动服务器"""
    server = WebSocketAgentServer(host="localhost", port=8765)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")


if __name__ == "__main__":
    main()
