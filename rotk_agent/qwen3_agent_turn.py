import asyncio
import argparse
from contextvars import ContextVar
from datetime import datetime
import os
import sys
import json
import httpx
import toml
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable, Union
from string import Template

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from protocol import AgentClient

# 配置 rich 库
from rich.console import Console
from rich import print_json

console = Console()
console_system = Console()
# Replace console.print with an "empty" function to avoid printing to console
# console.print = lambda *a, **k: None

@dataclass
class LLMConfig:
    """LLM Configuration"""
    provider: str  # "openai", "deepseek", "infinigence"
    model_id: str
    api_key: str
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    enable_thinking: bool = False


@dataclass
class Message:
    """Message"""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ToolDefinition:
    """Tool Definition"""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable


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
        # If it is an asynchronous function
        if asyncio.iscoroutinefunction(tool.function):
            return await tool.function(**arguments)
        else:
            return tool.function(**arguments)


class LLMClient:
    """Independent LLM Client, directly call various LLM APIs"""
    
    # global LLM API Call count
    _global_api_call_count = 0
    _global_api_success_count = 0
    _global_api_error_count = 0

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = httpx.AsyncClient()
        
        if config.provider == "openai":
            self.base_url = config.base_url or "https://api.openai.com/v1/chat/completions"
        elif config.provider == "deepseek":
            self.base_url = config.base_url
        elif config.provider == "infinigence":
            self.base_url = "https://cloud.infini-ai.com/maas/v1/chat/completions"
        elif config.provider == "siliconflow":
            self.base_url = "https://api.siliconflow.cn/v1/chat/completions"
        elif config.provider == "vllm":
            self.base_url = config.base_url
        else:
            self.base_url = config.base_url

        self.config_thinking = True

        self.config.base_url = self.base_url
        self.config.enable_thinking = config.enable_thinking and self.config_thinking

        console_system.print("=======================================", style="yellow")
        console_system.print(self.config, style="yellow") 
        console_system.print("=======================================", style="yellow")

    async def chat_completion(
        self, 
        messages: List[Message], 
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send chat completion request"""
        
        formatted_messages = []
        for msg in messages:
            message_dict = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                message_dict["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                message_dict["tool_call_id"] = msg.tool_call_id
            formatted_messages.append(message_dict)
        
        payload = {
            "model": self.config.model_id,
            "messages": formatted_messages,
            "stream": False,
        }
        
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p
        if self.config.top_k is not None:
            payload["top_k"] = self.config.top_k
        if self.config.max_tokens is not None:
            payload["max_tokens"] = self.config.max_tokens
        # if self.config_thinking:
        #     if self.config.provider == "siliconflow":
        #         payload["enable_thinking"] = bool(self.config.enable_thinking)    
        #     elif self.config.provider.startswith("vllm"):
        #         payload["chat_template_kwargs"] = {
        #                 "enable_thinking": bool(self.config.enable_thinking)
        #             }
        
        if tools:
            payload["tools"] = self._format_tools(tools)
            payload["tool_choice"] = "auto"
            payload["parallel_tool_calls"] = True
            
        payload.update(kwargs)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        
        console.print(f"╭─────────────────────────────────────────────────────── LLM request payload: ─────────────────────────────────────────────────╮", style="green")
        console.print(f"│ {json.dumps(payload, indent=2, ensure_ascii=False)}", style="green", highlight=False)
        console.print(f"╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯", style="green")

        # Send request
        # Count API call (count before sending to ensure all calls are tracked)
        LLMClient._global_api_call_count += 1
        print(f"🔍 API call count: {LLMClient._global_api_call_count}")
        
        try:
            response = await self.client.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=180.0
            )
            
            if response.status_code != 200:
                error_details = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "url": str(response.url),
                    "request_payload": payload,
                    "config": {
                        "provider": self.config.provider,
                        "model_id": self.config.model_id,
                        "base_url": self.base_url
                    }
                }
                
                try:
                    response_data = response.json()
                    error_details["response_json"] = response_data
                    error_message = response_data.get("error", {}).get("message", response.text)
                except:
                    error_details["response_text"] = response.text
                    error_message = response.text
                
                console.print("🚨 LLM API error details:", style="red bold")
                console.print(f"Status code: {error_details['status_code']}", style="red")
                console.print(f"URL: {error_details['url']}", style="red")
                console.print(f"Provider: {error_details['config']['provider']}", style="red")
                console.print(f"Model: {error_details['config']['model_id']}", style="red")
                console.print("Response content:", style="red")
                print_json(data=error_details.get("response_json", error_details.get("response_text", "")), indent=2)
                
                # Count failed API calls
                LLMClient._global_api_error_count += 1
                raise Exception(f"LLM API error: {response.status_code} - {error_message}")
                
            response_data = response.json()
            # Count successful API calls
            LLMClient._global_api_success_count += 1
            return response_data
            
        except httpx.ConnectError as e:
            # Count failed API calls
            LLMClient._global_api_error_count += 1
            error_msg = f"Cannot connect to {self.config.provider} API server: {self.base_url}"
            console.print(f"🔌 Connection error: {error_msg}", style="red")
            console.print(f"Please check network connection and API server status", style="yellow")
            raise Exception(error_msg) from e
            
        except httpx.TimeoutException as e:
            # Count failed API calls
            LLMClient._global_api_error_count += 1
            error_msg = f"{self.config.provider} API request timeout (>180 seconds)"
            console.print(f"⏱️ Timeout error: {error_msg}", style="red")
            console.print(f"Please check network status or try again", style="yellow")
            raise Exception(error_msg) from e
            
        except httpx.HTTPStatusError as e:
            # Count failed API calls
            LLMClient._global_api_error_count += 1
            error_msg = f"{self.config.provider} API HTTP error: {e.response.status_code}"
            console.print(f"🌐 HTTP error: {error_msg}", style="red")
            raise Exception(error_msg) from e
            
        except Exception as e:
            # Count failed API calls
            LLMClient._global_api_error_count += 1
            error_msg = f"Unknown error occurred while sending API request: {str(e)}"
            console.print(f"❌ Unknown error: {error_msg}", style="red")
            console.print(f"Request URL: {self.base_url}/chat/completions", style="yellow")
            console.print(f"Provider: {self.config.provider}", style="yellow")
            raise Exception(error_msg) from e
    
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
    
    def get_api_stats(self) -> Dict[str, int]:
        """Get API call statistics"""
        return {
            "total_calls": LLMClient._global_api_call_count,
            "successful_calls": LLMClient._global_api_success_count,
            "failed_calls": LLMClient._global_api_error_count,
            "success_rate": round(LLMClient._global_api_success_count / LLMClient._global_api_call_count * 100, 2) if LLMClient._global_api_call_count > 0 else 0.0
        }
    
    async def close(self):
        """Close client"""
        await self.client.aclose()
        import sys
        sys.exit(0)


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


def load_config(config_path: str = ".configs.toml", provider: str = "vllm") -> LLMConfig:
    """Load LLM configuration from config file"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    config = toml.load(config_path)
    try:
        provider_config = config[provider]
    except KeyError:
        raise ValueError(f"Invalid provider: {provider}")

    try:
        model_id = provider_config["model_id"]
    except KeyError:
        raise ValueError(f"Model ID not found for {provider}")
    
    api_key = provider_config.get("api_key", "EMPTY")
    base_url = provider_config.get("base_url", "")
    enable_thinking = provider_config.get("enable_thinking", False)
    temperature = provider_config.get("temperature")
    top_p = provider_config.get("top_p")
    top_k = provider_config.get("top_k")
    max_tokens = provider_config.get("max_tokens")

    return LLMConfig(
        provider=provider,
        model_id=model_id,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        top_k=top_k,
        enable_thinking=enable_thinking
    )


class RoTKChatAgent:
    
    def __init__(self, llm_config: LLMConfig, faction: str = "wei", system_prompt: str = "", max_api_calls_per_turn: int = 25):
        self.llm_client = LLMClient(llm_config)
        self.tool_manager = ToolManager()
        self.system_prompt = system_prompt
        self.conversation_history: List[Message] = []
        self.max_iterations = 1000
        self.faction = faction
        
        self._history_lock = asyncio.Lock()
        self._agent_registered: bool = False
        
        self._strategy_last_ping_ts: float = 0.0
        # 🆕 最近一次已处理的回合号（用于 rotk_agent/qwen3_agent_turn.py 幂等）
        self._last_turn_notified: int = -1
        # 🆕 回合门控：控制 LLM API 调用开关（end_turn 后关闭，turn_start 到达后开启）
        self._turn_gate: asyncio.Event = asyncio.Event()
        self._turn_gate.set()
        
        # 🆕 每回合 LLM API 调用预算，防止弱模型无限调用不结束回合；turn_start 时重置
        self.max_api_calls_per_turn: int = max_api_calls_per_turn
        self._api_calls_this_turn: int = 0
        
    # ======== Turn Gate Control Functions ========
    # These functions are used to control and record the turn gate status for LLM API calls,
    # ensuring that LLM inference is only performed during allowed turns.
    def _log_gate_status(self, action: str):
        """记录门控状态变化"""
        status = "OPEN" if self._turn_gate.is_set() else "CLOSED"
        console.print(f"🚪 Turn gate {action}: {status}", style="cyan")
    
    async def _wait_for_turn_gate(self) -> bool:
        """等待回合门控开启，返回是否应该继续执行 LLM API 调用。
        期间轮询 RemoteContext 的 turn_start 状态，主动解除门控，避免死等。"""
        if self._turn_gate.is_set():
            return True
        console.print("⏸️ Waiting for next turn_start to resume LLM calls...", style="yellow")
        while not self._turn_gate.is_set():
            # 使用统一的turn_start处理方法
            try:
                if await self._process_turn_start_if_available("wait_gate"):
                    break  # 成功处理了turn_start，门控已开启，退出等待
                
                # 检查游戏是否结束
                status = RemoteContext.get_status() or {}
                if status.get("game_ended", False):
                    # 游戏结束时确保不阻塞
                    if not self._turn_gate.is_set():
                        self._set_turn_gate("game_ended - emergency (wait)")
                    return False
            except Exception as e:
                console.print(f"⚠️ Polling status while waiting failed: {e}", style="yellow")
            
            # 短暂等待，避免忙等
            try:
                await asyncio.wait_for(self._turn_gate.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                console.print(f"⚠️ Waiting for turn_start interrupted: {e}", style="yellow")
                return False
        console.print("▶️ Turn started. Resuming LLM calls.", style="green")
        return True
    
    def _set_turn_gate(self, action: str = "manual"):
        """Unified turn gate opening operation for LLM API calls"""
        try:
            self._turn_gate.set()
            self._log_gate_status(f"OPENED ({action})")
        except Exception as e:
            console.print(f"⚠️ Failed to set turn gate: {e}", style="yellow")
    
    def _clear_turn_gate(self, action: str = "manual"):
        """Unified turn gate closing operation for LLM API calls"""
        try:
            self._turn_gate.clear()
            self._log_gate_status(f"CLOSED ({action})")
        except Exception as e:
            console.print(f"⚠️ Failed to clear turn gate: {e}", style="yellow")
    
    async def _process_turn_start_if_available(self, context_name: str = "") -> bool:
        """统一处理turn_start事件检测和通知注入
        
        Args:
            context_name: 调用上下文名称，用于日志区分
        
        Returns:
            bool: 是否成功处理了turn_start事件
        """
        try:
            status = RemoteContext.get_status() or {}
            turn_evt = status.get("turn_start")
            if isinstance(turn_evt, dict):
                evt_faction = str(turn_evt.get("faction", "")).lower()
                evt_turn = turn_evt.get("turn_number", None)
                # 仅当：阵营匹配 且 回合号严格大于已处理回合号 时，才处理
                if evt_faction == str(self.faction).lower() and isinstance(evt_turn, int):
                    if evt_turn > self._last_turn_notified:
                        # 🔧 额外检查：确保门控当前是关闭的（意味着我们确实在等待新回合）
                        if self._turn_gate.is_set():
                            console.print(f"⚠️ Found turn_start but gate is already open - likely a stale event (evt_turn={evt_turn}, last={self._last_turn_notified}) [{context_name}]", style="yellow")
                            return False
                        
                        # 注入一条精简 user 提示
                        hint = f"你的回合开始（第{evt_turn}回合）。所有资源已恢复。请开始行动。"
                        async with self._history_lock:
                            self.conversation_history.append(Message(role="user", content=hint))
                        self._last_turn_notified = evt_turn
                        self._api_calls_this_turn = 0  # 新回合重置每回合 API 调用计数
                        console.print(f"📣 Injected turn_start hint for faction={self.faction}, turn={evt_turn} [{context_name}]", style="green")
                        # 解除回合门控，允许 LLM API 调用
                        self._set_turn_gate(f"turn_start ({context_name})")
                        return True
                    else:
                        if context_name:
                            console.print(f"⏳ Detected turn_start but not newer (evt_turn={evt_turn}, last={self._last_turn_notified}) [{context_name}]", style="dim yellow")
                else:
                    if evt_faction and evt_faction != str(self.faction).lower() and context_name:
                        console.print(f"⏳ Detected turn_start for other faction: {evt_faction} [{context_name}]", style="dim yellow")
            return False
        except Exception as e:
            console.print(f"⚠️ Turn-start processing failed [{context_name}]: {e}", style="yellow")
            return False
    # ======== Turn Gate Control Functions End ========
        

    def register_tool(self, name: str, function: Callable, description: str, parameters: Dict[str, Any]):
        """Register tool"""
        tool = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            function=function
        )
        self.tool_manager.register_tool(tool)

    
    # ==================== Tool Calls Parsing Functions Start ====================
    def _parse_text_based_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse text-based tool calls from content field.
        
        Expected format examples:
        - '{"name": "perform_action", "arguments": {"action": "get_faction_state", "params": {"faction": "shu"}}}\n</tool_call>'
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
                    console.print(f"⚠️ Found text-based tool call with content", style="red")
                    console.print(f"⚠️ Failed to parse tool call JSON: {json_str} - {e}", style="red")
                    return True
                except Exception as e:
                    console.print(f"⚠️ Error parsing text-based tool calls: {e}", style="red")
                    return True
                
        except Exception as e:
            console.print(f"⚠️ Error parsing text-based tool calls: {e}", style="red")
        
        return tool_calls

    async def _handle_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        """Handle tool calls"""
        console.print(f"🔧 Handling {len(tool_calls)} tool calls", style="cyan")
        
        # Support parallel execution of multiple tool calls
        parallel_execution = len(tool_calls) > 1 and all(
            tool_call["function"]["name"] == "perform_action" 
            for tool_call in tool_calls
        )
        
        if parallel_execution:
            console.print("⚡ Multiple perform_action calls detected, using parallel execution mode", style="cyan")
            await self._handle_tool_calls_parallel(tool_calls)
        else:
            console.print("🔄 Using sequential execution mode", style="cyan")
            await self._handle_tool_calls_sequential(tool_calls)
    
    async def _handle_tool_calls_sequential(self, tool_calls: List[Dict[str, Any]]):
        """Sequential execution of tool calls"""
        for tool_call in tool_calls:
            await self._execute_single_tool_call(tool_call)
    
    async def _handle_tool_calls_parallel(self, tool_calls: List[Dict[str, Any]]):
        """Parallel execution of tool calls"""
        tasks = []
        for tool_call in tool_calls:
            task = asyncio.create_task(self._execute_single_tool_call(tool_call))
            tasks.append(task)
        
        await asyncio.gather(*tasks)
    
    async def _execute_single_tool_call(self, tool_call: Dict[str, Any]):
        """Execute single tool call"""
        tool_call_id = tool_call["id"]
        function_name = tool_call["function"]["name"]
        arguments_str = tool_call["function"]["arguments"]
        
        console.print(f"╭───────────────────────────────── Executing tool '{function_name}' with arguments ───────────────────────────────────╮", style="magenta")
        console.print(f"│ {arguments_str}", style="magenta", highlight=False)
        console.print(f"╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯", style="magenta")
        
        try:
            # Parse parameters
            arguments = json.loads(arguments_str) if arguments_str else {}
            
            if 'params' in arguments and isinstance(arguments['params'], str):
                console.print("⚠️ 'params' is a string, trying to decode again...", style="yellow")
                try:
                    arguments['params'] = json.loads(arguments['params'])
                except json.JSONDecodeError as e:
                    raise ValueError(f"LLM generated invalid JSON string for 'params': {arguments['params']}. Error: {e}")
            
            # Intercept misuse: perform_action attempting to call end_turn
            if function_name == "perform_action":
                action_name = (arguments or {}).get("action")
                if action_name == "end_turn":
                    error_message = (
                        "❌ 工具使用错误！'end_turn' 是一个独立的工具，不能通过 'perform_action' 调用。\n"
                        "正确的调用方式是：\n"
                        '{"name": "end_turn", "arguments": {}}\n\n'
                        "请直接使用 end_turn 工具来结束回合。"
                    )
                    tool_error = {
                        "success": False,
                        "error": "Invalid tool usage",
                        "message": error_message
                    }
                    # Append tool error response and a user correction hint
                    tool_message = Message(
                        role="tool",
                        content=json.dumps(tool_error, ensure_ascii=False),
                        tool_call_id=tool_call_id
                    )
                    correction_message = Message(
                        role="user",
                        content=(
                            "请注意：你刚才试图通过 perform_action 调用 end_turn，这是错误的。\n"
                            "end_turn 是一个独立的工具。正确的调用方式是：\n"
                            '{"name": "end_turn", "arguments": {}}\n\n'
                            "请直接使用 end_turn 工具来结束当前回合。"
                        )
                    )
                    async with self._history_lock:
                        self.conversation_history.append(tool_message)
                        self.conversation_history.append(correction_message)
                    return

            # Execute tool
            result = await self.tool_manager.execute_tool(function_name, arguments)
            filtered_result = self._filter_tool_result(function_name, result, arguments)

            # console.print(f"╭──────────────────────────────── Tool Result(filtered): {function_name} ────────────────────────────────╮", style="magenta")
            # console.print(f"│ {json.dumps(filtered_result, indent=2, ensure_ascii=False)}", style="magenta", highlight=False)
            # console.print(f"╰───────────────────────────────────────────────────────────────────────────────────────────────╯", style="magenta")

            tool_message = Message(
                role="tool",
                content=json.dumps(filtered_result, ensure_ascii=False),
                tool_call_id=tool_call_id
            )
            async with self._history_lock:
                self.conversation_history.append(tool_message)
            
        except Exception as e:
            console.print(f"Tool execution error during tool call: {e}, function_name: {function_name}", style="red")
            # Add error information to conversation history (using lock to protect parallel access)
            error_message = Message(
                role="tool",
                content=json.dumps({"error": str(e)}, ensure_ascii=False),
                tool_call_id=tool_call_id
            )
            # continue chat with LLM even if there is an error
            async with self._history_lock:
                self.conversation_history.append(error_message)

    # ==================== Tool Calls Execution Functions End ====================


    # ==================== Strategy keyword detection and reporting Start ====================
    def _contains_strategy_keywords(self, text: str) -> bool:
        """Detects basic strategy thinking: keywords + structure words within proximity, without negation."""
        if not text:
            return False
        
        import re
        t = text.lower()
        
        # Strategy keywords
        zh_keys = [
            "策略", "战略", "战术", "推进", "收缩", "防守", "进攻", "包抄", "侧翼", "伏击", "牵制",
            "佯攻", "撤退", "补给", "集结", "兵力部署", "路线", "优先级", "据点", "卡位", "占领",
            "固守", "视野", "地形优势", "补给线", "防线", "桥头堡", "绕后", "夹击", "高地", "chokepoint",
            "协同", "集火", "分兵"
        ]
        en_keys = [
            "strategy", "strategic", "tactic", "tactical", "plan", "objective", "priority",
            "advance", "retreat", "hold", "defend", "attack", "flank", "ambush", "harass",
            "pin down", "fix-in-place", "regroup", "supply", "chokepoint", "terrain advantage",
            "strongpoint", "encircle"
        ]
        
        # Structure words
        structure_terms = ["先", "然后", "再", "首先", "优先", "目标", "步骤", "顺序", "选择", "方案", "计划",
                           "first", "then", "next", "priority", "goal", "objective", "step", "order"]
        
        # Negation words (to avoid false positives)
        negation_zh = ["不", "不要", "不能", "不可", "停止", "禁止", "避免", "取消"]
        negation_en = ["not", "don't", "can't", "won't", "avoid", "stop", "cancel", "never"]
        
        # Find all keyword positions
        keyword_positions = []
        for kw in zh_keys:
            if kw in text:
                for match in re.finditer(re.escape(kw), text):
                    keyword_positions.append((match.start(), match.end(), kw))
        for kw in en_keys:
            if kw in t:
                for match in re.finditer(re.escape(kw), t):
                    keyword_positions.append((match.start(), match.end(), kw))
        
        if not keyword_positions:
            return False
        
        # Find all structure word positions
        structure_positions = []
        for sw in structure_terms:
            search_text = text if any(c >= '\u4e00' for c in sw) else t  # Chinese or English
            if sw in search_text:
                for match in re.finditer(re.escape(sw), search_text):
                    structure_positions.append((match.start(), match.end(), sw))
        
        if not structure_positions:
            return False
        
        # Check proximity (within 50 characters) and no negation
        proximity_window = 50
        for kw_start, kw_end, kw_text in keyword_positions:
            # Check for negation near keyword (±20 chars)
            negation_window = 20
            context_start = max(0, kw_start - negation_window)
            context_end = min(len(text), kw_end + negation_window)
            context = text[context_start:context_end].lower()
            
            # Skip if negation found near keyword
            if any(neg in context for neg in negation_zh + negation_en):
                continue
            
            # Check proximity with structure words
            for st_start, st_end, st_text in structure_positions:
                distance = min(abs(kw_start - st_end), abs(st_start - kw_end))
                if distance <= proximity_window:
                    return True
        
        return False

    def _contains_strategy_sequence(self, text: str) -> bool:
        """Detect sequence-based strategy phrases with improved flexibility and negation handling."""
        if not text:
            return False
        import re
        t = text.lower()

        # Negation words
        negation_zh = ["不", "不要", "不能", "不可", "停止", "禁止", "避免", "取消"]
        negation_en = ["not", "don't", "can't", "won't", "avoid", "stop", "cancel", "never"]

        # Helper function to check for negation near a match
        def has_negation_near(match_obj, source_text):
            start, end = match_obj.span()
            context_start = max(0, start - 15)
            context_end = min(len(source_text), end + 15)
            context = source_text[context_start:context_end].lower()
            return any(neg in context for neg in negation_zh + negation_en)

        # Expanded regex patterns (20 -> 40 characters window)
        zh_patterns = [
            r"(移动|前进|靠近|靠拢|调整|转移|推进|到达).{0,40}(攻击|开火|打击|交战|冲锋|压制|集火|歼灭|突击)",
            r"(位置|坐标).{0,40}(攻击|开火|打击|交战)",
            r"(攻击|开火|打击|交战|冲锋|压制|集火|突击).{0,40}(移动|前进|靠近|靠拢|调整|转移|撤退|推进|到达)",
        ]
        en_patterns = [
            r"(move|advance|relocate|close in|position).{0,40}(attack|engage|fire|strike|assault)",
            r"(attack|engage|fire|strike|assault).{0,40}(move|advance|relocate|retreat|position)",
        ]

        # Check regex patterns with negation filtering
        for pat in zh_patterns:
            for match in re.finditer(pat, text):
                if not has_negation_near(match, text):
                    return True
        for pat in en_patterns:
            for match in re.finditer(pat, t):
                if not has_negation_near(match, t):
                    return True

        # Extended sentence sequence detection (check up to 2 sentences ahead)
        move_terms_zh = ["移动", "前进", "靠近", "靠拢", "调整", "转移", "推进", "到达", "位置", "坐标", "观察", "侦查"]
        attack_terms_zh = ["攻击", "开火", "打击", "交战", "冲锋", "压制", "集火", "歼灭", "突击", "支援", "协同", "集中火力"]
        move_terms_en = ["move", "advance", "relocate", "close in", "position", "coordinate", "retreat"]
        attack_terms_en = ["attack", "engage", "fire", "strike", "assault", "charge", "suppress"]

        def has_terms_without_negation(seg: str, terms_zh: list[str], terms_en: list[str]) -> bool:
            s = seg.lower()
            # Check for terms
            found_terms = []
            for term in terms_zh:
                if term in seg:
                    found_terms.append(term)
            for term in terms_en:
                if term in s:
                    found_terms.append(term)
            
            if not found_terms:
                return False
            
            # Check for negation near found terms
            for term in found_terms:
                term_pos = seg.find(term) if term in seg else s.find(term)
                if term_pos != -1:
                    context_start = max(0, term_pos - 15)
                    context_end = min(len(seg), term_pos + len(term) + 15)
                    context = seg[context_start:context_end].lower()
                    if not any(neg in context for neg in negation_zh + negation_en):
                        return True
            return False

        segments = re.split(r"[。；;\.!?\n]+", text)
        segments = [seg.strip() for seg in segments if seg.strip()]
        
        # Check current and next 2 sentences
        for i in range(len(segments)):
            if not segments[i]:
                continue
            
            # Check within next 2 sentences (more flexible)
            for j in range(i + 1, min(i + 3, len(segments))):
                if not segments[j]:
                    continue
                
                a, b = segments[i], segments[j]
                # Move/position -> attack
                if (has_terms_without_negation(a, move_terms_zh, move_terms_en) and 
                    has_terms_without_negation(b, attack_terms_zh, attack_terms_en)):
                    return True
                # Attack -> move
                if (has_terms_without_negation(a, attack_terms_zh, attack_terms_en) and 
                    has_terms_without_negation(b, move_terms_zh, move_terms_en)):
                    return True

        # Same sentence detection with adaptive threshold
        def find_terms_positions(text_input: str, terms: list[str]) -> list:
            positions = []
            search_text = text_input.lower()
            for term in terms:
                term_lower = term.lower()
                start = 0
                while True:
                    pos = search_text.find(term_lower, start)
                    if pos == -1:
                        break
                    # Check for negation around this position
                    context_start = max(0, pos - 15)
                    context_end = min(len(search_text), pos + len(term_lower) + 15)
                    context = search_text[context_start:context_end]
                    if not any(neg in context for neg in negation_zh + negation_en):
                        positions.append(pos)
                    start = pos + 1
            return positions

        move_positions = find_terms_positions(text, move_terms_zh + move_terms_en)
        attack_positions = find_terms_positions(text, attack_terms_zh + attack_terms_en)
        
        # Adaptive threshold based on text length
        base_threshold = 80
        text_length_factor = min(len(text) / 200, 2.0)  # Scale with text length, max 2x
        adaptive_threshold = int(base_threshold * text_length_factor)
        
        for move_pos in move_positions:
            for attack_pos in attack_positions:
                if abs(move_pos - attack_pos) <= adaptive_threshold:
                    return True

        return False

    async def _async_strategy_detection(self, assistant_text: str):
        """If strategy content is detected, report strategy_ping (throttling) to ENV."""
        import time
        # Throttling: at least 1 time per 2 seconds
        now = time.time()
        if (now - getattr(self, "_strategy_last_ping_ts", 0.0)) < 2.0:
            return
        # Keyword or sequence hit determines strategy
        # The two detection functions are now independent and orthogonal
        hit_keywords = self._contains_strategy_keywords(assistant_text)
        hit_sequence = self._contains_strategy_sequence(assistant_text)
        if not (hit_keywords or hit_sequence):
            return
        # Update throttling time after passing
        self._strategy_last_ping_ts = now
        evidence = assistant_text.strip()
        if len(evidence) > 120:
            evidence = evidence[:117] + "..."
        try:
            await self.tool_manager.execute_tool("perform_action", {
                "action": "strategy_ping",
                "params": {
                    "faction": self.faction,
                    # Sequence hit gives 1.0 points, otherwise 0.5 points
                    "score": 1.0 if hit_sequence else 0.5,
                    "evidence": evidence
                }
            })
        except Exception as e:
            console.print(f"⚠️ strategy_ping failed: {e}", style="yellow")
    # ==================== Strategy keyword detection and reporting End ====================


    # ==================== Tool Results Filtering Functions Start ====================
    def _filter_tool_result(self, function_name: str, result: Any, tool_arguments: Dict[str, Any] | None = None) -> Any:
        
        if not isinstance(result, dict):
            return result

        import copy
        data = copy.deepcopy(result)

        if function_name != "perform_action":
            return data

        # 1) 首选：基于 tool_arguments.action 的精确分流
        action = (tool_arguments or {}).get("action") if isinstance(tool_arguments, dict) else None
        if isinstance(action, str):
            action_norm = action.strip().lower()
        else:
            action_norm = None

        action_map = {
            "move": self._filter_move_result,
            "get_faction_state": self._filter_faction_state_result,
            "observation": self._filter_observation_result,
            "attack": self._filter_attack_result,
        }

        if action_norm in action_map:
            return action_map[action_norm](data)

        return data
    
    def _filter_observation_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Filter observation result, remove redundant fields"""
        import copy
        filtered_result = copy.deepcopy(result)
        
        if "unit_info" in filtered_result and isinstance(filtered_result["unit_info"], dict):
            unit_info = filtered_result["unit_info"]
            
            if "status" in unit_info and isinstance(unit_info["status"], dict):
                status = unit_info["status"]
                status.pop("morale", None)
                status.pop("fatigue", None)
            
            if "capabilities" in unit_info and isinstance(unit_info["capabilities"], dict):
                capabilities = unit_info["capabilities"]
                noise_capabilities = ["attack_points", "construction_points", "skill_points"]
                for noise_key in noise_capabilities:
                    capabilities.pop(noise_key, None)
            
            unit_info.pop("available_skills", None)
        
        if "visible_environment" in filtered_result and isinstance(filtered_result["visible_environment"], list):
            filtered_env = []
            for tile in filtered_result["visible_environment"]:
                if isinstance(tile, dict):
                    filtered_tile = {
                        "position": tile.get("position"),
                        "terrain": tile.get("terrain"),
                    }
                    
                    # Always include units field
                    units = tile.get("units", [])
                    filtered_tile["units"] = units
                    
                    # Simplify movement_accessibility - only keep if reachable
                    movement_access = tile.get("movement_accessibility", {})
                    if isinstance(movement_access, dict) and "reachable" in movement_access:
                        filtered_tile["reachable"] = movement_access["reachable"]
                    
                    # Simplify attack_range_info - only keep if in attack range
                    attack_info = tile.get("attack_range_info")
                    if isinstance(attack_info, dict) and "in_attack_range" in attack_info:
                        filtered_tile["attackable"] = attack_info["in_attack_range"]
                    elif attack_info is True or attack_info is False:
                        filtered_tile["attackable"] = attack_info
                    
                    filtered_env.append(filtered_tile)
            
            filtered_result["visible_environment"] = filtered_env
        
        return filtered_result
    
    def _filter_faction_state_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Filter faction_state result, remove redundant fields to save tokens"""
        import copy
        filtered_result = copy.deepcopy(result)
        filtered_result.pop("success", None)
        
        # 保留基本的阵营状态信息
        if "units" in filtered_result and isinstance(filtered_result["units"], list):
            filtered_units = []
            for unit in filtered_result["units"]:
                if isinstance(unit, dict):
                    filtered_unit = copy.deepcopy(unit)
                    
                    # 过滤 unit_status 中的噪声字段
                    if "unit_status" in filtered_unit and isinstance(filtered_unit["unit_status"], dict):
                        unit_status = filtered_unit["unit_status"]
                        # 移除 morale 和 fatigue，这些在其他filter中也被认为是噪声
                        unit_status.pop("morale", None)
                        unit_status.pop("fatigue", None)
                    
                    # 过滤 capabilities 中的冗余字段
                    if "capabilities" in filtered_unit and isinstance(filtered_unit["capabilities"], dict):
                        capabilities = filtered_unit["capabilities"]
                        # 移除 long_rest_resources，ENV中没有对应实现
                        capabilities.pop("long_rest_resources", None)
                        
                        # 也可以移除其他噪声字段（参考observation过滤器）
                        noise_capabilities = ["attack_points", "construction_points", "skill_points"]
                        for noise_key in noise_capabilities:
                            capabilities.pop(noise_key, None)
                    
                    # 移除 available_skills，通常是空数组，没有实际意义
                    filtered_unit.pop("available_skills", None)
                    
                    filtered_units.append(filtered_unit)
            
            filtered_result["units"] = filtered_units
        
        return filtered_result
    
    def _filter_move_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Filter move result, keep critical error or success information"""
        if not result.get("result", True):
            if "suggested_action" in result:
                essential_keys = {
                    "result", "details", "failure_reason", 
                    "current_movement_points", "required_movement_points",
                    "closest_reachable_position", "suggested_action", "suggestion"
                }
                filtered_result = {k: v for k, v in result.items() if k in essential_keys}
                return filtered_result
        # Success case: remove only success and message, keep others
        try:
            filtered = dict(result)
            if "success" in filtered:
                filtered.pop("success", None)
            if "message" in filtered:
                filtered.pop("message", None)
            # Remove verbose movement description path details to save tokens
            if "movement_descriptions" in filtered:
                filtered.pop("movement_descriptions", None)
            if "action_status" in filtered:
                filtered.pop("action_status", None)
            return filtered
        except Exception:
            return result
    
    def _filter_attack_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Filter attack result, keep only essential battle information to reduce token consumption"""
        if result.get("result", True):
            filtered_result = {
                "result": result.get("result"),
                "remaining_resources": result.get("remaining_resources")
            }
            
            # Process battle_summary
            if "battle_summary" in result and isinstance(result["battle_summary"], dict):
                battle_summary = result["battle_summary"]
                filtered_battle = {}
                
                # Extract essential attacker info
                if "attacker_info" in battle_summary:
                    attacker = battle_summary["attacker_info"]
                    filtered_battle["attacker_info"] = {
                        k: attacker.get(k) for k in ["unit_id", "unit_type", "faction", "position", "terrain"]
                        if k in attacker
                    }
                
                # Extract essential target info
                if "target_info" in battle_summary:
                    target = battle_summary["target_info"]
                    filtered_battle["target_info"] = {
                        k: target.get(k) for k in ["unit_id", "unit_type", "faction", "position", "terrain"]
                        if k in target
                    }
                
                # Extract essential battle result info
                if "battle_result" in battle_summary and isinstance(battle_summary["battle_result"], dict):
                    battle_result = battle_summary["battle_result"]
                    filtered_battle["battle_result"] = {
                        k: battle_result.get(k) for k in ["is_critical", "damage_dealt", "target_destroyed", "terrain_effects", "combat_log"]
                        if k in battle_result
                    }
                
                filtered_result["battle_summary"] = filtered_battle
            
            # Add essential tactical info with better naming
            if "tactical_info" in result and isinstance(result["tactical_info"], dict):
                tactical = result["tactical_info"]
                if "attack_was_effective" in tactical:
                    filtered_result["attack_was_effective"] = tactical["attack_was_effective"]
                if "target_strength_percentage" in tactical:
                    filtered_result["target_remaining_manpower"] = f"{tactical['target_strength_percentage']}%"
            
            return filtered_result
        
        return result


    async def _shrink_history(self, window: int = 5):
        # save the first system message
        system_msgs = [m for m in self.conversation_history if m.role == "system"][:1]
        # Hardcode: keep the first user message
        user_msgs = [m for m in self.conversation_history if m.role == "user"][:1]
        # get the last window messages from non-system messages
        non_system_msgs = [m for m in self.conversation_history if m.role != "system"]
        # 修改：找到最后一次 assistant 的消息，保留该消息及之后的所有消息；若不存在则退回窗口截取
        last_assistant_idx = None
        for i in range(len(non_system_msgs) - 1, -1, -1):
            if getattr(non_system_msgs[i], "role", None) == "assistant":
                last_assistant_idx = i
                break
        if last_assistant_idx is not None:
            tail = non_system_msgs[last_assistant_idx:]
        else:
            tail = non_system_msgs[-window:]
        
        self.conversation_history = system_msgs + user_msgs + tail
    # ==================== Tool Results Filtering Functions End ====================


    async def _register_agent_info(self):
        """Register agent information to environment"""
        try:
            config = self.llm_client.config
            
            registration_params = {
                "faction":  self.faction,
                "provider": config.provider,
                "model_id": config.model_id,
                "base_url": config.base_url or "unknown",
                "agent_id": getattr(self, 'agent_id', 'unknown'),
                "version": "1.0.0",  # Agent version
                "note": f"Agent using {config.provider}",
                # 添加 enable_thinking 字段
                "enable_thinking": config.enable_thinking
            }
            
            result = await self.tool_manager.execute_tool("perform_action", {
                "action": "register_agent_info",
                "params": registration_params
            })
            if result.get("success"):
                console.print(f"✅ Agent information registered successfully: {self.faction} faction - {config.provider}:{config.model_id} (thinking: {config.enable_thinking})", style="cyan")
            else:
                console.print(f"⚠️ Agent information registration failed: {result.get('message', 'unknown error')}", style="red")
            
        except Exception as e:
            console.print(f"❌ Agent information registration error: {e}", style="red")


    async def _report_llm_stats(self):
        """Report LLM API interaction statistics to ENV"""
        try:
            api_stats = self.llm_client.get_api_stats()
            console.print(f"📊 Report LLM API statistics: {api_stats}", style="cyan")
            
            result = await self.tool_manager.execute_tool("perform_action", {
                "action": "report_llm_stats",
                "params": {
                    "faction": self.faction,
                    "api_stats": api_stats,
                    "provider": self.llm_client.config.provider,
                    "model_id": self.llm_client.config.model_id
                }
            })
            
            if result.get("success"):
                console.print("✅ LLM statistics reported successfully", style="cyan")
            else:
                console.print(f"⚠️ LLM statistics reported failed: {result.get('message', 'unknown error')}", style="red")
                
        except Exception as e:
            console.print(f"❌ LLM statistics reported failed: {e}", style="red")

    async def stop(self):
        """Stop agent"""
        # Report LLM statistics before stopping
        await self._report_llm_stats()
        await self.llm_client.close()


    async def chat(self, user_prompt: str, max_iterations: Optional[int] = None) -> Dict[str, Any]:
        """Main chat loop"""
        if max_iterations:
            self.max_iterations = max_iterations

        if not self._agent_registered:
            await self._register_agent_info()
            self._agent_registered = True
        
        # Initialize conversation
        self.conversation_history = [
            Message(role="system", content=self.system_prompt)
        ]
        self.conversation_history.append(
            Message(role="user", content=user_prompt)
        )

        iterations = 0
        while iterations < self.max_iterations:
            iterations += 1
            
            # 🆕 Check if the game has ended
            try:
                status = RemoteContext.get_status() or {}
                # 🆕 Only display debug information when the status contains the game_ended field or an exception occurs
                if "game_ended" in status:
                    console.print(f"🔍 Status check (iteration {iterations}): {status}", style="dim cyan")
                if status.get("game_ended", False):
                    console.print(f"🏁 Game ended @iteration {iterations}, preparing to report LLM stats and exit", style="yellow bold")
                    # 游戏结束时确保解除等待，防止潜在阻塞，但不改变门控的语义状态
                    if not self._turn_gate.is_set():
                        self._set_turn_gate("game_ended - emergency")
                    await self.stop()
                    return {
                        "success": True,
                        "message": "Game ended, LLM stats reported",
                        "iterations": iterations,
                        "reason": "game_ended"
                    }
                # 🆕 Turn-start injection: 在每次循环开始时消费最新的回合开始事件
                # 注意：turn_start的实际处理逻辑已经统一到 _wait_for_turn_gate 中，避免重复检测
            except Exception as status_error:
                console.print(f"⚠️ Error checking game status: {status_error}", style="red")
            
            try:
                # 🆕 若处于等待下一回合期间，则暂停一切 LLM API 调用
                if not await self._wait_for_turn_gate():
                    continue  # 门控未开启或异常，跳过 LLM API 调用
                # 🆕 每回合 LLM API 调用预算：超过则强制 end_turn，防止弱模型无限调用不结束回合
                if self._api_calls_this_turn >= self.max_api_calls_per_turn:
                    console.print(f"🎫 Per-turn API call budget exhausted ({self.max_api_calls_per_turn}), triggering end_turn...", style="yellow")
                    try:
                        await self.tool_manager.execute_tool("end_turn", {})
                    except Exception as e:
                        console.print(f"⚠️ end_turn (budget) failed: {e}", style="yellow")
                    continue
                self._api_calls_this_turn += 1
                # Check if the conversation_history is too long, trim it if necessary
                console.print(f"🔍 Conversation history length: {len(self.conversation_history)}", style="cyan")
                if len(self.conversation_history) > 20:
                    await self._shrink_history(window=10)
                    console.print("🧹 Context overflow detected, history has been trimmed and continued", style="cyan")   

                # Get LLM response
                response = await self.llm_client.chat_completion(
                    messages=self.conversation_history,
                    tools=self.tool_manager.get_tool_definitions()
                )

                choice = response["choices"][0]
                message = choice["message"]
                finish_reason = choice["finish_reason"]
                
                console.print(f"╭─────────────────────────────────────────────────────── LLM response @iteration {iterations}: ────────────────────────────────────────────────────────╮", style="yellow")
                console.print(f"│ {json.dumps(response, indent=2, ensure_ascii=False)}", style="yellow", highlight=False)
                console.print(f"╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯", style="yellow")

                # Add assistant response to history
                assistant_message = Message(
                    role="assistant",
                    content=message.get("content", ""),
                    tool_calls=message.get("tool_calls")
                )
                self.conversation_history.append(assistant_message)

                # 🆕 Attempt strategy keyword detection and report after receiving LLM response
                console.print("🔍 Attempting strategy detection @iteration {iterations}", style="cyan")
                asyncio.create_task(self._async_strategy_detection(message.get("content", "")))
                console.print("🔍 Strategy detection completed", style="cyan")

                # === Detect text-based tool calls ===
                # Some models (like Qwen3-30B) put tool calls in content instead of tool_calls array
                tool_calls_to_use = message.get("tool_calls", [])
                if not tool_calls_to_use and message.get("content"):
                    console.print(f"🔧 Detecting text-based tool calls in content @iteration {iterations}: {message['content']}", style="cyan")
                    parsed_tool_calls = self._parse_text_based_tool_calls(message["content"])
                    if parsed_tool_calls:
                        console.print("🔧 Detected text-based tool calls, converting to standard format @iteration {iterations}", style="cyan")
                        self.conversation_history.append(
                            Message(
                                role="user", 
                                content="Note: You should not put the tool call information in the `content` field. You must follow the tool call format. Please try again.")
                        )
                        continue  # Only continue if tool calls are detected
                    else:
                        console.print("🔧 Undetected text-based tool calls. @iteration {iterations}", style="cyan")

                # 1) If there are tool calls, handle them — no matter the finish_reason
                if message.get("tool_calls"):
                    console.print(f"🔧 Handling tool calls @iteration {iterations}: {message['tool_calls']}", style="cyan")
                    await self._handle_tool_calls(message["tool_calls"])
                    continue

                # 2) Hit max length? Ask model to continue (or just continue loop)
                if finish_reason == "length":
                    # Option A: push a tiny user nudge to continue
                    self.conversation_history.append(
                        Message(
                            role="user", 
                            content="Note: The game is turn-based, you should think carefully and give the critical information of your strategy.")
                    )
                    continue

                # 3) Normal terminal cases
                if finish_reason in ("stop"):
                    self.conversation_history.append(
                        Message(
                            role="user", 
                            content="Note: You are the commander. You decide the strategy and the action. Do not ask for confirmation. After you get the enemy's coordinates, you should move all your units to the enemy's position and attack them.")
                    )
                    continue

                # 4) Normal terminal cases
                if finish_reason in ("content_filter"):
                    print(f"success: True, response: {message.get('content', '')}, iterations: {iterations}, finish_reason: {finish_reason}")
                    break

                # 5) an unexpected finish reason
                console.print(f"Unexpected finish reason @iteration {iterations}: {finish_reason}", style="red")
                return {
                    "success": False,
                    "error": f"Unexpected finish reason: {finish_reason}",
                    "iterations": iterations
                }
            except Exception as e:
                # Use global error logging function
                error_details = create_error_details(e, iteration=iterations, function_name="RoTKChatAgent.chat")
                
                if _is_account_balance_error(e, error_details):
                    console.print("🛑 Account balance error detected, stopping agent", style="red bold")
                    await self.stop()
                    return {
                        "success": False,
                        "error": str(e),
                        "error_details": error_details,
                        "iterations": iterations,
                        "reason": "account_balance_insufficient"
                    }

                # Check if it is a context overflow error
                if _is_context_overflow_error(e, error_details):
                    await self._shrink_history(window=40)
                    console.print("🧹 Context overflow error detected, history has been trimmed and continued", style="cyan")
                    continue                
                
                # Record error log
                log_file = log_error_to_file(error_details, display_console=True)
                
                return {
                    "success": False,
                    "error": str(e),
                    "error_details": error_details,
                    "iterations": iterations,
                    "error_log_file": log_file
                }
        # Max iterations reached
        asyncio.create_task(self._report_llm_stats())
        return {
            "success": False,
            "error": "Max iterations reached",
            "iterations": iterations
        }
  

class AgentDemo:
    """Agent client demo class - compatible with existing code"""

    def __init__(
        self,
        hub_url="ws://localhost:8000/ws/metaverse",
        env_id="env_1",
        agent_id="agent_1",
    ):
        self.hub_url = hub_url
        self.env_id = env_id
        self.agent_id = agent_id
        self.agent_client = None
        self.messages = []

        self.init_client()

    def init_client(self):
        # Create client
        self.agent_client = AgentClient(self.hub_url, self.env_id, self.agent_id)
        self.setup_hub_listeners()
        RemoteContext.set_client(self.agent_client)
        # Initialize state
        RemoteContext.set_status({"self_status": {}, "env_status": {}})

    def setup_hub_listeners(self):
        """Set event listeners"""

        def on_connect(data):
            message = f"✅ Agent connected successfully: {data}"
            console.print(message, style="cyan")
            self.messages.append(message)

        def on_message(data):
            message = f"📨 Agent received message: {data}"
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
                # 🔧 Fix: Update state instead of replace, preserve existing state fields
                try:
                    current_status = RemoteContext.get_status() or {}
                except:
                    current_status = {}
                current_status.update({"self_status": {f"Task{msg_data['id']}": outcome}})
                RemoteContext.set_status(current_status)
                message += f"\n   结果: {outcome}, 结果类型: {outcome_type}"
            elif msg_type == "game_end_notification":
                # 🆕 Handle game end notification
                console.print("🏁 Received game end notification, preparing to report LLM stats and exit", style="yellow bold")
                # 🔧 Fix: update status instead of replace, keep existing status fields
                try:
                    current_status = RemoteContext.get_status() or {}
                except:
                    current_status = {}
                current_status.update({"game_ended": True})
                RemoteContext.set_status(current_status)
                console.print(f"🔧 State updated: {current_status}", style="cyan")  # 🆕 Debug information
                message += f"\n    Game end notification: {msg_data}"
            elif msg_type == "turn_start":
                # 🆕 Handle turn start notification and store to status for agent loop to consume
                try:
                    current_status = RemoteContext.get_status() or {}
                except:
                    current_status = {}
                # 只保存最后一条 turn_start（幂等处理在 Agent 侧完成）
                current_status.update({"turn_start": {
                    "type": msg_type,
                    "faction": msg_data.get("faction"),
                    "turn_number": msg_data.get("turn_number"),
                    "timestamp": msg_data.get("timestamp"),
                    "message": msg_data.get("message")
                }})
                RemoteContext.set_status(current_status)
                console.print(f"📬 Received turn_start: {current_status.get('turn_start')}", style="cyan")
            # console.print(message, style="blue")
            self.messages.append(message)

        def on_disconnect(data):
            message = f"❌ Agent disconnected: {data}"
            console.print(message, style="red")
            self.messages.append(message)

        def on_error(data):
            message = f"⚠️ Agent error: {data}"
            msg_data = data.get("payload", {})
            error = msg_data.get("error", "Unknown error")
            console.print(message, style="red")
            # Only update id_map when msg_data has the id field
            if "id" in msg_data:
                RemoteContext.get_id_map().update({msg_data["id"]: error})
            self.messages.append(message)
            console.print("error handled", style="red")

        self.agent_client.add_hub_listener("connect", on_connect)
        self.agent_client.add_hub_listener("message", on_message)
        self.agent_client.add_hub_listener("disconnect", on_disconnect)
        self.agent_client.add_hub_listener("error", on_error)

    async def connect(self):
        """Create and connect Agent client"""
        console_system.print("🤖 Create Agent client", style="bold blue")
        console_system.print(f"📡 Server: {self.hub_url}")
        console_system.print(f"🌍 Environment ID: {self.env_id}")
        console_system.print(f"🆔 Agent ID: {self.agent_id}")
        console_system.print("=" * 50)

        # Connect
        console_system.print("🔗 Connecting to server...", style="cyan")
        try:
            await self.agent_client.connect()
            console_system.print("✅ Agent connected successfully!", style="bold cyan")

            # Wait for connection to stabilize
            await asyncio.sleep(1)
            return True
        except Exception as e:
            console_system.print(f"❌ Connection failed: {e}", style="bold red")
            return False

    def get_faction_from_env(self) -> str:
        """Get faction from environment variable, default to wei"""
        return os.environ.get("AGENT_FACTION", "wei").lower()

    def get_faction_info(self, faction: str) -> dict:
        """Get faction basic information"""
        faction_configs = {
            "wei": {"name": "魏", "enemy": "shu"},
            "shu": {"name": "蜀", "enemy": "wei"},
            "wu": {"name": "吴", "enemy": "wei"}
        }
        return faction_configs.get(faction, faction_configs["wei"])

    def load_prompt(self, name: str, base_dir: str = "rotk_agent/prompts") -> str:
        import pathlib
        path = pathlib.Path(base_dir) / f"{name}.md"
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    async def interactive_demo(self):
        # Get faction information from environment variable
        faction = self.get_faction_from_env()
        faction_info = self.get_faction_info(faction)
        opponent_info = self.get_faction_info(faction_info["enemy"])

        raw_prompt = self.load_prompt(name="system_prompt_turn_cn")
        tmpl = Template(raw_prompt)
        system_prompt = tmpl.safe_substitute(
            faction=faction,
            faction_name=faction_info["name"],
            opponent=faction_info["enemy"],
            opponent_name=opponent_info["name"],
        )

        user_prompt = f"""
**当前配置**:
- **我方势力**: {faction_info["name"]} ({faction})
- **主要敌人**: {opponent_info["name"]} ({faction_info["enemy"]})
- 你在使用工具的时候，建议附加简短的决策说明，以增加决策分指标。
- 了解当前敌我态势，思考对战策略，调动你的所有unit消灭所有敌人。
        """
# - 多用perform_action: "arguments": "{{"action":"get_faction_state","params":{{"faction":"wei"|"shu"|"wu"}}}}"了解当前敌我态势.

        count = 0
        while True:
            count += 1
            console.print(f"🔄 Launch {count}th expedition...", style="bold cyan")
            try:
                await asyncio.create_task(create_agent(faction, system_prompt, user_prompt))
                await asyncio.sleep(0.1)  # Short delay to view results

            except KeyboardInterrupt:
                print("\n👋 User interrupted, exiting")
                break
            except Exception as e:
                print(f"❌ Command execution error: {e}")

    def show_summary(self):
        """Show demo summary"""
        console_system.print("\n📊 Agent demo summary", style="bold blue")
        console_system.print("=" * 25)
        console_system.print(f"📈 Total messages: {len(self.messages)}")
        console_system.print(f"🆔 Agent ID: {self.agent_id}")
        console_system.print(f"🌍 Environment ID: {self.env_id}")

        if self.messages:
            console.print("\n📝 Message history (last 10):")
            for i, msg in enumerate(self.messages[-10:], 1):
                console.print(f"   {i}. {msg}")

    async def cleanup(self):
        """Clean up resources"""
        console_system.print("\n🧹 Cleaning up connection...", style="cyan")
        try:
            if self.agent_client:
                await self.agent_client.disconnect()
                console_system.print("✅ Agent connection closed", style="cyan")
        except Exception as e:
            console_system.print(f"⚠️ Error closing connection: {e}", style="red")

    async def run_interactive_demo(self):
        """Run interactive demo"""
        console_system.print(f"🎮 Agent interactive demo", style="bold blue")
        console_system.print("🎯 You can manually control the Agent to perform various actions", style="cyan")
        console_system.print("=" * 50)

        try:
            # Connect
            if not await self.connect():
                return
            # Launch interactive Agent demo
            await self.interactive_demo()

            # Show summary
            self.show_summary()

        except KeyboardInterrupt:
            print("\n⚠️ User interrupted demo")
        except Exception as e:
            print(f"\n❌ Error during demo: {e}")
        finally:
            await self.cleanup()


# ==================== Global error logging functionality ====================

def create_error_details(exception: Exception, **extra_context) -> Dict[str, Any]:
    """
    Create detailed error information dictionary
    
    Args:
        exception: Exception object
        **extra_context: Additional context information (such as iteration, function_name, etc.)
    
    Returns:
        Dictionary containing detailed error information
    """
    import traceback
    import httpx
    
    error_details = {
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "timestamp": datetime.now().isoformat()
    }
    
    # Add additional context information
    error_details.update(extra_context)
    
    # Get the complete stack trace
    tb_lines = traceback.format_exception(type(exception), exception, exception.__traceback__)
    error_details["full_traceback"] = "".join(tb_lines)
    
    # Add specific information for different types of exceptions
    if isinstance(exception, httpx.HTTPStatusError):
        error_details["http_status_code"] = exception.response.status_code
        error_details["response_headers"] = dict(exception.response.headers)
        try:
            error_details["response_body"] = exception.response.text
        except:
            error_details["response_body"] = "Cannot read response body"
            
    elif isinstance(exception, httpx.ConnectError):
        error_details["connection_error"] = "Cannot connect to server"
        error_details["request_url"] = str(exception.request.url) if hasattr(exception, 'request') and exception.request else "未知"
        
    elif isinstance(exception, httpx.TimeoutException):
        error_details["timeout_error"] = "Request timeout"
        error_details["request_url"] = str(exception.request.url) if hasattr(exception, 'request') and exception.request else "未知"
        
    elif isinstance(exception, httpx.RequestError):
        error_details["request_error"] = "Request error"
        error_details["request_url"] = str(exception.request.url) if hasattr(exception, 'request') and exception.request else "未知"
        
    elif isinstance(exception, TimeoutError):
        error_details["timeout_error"] = "Operation timeout"
        
    elif "JSON" in str(exception) or "json" in str(exception):
        error_details["json_error"] = "JSON parsing error, maybe the API return format is incorrect"
    
    return error_details


def log_error_to_file(error_details: Dict[str, Any], display_console: bool = True) -> Optional[str]:
    """
    Save error details to file and optionally display on console
    
    Args:
        error_details: Error details dictionary
        display_console: Whether to display error information on console
        
    Returns:
        Error log file path, if saving fails then return None
    """
    # 在控制台显示详细错误信息
    if display_console:
        console.print("=" * 80, style="red")
        console.print("🚨 Detailed error information", style="red bold")
        console.print("=" * 80, style="red")
        console.print(f"📍 Exception type: {error_details.get('exception_type', 'Unknown')}", style="red")
        console.print(f"📝 Error message: {error_details.get('exception_message', 'Unknown')}", style="red") 
        console.print(f"⏰ Occurrence time: {error_details.get('timestamp', 'Unknown')}", style="red")
        
        # Display function/iteration information (if available)
        if "function_name" in error_details:
            console.print(f"🔧 Occurred function: {error_details['function_name']}", style="red")
        if "iteration" in error_details:
            console.print(f"🔄 Current iteration: {error_details['iteration']}", style="red")
        
        # Display specific information based on exception type
        if "http_status_code" in error_details:
            console.print(f"🌐 HTTP status code: {error_details['http_status_code']}", style="red")
            console.print(f"📤 Response headers: {error_details['response_headers']}", style="yellow")
            console.print(f"📥 Response body: {error_details['response_body'][:500]}...", style="yellow")
            
        if "connection_error" in error_details:
            console.print(f"🔌 Connection error: {error_details['connection_error']}", style="red")
            console.print(f"🎯 Request URL: {error_details['request_url']}", style="yellow")
            
        if "timeout_error" in error_details:
            console.print(f"⏱️ Timeout error: {error_details['timeout_error']}", style="red")
            if "request_url" in error_details:
                console.print(f"🎯 Request URL: {error_details['request_url']}", style="yellow")
            
        if "json_error" in error_details:
            console.print(f"📋 JSON error: {error_details['json_error']}", style="red")
        
        # Display stack trace (optional)
        console.print("\n🔍 Complete stack trace:", style="red")
        console.print(error_details.get("full_traceback", ""), style="dim red")
    
    # Save error information to file
    try:
        error_log_file = f"error_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(error_log_file, 'w', encoding='utf-8') as f:
            json.dump(error_details, f, ensure_ascii=False, indent=2)
        
        if display_console:
            console.print(f"💾 Error details saved to: {error_log_file}", style="blue")
            console.print("=" * 80, style="red")
        
        return error_log_file
    except Exception as log_error:
        if display_console:
            console.print(f"⚠️ Cannot save error log: {log_error}", style="yellow")
        return None


def handle_error_with_logging(exception: Exception, **extra_context) -> Dict[str, Any]:
    """
    Function to handle exceptions and generate error logs
    
    Args:
        exception: Exception object
        **extra_context: Additional context information
        
    Returns:
        Dictionary containing error information
    """
    error_details = create_error_details(exception, **extra_context)
    log_file = log_error_to_file(error_details, display_console=True)
    
    return {
        "success": False,
        "error": str(exception),
        "error_details": error_details,
        "error_log_file": log_file
    }


# ==================== Tool function implementation ====================

async def get_env_response(request_id, timeout_seconds: float =60.0):
    """Get the response of the action execution, with timeout and ID conflict detection"""
    import time
    
    start_time = time.time()
    console.print(f"⏳ Waiting for ENV response ID: {request_id}, timeout set to: {timeout_seconds}s", style="cyan")
    # raise TimeoutError("test")
    while True:
        # Check if there is a response
        response = RemoteContext.get_id_map().get(request_id, None)
        if response is not None:
            # Remove the response from the mapping
            RemoteContext.get_id_map().pop(request_id, None)
            elapsed = time.time() - start_time
            console.print(f"✅ Received ENV response ID: {request_id}, elapsed time: {elapsed:.2f}s", style="cyan")
            return response
        
        # Check timeout
        elapsed = time.time() - start_time
        if elapsed >= timeout_seconds:
            console.print(f"⏰ ENV response timeout ID: {request_id}, elapsed time: {elapsed:.2f}s", style="red")
            console.print(f"🔍 Current ID mapping state: {dict(RemoteContext.get_id_map())}", style="red")
            timeout_error = TimeoutError(f"ENV response timeout: ID {request_id}, timeout time: {timeout_seconds}s")
            # Add additional context information to the exception object
            timeout_error.request_id = request_id
            timeout_error.elapsed_time = elapsed
            timeout_error.timeout_seconds = timeout_seconds
            raise timeout_error
        
        await asyncio.sleep(0.1)  # Waiting for response


async def perform_action(action: str, params: Any):
    """Execute action"""
    # 🚨 Defensive programming: prohibit calling end_turn via perform_action (should use the standalone end_turn tool)
    if action == "end_turn":
        raise ValueError("Invalid tool usage: 'end_turn' must be called via the standalone 'end_turn' tool, not 'perform_action'.")
    
    try:
        # Lightweight parameter validation before sending to ENV
        # _validate_action_payload(action, params)
        client = RemoteContext.get_client()
        request_id = await client.send_action(action, params)
        response = await get_env_response(request_id, timeout_seconds=5)
        
        # Smart delay logic: add appropriate waiting time based on action type and result
        delay_time = _calculate_action_delay(action, params, response)
        if delay_time > 0:
            console.print(f"⏳ Waiting for {delay_time}s to complete the action...", style="cyan")
            await asyncio.sleep(delay_time)

        return response
        
    except TimeoutError as e:
        console.print(f"⏰ [perform_action] Action execution timeout: {e}", style="red")
        handle_error_with_logging(
            e, 
            function_name="perform_action",
            action=action,
            params=params,
            request_id=getattr(e, 'request_id', 'unknown'),
            elapsed_time=getattr(e, 'elapsed_time', 'unknown'),
            timeout_seconds=getattr(e, 'timeout_seconds', 'unknown')
        )
        raise e
    except Exception as e:
        console.print(f"❌ [perform_action] Action execution error: {e}", style="red")
        handle_error_with_logging(
            e, 
            function_name="perform_action",
            action=action,
            params=params
        )
        raise e


async def get_available_actions() -> list[Dict[str, Any]]:
    """Get the current available actions"""
    result = await perform_action("get_action_list", {})
    return result


# ==================== Command processing function ====================

async def create_agent(faction: str = "wei", system_prompt: str = "", user_prompt: str = ""):
    # Load configuration and create independent chat agent
    try:
        config_path = os.path.join(os.getcwd(), ".configs.toml")
        console_system.print(f"Found configuration file in current working directory: {config_path}")
        console_system.print("Attempting to load configuration file")
        
        provider = os.environ.get("LLM_PROVIDER", "openai")
        llm_config = load_config(config_path, provider=provider)
        agent = RoTKChatAgent(llm_config, faction, system_prompt)
        
        # Register tools
        # agent.register_tool(
        #     name="get_available_actions",
        #     function=get_available_actions,
        #     description="获取可以执行的action列表。",
        #     parameters={"type": "object", "additionalProperties": False, "properties": {}, "required": []},
        # )
        
        agent.register_tool(
            name="perform_action",
            function=perform_action,
            description="Execute a specific action in the game environment.",
            parameters={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "The name of the action to execute.",
                        "enum": ["move", "attack", "get_faction_state"],
                    },
                    "params": {
                        "description": "Parameters object for the specified action.",
                        "oneOf": [
                            {
                                "type": "object",
                                "description": "Move a unit to a target position. Consumes Movement Points (MP).",
                                "additionalProperties": False,
                                "properties": {
                                    "unit_id": {"type": "integer", "minimum": 0, "description": "Friendly unit identifier."},
                                    "target_position": {
                                        "type": "object",
                                        "description": "Target position in flat-topped even-q offset coordinates.",
                                        "additionalProperties": False,
                                        "properties": {
                                            "col": {"type": "integer", "minimum": -7, "maximum": 7, "description": "Target column (even-q offset), range -7 to 7."},
                                            "row": {"type": "integer", "minimum": -7, "maximum": 7, "description": "Target row (even-q offset), range -7 to 7."}
                                        },
                                        "required": ["col", "row"]
                                    }
                                },
                                "required": ["unit_id", "target_position"],
                                "title": "move"
                            },
                            {
                                "type": "object",
                                "description": "Attack a target unit with a friendly unit. Consumes 1 Action Point (AP).",
                                "additionalProperties": False,
                                "properties": {
                                    "unit_id": {"type": "integer", "minimum": 0, "description": "Attacking friendly unit identifier."},
                                    "target_id": {"type": "integer", "minimum": 0, "description": "Target enemy unit identifier."}
                                },
                                "required": ["unit_id", "target_id"],
                                "title": "attack"
                            },
                            {
                                "type": "object",
                                "description": "Retrieve the status of the specified faction, including unit positions, HP, remaining AP and MP. Does not consume any points.",
                                "additionalProperties": False,
                                "properties": {
                                    "faction": {"type": "string", "enum": ["wei", "shu", "wu"], "description": "Faction to query (one of: wei, shu, wu)."}
                                },
                                "required": ["faction"],
                                "title": "get_faction_state"
                            }
                        ]
                    },
                },
                "required": ["action", "params"],
            },
        )
        
        async def end_turn():
            """End current turn to recover"""
            try:
                client = RemoteContext.get_client()
                request_id = await client.send_action("end_turn", {"faction": faction})
                response = await get_env_response(request_id, timeout_seconds=5)

                # Only close the turn gate when ENV confirms success
                # Accept either response["success"] == True or response["result"] == True
                resp_success = False
                if isinstance(response, dict):
                    resp_success = bool(response.get("success") is True or response.get("result") is True)

                if resp_success:
                    agent._clear_turn_gate("end_turn")
                    # Clear old turn_start event to avoid duplicate processing
                    try:
                        current_status = RemoteContext.get_status() or {}
                        if "turn_start" in current_status:
                            current_status.pop("turn_start", None)
                            RemoteContext.set_status(current_status)
                            console.print("🗑️ Cleared old turn_start event from RemoteContext", style="dim cyan")
                    except Exception as e:
                        console.print(f"⚠️ Failed to clear turn_start event: {e}", style="yellow")
                    console.print("⏹️ Turn ended. Pausing LLM calls until next turn_start...", style="yellow")
                else:
                    console.print(f"⚠️ end_turn response did not indicate success; gate remains OPEN. Response: {response}", style="yellow")
                # return response
                return {"result": "The current turn is over. Wait for the next turn_start to resume."}
            except Exception as e:
                console.print(f"❌ end_turn error: {e}", style="red")
                raise
        
        agent.register_tool(
            name="end_turn",
            function=end_turn,
            description="结束本回合，恢复行动力和移动力。",
            parameters={"type": "object", "properties": {}, "required": []},
        )

        # Execute chat task
        result = await agent.chat(user_prompt)
        console_system.print(f"Chat task completed: {result}")
        
        # # Clean up resources
        # await agent.stop()
        
    except (ValueError, KeyError, FileNotFoundError) as e:
        # 配置错误（如 Invalid provider、Model ID not found、配置文件缺失）：立即退出，避免无限重试
        console_system.print(f"Fatal LLM config error: {e}", style="red bold")
        console_system.print("Fix the provider name in match list or .configs.toml and retry. Exiting.", style="yellow")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        console_system.print(f"Chat process error: {e}", style="red")
        import traceback
        traceback.print_exc()


def _calculate_action_delay(action: str, params: Any, response: Any) -> float:
    """
    Calculate smart delay time based on action type, parameters and response result
    
    Args:
        action: Action type (e.g. "move", "attack" etc.)
        params: Action parameters
        response: Server response result
    
    Returns:
        float: Delay seconds, 0 means no delay
    """
    if not (isinstance(response, dict) and response.get("result", False)):
        return 0.0
    
    if action == "move":
        # Move action: estimate delay based on path length and distance
        return _calculate_move_delay(params, response)
    elif action == "attack":
        # Attack action: fixed delay to wait for attack animation
        return 0.2  # Attack animation usually takes less than 0.2 seconds
    elif action in ["get_faction_state", "observation", "get_action_list"]:
        # Query action: no delay
        return 0.0
    else:
        # Other action: conservative default delay
        return 0.1


def _calculate_move_delay(params: Any, response: Any) -> float:
    """Calculate the delay time for move action"""
    try:
        # Method 1: get estimated time from movement_details in response
        if isinstance(response, dict) and "movement_details" in response:
            estimated_duration = response["movement_details"].get("estimated_duration_seconds", 0)
            if estimated_duration > 0:
                # Add 10% buffer time to ensure animation completion
                return estimated_duration * 1.1
        
        # Method 2: estimate delay based on path length (backup)
        if isinstance(response, dict) and "movement_details" in response:
            path_length = response["movement_details"].get("path_length", 0)
            if path_length > 0:
                # Assuming animation speed is 2 squares/second, add buffer
                return path_length / 2.0 + 0.2
        
        # Method 3: calculate Manhattan distance based on start and target position (last fallback)
        if isinstance(params, dict) and "target_position" in params:
            # Here we cannot get the start position, use conservative estimate
            return 1.0  #  1 second delay
        
        # Default delay
        return 1.0
    
    except Exception as e:
        console.print(f"⚠️ Error calculating move delay: {e}", style="yellow")
        return 1.0

def _is_context_overflow_error(exc: Exception, error_details: dict | None = None) -> bool:
    """Check if it is a context/token overflow error (compatible with common error messages from multiple providers)"""
    import json
    txt = str(exc) if exc else ""
    blob = txt
    if error_details:
        try:
            blob += " " + json.dumps(error_details, ensure_ascii=False)
        except Exception:
            pass
    s = blob.lower()

    # Common trigger words (OpenAI/compatible stack/vLLM/SiliconFlow etc.)
    triggers = [
        "maximum context length",
        "max context length",
        "context length is",
        "context window",
        "prompt is too long",
        "too many tokens",
        "exceeds the maximum",
        "requested",  # with tokens
        "tokens"      # with requested
    ]
    if any(k in s for k in triggers):
        return True

    # extracted from the response (if saved to error_details)
    try:
        rsp = (error_details or {}).get("response_json") or {}
        msg = (rsp.get("error") or {}).get("message", "")
        if msg and any(k in msg.lower() for k in ["context", "token", "too long"]):
            return True
    except Exception:
        pass

    return False


def _is_account_balance_error(exc: Exception, error_details: dict | None = None) -> bool:
    context = f"{exc}"
    if error_details:
        context = f"{context}\n{error_details}"
    lowered = context.lower()
    return (
        ("balance" in lowered and "insufficient" in lowered)
        or "account balance" in lowered
        or "30001" in lowered
    )


def _validate_action_payload(action: str, params: Any) -> None:
    """Lightweight validation for perform_action payload.
    Raises ValueError with actionable hints for the LLM to self-correct.
    """
    try:
        if not isinstance(action, str):
            raise ValueError("'action' must be a string.")
        a = action.strip().lower()
        # Pass-through for system actions triggered by Agent (not by LLM)
        if a in ("register_agent_info", "report_llm_stats"):
            return
        if a not in ("move", "attack", "get_faction_state"):
            raise ValueError(f"Unsupported action: {action}.")

        if not isinstance(params, dict):
            raise ValueError("'params' must be an object.")

        if a == "move":
            unit_id = params.get("unit_id")
            target_position = params.get("target_position")
            if not isinstance(unit_id, int) or unit_id < 0:
                raise ValueError("move.params.unit_id is required and must be integer >= 0.")
            if not isinstance(target_position, dict):
                raise ValueError("move.params.target_position must be an object.")
            col = target_position.get("col")
            row = target_position.get("row")
            if not isinstance(col, int) or not isinstance(row, int):
                raise ValueError("move.target_position.col/row must be integers.")
            if not (0 <= col <= 14 and 0 <= row <= 14):
                raise ValueError("move.target_position.col/row must be within [0,14].")

        elif a == "attack":
            unit_id = params.get("unit_id")
            target_id = params.get("target_id")
            if not isinstance(unit_id, int) or unit_id < 0:
                raise ValueError("attack.params.unit_id is required and must be integer >= 0.")
            if not isinstance(target_id, int) or target_id < 0:
                raise ValueError("attack.params.target_id is required and must be integer >= 0.")

        elif a == "get_faction_state":
            f = params.get("faction")
            if f not in ("wei", "shu", "wu"):
                raise ValueError("get_faction_state.params.faction must be one of ['wei','shu','wu'].")
    except ValueError as e:
        # Surface a concise, helpful error to the LLM via exception
        raise


async def main():
    """Main function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Agent demo program")

    parser.add_argument(
        "--hub-url",
        default="ws://localhost:8000/ws/metaverse",
        help="Hub address (default: ws://localhost:8000/ws/metaverse)",
    )
    parser.add_argument(
        "--env-id", type=str, default="env_1", help="Environment ID (default: env_1)"
    )
    parser.add_argument(
        "--agent-id", type=str, default="agent_1", help="Agent ID (default: agent_1)"
    )
    parser.add_argument(
        "--provider", type=str, default="openai", help="Provider (default: openai)"
    )
    parser.add_argument(
        "--faction", 
        type=str, 
        default="wei", 
        choices=["wei", "shu", "wu"],
        help="faction to control (default: wei)"
    )

    args = parser.parse_args()

    console_system.print(f"📡 Hub: {args.hub_url}")
    console_system.print(f"🌍 Environment ID: {args.env_id}")
    console_system.print(f"🆔 Agent ID: {args.agent_id}")
    console_system.print(f"🔧 Provider: {args.provider}")
    console_system.print(f"⚔️ Faction: {args.faction}", style="bold red")
    console_system.print("=" * 60)

    # Set environment variables
    os.environ["LLM_PROVIDER"] = args.provider
    os.environ["AGENT_FACTION"] = args.faction

    # Create demo instance
    demo = AgentDemo(args.hub_url, args.env_id, args.agent_id)
    console_system.print("🎮 Interactive mode", style="bold blue")
    await demo.run_interactive_demo()


if __name__ == "__main__":
    asyncio.run(main())
