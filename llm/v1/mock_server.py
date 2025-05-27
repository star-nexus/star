# mock_server.py
import asyncio, json, websockets, time

# 当前 handler 每个连接独立执行；你可以在 obs 里放 session_id 来区分，或让不同客户端收到不同战场。
async def handler(ws):
    print("★ Client connected")
    async for raw in ws:
        msg = json.loads(raw)
        print("⇐", msg)
        # 注册完立刻推送一份假 observation
        if msg["type"] == "register":
            obs = {
                "type": "observation",
                "payload": {
                    "turn": 1,
                    "friendly_unit_ids": {
                        "34": {"hp": 50, "pos": [100, 22]},
                        "105": {"hp": 40, "pos": [200, 25]}
                    },
                    "enemy_unit_ids": {
                        "201": {"hp": 60, "pos": [65, 40]},
                        "205": {"hp": 70, "pos": [88, 55]}
                    }
                }
            }
            await ws.send(json.dumps(obs))
        elif msg["type"] == "decision":
            print("✔ 收到 LLM 决策，关服退出")
            await ws.close()

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("Mock ECS listening at ws://localhost:8765/ws")
        while True:
            await asyncio.sleep(3600)

asyncio.run(main())

