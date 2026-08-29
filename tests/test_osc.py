"""Test OSC forwarding to VSeeFace via WebSocket."""
import asyncio
import websockets
import json
import sys

async def test_osc_forward():
    """Test OSC forwarding to VSeeFace."""
    try:
        async with websockets.connect(
            'ws://127.0.0.1:8000/ws/chat',
            ping_interval=30,
            ping_timeout=10,
            close_timeout=10
        ) as ws:
            # Send Joy emotion blendshape
            emotion_msg = json.dumps({
                'type': 'OSC',
                'address': '/VMC/Ext/Blend/Val',
                'args': ['Joy', 0.75]
            })
            await ws.send(emotion_msg)
            print('[TEST] Sent Joy=0.75 OSC message')
            
            # Send Apply
            apply_msg = json.dumps({
                'type': 'OSC',
                'address': '/VMC/Ext/Blend/Apply',
                'args': []
            })
            await ws.send(apply_msg)
            print('[TEST] Sent Apply OSC message')
            
            # Wait and listen for any response
            await asyncio.sleep(3)
            
            # Try to receive any messages (timeout after 2 seconds)
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                print(f'[TEST] Received: {msg[:200]}')
            except asyncio.TimeoutError:
                print('[TEST] No response received (timeout)')
            except websockets.exceptions.ConnectionClosed:
                print('[TEST] Connection closed by server')
            
            print('[TEST] Test complete - check VSeeFace for smile')
        return True
    except Exception as e:
        print(f'[TEST ERROR] {e}')
        return False

if __name__ == '__main__':
    result = asyncio.run(test_osc_forward())
    print(f'Test result: {"SUCCESS" if result else "FAILED"}')
    sys.exit(0 if result else 1)
