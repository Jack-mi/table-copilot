#!/bin/bash
# 检查 WebSocket 服务器状态

echo "=== WebSocket 服务器状态检查 ==="
echo ""

# 检查进程
echo "1. 检查进程:"
PID=$(lsof -ti:8765 2>/dev/null)
if [ -n "$PID" ]; then
    echo "   ✅ 进程运行中 (PID: $PID)"
    ps -p $PID -o pid,etime,command 2>/dev/null || echo "   ⚠️  进程信息获取失败"
else
    echo "   ❌ 没有进程在端口 8765 上运行"
fi

echo ""

# 检查端口
echo "2. 检查端口 8765:"
if lsof -ti:8765 >/dev/null 2>&1; then
    echo "   ✅ 端口 8765 已被占用"
    lsof -i:8765 | grep LISTEN || echo "   ⚠️  端口被占用但可能不在监听状态"
else
    echo "   ❌ 端口 8765 未被占用"
fi

echo ""

# 尝试连接测试
echo "3. 连接测试:"
cd "$(dirname "$0")"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    python3 -c "
import asyncio
import websockets
import sys
import os

# 禁用代理
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'

async def test():
    try:
        # 使用 open_timeout 而不是 timeout
        async with websockets.connect('ws://localhost:8765', open_timeout=2, ping_interval=None) as ws:
            print('   ✅ 连接成功')
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1)
                print(f'   ✅ 收到服务器消息: {msg[:50]}...')
            except asyncio.TimeoutError:
                print('   ⚠️  未收到服务器消息（超时）')
            except Exception as e:
                print(f'   ⚠️  接收消息时出错: {e}')
            return True
    except ConnectionRefusedError:
        print('   ❌ 连接被拒绝 - 服务器可能未运行')
        return False
    except asyncio.TimeoutError:
        print('   ❌ 连接超时 - 服务器可能无响应')
        return False
    except OSError as e:
        if 'Connection refused' in str(e):
            print('   ❌ 连接被拒绝')
        else:
            print(f'   ❌ 网络错误: {e}')
        return False
    except Exception as e:
        error_msg = str(e)
        if 'SOCKS proxy' in error_msg:
            print('   ⚠️  代理配置问题，但服务器可能正在运行')
            print('   💡 提示: 检查浏览器是否能连接（不受代理影响）')
        else:
            print(f'   ❌ 连接错误: {error_msg[:100]}')
        return False

result = asyncio.run(test())
sys.exit(0 if result else 1)
" 2>&1
else
    echo "   ⚠️  虚拟环境未找到，跳过连接测试"
fi

echo ""
echo "=== 检查完成 ==="
