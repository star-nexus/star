
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 分布式客户端（新版，兼容多会话/阵营 mock_server.py）

功能：
1. 通过 WebSocket 与 ECS 服务器建立长连，完成注册 + 心跳
2. 按服务器推送的 observation 构造 prompt 调用 OpenAI-兼容 LLM
3. 解析 LLM JSON 决策，仅提交己方 unit 的动作
4. 支持断线自动重连、日志 DEBUG 输出
"""
from __future__ import annotations
import os, json, time, asyncio, logging, uuid, yaml
from pathlib import Path

import websockets
from dotenv import load_dotenv
from openai import AsyncOpenAI

# ────────────────────────────────── 环境配置 ──────────────────────────────────
load_dotenv()

WS_URL          = os.getenv("WS_URL", "ws://localhost:8765/ws")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")            # 必填
OPENAI_MODEL    = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo-0125")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")

HEARTBEAT_SEC   = int(os.getenv("HEARTBEAT_SEC", 15))
SESSION_ID      = os.getenv("SESSION_ID") or f"client-{uuid.uuid4().hex[:8]}"
FACTION         = os.getenv("FACTION", "A")              # "A" 或 "B"

# OpenAI 客户端
client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

# 日志设置
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("LLMClient")
if os.getenv("LOGLEVEL") == "DEBUG":
    log.setLevel(logging.DEBUG)

# ─────────────────────────────── Prompt 模板加载 ──────────────────────────────
TEMPLATE_DIR   = Path(__file__).parent / "templates"
DECISION_TMPL  = yaml.safe_load((TEMPLATE_DIR / "decision_prompt_en.yaml").read_text())

def build_prompt(observation: dict) -> list[dict]:
    """把 observation 填充进模板；异常时返回空动作提示"""
    try:
        situation_json = json.dumps(observation, ensure_ascii=False, indent=2)
        user_content   = DECISION_TMPL["prompt"].replace("{situation}", situation_json)
    except Exception as exc:
        log.exception("⚠️  build_prompt 失败，fallback 空动作: %s", exc)
        user_content = ("The observation cannot be parsed.\n"
                        "Return an empty JSON object {}.")
    return [
        {"role": "system", "content": DECISION_TMPL.get("system", "You are an AI commander.")},
        {"role": "user",   "content": user_content},
    ]

# ──────────────────────────────── 主客户端类 ────────────────────────────────
class LLMClient:
    def __init__(self, ws_url: str):
        self.ws_url     = ws_url
        self.session_id = SESSION_ID
        self.faction    = FACTION

    # 顶层循环：掉线→重连
    async def start(self):
        while True:
            try:
                async with websockets.connect(self.ws_url, ping_interval=None) as ws:
                    log.info("✔ 已连接 WebSocket")
                    await self._register(ws)
                    await asyncio.gather(self._heartbeat(ws), self._listen(ws))
            except Exception as e:
                log.warning("⚠ WebSocket 断开/错误 %s，3 秒后重连…", e)
                await asyncio.sleep(3)

    # ──────────── 服务端交互 ────────────
    async def _register(self, ws):
        msg = {
            "type":       "register",
            "session_id": self.session_id,
            "faction":    self.faction,
            "timestamp":  time.time(),
        }
        await ws.send(json.dumps(msg))
        log.info("→ 发送 register(%s, faction=%s)", self.session_id, self.faction)

    async def _heartbeat(self, ws):
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_SEC)
                hb = {"type": "heartbeat", "session_id": self.session_id,
                      "timestamp": time.time()}
                await ws.send(json.dumps(hb))
            except Exception:
                break   # 外层负责重连

    async def _listen(self, ws):
        async for raw in ws:
            msg = json.loads(raw)
            mtype = msg.get("type")
            if mtype == "observation":
                decision_payload = await self._handle_observation(msg["payload"])
                decision = {
                    "type": "decision",
                    "session_id": self.session_id,
                    "timestamp":  time.time(),
                    "payload":   decision_payload,
                }
                await ws.send(json.dumps(decision))
                log.info("↑ 已回传 decision (turn=%s)", msg["payload"].get("turn"))
            elif mtype == "pause":
                log.info("⏸ 游戏暂停 - 等待对手或重连…")
            # 其他类型可在此扩展

    # ──────────── 调用 LLM ────────────
    async def _handle_observation(self, payload: dict) -> dict:
        prompt = build_prompt(payload)
        log.debug("🛈 Prompt to LLM:\n%s", prompt)
        try:
            completion = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=prompt,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content.strip()
            log.debug("🛈 LLM raw response: %s", content)
            actions = json.loads(content)
        except Exception as e:
            log.error("LLM 调用/解析失败：%s", e)
            actions = {}
        return {"actions": actions}

# ──────────────────────────────── 程序入口 ────────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(LLMClient(WS_URL).start())
    except KeyboardInterrupt:
        log.info("用户中断，客户端退出。")
