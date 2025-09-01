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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from protocol import AgentClient

# 配置 rich 库
from rich.console import Console
from rich import print_json

console = Console()


@dataclass
class LLMConfig:
    """LLM Configuration"""
    provider: str  # "openai", "deepseek", "infinigence"
    model_id: str
    api_key: str
    base_url: Optional[str] = None
    temperature: float = 0.2
    max_tokens: Optional[int] = None
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
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = httpx.AsyncClient()
        
        # LLM API interaction statistics
        # Count the number of interactions at the beginning of the method to ensure all requests are recorded
        self.api_call_count = 0  # Total number of calls
        self.api_success_count = 0  # Number of successful calls
        self.api_error_count = 0  # Number of failed calls
        
        if config.provider == "openai":
            self.base_url = config.base_url or "https://api.openai.com/v1"
        elif config.provider == "deepseek":
            self.base_url = "https://api.deepseek.com"
        elif config.provider == "infinigence":
            self.base_url = "https://cloud.infini-ai.com/maas/v1"
        elif config.provider == "siliconflow":
            self.base_url = "https://api.siliconflow.cn/v1"
        elif config.provider == "vllm":
            self.base_url = config.base_url or "http://172.16.75.202:10000/v1"
        else:
            self.base_url = config.base_url or "https://api.openai.com/v1"

        self.config_thinking = False

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
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }
        
        if self.config_thinking:
            if self.config.provider == "siliconflow":
                payload["enable_thinking"] = bool(self.config.enable_thinking)    
            elif self.config.provider.startswith("vllm"):
                payload["chat_template_kwargs"] = {
                        "enable_thinking": bool(self.config.enable_thinking)
                    }
            
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
        self.api_call_count += 1
        
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
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
                self.api_error_count += 1
                raise Exception(f"LLM API error: {response.status_code} - {error_message}")
                
            response_data = response.json()
            # Count successful API calls
            self.api_success_count += 1
            return response_data
            
        except httpx.ConnectError as e:
            # Count failed API calls
            self.api_error_count += 1
            error_msg = f"Cannot connect to {self.config.provider} API server: {self.base_url}"
            console.print(f"🔌 Connection error: {error_msg}", style="red")
            console.print(f"Please check network connection and API server status", style="yellow")
            raise Exception(error_msg) from e
            
        except httpx.TimeoutException as e:
            # Count failed API calls
            self.api_error_count += 1
            error_msg = f"{self.config.provider} API request timeout (>180 seconds)"
            console.print(f"⏱️ Timeout error: {error_msg}", style="red")
            console.print(f"Please check network status or try again", style="yellow")
            raise Exception(error_msg) from e
            
        except httpx.HTTPStatusError as e:
            # Count failed API calls
            self.api_error_count += 1
            error_msg = f"{self.config.provider} API HTTP error: {e.response.status_code}"
            console.print(f"🌐 HTTP error: {error_msg}", style="red")
            raise Exception(error_msg) from e
            
        except Exception as e:
            # Count failed API calls
            self.api_error_count += 1
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
            "total_calls": self.api_call_count,
            "successful_calls": self.api_success_count,
            "failed_calls": self.api_error_count,
            "success_rate": round(self.api_success_count / self.api_call_count * 100, 2) if self.api_call_count > 0 else 0.0
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
    temperature = provider_config.get("temperature", 0.7)
    max_tokens = provider_config.get("max_tokens", 1000)
    enable_thinking = provider_config.get("enable_thinking", False)
    
    return LLMConfig(
        provider=provider,
        model_id=model_id,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        enable_thinking=enable_thinking
    )


class RoTKChatAgent:
    
    def __init__(self, llm_config: LLMConfig, faction: str = "wei", system_prompt: str = ""):
        self.llm_client = LLMClient(llm_config)
        self.tool_manager = ToolManager()
        self.system_prompt = system_prompt
        self.conversation_history: List[Message] = []
        self.max_iterations = 100
        self.faction = faction
        
        self._history_lock = asyncio.Lock()
        self._agent_registered: bool = False
        
        self._strategy_last_ping_ts: float = 0.0
        
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
            
            # Execute tool
            result = await self.tool_manager.execute_tool(function_name, arguments)
            
            console.print(f"╭──────────────────────────────── Tool '{function_name}' Result ────────────────────────────────╮", style="magenta")
            console.print(f"│ {json.dumps(result, indent=2, ensure_ascii=False)}", style="magenta", highlight=False)
            console.print(f"╰───────────────────────────────────────────────────────────────────────────────────────────────╯", style="magenta")
            

            filtered_result = self._filter_tool_result(function_name, result)
            
            tool_message = Message(
                role="tool",
                content=json.dumps(filtered_result, ensure_ascii=False),
                tool_call_id=tool_call_id
            )
            async with self._history_lock:
                self.conversation_history.append(tool_message)
            
        except Exception as e:
            console.print(f"Tool execution error during tool call: {e}", style="red")
            # Add error information to conversation history (using lock to protect parallel access)
            error_message = Message(
                role="tool",
                content=json.dumps({"error": str(e)}, ensure_ascii=False),
                tool_call_id=tool_call_id
            )
            # continue chat with LLM even if there is an error
            async with self._history_lock:
                self.conversation_history.append(error_message)

    # ==================== Strategy keyword detection and reporting ====================
    def _contains_strategy_keywords(self, text: str) -> bool:
        """Detects basic strategy thinking, defined by the presence of keywords and structure words."""
        if not text:
            return False
        t = text.lower()
        zh_keys = [
            "策略", "战略", "战术", "推进", "收缩", "防守", "进攻", "包抄", "侧翼", "伏击", "牵制",
            "佯攻", "撤退", "补给", "集结", "兵力部署", "路线", "优先级", "据点", "卡位", "占领",
            "固守", "视野", "地形优势", "补给线", "防线", "桥头堡", "绕后", "夹击", "高地", " chokepoint",
            "协同", "集火", "分兵"
        ]
        en_keys = [
            "strategy", "strategic", "tactic", "tactical", "plan", "objective", "priority",
            "advance", "retreat", "hold", "defend", "attack", "flank", "ambush", "harass",
            "pin down", "fix-in-place", "regroup", "supply", "chokepoint", "terrain advantage",
            "strongpoint", "encircle"
        ]
        # 1. Must contain strategy keywords
        key_hit = any(k in text for k in zh_keys) or any(k in t for k in en_keys)
        if not key_hit:
            return False
            
        # 2. Must also contain structure words to be considered as basic strategy thinking
        structure_terms = ["先", "然后", "再", "首先", "优先", "目标", "步骤", "顺序", "选择", "方案", "计划",
                           "first", "then", "next", "priority", "goal", "objective", "step", "order"]
        structure_hit = any(term in text for term in structure_terms) or any(term in t for term in structure_terms)
        
        return structure_hit

    def _contains_strategy_sequence(self, text: str) -> bool:
        """Detect sequence-based strategy phrases, such as "position/move -> attack" or "attack -> move"."""
        if not text:
            return False
        import re
        t = text.lower()

        # Chinese sequence regular expression (limited to≤20 characters)
        zh_patterns = [
            r"(移动|前进|靠近|靠拢|调整|转移|推进|到达).{0,20}(攻击|开火|打击|交战|冲锋|压制|集火|歼灭|突击)",
            r"(位置|坐标).{0,20}(攻击|开火|打击|交战)",
            r"(攻击|开火|打击|交战|冲锋|压制|集火|突击).{0,20}(移动|前进|靠近|靠拢|调整|转移|撤退|推进|到达)",
        ]
        # English sequence regular expression (match in lowercase text)
        en_patterns = [
            r"(move|advance|relocate|close in|position).{0,20}(attack|engage|fire|strike|assault)",
            r"(attack|engage|fire|strike|assault).{0,20}(move|advance|relocate|retreat|position)",
        ]

        for pat in zh_patterns:
            if re.search(pat, text):
                return True
        for pat in en_patterns:
            if re.search(pat, t):
                return True

        # Sentence sequence detection: previous sentence contains move/position, next sentence contains attack; or vice versa
        move_terms_zh = ["移动", "前进", "靠近", "靠拢", "调整", "转移", "推进", "到达", "位置", "坐标", "观察", "侦查"]
        attack_terms_zh = ["攻击", "开火", "打击", "交战", "冲锋", "压制", "集火", "歼灭", "突击", "支援", "协同", "集中火力"]
        move_terms_en = ["move", "advance", "relocate", "close in", "position", "coordinate", "retreat"]
        attack_terms_en = ["attack", "engage", "fire", "strike", "assault", "charge", "suppress"]

        segments = re.split(r"[。；;\.!?\n]+", text)
        def has_any(seg: str, terms_zh: list[str], terms_en: list[str]) -> bool:
            s = seg.lower()
            if any(k in seg for k in terms_zh):
                return True
            if any(k in s for k in terms_en):
                return True
            return False

        for i in range(len(segments) - 1):
            a = segments[i].strip()
            b = segments[i + 1].strip()
            if not a or not b:
                continue
            # Move/position -> attack
            if has_any(a, move_terms_zh, move_terms_en) and has_any(b, attack_terms_zh, attack_terms_en):
                return True
            # Attack -> move
            if has_any(a, attack_terms_zh, attack_terms_en) and has_any(b, move_terms_zh, move_terms_en):
                return True

        # Same sentence index order detection (relaxed threshold)
        # First appear any move/position word, then appear any attack word, or vice versa
        def first_index(seg: str, terms: list[str]) -> int:
            idxs = []
            ls = seg.lower()
            for term in terms:
                pos = seg.find(term)
                if pos == -1:
                    pos = ls.find(term)
                if pos != -1:
                    idxs.append(pos)
            return min(idxs) if idxs else -1

        move_idx = first_index(text, move_terms_zh + move_terms_en)
        attack_idx = first_index(text, attack_terms_zh + attack_terms_en)
        if move_idx != -1 and attack_idx != -1 and abs(attack_idx - move_idx) <= 80:
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
    
    def _filter_tool_result(self, function_name: str, result: Any) -> Any:
        """Filter tool results, remove redundant information to keep conversation history concise"""
        if not isinstance(result, dict):
            return result
        
        import copy
        filtered_result = copy.deepcopy(result)
        
        if function_name == "perform_action":
            if "visible_environment" in filtered_result and "unit_info" in filtered_result:
                filtered_result = self._filter_observation_result(filtered_result)
            elif "faction" in filtered_result and "units" in filtered_result and "total_units" in filtered_result:
                filtered_result = self._filter_faction_state_result(filtered_result)
            elif "message" in filtered_result and ("moved successfully" in str(filtered_result.get("message", "")) or 
                                                  "failure_reason" in filtered_result):
                filtered_result = self._filter_move_result(filtered_result)
            elif "battle_summary" in filtered_result and "casualties_inflicted" in filtered_result:
                filtered_result = self._filter_attack_result(filtered_result)
        
        return filtered_result
    
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
        """Filter faction_state result"""
        return result
    
    def _filter_move_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Filter move result, keep critical error or success information"""
        if not result.get("success", True):
            if "suggested_action" in result:
                essential_keys = {
                    "success", "message", "failure_reason", 
                    "current_movement_points", "required_movement_points",
                    "closest_reachable_position", "suggested_action", "suggestion"
                }
                filtered_result = {k: v for k, v in result.items() if k in essential_keys}
                return filtered_result
        
        return result
    
    def _filter_attack_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Filter attack result"""
        if result.get("success", True):
            essential_keys = {
                "success", "message", "battle_summary", 
                "remaining_resources", "tactical_info"
            }
            filtered_result = {k: v for k, v in result.items() if k in essential_keys}
            
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


    async def _shrink_history(self, window: int = 40):
        # save the first system message
        system_msgs = [m for m in self.conversation_history if m.role == "system"][:1]
        # Hardcode: keep the first user message
        user_msgs = [m for m in self.conversation_history if m.role == "user"][:1]
        # get the last window messages from non-system messages
        non_system_msgs = [m for m in self.conversation_history if m.role != "system"]
        tail = non_system_msgs[-window:]
        
        self.conversation_history = system_msgs + user_msgs + tail


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
                "note": f"Agent using {config.provider}"
            }
            result = await self.tool_manager.execute_tool("perform_action", {
                "action": "register_agent_info",
                "params": registration_params
            })
            if result.get("success"):
                console.print(f"✅ Agent information registered successfully: {self.faction} faction - {config.provider}:{config.model_id}", style="cyan")
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
                    await self.stop()
                    return {
                        "success": True,
                        "message": "Game ended, LLM stats reported",
                        "iterations": iterations,
                        "reason": "game_ended"
                    }
            except Exception as status_error:
                console.print(f"⚠️ Error checking game status: {status_error}", style="red")
            
            try:
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
                    if iterations == 10 or iterations == 70:
                        self.conversation_history.append(Message(role="user", content="After getting the enemy coordinates, move all your units to the enemy's position and attack them once they are in range."))
                    continue  # keep the loop going

                # 2) Hit max length? Ask model to continue (or just continue loop)
                if finish_reason == "length":
                    # Option A: push a tiny user nudge to continue
                    self.conversation_history.append(
                        Message(
                            role="user", 
                            content="Note: If you need to call tools, please call them directly or with only critical explanation.")
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
        console.print("🤖 Create Agent client", style="bold blue")
        console.print(f"📡 Server: {self.hub_url}")
        console.print(f"🌍 Environment ID: {self.env_id}")
        console.print(f"🆔 Agent ID: {self.agent_id}")
        console.print("=" * 50)

        # Connect
        console.print("🔗 Connecting to server...", style="cyan")
        try:
            await self.agent_client.connect()
            console.print("✅ Agent connected successfully!", style="bold cyan")

            # Wait for connection to stabilize
            await asyncio.sleep(1)
            return True
        except Exception as e:
            console.print(f"❌ Connection failed: {e}", style="bold red")
            return False

    def get_faction_from_env(self) -> str:
        """Get faction from environment variable, default to wei"""
        return os.environ.get("AGENT_FACTION", "wei").lower()

    def get_faction_info(self, faction: str) -> dict:
        """Get faction basic information"""
        faction_configs = {
            "wei": {"name": "魏", "enemy": "蜀 (shu)"},
            "shu": {"name": "蜀", "enemy": "魏 (wei)"},
            "wu": {"name": "吴", "enemy": "魏 (wei)"}
        }
        return faction_configs.get(faction, faction_configs["wei"])

    async def interactive_demo(self):
        # Get faction information from environment variable
        faction = self.get_faction_from_env()
        faction_info = self.get_faction_info(faction)
        
        system_prompt = f"""
        # 核心规则

        ## 1. 目标与阵营
        - 你是 **{faction_info["name"]} ({faction})** 阵营的指挥官，目标是指挥己方单位消灭所有 **{faction_info["enemy"]}** 敌军。  
        - 游戏为 **即时制**：双方可同时操作，需要快速反应。

        ## 2. 地图与坐标
        - 地图：15×15 六边形格，**flat-topped even-q offset** 坐标 `(col,row)`。  
        - 轴向规则：`col` 右正、左负；`row` 上正、下负。  
        - 邻居坐标：
        - 若 `col` 偶数: `(c+1,r) (c+1,r-1) (c,r-1) (c-1,r-1) (c-1,r) (c,r+1)`  
        - 若 `col` 奇数: `(c+1,r+1) (c+1,r) (c,r-1) (c-1,r) (c-1,r+1) (c,r+1)`  
        - 距离：offset→axial (`q=c`, `r=r-floor(c/2)`)，再计算  
        `d = (|dq|+|dr|+|d(q+r)|)/2`。  
        - **禁止** 使用欧式/曼哈顿/切比雪夫距离。攻击/移动必须用 hex 距离验证。

        ## 3. 工具调用规范
        - **必须**使用 `tool_calls`，不得把 JSON 写在 `content`。  
        - **参数格式**：`function.arguments` 是单层 JSON 对象，绝不能带反斜杠或外层引号。  
        - **禁止**：
        - 在 `perform_action` 内调用 `get_available_actions`。  
        - 在 `content` 输出 JSON/工具调用。  
        - 臆造 `unit_id`、`target_id`、坐标等数据。必须先通过工具获取。  

        ### 工具列表
        - **get_available_actions**: 获取当前可执行动作，参数 `{{}}`。  
        - **perform_action**: 执行动作，参数体：
        - `{{"action":"move","params":{{"unit_id":<ID>,"target_position":{{"col":X,"row":Y}}}}}}`  
        - `{{"action":"attack","params":{{"unit_id":<ID>,"target_id":<ENEMY_ID>}}}}`  
        - `{{"action":"get_faction_state","params":{{"faction":"{faction}"|"shu"|"wu"}}}}`  
        - `{{"action":"observation","params":{{"unit_id":<ID>,"observation_level":"basic"}}}}`  
        - **stop_running**: 暂停一回合恢复 AP，参数 `{{}}`。

        ### 并行调用
        - 允许一次回复中包含 **多个 tool_calls**（如对多个单位同时 observation/move/attack）。  
        - 遇到独立操作时，**合并到同一轮**。  
        - 串行仅用于前一步结果必须依赖时。  

        ## 4. 前置检查清单（执行顺序）
        1. `get_available_actions`  
        2. `perform_action` → `{{"action":"get_faction_state","params":{{"faction":"{faction}"}}}}`  
        3. `perform_action` → `{{"action":"get_faction_state","params":{{"faction":"shu"}}}}`（如果敌军）  
        4. 针对每个己方单位：`perform_action` → `{{"action":"observation","params":{{"unit_id":<ID>,"observation_level":"basic"}}}}`

        ## 5. 推荐 OODA 流程
        1. **观察 (Observe)**：执行前置检查，持续更新状态。  
        2. **判断 (Orient)**：确定威胁/机会，精炼描述即可。  
        3. **决策 (Decide)**：规划行动（先攻后移或先移后攻），简洁表述。  
        4. **行动 (Act)**：调用 `perform_action` 完成操作。  
        5. **评估 (Assess)**：若失败（AP不足/超距/ID错误等），立刻回到观察阶段并修正。

        ## 6. 行动点 (AP)
        - move / attack 消耗 AP；AP 会自动恢复。行动规划需考虑 AP。  
        """

        user_prompt = f"""
    **当前配置**:
    - **势力**: {faction_info["name"]} ({faction}) - 我方
    - **主要敌人**: {faction_info["enemy"]}
    - 你在使用工具的时候，建议附加简短的决策说明，以增加决策分指标。
    - 多用perform_action: "arguments": "{{"action":"get_faction_state","params":{{"faction":"wei"|"shu"|"wu"}}}}"了解当前态势，然后调动所有单位积极进攻，消灭敌人。
        """
    
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
        console.print("\n📊 Agent demo summary", style="bold blue")
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
        console.print("\n🧹 Cleaning up connection...", style="cyan")
        try:
            if self.agent_client:
                await self.agent_client.disconnect()
                console.print("✅ Agent connection closed", style="cyan")
        except Exception as e:
            console.print(f"⚠️ Error closing connection: {e}", style="red")

    async def run_interactive_demo(self):
        """Run interactive demo"""
        console.print(f"🎮 Agent interactive demo", style="bold blue")
        console.print("🎯 You can manually control the Agent to perform various actions", style="cyan")
        console.print("=" * 50)

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
    try:
        client = RemoteContext.get_client()
        request_id = await client.send_action(action, params)
        response = await get_env_response(request_id, timeout_seconds=0.001)
        
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
        console.print(f"Found configuration file in current working directory: {config_path}")
        console.print("Attempting to load configuration file")
        console.print(config_path)
        
        provider = os.environ.get("LLM_PROVIDER", "openai")
        llm_config = load_config(config_path, provider=provider)
        agent = RoTKChatAgent(llm_config, faction, system_prompt)
        
        # Register tools
        agent.register_tool(
            name="get_available_actions",
            function=get_available_actions,
            description="获取可以执行的action列表。",
            parameters={"type": "object", "additionalProperties": False, "properties": {}, "required": []},
        )
        
        agent.register_tool(
            name="perform_action",
            function=perform_action,
            description="在游戏环境中执行一个特定的动作。",
            parameters={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "要执行的动作的名称。",
                        "enum": ["move", "attack", "get_faction_state", "observation"],
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
            """Game over detected, agent should stop"""
            return {"message": "You chose to stop running. Take a reset and start again."}
        
        agent.register_tool(
            name="stop_running",
            function=stop_running,
            description="暂停一回合以恢复行动力。行动力已恢复，请继续进行。",
            parameters={"type": "object", "properties": {}, "required": []},
        )

        # Execute chat task
        result = await agent.chat(user_prompt)
        console.print(f"Chat task completed: {result}")
        
        # Clean up resources
        await agent.stop()
        
    except Exception as e:
        console.print(f"Chat process error: {e}", style="red")
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
    if not isinstance(response, dict) or not response.get("success", False):
        # No delay when action fails
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

    console.print(f"📡 Hub: {args.hub_url}")
    console.print(f"🌍 Environment ID: {args.env_id}")
    console.print(f"🆔 Agent ID: {args.agent_id}")
    console.print(f"🔧 Provider: {args.provider}")
    console.print(f"⚔️ Faction: {args.faction}", style="bold red")
    console.print("=" * 60)

    # Set environment variables
    os.environ["LLM_PROVIDER"] = args.provider
    os.environ["AGENT_FACTION"] = args.faction

    # Create demo instance
    demo = AgentDemo(args.hub_url, args.env_id, args.agent_id)
    console.print("🎮 Interactive mode", style="bold blue")
    await demo.run_interactive_demo()


if __name__ == "__main__":
    asyncio.run(main())
