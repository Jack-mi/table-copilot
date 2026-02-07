"""
测试客户端，用于测试 WebSocket 服务器
"""
import asyncio
import json
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_websocket_client():
    """测试 WebSocket 客户端"""
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info(f"Connected to {uri}")
            
            # 接收连接确认消息
            response = await websocket.recv()
            logger.info(f"Server response: {response}")
            
            # 测试多轮对话
            session_id = "test_session_001"
            test_messages = [
                "Hello, how are you?",
                "What is 2+2?",
                "Can you tell me a joke?",
            ]
            
            for i, message in enumerate(test_messages, 1):
                logger.info(f"\n--- Round {i} ---")
                logger.info(f"Sending: {message}")
                
                # 发送消息
                await websocket.send(json.dumps({
                    "type": "message",
                    "content": message,
                    "session_id": session_id
                }))
                
                # 接收状态消息
                status_response = await websocket.recv()
                logger.info(f"Status: {status_response}")
                
                # 持续接收，直到拿到最终的 response 消息
                final_response = None
                while True:
                    raw = await websocket.recv()
                    data = json.loads(raw)
                    msg_type = data.get("type")
                    if msg_type == "response":
                        final_response = data
                        break
                    logger.info(f"Stream event: {raw}")
                
                if final_response:
                    logger.info(f"Response type: {final_response.get('type')}")
                    logger.info(f"Response content: {final_response.get('content', '')[:200]}")
            
            # 测试清除历史
            logger.info("\n--- Clearing History ---")
            await websocket.send(json.dumps({
                "type": "clear_history",
                "session_id": session_id
            }))
            response = await websocket.recv()
            logger.info(f"Clear history response: {response}")
            
            # 测试心跳
            logger.info("\n--- Testing Ping ---")
            await websocket.send(json.dumps({"type": "ping"}))
            response = await websocket.recv()
            logger.info(f"Pong response: {response}")
            
    except websockets.exceptions.ConnectionRefused:
        logger.error("Connection refused. Make sure the server is running.")
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_websocket_client())
