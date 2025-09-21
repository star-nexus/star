from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
import asyncio
import os
import json
from rich import console

console = console.Console()

@dataclass
class LLMConfig:
    """LLM Configuration"""
    provider: str  # "openai", "deepseek", "infinigence"
    model_id: str = "/home/Assets/models/gpt-oss-20b"
    api_key: str = "EMPTY"
    base_url: Optional[str] = "http://172.16.75.203:10000/v1/"
    temperature: float = 0.7

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

    def __init__(self, config: LLMConfig):
        self.config = config
        
        # Initialize OpenAI client
        if config.provider == "vllm":
            base_url = config.base_url or "http://172.16.75.203:10000/v1"
        else:
            base_url = config.base_url or "http://172.16.75.203:10000/v1"

        self.client = AsyncOpenAI(
            api_key="EMPTY",
            base_url=base_url
        )
    async def chat_completion(
        self,
        input_items: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]] = None,
        instructions: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send Responses API request"""
    
        payload = {
            "model": self.config.model_id,
            "input": input_items,
            "temperature": self.config.temperature,
        }
        
        if instructions:
            payload["instructions"] = instructions
        
            
        if tools:
            payload["tools"] = self._format_tools(tools)
            # Responses API doesn't use tool_choice and parallel_tool_calls
            # payload["tool_choice"] = "auto"
            # payload["parallel_tool_calls"] = True
            
        payload.update(kwargs)

        # 正确打印payload内容
        console.print(payload, style="green")

        # console.print(f"╭───────────────────────────────── LLM request payload: ───────────────────────────────────╮", style="magenta")
        # console.print(f"│ {json.dumps(payload['input'], indent=2, ensure_ascii=False)}", style="green", highlight=False)
        # console.print(f"╰───────────────────────────────────────────────────────────────────────────────────────╯", style="magenta")



        response = await self.client.responses.create(**payload)
        
        console.print(f"╭───────────────────────────────── LLM response: ───────────────────────────────────╮", style="magenta")
        console.print(f"│ {json.dumps(response.model_dump(), indent=2, ensure_ascii=False)}", style="yellow", highlight=False)
        console.print(f"╰───────────────────────────────────────────────────────────────────────────────────────╯", style="magenta")
        
        return response

    def _format_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """Format tool definitions to Responses API format"""
        formatted_tools = []
        for tool in tools:
            item = {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            # Enable strict mode when schema appears compatible
            try:
                params = tool.parameters or {}
                if isinstance(params, dict) and params.get("type") == "object":
                    if params.get("additionalProperties") is False and isinstance(params.get("required"), list):
                        item["strict"] = True
            except Exception:
                pass
            formatted_tools.append(item)
        return formatted_tools


class RoTKChatAgent:
    
    def __init__(
        self,
        llm_config,
        faction: str = "wei",
        system_prompt: str = "",
        reinject_reasoning: bool = True,
        reinject_output_text: bool = True,
    ):
        self.llm_client = LLMClient(llm_config)
        self.tool_manager = ToolManager()
        self.system_prompt = system_prompt
        self.conversation_history: List[Message] = []
        self.max_iterations = 1000
        self.faction = faction
        self.reinject_reasoning = reinject_reasoning
        self.reinject_output_text = reinject_output_text

        self._agent_registered = False
        

    async def _handle_tool_calls(self, tool_calls) -> List[Dict[str, Any]]:
        """Handle tool calls and return function_call_output items for Responses API."""
        console.print(f"🔧 Handling {len(tool_calls)} tool calls", style="cyan")

        def get_name(tc) -> str:
            # Responses API: tool_call is a Pydantic model object with direct attributes
            return tc.name

        # Support parallel execution of multiple perform_action calls
        parallel_execution = len(tool_calls) > 1 and all(get_name(tc) == "perform_action" for tc in tool_calls)

        if parallel_execution:
            console.print("⚡ Multiple perform_action calls detected, using parallel execution mode", style="cyan")
            return await self._handle_tool_calls_parallel(tool_calls)
        else:
            console.print("🔄 Using sequential execution mode", style="cyan")
            return await self._handle_tool_calls_sequential(tool_calls)
    
    async def _handle_tool_calls_sequential(self, tool_calls) -> List[Dict[str, Any]]:
        """Sequential execution of tool calls. Returns list of function_call_output items."""
        outputs: List[Dict[str, Any]] = []
        for tool_call in tool_calls:
            out = await self._execute_single_tool_call(tool_call)
            if out:
                outputs.append(out)
        return outputs
    
    async def _handle_tool_calls_parallel(self, tool_calls) -> List[Dict[str, Any]]:
        """Parallel execution of tool calls. Returns list of function_call_output items."""
        tasks = []
        for tool_call in tool_calls:
            task = asyncio.create_task(self._execute_single_tool_call(tool_call))
            tasks.append(task)
        results = await asyncio.gather(*tasks)
        return [r for r in results if r]
    
    async def _execute_single_tool_call(self, tool_call) -> Optional[Dict[str, Any]]:
        """Execute single tool call and return a function_call_output item for Responses API."""
        # Responses API format: tool_call is a Pydantic model object with direct attributes
        function_name = tool_call.name
        arguments_str = tool_call.arguments
        tool_call_id = tool_call.call_id

        console.print(f"╭───────────────────────────────── Executing tool '{function_name}' with arguments ───────────────────────────────────╮", style="magenta")
        console.print(f"│ {arguments_str}", style="magenta", highlight=False)
        console.print(f"╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯", style="magenta")

        try:
            # Parse parameters
            arguments = json.loads(arguments_str) if isinstance(arguments_str, str) and arguments_str else (arguments_str or {})

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

            return {
                "type": "function_call_output",
                "call_id": tool_call_id,
                "output":  json.dumps(result) # str(json.dumps(result, ensure_ascii=False))
            }

        except Exception as e:
            console.print(f"Tool execution error during tool call: {e}", style="red")
            return {
                "type": "function_call_output",
                "call_id": tool_call_id,
                "output": str({"error": str(e)}) # str(json.dumps({"error": str(e)}, ensure_ascii=False))
            }


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
                "enable_thinking": False
            }
            
            result = await self.tool_manager.execute_tool("perform_action", {"action": "register_agent_info"})
            if result:
                console.print(f"✅ Agent information registered successfully: {self.faction} faction - {config.provider}:{config.model_id} (thinking: {False})", style="cyan")
            else:
                console.print(f"⚠️ Agent information registration failed: {result}", style="red")
            
        except Exception as e:
            console.print(f"❌ Agent information registration error: {e}", style="red")

    def register_tool(self, name: str, function: Callable, description: str, parameters: Dict[str, Any]):
        """Register tool"""
        tool = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            function=function
        )
        self.tool_manager.register_tool(tool)

    async def chat(self, user_prompt: str, max_iterations: Optional[int] = None) -> Dict[str, Any]:
        """Main chat loop (Responses API)"""

        if not self._agent_registered:
            await self._register_agent_info()
            self._agent_registered = True
        
        if max_iterations:
            self.max_iterations = max_iterations

        # 初始化输入
        input_items: List[Dict[str, Any]] = [{"role": "user", "content": "You just need to randomly choose a tool to call."}]
        iterations = 0

        while iterations < 10:
            iterations += 1

            try:
                # 调用 LLM
                response = await self.llm_client.chat_completion(
                    input_items=input_items,
                    tools=self.tool_manager.get_tool_definitions(),
                    instructions=self.system_prompt,
                )

                reasoning_chunks = []
                for it in response.output:
                    if getattr(it, "type", None) == "reasoning":
                        for c in it.content:
                            if c.get("type") == "reasoning_text":
                                reasoning_chunks.append(c["text"])
                if reasoning_chunks:
                    input_items.append({
                        "role": "assistant",
                        "content": "[REASONING-LOG:]\n".join(reasoning_chunks).strip()
                    })
                        
                def _get(obj, key, default=None):
                    # 既支持 pydantic 对象，也支持 dict
                    if isinstance(obj, dict):
                        return obj.get(key, default)
                    return getattr(obj, key, default)

                # ③ 没有 function_call：把 output_text 收集为最终文本/或历史
                text_parts = []
                for it in response.output:
                    t = _get(it, "type")
                    if t == "message":
                        for c in (_get(it, "content") or []):
                            if _get(c, "type") == "output_text":
                                txt = _get(c, "text", "")
                                if txt:
                                    text_parts.append(txt)
                    elif t == "output_text":
                        for c in (_get(it, "content") or []):
                            txt = _get(c, "text", "")
                            if txt:
                                text_parts.append(txt)

                final_text = "".join(text_parts).strip()

                if final_text:
                    input_items.append({"role": "assistant", "content": final_text})
                    input_items.append({"role": "user", "content": "You just need to randomly choose a tool to call."})
                


                raw_calls = [it for it in response.output if getattr(it, "type", None) == "function_call"]

                def _clean_tool_name(name: str) -> str:
                    # 防止出现 perform_action<|channel|>commentary 之类脏 token
                    return name.split("<|", 1)[0].strip()

                if raw_calls:
                    # 执行工具时用清洗后的名字
                    cleaned_calls = []
                    for it in raw_calls:
                        # 构造一个“干净版”的 function_call item，用于回灌
                        cleaned_calls.append(type(it)(
                            **{**it.__dict__, "name": _clean_tool_name(it.name)}  # pydantic 对象/命名元组按你的响应结构调整
                        ))

                    # 先执行工具（内部也用清洗后的名字）
                    results = await self._handle_tool_calls(cleaned_calls)

                    if results:
                        input_items.extend(cleaned_calls)
                        input_items.extend(results)   


            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "iterations": iterations,
                }

        # ========== 6. 达到最大迭代数 ==========
        return {
            "success": False,
            "error": "Max iterations reached",
            "iterations": iterations
        }

async def perform_action(action: str, params: Dict[str, Any] | None = None):
    """Execute action"""
    # return f"{sign}: Next Tuesday you will befriend a baby otter."
    return json.dumps({"success": True, "state": "active", "faction": "wei", "total_units": 5, "alive_units": 5, 
"actionable_units": 5, "units": [{"unit_id": 231, "unit_type": "infantry", "faction": "wei", "position": {"col": 3,
"row": 3}, "status": {"current_count": 100, "max_count": 100, "health_percentage": 1.0, "morale": "normal", 
"fatigue": "none"}, "capabilities": {"movement": 10, "attack_range": 1, "vision_range": 2, "action_points": 2, 
"max_action_points": 2, "attack_points": 1, "construction_points": 1, "skill_points": 1}, "available_skills": []}, 
{"unit_id": 232, "unit_type": "archer", "faction": "wei", "position": {"col": 4, "row": 3}, "status": 
{"current_count": 100, "max_count": 100, "health_percentage": 1.0, "morale": "normal", "fatigue": "none"}, 
"capabilities": {"movement": 10, "attack_range": 3, "vision_range": 4, "action_points": 2, "max_action_points": 2, 
"attack_points": 1, "construction_points": 1, "skill_points": 1}, "available_skills": []}, {"unit_id": 233, "unit_type": 
"archer", "faction": "wei", "position": {"col": 4, "row": 2}, "status": {"current_count": 100, "max_count": 100, 
"health_percentage": 1.0, "morale": "normal", "fatigue": "none"}, "capabilities": {"movement": 10, "attack_range": 3,
"vision_range": 4, "action_points": 2, "max_action_points": 2, "attack_points": 1, "construction_points": 1, 
"skill_points": 1}, "available_skills": []}, {"unit_id": 234, "unit_type": "archer", "faction": "wei", "position": 
{"col": 3, "row": 2}, "status": {"current_count": 100, "max_count": 100, "health_percentage": 1.0, "morale": 
"normal", "fatigue": "none"}, "capabilities": {"movement": 10, "attack_range": 3, "vision_range": 4, "action_points":
2, "max_action_points": 2, "attack_points": 1, "construction_points": 1, "skill_points": 1}, "available_skills": []}, 
{"unit_id": 235, "unit_type": "cavalry", "faction": "wei", "position": {"col": 2, "row": 3}, "status": 
{"current_count": 100, "max_count": 100, "health_percentage": 1.0, "morale": "normal", "fatigue": "none"}, 
"capabilities": {"movement": 15, "attack_range": 1, "vision_range": 3, "action_points": 2, "max_action_points": 2, 
"attack_points": 1, "construction_points": 1, "skill_points": 1}, "available_skills": []}]})
        


async def get_available_actions() -> list[Dict[str, Any]]:
    payload = json.loads(await perform_action("get_action_list", {}))
    return payload

async def create_agent(faction: str = "wei", system_prompt: str = "", user_prompt: str = ""):
    # Load configuration and create independent chat agent
    try:
        config_path = os.path.join(os.getcwd(), ".configs.toml")
        console.print(f"Found configuration file in current working directory: {config_path}")
        console.print("Attempting to load configuration file")
        
        provider = os.environ.get("LLM_PROVIDER", "vllm2")
        llm_config = LLMConfig(provider=provider, model_id="/home/Assets/models/gpt-oss-20b", api_key=os.environ.get("EMPTY"), base_url="http://172.16.75.203:10000/v1")
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
                        "enum": ["move", "attack", "get_faction_state"],
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
    
    except Exception as e:
        console.print(f"Chat process error: {e}", style="red")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(create_agent())