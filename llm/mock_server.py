# mock_server.py
import asyncio, json, websockets, time

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
                    "units": {"34": {"hp": 50, "pos": [1,2]},
                              "105": {"hp": 40, "pos": [0,0]}}
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

