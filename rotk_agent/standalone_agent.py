import asyncio
import argparse
from contextvars import ContextVar
import os
import sys
import json
import httpx
import toml
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable, Union

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from protocol import AgentClient

# 配置 rich 库
from rich.console import Console
from rich import print_json

console = Console()

rule = """# 游戏核心规则

## 1. 游戏目标
你是 **魏 (wei)** 阵营的指挥官。你的目标是运用策略，指挥你的单位，消灭所有 **蜀 (shu)** 阵营的敌方单位以获得胜利。

## 2. 阵营与游戏模式
- **阵营**: 游戏中有两个对立阵营：**魏 (wei)** 和 **蜀 (shu)**。
- **即时制**: 游戏按即时制进行。双方可以同时操作单位，你需要快速反应。

## 3. 地图与坐标系
- **地图网格**: 游戏地图由六边形格子构成，大小约为 15x15。
- **坐标系统**:
    - 使用 (列, 行) 即 `(col, row)` 坐标系。
    - 地图中心为 `(col: 0, row: 0)`。
    - `col` 轴: **向右为正方向** (值增大)，向左为负方向 (值减小)。
    - `row` 轴: **向下为正方向** (值增大)，向上为负方向 (值减小)。
- **出生点**:
    - **蜀 (shu)** (敌方): 出生在地图 **左上角**，坐标值较小 (如 `col` 和 `row` 均为负数)。
    - **魏 (wei)** (我方): 出生在地图 **右下角**，坐标值较大 (如 `col` 和 `row` 均为正数)。

## 4. 行动机制：通过 `perform_action` 工具
- **核心工具**: 游戏中的所有单位动作（如移动和攻击）都**必须**通过调用 `perform_action` 工具来执行。你不能直接调用 `move` 或 `attack`。

- **工具用法**: `perform_action` 工具接收两个参数：
    1.  `action`: 一个字符串，指定要执行的动作名称 (例如: `"move"`, `"attack"`, `"faction_state"`, `"observation"`, `"end_turn"`)。
    2.  `params`: 一个JSON对象（字典），包含该动作所需的所有参数 (例如: `{"unit_id": 123, "target_position": {"col": 1, "row": 2}}`)。

- **严禁臆造 (No Fabrication)**:
    - 不能凭空编造或复用示例中的 `unit_id`、`target_id`、坐标或任何战场信息。
    - 在未通过工具获取真实数据前，不得假设任何单位的ID、位置、可视范围或敌人位置。
    - 示例中的ID仅为占位说明，绝不能直接使用。

- **前置检查清单 (必须遵循，按顺序执行)**:
    1.  调用 `perform_action(action="faction_state", params={"faction": "wei"})` 获取我方全部单位ID与状态。
    2.  调用 `perform_action(action="faction_state", params={"faction": "shu"})` 获取敌方单位信息（若可见）。
    3.  对每个准备操作的我方单位，调用 `perform_action(action="observation", params={"unit_id": <WEI_UNIT_ID>, "observation_level": "basic"})` 获取该单位可见环境与附近可攻击/可移动的目标。
    4.  在确认单位的 `action_points` 足够、目标在视野和/或攻击/移动范围内后，才可执行后续动作。

- **使用示例（仅作格式参考，不要使用其中的数字）**:
    - 移动单位：
      `perform_action(action="move", params={"unit_id": <WEI_UNIT_ID>, "target_position": {"col": <COL>, "row": <ROW>}})`
    - 攻击敌人：
      `perform_action(action="attack", params={"unit_id": <WEI_UNIT_ID>, "target_id": <SHU_UNIT_ID>})`

- **行动点 (AP)**: 执行 `perform_action` 会消耗对应单位的行动点 (AP)。AP会随时间恢复。行动前，务必通过上述前置检查确认AP充足。

## 5. 推荐操作流程 (OODA Loop)
游戏是即时进行的，建议你遵循“观察-判断-决策-行动”的循环，快速响应战场变化：
1.  **观察 (Observe)**: 先执行前置检查清单，持续使用 `available_actions` 与 `faction_state` / `observation` 获取最新战况。
2.  **判断 (Orient)**: 基于最新状态确定威胁与机会，选择要操作的单位和目标。
3.  **决策 (Decide)**: 规划本回合要执行的具体动作及顺序（移动→攻击或先攻击→再移动，视AP与地形而定）。
4.  **行动 (Act)**: 通过 `perform_action` 执行动作，严格按参数格式传入 `action` 与 `params`。
5.  **评估 (Assess)**: 检查动作返回结果；若失败，立即回到观察阶段查找原因（ID错误、范围不足、AP不足等）。必要时调用 `end_turn` 结束回合。
"""

@dataclass
class LLMConfig:
    """LLM 配置类"""
    provider: str  # "openai", "deepseek", "infinigence"
    model_id: str
    api_key: str
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None


@dataclass
class ToolDefinition:
    """工具定义类"""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable


@dataclass
class Message:
    """消息类"""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class LLMClient:
    """独立的 LLM 客户端，直接调用各种 LLM API"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = httpx.AsyncClient()
        
        # 设置不同提供商的 base_url
        if config.provider == "openai":
            self.base_url = config.base_url or "https://api.openai.com/v1"
        elif config.provider == "deepseek":
            self.base_url = "https://api.deepseek.com/v1"
        elif config.provider == "infinigence":
            self.base_url = "https://cloud.infini-ai.com/maas/v1"
        elif config.provider == "vllm":
            # vLLM 默认在 http://localhost:8000 启动 OpenAI 兼容服务
            self.base_url = config.base_url or "http://172.16.75.202:10000/v1"
        else:
            self.base_url = config.base_url or "https://api.openai.com/v1"

        print("=======================================")
        print(self.config)
        print("=======================================")

    async def chat_completion(
        self, 
        messages: List[Message], 
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """发送聊天完成请求"""
        
        # 转换消息格式
        formatted_messages = []
        for msg in messages:
            message_dict = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                message_dict["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                message_dict["tool_call_id"] = msg.tool_call_id
            formatted_messages.append(message_dict)
        
        # 构建请求payload
        payload = {
            "model": self.config.model_id,
            "messages": formatted_messages,
            "temperature": self.config.temperature,
        }
        
        if self.config.max_tokens:
            payload["max_tokens"] = self.config.max_tokens
            
        # 添加工具定义
        if tools:
            payload["tools"] = self._format_tools(tools)
            
        # 添加额外参数
        payload.update(kwargs)
        
        # 设置请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        
        console.print("LLM client request payload start", style="purple")
        print_json(data=payload, indent=2, ensure_ascii=False)
        console.print("LLM client request payload end", style="purple")

        # 发送请求
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0
        )
        
        if response.status_code != 200:
            raise Exception(f"LLM API 错误: {response.status_code} - {response.text}")
        console.print("LLM client response status code", style="purple")
        console.print(response.status_code, style="purple")
        console.print("LLM client response json", style="purple")
        print_json(data=response.json(), indent=2, ensure_ascii=False)
        console.print("LLM client response end", style="purple")
        return response.json()
    
    def _format_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """格式化工具定义为 OpenAI 格式"""
        formatted_tools = []
        for tool in tools:
            formatted_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        return formatted_tools
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


class ToolManager:
    """工具管理器"""
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
    
    def register_tool(self, tool: ToolDefinition):
        """注册工具"""
        self.tools[tool.name] = tool
    
    def get_tool_definitions(self) -> List[ToolDefinition]:
        """获取所有工具定义"""
        return list(self.tools.values())
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """执行工具"""
        if tool_name not in self.tools:
            raise ValueError(f"工具 {tool_name} 不存在")
        
        tool = self.tools[tool_name]
        try:
            # 如果是异步函数
            if asyncio.iscoroutinefunction(tool.function):
                return await tool.function(**arguments)
            else:
                return tool.function(**arguments)
        except Exception as e:
            return {"error": f"工具执行错误: {str(e)}"}


class StandaloneChatAgent:
    """独立的聊天代理"""
    
    def __init__(self, llm_config: LLMConfig):
        self.llm_client = LLMClient(llm_config)
        self.tool_manager = ToolManager()
        self.conversation_history: List[Message] = []
        self.max_iterations = 100  # 防止无限循环
        
    def register_tool(self, name: str, function: Callable, description: str, parameters: Dict[str, Any]):
        """注册工具"""
        tool = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            function=function
        )
        self.tool_manager.register_tool(tool)
    
    async def chat(self, task: str, max_iterations: Optional[int] = None) -> Dict[str, Any]:
        """主要的聊天循环"""
        if max_iterations:
            self.max_iterations = max_iterations
            
        # 初始化对话
        self.conversation_history = [
            Message(role="user", content=task)
        ]
        
        iterations = 0
        while iterations < self.max_iterations:
            iterations += 1
            
            try:
                # 获取 LLM 响应
                response = await self.llm_client.chat_completion(
                    messages=self.conversation_history,
                    tools=self.tool_manager.get_tool_definitions()
                )
                
                choice = response["choices"][0]
                message = choice["message"]
                finish_reason = choice["finish_reason"]
                
                console.print(f"╭─────────────────────────────────────────────────────── Tool call response ────────────────────────────────────────────────────────╮", style="yellow")
                console.print(f"│ {json.dumps(choice, indent=2, ensure_ascii=False)}", style="yellow", highlight=False)
                console.print(f"╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯", style="yellow")
                
                # 将助手响应添加到历史
                assistant_message = Message(
                    role="assistant",
                    content=message.get("content", ""),
                    tool_calls=message.get("tool_calls")
                )
                self.conversation_history.append(assistant_message)
                
                # 检查是否需要工具调用
                if finish_reason == "tool_calls" and message.get("tool_calls"):
                    await self._handle_tool_calls(message["tool_calls"])
                elif finish_reason == "stop":
                    # 对话完成
                    return {
                        "success": True,
                        "response": message.get("content", ""),
                        "iterations": iterations,
                        "finish_reason": finish_reason
                    }
                else:
                    # 其他完成原因
                    return {
                        "success": True,
                        "response": message.get("content", ""),
                        "iterations": iterations,
                        "finish_reason": finish_reason
                    }
                    
            except Exception as e:
                console.print(f"聊天过程中发生错误: {e}", style="red")
                return {
                    "success": False,
                    "error": str(e),
                    "iterations": iterations
                }
        
        # 达到最大迭代次数
        return {
            "success": False,
            "error": "达到最大迭代次数",
            "iterations": iterations
        }
    
    async def _handle_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        """处理工具调用"""
        for tool_call in tool_calls:
            tool_call_id = tool_call["id"]
            function_name = tool_call["function"]["name"]
            arguments_str = tool_call["function"]["arguments"]
            
            console.print(f"╭──────────────────────────────────────── Executing tool '{function_name}' with arguments ────────────────────────────────────────╮", style="green")
            console.print(f"│ {arguments_str}", style="green", highlight=False)
            console.print(f"╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯", style="green")
            
            try:
                # 解析参数
                arguments = json.loads(arguments_str) if arguments_str else {}
                
                # LLM有时会生成双重编码的JSON，特别是对于嵌套的'params'。
                # 在这里增加一层健壮性检查。
                if 'params' in arguments and isinstance(arguments['params'], str):
                    console.print("⚠️ 'params' 是一个字符串，尝试再次解码...", style="yellow")
                    try:
                        arguments['params'] = json.loads(arguments['params'])
                    except json.JSONDecodeError as e:
                        # 如果解码失败，说明LLM生成的JSON格式不正确。
                        # 这是无法恢复的错误，我们应该抛出异常，让上层捕获并通知LLM。
                        raise ValueError(f"LLM为'params'生成了无效的JSON字符串: {arguments['params']}. 错误: {e}")
                
                # 执行工具
                result = await self.tool_manager.execute_tool(function_name, arguments)
                
                console.print("Tool result", style="green")
                console.print(json.dumps(result, indent=2, ensure_ascii=False), style="green", highlight=False)
                
                # 将工具结果添加到对话历史
                tool_message = Message(
                    role="tool",
                    content=json.dumps(result, ensure_ascii=False),
                    tool_call_id=tool_call_id
                )
                self.conversation_history.append(tool_message)
                
            except Exception as e:
                console.print(f"工具执行错误: {e}", style="red")
                # 添加错误信息到对话历史
                error_message = Message(
                    role="tool",
                    content=json.dumps({"error": str(e)}, ensure_ascii=False),
                    tool_call_id=tool_call_id
                )
                self.conversation_history.append(error_message)
    
    async def stop(self):
        """停止代理"""
        await self.llm_client.close()


def load_config(config_path: str = ".configs.toml") -> LLMConfig:
    """从配置文件加载 LLM 配置"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    config = toml.load(config_path)
    default_config = config.get("default", {})
    model_id = default_config.get("model_id", "deepseek-chat")
    
    # 根据模型ID推断提供商
    if "claude" in model_id:
        provider = "infinigence"  # 根据观察，claude模型通过infinigence提供
        provider_config = config.get("infinigence", {})
    elif "deepseek" in model_id:
        provider = "deepseek"
        provider_config = config.get("deepseek", {})
    elif "gpt" in model_id or "openai" in model_id:
        provider = "openai"
        provider_config = config.get("openai", {})
    elif model_id.startswith("vllm:") or config.get("vllm", {}).get("enabled"):
        # vLLM 支持：model_id 以 "vllm:" 开头或配置中启用了 vllm
        provider = "vllm"
        provider_config = config.get("vllm", {})
        # 如果model_id以vllm:开头，移除前缀作为实际的模型名
        if model_id.startswith("vllm:"):
            model_id = model_id[5:]  # 移除 "vllm:" 前缀
    else:
        # 默认尝试deepseek
        provider = "deepseek"
        provider_config = config.get("deepseek", {})
    
    api_key = provider_config.get("api_key")
    if not api_key:
        if provider == "vllm":
            # vLLM 本地服务通常不需要真实的 API key，使用假的 token
            api_key = "EMPTY"
        else:
            raise ValueError(f"未找到 {provider} 的 API key")
    
    # 获取自定义 base_url（如果有的话）
    base_url = provider_config.get("base_url")
    
    return LLMConfig(
        provider=provider,
        model_id=model_id,
        api_key=api_key,
        base_url=base_url,
        temperature=0.7
    )


class RemoteContext:
    """保持与原有代码兼容的远程上下文"""
    client: ContextVar[AgentClient] = ContextVar("client")
    status: ContextVar[dict] = ContextVar("status")
    task_manager: ContextVar[object] = ContextVar("task_manager")
    id_map: ContextVar[dict] = ContextVar("id_map", default={})

    @staticmethod
    def set_client(client: AgentClient):
        RemoteContext.client.set(client)

    @staticmethod
    def get_client() -> AgentClient:
        return RemoteContext.client.get()

    @staticmethod
    def set_status(status: dict):
        RemoteContext.status.set(status)

    @staticmethod
    def get_status() -> dict:
        return RemoteContext.status.get()

    @staticmethod
    def set_task_manager(task_manager: object):
        RemoteContext.task_manager.set(task_manager)

    @staticmethod
    def get_task_manager() -> object:
        return RemoteContext.task_manager.get()

    @staticmethod
    def set_id_map(id_map: dict):
        RemoteContext.id_map.set(id_map)

    @staticmethod
    def get_id_map() -> dict:
        return RemoteContext.id_map.get()


class AgentDemo:
    """Agent 客户端演示类 - 保持与原有代码兼容"""

    def __init__(
        self,
        server_url="ws://localhost:8000/ws/metaverse",
        env_id="env_1",
        agent_id="agent_1",
    ):
        self.server_url = server_url
        self.env_id = env_id
        self.agent_id = agent_id
        self.agent_client = None
        self.messages = []

        self.init_client()

    def init_client(self):
        # 创建客户端
        self.agent_client = AgentClient(self.server_url, self.env_id, self.agent_id)
        self.setup_hub_listeners()
        RemoteContext.set_client(self.agent_client)
        # 初始化状态
        RemoteContext.set_status({"self_status": {}, "env_status": {}})

    def setup_hub_listeners(self):
        """设置事件监听器"""

        def on_connect(data):
            message = f"✅ Agent 连接成功: {data}"
            console.print(message, style="green")
            self.messages.append(message)

        def on_message(data):
            message = f"📨 Agent 收到消息: {data}"
            # print(message)
            msg_data = data.get("payload")
            msg_type = msg_data.get("type")
            if msg_type == "action":
                action = msg_data.get("action")
                params = msg_data.get("parameters")
                message += f"\n   动作: {action}, 参数: {params}"
            elif msg_type == "outcome":
                outcome_type = msg_data.get("outcome_type")
                outcome = msg_data.get("outcome")
                RemoteContext.get_id_map().update({msg_data["id"]: outcome})
                RemoteContext.set_status(
                    {"self_status": {f"任务{msg_data['id']}": outcome}}
                )
                message += f"\n   结果: {outcome}, 结果类型: {outcome_type}"
            # console.print(message, style="blue")
            self.messages.append(message)

        def on_disconnect(data):
            message = f"❌ Agent 连接断开: {data}"
            console.print(message, style="red")
            self.messages.append(message)

        def on_error(data):
            message = f"⚠️ Agent 错误: {data}"
            msg_data = data.get("payload", {})
            error = msg_data.get("error", "未知错误")
            console.print(message, style="yellow")
            # 只有当msg_data有id字段时才更新id_map
            if "id" in msg_data:
                RemoteContext.get_id_map().update({msg_data["id"]: error})
            self.messages.append(message)
            console.print("error 处理完毕", style="red")

        self.agent_client.add_hub_listener("connect", on_connect)
        self.agent_client.add_hub_listener("message", on_message)
        self.agent_client.add_hub_listener("disconnect", on_disconnect)
        self.agent_client.add_hub_listener("error", on_error)

    async def connect(self):
        """创建并连接 Agent 客户端"""
        console.print("🤖 创建 Agent 客户端", style="bold blue")
        console.print(f"📡 服务器: {self.server_url}")
        console.print(f"🌍 环境ID: {self.env_id}")
        console.print(f"🆔 Agent ID: {self.agent_id}")
        console.print("=" * 50)

        # 连接
        console.print("🔗 正在连接到服务器...", style="yellow")
        try:
            await self.agent_client.connect()
            console.print("✅ Agent 连接成功！", style="bold green")

            # 等待连接稳定
            await asyncio.sleep(1)
            return True
        except Exception as e:
            console.print(f"❌ 连接失败: {e}", style="bold red")
            return False

    async def interactive_demo(self):

        while True:
            try:
                await asyncio.create_task(chat(["chat", rule + "控制wei阵营,消灭敌人,获得胜利。"]))
                await asyncio.sleep(0.1)  # 短暂延迟以便查看结果

            except KeyboardInterrupt:
                print("\n👋 用户中断，退出")
                break
            except Exception as e:
                print(f"❌ 命令执行错误: {e}")

    def show_summary(self):
        """显示演示总结"""
        console.print("\n📊 Agent 演示总结", style="bold cyan")
        console.print("=" * 25)
        console.print(f"📈 总消息数: {len(self.messages)}")
        console.print(f"🆔 Agent ID: {self.agent_id}")
        console.print(f"🌍 环境 ID: {self.env_id}")

        if self.messages:
            console.print("\n📝 消息历史 (最近10条):")
            for i, msg in enumerate(self.messages[-10:], 1):
                console.print(f"   {i}. {msg}")

    async def cleanup(self):
        """清理资源"""
        console.print("\n🧹 正在清理连接...", style="yellow")
        try:
            if self.agent_client:
                await self.agent_client.disconnect()
                console.print("✅ Agent 连接已断开", style="green")
        except Exception as e:
            console.print(f"⚠️ 断开连接时出错: {e}", style="yellow")

    async def run_interactive_demo(self):
        """运行交互式演示"""
        console.print("🎮 Standalone Agent 交互式演示", style="bold cyan")
        console.print("🎯 你可以手动控制 Agent 执行各种动作", style="cyan")
        console.print("=" * 50)

        try:
            # 连接
            if not await self.connect():
                return
            # 进入交互模式
            await self.interactive_demo()

            # 显示总结
            self.show_summary()

        except KeyboardInterrupt:
            print("\n⚠️ 用户中断演示")
        except Exception as e:
            print(f"\n❌ 演示过程中发生错误: {e}")
        finally:
            await self.cleanup()


# ==================== 工具函数实现 ====================

async def get_response(request_id):
    """获取动作执行的响应"""
    # print(f"等待响应: {request_id}")
    while not RemoteContext.get_id_map().get(request_id, None):
        await asyncio.sleep(0.1)  # 等待响应
    response = RemoteContext.get_id_map().pop(request_id)
    # print(f"响应结果: {response}")
    return response


async def perform_action(action: str, params: Any):
    """执行动作"""
    # print(f"🚀 执行动作: {action}, 参数: {params}")

    response = None

    client = RemoteContext.get_client()
    # print(f"当前客户端: {client}")

    success = await client.send_action(action, params)
    # print(f"执行动作的立刻结果 - success: {success}")
    response = await get_response(success)

    # if response:
        #  print_json(data=response)
    return response


async def available_actions() -> list[Dict[str, Any]]:
    """获取当前可用的动作"""
    result = await perform_action("action_list", {})
    return result


# ==================== 命令处理函数 ====================

async def chat(parts):
    if len(parts) > 1:
        custom_action = parts[0]
        params = parts[1] if len(parts) > 1 else ""

        # 加载配置并创建独立的聊天代理
        try:
            config_path = os.path.join(os.getcwd(), ".configs.vllm.toml")
            # config_path = os.path.join(os.getcwd(), ".configs.toml")
            console.print(f"在当前工作目录找到配置文件: {config_path}")
            console.print("尝试加载配置文件")
            console.print(config_path)
            
            llm_config = load_config(config_path)
            agent = StandaloneChatAgent(llm_config)
            
            # 注册工具
            agent.register_tool(
                name="available_actions",
                function=available_actions,
                description="获取当前可以执行的可用动作列表。",
                parameters={"type": "object", "properties": {}, "required": []},
            )
            
            agent.register_tool(
                name="perform_action",
                function=perform_action,
                description="在游戏环境中执行一个特定的动作。",
                parameters={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "要执行的动作的名称。",
                        },
                        "params": {
                            "type": "object",
                            "description": "指定动作所需的参数字典。",
                            "additionalProperties": True,
                        },
                    },
                    "required": ["action", "params"],
                },
            )
            
            async def stop_running():
                """检测到游戏结束时停止运行"""
                return {"message": "Game over detected, agent should stop", "stop_requested": True}
            
            agent.register_tool(
                name="stop_running",
                function=stop_running,
                description="当检测到游戏结束时，停止代理的运行。",
                parameters={"type": "object", "properties": {}, "required": []},
            )

            # 执行聊天任务
            result = await agent.chat(task=params)
            console.print(f"聊天任务完成: {result}")
            
            # 清理资源
            await agent.stop()
            
        except Exception as e:
            console.print(f"聊天过程中发生错误: {e}", style="red")
            import traceback
            traceback.print_exc()
    else:
        print("❌ 请指定动作，如: chat dance")


async def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Standalone Agent 演示程序")

    parser.add_argument(
        "--server-url",
        default="ws://localhost:8000/ws/metaverse",
        help="服务器地址 (默认: ws://localhost:8000/ws/metaverse)",
    )
    parser.add_argument(
        "--env-id", type=str, default="env_1", help="环境ID (默认: env_1)"
    )
    parser.add_argument(
        "--agent-id", type=str, default="agent_1", help="Agent ID (默认: 1)"
    )

    args = parser.parse_args()

    console.print(f"📡 服务器: {args.server_url}")
    console.print(f"🌍 环境ID: {args.env_id}")
    console.print(f"🆔 Agent ID: {args.agent_id}")
    console.print("=" * 60)

    # 创建演示实例
    demo = AgentDemo(args.server_url, args.env_id, args.agent_id)
    console.print("🎮 交互式模式", style="bold cyan")
    await demo.run_interactive_demo()


if __name__ == "__main__":
    asyncio.run(main())
