#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 分布式客户端 (WebSocket + ChatGPT API)

1. 连接远程 ECS WebSocket 服务端，完成注册 & 心跳
2. 收到 observation 后构造 prompt 调用 OpenAI ChatCompletion
3. 解析模型返回的 JSON 动作并回发 decision
"""
import os, json, time, asyncio, logging, uuid, yaml
import websockets
# import openai
from pathlib import Path
from dotenv import load_dotenv

from openai import AsyncOpenAI

load_dotenv()  # 读取 .env

# ----------------- 基础配置 -----------------
WS_URL         = os.getenv("WS_URL", "ws://localhost:8765/ws")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
HEARTBEAT_SEC  = int(os.getenv("HEARTBEAT_SEC", 30))
SESSION_ID     = os.getenv("SESSION_ID") or f"client-{uuid.uuid4().hex[:8]}"

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("LLMClient")
log.setLevel(logging.DEBUG)

# ----------------- Prompt 构造 -----------------
TEMPLATE_DIR   = Path(__file__).parent / "templates"
DECISION_TMPL  = yaml.safe_load((TEMPLATE_DIR/"decision_prompt_en.yaml").read_text())

def build_prompt(observation: dict) -> list[dict]:
    """Robust prompt builder with graceful fallback."""
    try:
        situation_json = json.dumps(observation, ensure_ascii=False, indent=2)

        # **直接替换，不再触发占位符解析**
        user_content = DECISION_TMPL["prompt"].replace("{situation}", situation_json)

    except Exception as exc:
        log.exception("⚠️  Failed to build prompt, falling back to empty-action prompt: %s", exc)
        user_content = (
            "The current observation could not be parsed.\n"
            "Output an empty JSON object (`{}`) so that the game can continue."
        )

    return [
        {"role": "system", "content": DECISION_TMPL.get("system", "You are an AI commander.")},
        {"role": "user",   "content": user_content},
    ]

# ----------------- 核心异步客户端 -----------------
class LLMClient:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.session_id = SESSION_ID

    async def start(self):
        """顶层循环：掉线自动重连"""
        while True:
            try:
                async with websockets.connect(self.ws_url, ping_interval=None) as ws:
                    log.info("✔  已连接 WebSocket")
                    await self._register(ws)
                    # 并发执行心跳与消息监听
                    await asyncio.gather(self._heartbeat(ws), self._listen(ws))
            except Exception as e:
                log.warning(f"⚠  WebSocket 断开或出错：{e}，3 秒后重连...")
                await asyncio.sleep(3)

    # ---------- 与 ECS 服务端交互 ----------
    async def _register(self, ws):
        msg = {"type": "register", "session_id": self.session_id, "timestamp": time.time()}
        await ws.send(json.dumps(msg))
        log.info(f"→ 已发送 register({self.session_id})")

    async def _heartbeat(self, ws):
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_SEC)
                hb = {"type": "heartbeat", "session_id": self.session_id, "timestamp": time.time()}
                await ws.send(json.dumps(hb))
            except Exception:
                break  # 由外层循环重连

    async def _listen(self, ws):
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") == "observation":
                decision_payload = await self._handle_observation(msg["payload"])
                decision = {
                    "type": "decision",
                    "session_id": self.session_id,
                    "timestamp": time.time(),
                    "payload": decision_payload,
                }
                await ws.send(json.dumps(decision))
                log.info("↑ 已回传 decision")

    # ---------- 调用 LLM ----------
    async def _handle_observation(self, payload: dict) -> dict:
        prompt = build_prompt(payload)
        log.debug("🛈 Prompt sent to LLM:\n%s", prompt)
        try:
            completion = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=prompt,
                temperature=0.2,
                response_format={"type": "json_object"},  # 推荐要求模型输出 JSON
            )
            log.debug("🛈 Completion raw object: %s", completion)
            content = completion.choices[0].message.content.strip()
            log.debug("🛈 Raw LLM response: %s", content)
            actions = json.loads(content)  # 模型需保证输出的是符合协议的 JSON
        except Exception as e:
            log.error(f"模型调用或解析失败：{e}")
            actions = {}  # 兜底：无动作
        return {"actions": actions}

# ----------------- 入口 -----------------
if __name__ == "__main__":
    asyncio.run(LLMClient(WS_URL).start())

