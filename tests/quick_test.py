#!/usr/bin/env python3
"""
快速测试 WebSocket 服务的脚本
用法: python3 quick_test.py
"""
import asyncio
import json
import websockets
import sys


async def test_websocket():
    import os
    # 禁用代理
    os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
    os.environ['no_proxy'] = 'localhost,127.0.0.1'
    
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri, ping_interval=None) as websocket:
            print("✅ 连接成功!")
            
            # 接收连接确认消息
            response = await websocket.recv()
            print(f"📨 服务器消息: {response}")
            
            # 发送测试消息
            test_message = {
                "type": "message",
                "content": "你好，请用一句话介绍你自己",
                "session_id": "curl_test"
            }
            
            print(f"\n📤 发送消息: {json.dumps(test_message, ensure_ascii=False)}")
            await websocket.send(json.dumps(test_message, ensure_ascii=False))
            
            # 接收状态消息
            status = await websocket.recv()
            status_data = json.loads(status)
            print(f"⏳ 状态: {status_data.get('message', '')}")
            
            # 持续接收，直到拿到最终的 response 消息
            final_response = None
            while True:
                raw = await websocket.recv()
                data = json.loads(raw)
                msg_type = data.get("type")
                if msg_type == "response":
                    final_response = data
                    break
                # 对于流式事件（thought/tool_call 等），仅打印调试信息
                print(f"📡 流式事件: {msg_type} -> {raw}")
            
            if final_response:
                print(f"\n✅ 响应成功!")
                print(f"💬 内容: {final_response.get('content', '')}")
                
    except ConnectionRefusedError:
        print("❌ 连接失败: 服务器未启动，请先运行 python3 websocket_server.py")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_websocket())
