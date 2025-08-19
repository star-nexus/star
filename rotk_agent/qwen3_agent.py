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

## 4. 行动机制：通过 `perform_action` 工具
- **核心工具**: 游戏中的所有单位动作（如move和attack）都**必须**通过调用 `perform_action` 工具来执行。你不能直接调用 `move` 或 `attack` 或 `get_faction_state。

- **工具用法**: `perform_action` 工具接收两个参数：
    1.  `action`: 一个字符串，指定要执行的动作名称 (例如: `"move"`, `"attack"`, `"get_faction_state"`, `"observation"`, `"end_turn"`)。
    2.  `params`: 一个JSON对象（字典），包含该动作所需的所有参数 (例如: `{"unit_id": 123, "target_position": {"col": 1, "row": 2}}`)。

- **严禁臆造 (No Fabrication)**:
    - 不能凭空编造或复用示例中的 `unit_id`、`target_id`、坐标或任何战场信息。
    - 在未通过工具获取真实数据前，不得假设任何单位的ID、位置、可视范围或敌人位置。
    - 示例中的ID仅为占位说明，绝不能直接使用。

- **前置检查清单 (必须遵循，按顺序执行)**:
    1.  调用 `get_available_actions` 工具获取当前可以执行的action列表。
    2.  调用 `perform_action` 工具 "arguments": "{\"action\": \"faction_state\", \"params\": {\"faction\": \"wei\"}}" 获取我方全部单位ID与状态。
    3.  调用 `perform_action` 工具 "arguments": "{\"action\": \"faction_state\", \"params\": {\"faction\": \"shu\"}}" 获取敌方单位信息（若可见）。
    4.  对每个准备操作的我方单位，调用 `perform_action`工具 "arguments": "{\"action\": \"observation\", \"params\": {\"unit_id\": <WEI_UNIT_ID>, \"observation_level\": \"basic\"}}" 获取该单位可见环境与附近可攻击/可移动的目标。

- **使用示例（仅作格式参考，不要使用其中的数字）**:
    - 移动单位：
      `perform_action(action="move", params={"unit_id": <WEI_UNIT_ID>, "target_position": {"col": <COL>, "row": <ROW>}})`
    - 攻击敌人：
      `perform_action(action="attack", params={"unit_id": <WEI_UNIT_ID>, "target_id": <SHU_UNIT_ID>})`

- **行动点 (AP)**: 执行 `perform_action` 会消耗对应单位的行动点 (AP)。AP会随时间恢复。行动前，务必通过上述前置检查确认AP充足。

## 5. 推荐操作流程 (OODA Loop)
游戏是即时进行的，建议你遵循“观察-判断-决策-行动”的循环，快速响应战场变化：
1.  **观察 (Observe)**: 先执行前置检查清单，持续使用 `get_faction_state` / `observation` 获取最新战况。
2.  **判断 (Orient)**: 基于最新状态确定威胁与机会，选择要操作的单位和目标。必须使用精炼且准确的描述，不可大段描述。
3.  **决策 (Decide)**: 规划本回合要执行的具体action及顺序（移动→攻击或先攻击→再移动，视AP与地形而定）。必须使用精炼且准确的描述，不可大段描述。
4.  **行动 (Act)**: 使用`perform_action` tool来执行action，必须严格按参数格式传入 `action` 与 `params`。
5.  **评估 (Assess)**: 检查动作返回结果；若失败，立即回到观察阶段查找原因（ID错误、范围不足、AP不足等）。
"""

@dataclass
class LLMConfig:
    """LLM Configuration"""
    provider: str  # "openai", "deepseek", "infinigence"
    model_id: str
    api_key: str
    base_url: Optional[str] = None
    temperature: float = 0.2
    max_tokens: Optional[int] = None


@dataclass
class ToolDefinition:
    """Tool Definition"""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable


@dataclass
class Message:
    """Message"""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class LLMClient:
    """Independent LLM Client, directly call various LLM APIs"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = httpx.AsyncClient()
        
        if config.provider == "openai":
            self.base_url = config.base_url or "https://api.openai.com/v1"
        elif config.provider == "deepseek":
            self.base_url = "https://api.deepseek.com/v1"
        elif config.provider == "infinigence":
            self.base_url = "https://cloud.infini-ai.com/maas/v1"
        elif config.provider == "vllm":
            self.base_url = config.base_url or "http://172.16.75.202:10000/v1"
        else:
            self.base_url = config.base_url or "https://api.openai.com/v1"

        console.print("=======================================", style="yellow")
        console.print(self.config, style="yellow") 
        console.print("=======================================", style="yellow")

    async def chat_completion(
        self, 
        messages: List[Message], 
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send chat completion request"""
        
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
            "chat_template_kwargs": {"enable_thinking": False},
            "max_tokens": 800,
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
            raise Exception(f"LLM API error: {response.status_code} - {response.text}")
        console.print("LLM client response status code", style="purple")
        console.print(response.status_code, style="purple")
        console.print("LLM client response json", style="purple")
        print_json(data=response.json(), indent=2, ensure_ascii=False)
        console.print("LLM client response end", style="purple")
        return response.json()
    
    def _format_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """Format tool definitions to OpenAI format"""
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
        """Close client"""
        await self.client.aclose()


class ToolManager:
    """Tool Manager"""
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
    
    def register_tool(self, tool: ToolDefinition):
        """Register tool"""
        self.tools[tool.name] = tool
    
    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all tool definitions"""
        return list(self.tools.values())
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute tool"""
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} does not exist")
        
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
    """Independent chat agent"""
    
    def __init__(self, llm_config: LLMConfig):
        self.llm_client = LLMClient(llm_config)
        self.tool_manager = ToolManager()
        self.conversation_history: List[Message] = []
        self.max_iterations = 100  # 防止无限循环
        
    def register_tool(self, name: str, function: Callable, description: str, parameters: Dict[str, Any]):
        """Register tool"""
        tool = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            function=function
        )
        self.tool_manager.register_tool(tool)
    

    def _parse_text_based_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse text-based tool calls from content field.
        
        Expected format examples:
        - '{"name": "perform_action", "arguments": {"action": "faction_state", "params": {"faction": "shu"}}}\n</tool_call>'
        - '{"name": "get_available_actions", "arguments": {}}\n</tool_call>'
        """
        import re
        import uuid
        
        tool_calls = []
        
        try:
            # Pattern to match JSON followed by </tool_call>
            pattern = r'\{[^}]*(?:\{[^}]*\}[^}]*)*\}(?:\s*\n?</tool_call>)?'
            matches = re.findall(pattern, content.strip())
            
            for match in matches:
                # Clean up the match by removing </tool_call> if present
                json_str = re.sub(r'\s*\n?</tool_call>.*$', '', match.strip())
                
                try:
                    # Parse the JSON
                    tool_data = json.loads(json_str)
                    
                    # Extract function name and arguments
                    function_name = tool_data.get("name")
                    arguments = tool_data.get("arguments", {})
                    
                    if function_name:
                        # Convert to OpenAI tool call format
                        tool_call = {
                            "id": f"call_{uuid.uuid4().hex[:24]}",  # Generate a unique ID
                            "type": "function",
                            "function": {
                                "name": function_name,
                                "arguments": json.dumps(arguments, ensure_ascii=False)
                            }
                        }
                        tool_calls.append(tool_call)
                        console.print(f"📝 Parsed tool call: {function_name} with args: {arguments}", style="cyan")
                    
                except json.JSONDecodeError as e:
                    console.print(f"⚠️ Failed to parse tool call JSON: {json_str} - {e}", style="yellow")
                    continue
                    
        except Exception as e:
            console.print(f"⚠️ Error parsing text-based tool calls: {e}", style="yellow")
        
        return tool_calls


    async def chat(self, task: str, max_iterations: Optional[int] = None) -> Dict[str, Any]:
        """Main chat loop"""
        if max_iterations:
            self.max_iterations = max_iterations
            
        # 初始化对话
        self.conversation_history = [
            Message(role="system", content=task)
        ]
        self.conversation_history.append(
            Message(role="user", content="""
**出生点**:
    - **蜀 (shu)** (敌方): 出生在地图 **左上角**，坐标值较小。
    - **魏 (wei)** (我方): 出生在地图 **右下角**，坐标值较大。
    - 你需要了解环境可以采用的action获取双方态势，并根据态势制定策略， 并执行action。
""")
        )
        
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
                
                console.print(f"╭─────────────────────────────────────────────────────── LLM response: ────────────────────────────────────────────────────────╮", style="yellow")
                console.print(f"│ {json.dumps(choice, indent=2, ensure_ascii=False)}", style="yellow", highlight=False)
                console.print(f"╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯", style="yellow")


                # 将助手响应添加到历史
                assistant_message = Message(
                    role="assistant",
                    content=message.get("content", ""),
                    tool_calls=message.get("tool_calls")
                )
                self.conversation_history.append(assistant_message)

                # === Detect text-based tool calls ===
                # Some models (like Qwen3-30B) put tool calls in content instead of tool_calls array
                tool_calls_to_use = message.get("tool_calls", [])
                if not tool_calls_to_use and message.get("content"):
                    parsed_tool_calls = self._parse_text_based_tool_calls(message["content"])
                    if parsed_tool_calls:
                        console.print("🔧 Detected text-based tool calls, converting to standard format", style="cyan")
                        self.conversation_history.append(
                        Message(
                            role="user", 
                            # content="Continue. If you need to call tools, please call them directly, without any additional explanation."),
                            content="Note: You should not put the tool call information in the `content` field. You must follow the tool call format.")
                    )
                    continue


                # 1) If there are tool calls, handle them — no matter the finish_reason
                if message.get("tool_calls"):
                    await self._handle_tool_calls(message["tool_calls"])
                    continue  # keep the loop going

                # 2) Hit max length? Ask model to continue (or just continue loop)
                if finish_reason == "length":
                    # Option A: push a tiny user nudge
                    self.conversation_history.append(
                        Message(
                            role="user", 
                            # content="Continue. If you need to call tools, please call them directly, without any additional explanation."),
                            content="Note: If you need to call tools, please call them directly or with only critical explanation.")
                    )
                    continue

                # 3) Normal terminal cases
                if finish_reason in ("stop", "content_filter"):
                    print(f"success: True, response: {message.get('content', '')}, iterations: {iterations}, finish_reason: {finish_reason}")
                    break

                # 4) an unexpected finish reason
                console.print(f"Unexpected finish reason: {finish_reason}", style="red")
                return {
                    "success": False,
                    "error": f"Unexpected finish reason: {finish_reason}",
                    "iterations": iterations
                }
            except Exception as e:
                console.print(f"Error during chat: {e}", style="red")
                return {
                    "success": False,
                    "error": str(e),
                    "iterations": iterations
                }
        
        # 达到最大迭代次数
        return {
            "success": False,
            "error": "Max iterations reached",
            "iterations": iterations
        }
    
    async def _handle_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        """Handle tool calls"""
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
                    console.print("⚠️ 'params' is a string, trying to decode again...", style="yellow")
                    try:
                        arguments['params'] = json.loads(arguments['params'])
                    except json.JSONDecodeError as e:
                        # 如果解码失败，说明LLM生成的JSON格式不正确。
                        # 这是无法恢复的错误，我们应该抛出异常，让上层捕获并通知LLM。
                        raise ValueError(f"LLM generated invalid JSON string for 'params': {arguments['params']}. Error: {e}")
                
                # 执行工具
                result = await self.tool_manager.execute_tool(function_name, arguments)
                
                console.print(f"╭──────────────────────────────────────── Tool '{function_name}' Result ────────────────────────────────────────╮", style="yellow")
                console.print(f"│ {json.dumps(result, indent=2, ensure_ascii=False)}", style="green", highlight=False)
                console.print(f"╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯", style="yellow")
                

                # 过滤工具结果，移除冗余信息以保持对话历史精炼
                filtered_result = self._filter_tool_result(function_name, result)
                
                # 将过滤后的工具结果添加到对话历史
                tool_message = Message(
                    role="tool",
                    content=json.dumps(filtered_result, ensure_ascii=False),
                    tool_call_id=tool_call_id
                )
                self.conversation_history.append(tool_message)
                
            except Exception as e:
                console.print(f"Tool execution error: {e}", style="red")
                # 添加错误信息到对话历史
                error_message = Message(
                    role="tool",
                    content=json.dumps({"error": str(e)}, ensure_ascii=False),
                    tool_call_id=tool_call_id
                )
                self.conversation_history.append(error_message)
    
    def _filter_tool_result(self, function_name: str, result: Any) -> Any:
        """Filter tool results, remove redundant information to keep conversation history concise"""
        if not isinstance(result, dict):
            return result
        
        # 深拷贝结果以避免修改原始数据
        import copy
        filtered_result = copy.deepcopy(result)
        
        # 针对不同的工具类型进行过滤
        if function_name == "perform_action":
            # 根据结果结构判断动作类型
            if "visible_environment" in filtered_result and "unit_info" in filtered_result:
                # observation 结果
                filtered_result = self._filter_observation_result(filtered_result)
            elif "faction" in filtered_result and "units" in filtered_result and "total_units" in filtered_result:
                # faction_state 结果
                filtered_result = self._filter_faction_state_result(filtered_result)
            elif "message" in filtered_result and ("moved successfully" in str(filtered_result.get("message", "")) or 
                                                  "failure_reason" in filtered_result):
                # move 结果
                filtered_result = self._filter_move_result(filtered_result)
            elif "battle_summary" in filtered_result and "casualties_inflicted" in filtered_result:
                # attack 结果
                filtered_result = self._filter_attack_result(filtered_result)
        
        return filtered_result
    
    def _filter_observation_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """过滤 observation 结果，移除冗余字段"""
        # 创建结果的深拷贝以避免修改原始数据
        import copy
        filtered_result = copy.deepcopy(result)
        
        # 过滤 unit_info 字段，移除无用的噪声关键字
        if "unit_info" in filtered_result and isinstance(filtered_result["unit_info"], dict):
            unit_info = filtered_result["unit_info"]
            
            # 过滤 status 字段中的噪声关键字
            if "status" in unit_info and isinstance(unit_info["status"], dict):
                status = unit_info["status"]
                # 移除 morale 和 fatigue 字段
                status.pop("morale", None)
                status.pop("fatigue", None)
            
            # 过滤 capabilities 字段中的噪声关键字
            if "capabilities" in unit_info and isinstance(unit_info["capabilities"], dict):
                capabilities = unit_info["capabilities"]
                # 移除无用的能力字段
                noise_capabilities = ["attack_points", "construction_points", "skill_points"]
                for noise_key in noise_capabilities:
                    capabilities.pop(noise_key, None)
            
            # 移除 available_skills 字段
            unit_info.pop("available_skills", None)
        
        # 过滤 visible_environment 字段
        if "visible_environment" in filtered_result and isinstance(filtered_result["visible_environment"], list):
            filtered_env = []
            for tile in filtered_result["visible_environment"]:
                if isinstance(tile, dict):
                    # 保留核心信息，移除噪声字段
                    filtered_tile = {
                        "position": tile.get("position"),
                        "terrain": tile.get("terrain"),
                    }
                    
                    # 始终包含 units 字段
                    units = tile.get("units", [])
                    filtered_tile["units"] = units
                    
                    # 简化 movement_accessibility - 只保留是否可达
                    movement_access = tile.get("movement_accessibility", {})
                    if isinstance(movement_access, dict) and "reachable" in movement_access:
                        filtered_tile["reachable"] = movement_access["reachable"]
                    
                    # 简化 attack_range_info - 只保留是否在攻击范围内
                    attack_info = tile.get("attack_range_info")
                    if isinstance(attack_info, dict) and "in_attack_range" in attack_info:
                        filtered_tile["attackable"] = attack_info["in_attack_range"]
                    elif attack_info is True or attack_info is False:
                        filtered_tile["attackable"] = attack_info
                    
                    filtered_env.append(filtered_tile)
            
            filtered_result["visible_environment"] = filtered_env
        
        return filtered_result
    
    def _filter_faction_state_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """过滤 faction_state 结果"""
        # faction_state 结果通常已经比较精炼，暂时不做额外过滤
        return result
    
    def _filter_move_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """过滤 move 结果，保留关键错误信息或成功信息"""
        if not result.get("success", True):
            # 移动失败时，保留关键错误信息但简化建议
            if "suggested_action" in result:
                # 保留建议动作但移除详细的调试信息
                essential_keys = {
                    "success", "message", "failure_reason", 
                    "current_movement_points", "required_movement_points",
                    "closest_reachable_position", "suggested_action", "suggestion"
                }
                filtered_result = {k: v for k, v in result.items() if k in essential_keys}
                return filtered_result
        
        return result
    
    def _filter_attack_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """过滤 attack 结果"""
        if result.get("success", True):
            # 攻击成功时，保留核心战斗信息
            essential_keys = {
                "success", "message", "battle_summary", 
                "remaining_resources", "tactical_info"
            }
            filtered_result = {k: v for k, v in result.items() if k in essential_keys}
            
            # 进一步精简 battle_summary
            if "battle_summary" in filtered_result and isinstance(filtered_result["battle_summary"], dict):
                battle_summary = filtered_result["battle_summary"]
                essential_battle_keys = {
                    "attacker_info", "target_info", "casualties_inflicted", 
                    "target_destroyed", "distance"
                }
                filtered_result["battle_summary"] = {
                    k: v for k, v in battle_summary.items() if k in essential_battle_keys
                }
            
            return filtered_result
        
        return result

    async def stop(self):
        """Stop agent"""
        await self.llm_client.close()


def load_config(config_path: str = ".configs.toml") -> LLMConfig:
    """Load LLM configuration from config file"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    config = toml.load(config_path)
    default_config = config.get("default", {})
    model_id = default_config.get("model_id", "deepseek-chat")
    
    # 根据模型ID推断提供商
    if "claude" in model_id:
        provider = "infinigence"  # Based on observation, claude models are provided by infinigence
        provider_config = config.get("infinigence", {})
    elif "deepseek" in model_id:
        provider = "deepseek"
        provider_config = config.get("deepseek", {})
    elif "gpt" in model_id or "openai" in model_id:
        provider = "openai"
        provider_config = config.get("openai", {})
    elif model_id.startswith("vllm:") or config.get("vllm", {}).get("enabled"):
        # vLLM support: model_id starts with "vllm:" or vllm is enabled in config
        provider = "vllm"
        provider_config = config.get("vllm", {})
        # If model_id starts with vllm:, remove the prefix to get the actual model name
        if model_id.startswith("vllm:"):
            model_id = model_id[5:]  # Remove "vllm:" prefix
    else:
        # Default to deepseek
        provider = "deepseek"
        provider_config = config.get("deepseek", {})
    
    api_key = provider_config.get("api_key")
    if not api_key:
        if provider == "vllm":
            # vLLM local service usually doesn't require a real API key, use a fake token
            api_key = "EMPTY"
        else:
            raise ValueError(f"API key not found for {provider}")
    
    # Get custom base_url (if any)
    base_url = provider_config.get("base_url")
    
    return LLMConfig(
        provider=provider,
        model_id=model_id,
        api_key=api_key,
        base_url=base_url,
        temperature=0.2
    )


class RemoteContext:
    """Remote context compatible with existing code"""
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
    """Agent client demo class - compatible with existing code"""

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
        # Create client
        self.agent_client = AgentClient(self.server_url, self.env_id, self.agent_id)
        self.setup_hub_listeners()
        RemoteContext.set_client(self.agent_client)
        # Initialize state
        RemoteContext.set_status({"self_status": {}, "env_status": {}})

    def setup_hub_listeners(self):
        """Set event listeners"""

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
        count = 0
        while True:
            count += 1
            console.print(f"🔄 {count}th interaction", style="bold red")
            try:
                await asyncio.create_task(chat(["chat", rule + "控制wei阵营,消灭敌人,获得胜利。"]))
                await asyncio.sleep(0.1)  # Short delay to view results

            except KeyboardInterrupt:
                print("\n👋 User interrupted, exiting")
                break
            except Exception as e:
                print(f"❌ Command execution error: {e}")

    def show_summary(self):
        """Show demo summary"""
        console.print("\n📊 Agent demo summary", style="bold cyan")
        console.print("=" * 25)
        console.print(f"📈 Total messages: {len(self.messages)}")
        console.print(f"🆔 Agent ID: {self.agent_id}")
        console.print(f"🌍 Environment ID: {self.env_id}")

        if self.messages:
            console.print("\n📝 Message history (last 10):")
            for i, msg in enumerate(self.messages[-10:], 1):
                console.print(f"   {i}. {msg}")

    async def cleanup(self):
        """Clean up resources"""
        console.print("\n🧹 Cleaning up connection...", style="yellow")
        try:
            if self.agent_client:
                await self.agent_client.disconnect()
                console.print("✅ Agent connection closed", style="green")
        except Exception as e:
            console.print(f"⚠️ Error closing connection: {e}", style="yellow")

    async def run_interactive_demo(self):
        """Run interactive demo"""
        console.print("🎮 Standalone Agent interactive demo", style="bold cyan")
        console.print("🎯 You can manually control the Agent to perform various actions", style="cyan")
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
            print("\n⚠️ User interrupted demo")
        except Exception as e:
            print(f"\n❌ Error during demo: {e}")
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


async def get_available_actions() -> list[Dict[str, Any]]:
    """获取当前可用的动作"""
    result = await perform_action("get_action_list", {})
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
                name="get_available_actions",
                function=get_available_actions,
                description="获取可以执行的action列表。",
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
        help="Server address (default: ws://localhost:8000/ws/metaverse)",
    )
    parser.add_argument(
        "--env-id", type=str, default="env_1", help="Environment ID (default: env_1)"
    )
    parser.add_argument(
        "--agent-id", type=str, default="agent_1", help="Agent ID (default: 1)"
    )

    args = parser.parse_args()

    console.print(f"📡 Server: {args.server_url}")
    console.print(f"🌍 Environment ID: {args.env_id}")
    console.print(f"🆔 Agent ID: {args.agent_id}")
    console.print("=" * 60)

    # Create demo instance
    demo = AgentDemo(args.server_url, args.env_id, args.agent_id)
    console.print("🎮 Interactive mode", style="bold cyan")
    await demo.run_interactive_demo()


if __name__ == "__main__":
    asyncio.run(main())
