#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mock ECS Server (multi-client, faction-aware, frame-sync demo)

依赖:  pip install websockets
启动:  python mock_server.py
"""

import asyncio, json, itertools, time
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

HOST, PORT = "0.0.0.0", 8765

# ====== 全局状态 ======
TICK_RATE        = 2                   # demo 用 2 FPS; 实战改 30/60
TICK_INTERVAL    = 1 / TICK_RATE
NEXT_TICK        = 0
GAME_RUNNING     = asyncio.Event()     # 等到 A & B 都在线再 set()

# 会话表: sid -> {ws, faction, last_seen}
SESSIONS: dict[str, dict] = {}

# 权威战场状态 (示例)
GAME_STATE = {
    "units": {
        # id   hp   pos(x,y)   faction
        "34":  {"hp": 50, "pos": [100, 22], "faction": "A"},
        "105": {"hp": 40, "pos": [200, 25], "faction": "A"},
        "201": {"hp": 60, "pos": [65,  40], "faction": "B"},
        "205": {"hp": 70, "pos": [88,  55], "faction": "B"},
    }
}

# ====== 工具函数 ======
async def send_json(ws, obj):
    await ws.send(json.dumps(obj))

def split_units_by_faction(faction: str):
    friendly, enemy = {}, {}
    for uid, u in GAME_STATE["units"].items():
        (friendly if u["faction"] == faction else enemy)[uid] = u
    return friendly, enemy

# ====== 观测推送 ======
async def push_observation(session_id: str):
    session = SESSIONS[session_id]
    faction = session["faction"]
    ws      = session["ws"]

    friendly, enemy = split_units_by_faction(faction)

    obs = {
        "type": "observation",
        "payload": {
            "turn": NEXT_TICK,
            "friendly_unit_ids": friendly,
            "enemy_unit_ids": enemy
        }
    }
    await send_json(ws, obs)

# ====== 消息处理器 ======
async def on_register(ws, msg):
    sid      = msg["session_id"]
    faction  = msg["faction"]             # "A" 或 "B"

    # 覆盖或新增 (断线重连也 OK)
    SESSIONS[sid] = {"ws": ws, "faction": faction, "last_seen": time.time()}
    print(f"✔ 注册 sid={sid} 阵营={faction}  (当前在线 {len(SESSIONS)})")

    # 开局匹配: 同时存在 A 与 B 即可开始
    factions_online = {s["faction"] for s in SESSIONS.values()}
    if factions_online == {"A", "B"} and not GAME_RUNNING.is_set():
        print("⚑ A & B 就位，开始游戏!")
        GAME_RUNNING.set()

    await push_observation(sid)

async def on_decision(ws, msg):
    sid      = msg["session_id"]
    actions  = msg["payload"]["actions"]
    faction  = SESSIONS[sid]["faction"]

    # 应用动作 (仅演示 move，坐标直接写入; 真游戏还需合法性判定)
    for uid, act in actions.items():
        unit = GAME_STATE["units"].get(uid)
        if not unit or unit["faction"] != faction:
            continue  # 非己方单位，忽略
        if act.get("action") == "move":
            unit["pos"] = act.get("args", unit["pos"])
        if act.get("action") == "attack":
            defender_id = act.get("args")
            defender = GAME_STATE["units"].get(defender_id)
            if defender:
                defender["hp"] -= 1
                print(f"✓ {uid} 攻击 {defender_id} 成功")
                
    print(f"✓ 已应用 {sid} 动作: {actions}")

async def on_request_observation(ws, msg):
    await push_observation(msg["session_id"])

async def on_heartbeat(ws, msg):
    sid = msg["session_id"]
    if sid in SESSIONS:
        SESSIONS[sid]["last_seen"] = time.time()

# ====== 分派表 ======
DISPATCH = {
    "register":             on_register,
    "decision":             on_decision,
    "request_observation":  on_request_observation,
    "heartbeat":            on_heartbeat,
}

HEARTBEAT_TIMEOUT = 30      # 秒；超过视为掉线

# ====== 帧循环 ======
async def game_loop():
    global NEXT_TICK
    while True:
        await GAME_RUNNING.wait()       # 等匹配完成
        NEXT_TICK += 1
        # 1) 推送观测给所有在线会话
        for sid in list(SESSIONS):
            try:
                await push_observation(sid)
            except Exception as exc:
                print("✖ 会话掉线:", sid, exc)
                SESSIONS.pop(sid, None)
        # 2) 掉线检测
        now = time.time()
        for sid in list(SESSIONS):
            if now - SESSIONS[sid]["last_seen"] > HEARTBEAT_TIMEOUT:
                print("⌛ 心跳超时移除", sid)
                SESSIONS.pop(sid, None)
        # 3) 若阵营不足则暂停游戏
        if {s["faction"] for s in SESSIONS.values()} != {"A", "B"}:
            print("⏸ 阵营不足，暂停等待重连…")
            GAME_RUNNING.clear()
        await asyncio.sleep(TICK_INTERVAL)

# ====== 顶层连接处理 ======
async def handler(ws):
    print("★ Client connected")
    try:
        async for raw in ws:
            msg = json.loads(raw)
            mtype = msg.get("type")
            fn    = DISPATCH.get(mtype)
            if fn:
                await fn(ws, msg)
            else:
                print("⚠ 未知消息类型:", mtype)
    except (ConnectionClosedOK, ConnectionClosedError):
        pass  # 客户端主动关闭
    finally:
        # 清理 sessions 中已关闭的 websocket
        for sid, info in list(SESSIONS.items()):
            if info["ws"] is ws:
                print("➖ 客户端断开:", sid)
                SESSIONS.pop(sid, None)

# ====== 入口 ======
async def main():
    async with websockets.serve(handler, HOST, PORT):
        print(f"Mock ECS listening at ws://{HOST}:{PORT}/ws")
        await game_loop()               # 永不返回

if __name__ == "__main__":
    asyncio.run(main())
