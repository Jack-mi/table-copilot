#!/usr/bin/env python3
"""
检查 WebSocket 服务器是否运行
"""
import asyncio
import websockets
import sys


async def check_server():
    uri = "ws://localhost:8765"
    try:
        async with websockets.connect(uri, open_timeout=2) as ws:
            print("✅ WebSocket 服务器正在运行")
            # 接收连接消息
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1)
                print(f"   收到服务器消息: {msg[:100]}")
            except:
                pass
            return True
    except ConnectionRefusedError:
        print("❌ WebSocket 服务器未运行 (连接被拒绝)")
        print("   请运行: scripts/start_server.sh  （或 python3 -m backend.websocket_server）")
        return False
    except asyncio.TimeoutError:
        print("❌ 连接超时")
        return False
    except Exception as e:
        print(f"❌ 连接错误: {str(e)}")
        return False


if __name__ == "__main__":
    result = asyncio.run(check_server())
    sys.exit(0 if result else 1)
