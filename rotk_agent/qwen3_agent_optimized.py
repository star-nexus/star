"""
优化版 qwen3_agent - 基于事件驱动+插件化架构
主要优化：
1. 事件驱动响应处理
2. 插件化处理器系统  
3. 异步策略检测
4. 统一响应处理框架
5. 改进的日志和错误处理
"""

import asyncio
import argparse
from contextvars import ContextVar
from datetime import datetime
import os
import sys
import json
import httpx
import toml
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from protocol import AgentClient

# 配置 rich 库
from rich.console import Console
from rich import print_json

console = Console()

# ==================== 配置和数据类 ====================

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

@dataclass
class ResponseProcessingConfig:
    """响应处理配置"""
    enable_detailed_logging: bool = True
    enable_strategy_detection: bool = True
    async_strategy_detection: bool = True
    log_response_content: bool = False
    strategy_detection_threshold: float = 0.5
    max_log_content_length: int = 200

# ==================== 优化的响应处理系统 ====================
# 简化事件系统，保证与ENV通信的可靠性

# ==================== LLM客户端 ====================

class LLMClient:
    """Independent LLM Client, directly call various LLM APIs"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = httpx.AsyncClient()
        
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
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }
        
        # 针对不同提供商添加特殊参数
        if self.config.provider == "siliconflow":
            payload["enable_thinking"] = bool(self.config.enable_thinking)    
        elif self.config.provider.startswith("vllm"):
            payload["chat_template_kwargs"] = {
                    "enable_thinking": bool(self.config.enable_thinking)
                }
            
        # 添加工具定义与调用策略
        if tools:
            payload["tools"] = self._format_tools(tools)
            payload["tool_choice"] = "auto"
            payload["parallel_tool_calls"] = True
            
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
                
                console.print("🚨 LLM API 错误详情:", style="red bold")
                console.print(f"状态码: {error_details['status_code']}", style="red")
                console.print(f"URL: {error_details['url']}", style="red")
                console.print(f"提供商: {error_details['config']['provider']}", style="red")
                console.print(f"模型: {error_details['config']['model_id']}", style="red")
                console.print("响应内容:", style="red")
                print_json(data=error_details.get("response_json", error_details.get("response_text", "")), indent=2)
                
                raise Exception(f"LLM API error: {response.status_code} - {error_message}")
                
            console.print("LLM client response status code", style="purple")
            console.print(response.status_code, style="purple")
            console.print("LLM client response json", style="purple")
            response_data = response.json()
            print_json(data=response_data, indent=2, ensure_ascii=False)
            console.print("LLM client response end", style="purple")
            return response_data
            
        except httpx.ConnectError as e:
            error_msg = f"无法连接到 {self.config.provider} API 服务器: {self.base_url}"
            console.print(f"🔌 连接错误: {error_msg}", style="red")
            console.print(f"请检查网络连接和API服务器状态", style="yellow")
            raise Exception(error_msg) from e
            
        except httpx.TimeoutException as e:
            error_msg = f"{self.config.provider} API 请求超时 (>180秒)"
            console.print(f"⏱️ 超时错误: {error_msg}", style="red")
            console.print(f"请检查网络状况或尝试重新请求", style="yellow")
            raise Exception(error_msg) from e
            
        except httpx.HTTPStatusError as e:
            error_msg = f"{self.config.provider} API HTTP错误: {e.response.status_code}"
            console.print(f"🌐 HTTP错误: {error_msg}", style="red")
            raise Exception(error_msg) from e
            
        except Exception as e:
            error_msg = f"发送API请求时发生未知错误: {str(e)}"
            console.print(f"❌ 未知错误: {error_msg}", style="red")
            console.print(f"请求URL: {self.base_url}/chat/completions", style="yellow")
            console.print(f"提供商: {self.config.provider}", style="yellow")
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
    
    async def close(self):
        """Close client"""
        await self.client.aclose()

# ==================== 工具管理器 ====================

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

# ==================== 优化的聊天代理 ====================

class OptimizedStandaloneChatAgent:
    """优化的独立聊天代理"""
    
    def __init__(self, llm_config: LLMConfig, faction: str = "wei", system_prompt: str = ""):
        self.llm_client = LLMClient(llm_config)
        self.tool_manager = ToolManager()
        self.system_prompt = system_prompt
        self.conversation_history: List[Message] = []
        self.max_iterations = 100
        self.faction = faction
        
        # 优化的配置
        self.response_config = ResponseProcessingConfig(
            enable_detailed_logging=True,
            enable_strategy_detection=True,
            async_strategy_detection=True,
            log_response_content=False,
            strategy_detection_threshold=0.5,
            max_log_content_length=150
        )
        
        # 保护对话历史的锁
        self._history_lock = asyncio.Lock()
        
        # Agent注册状态标记
        self._agent_registered: bool = False
        
        # 策略检测节流控制
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
        """解析基于文本的工具调用"""
        import re
        import uuid
        
        tool_calls = []
        
        try:
            pattern = r'\{[^}]*(?:\{[^}]*\}[^}]*)*\}(?:\s*\n?</tool_call>)?'
            matches = re.findall(pattern, content.strip())
            
            for match in matches:
                json_str = re.sub(r'\s*\n?</tool_call>.*$', '', match.strip())
                
                try:
                    tool_data = json.loads(json_str)
                    function_name = tool_data.get("name")
                    arguments = tool_data.get("arguments", {})
                    
                    if function_name:
                        tool_call = {
                            "id": f"call_{uuid.uuid4().hex[:24]}",
                            "type": "function",
                            "function": {
                                "name": function_name,
                                "arguments": json.dumps(arguments, ensure_ascii=False)
                            }
                        }
                        tool_calls.append(tool_call)
                        console.print(f"📝 解析到工具调用: {function_name}", style="cyan")
                    
                except json.JSONDecodeError as e:
                    console.print(f"⚠️ 工具调用JSON解析失败: {json_str} - {e}", style="red")
                    self.conversation_history.append(
                        Message(role="user", content="Note: You should not put the tool call information in the `content` field. You must follow the tool call format. Please try again.")
                    )
                    continue
                    
        except Exception as e:
            console.print(f"⚠️ 解析文本工具调用时出错: {e}", style="red")
        
        return tool_calls
    
    def _log_llm_response(self, message: Dict[str, Any], finish_reason: str):
        """优化的LLM响应日志记录"""
        if not self.response_config.enable_detailed_logging:
            return
            
        # 简化的日志输出
        console.print("╭─── LLM Response ───╮", style="yellow")
        console.print(f"│ Finish Reason: {finish_reason}", style="yellow")
        console.print(f"│ Has Content: {bool(message.get('content'))}", style="yellow")
        console.print(f"│ Has Tool Calls: {bool(message.get('tool_calls'))}", style="yellow")
        
        # 只在配置启用时输出内容预览
        if self.response_config.log_response_content and message.get('content'):
            content_preview = str(message.get('content', ''))[:self.response_config.max_log_content_length]
            if len(content_preview) >= self.response_config.max_log_content_length:
                content_preview += "..."
            console.print(f"│ Content: {content_preview}", style="dim yellow")
        
        console.print("╰─────────────────────╯", style="yellow")
    
    async def _async_strategy_detection(self, content: str):
        """异步策略检测，不阻塞主流程"""
        if not content or not self.response_config.enable_strategy_detection:
            return
            
        try:
            import time
            # 节流：至少每2秒最多1次
            now = time.time()
            if (now - self._strategy_last_ping_ts) < 2.0:
                return
            
            # 检测策略内容
            hit_keywords = self._contains_strategy_keywords(content)
            hit_sequence = self._contains_strategy_sequence(content)
            
            if hit_keywords or hit_sequence:
                self._strategy_last_ping_ts = now
                score = 1.0 if hit_sequence else 0.5
                
                if score >= self.response_config.strategy_detection_threshold:
                    evidence = content.strip()
                    if len(evidence) > 120:
                        evidence = evidence[:117] + "..."
                    
                    console.print(f"🎯 检测到策略内容 (分数: {score}): {evidence[:50]}...", style="cyan")
                    
                    # 异步上报
                    await self.tool_manager.execute_tool("perform_action", {
                        "action": "strategy_ping",
                        "params": {
                            "faction": self.faction,
                            "score": score,
                            "evidence": evidence
                        }
                    })
        except Exception as e:
            console.print(f"⚠️ 策略检测失败: {e}", style="yellow")
    
    def _contains_strategy_keywords(self, text: str) -> bool:
        """检测策略关键词"""
        if not text:
            return False
        t = text.lower()
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
        
        key_hit = any(k in text for k in zh_keys) or any(k in t for k in en_keys)
        if not key_hit:
            return False
        
        structure_terms = ["先", "然后", "再", "首先", "优先", "目标", "步骤", "顺序", "选择", "方案", "计划",
                          "first", "then", "next", "priority", "goal", "objective", "step", "order"]
        structure_hit = any(term in text for term in structure_terms) or any(term in t for term in structure_terms)
        
        return structure_hit or self._contains_strategy_sequence(text)
    
    def _contains_strategy_sequence(self, text: str) -> bool:
        """检测序列式策略句式"""
        if not text:
            return False
        import re
        t = text.lower()

        # 中文序列正则
        zh_patterns = [
            r"(移动|前进|靠近|靠拢|调整|转移|推进|到达).{0,20}(攻击|开火|打击|交战|冲锋|压制|集火|歼灭|突击)",
            r"(位置|坐标).{0,20}(攻击|开火|打击|交战)",
            r"(攻击|开火|打击|交战|冲锋|压制|集火|突击).{0,20}(移动|前进|靠近|靠拢|调整|转移|撤退|推进|到达)",
        ]
        # 英文序列正则
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

        return False
    
    async def chat(self, user_prompt: str, max_iterations: Optional[int] = None) -> Dict[str, Any]:
        """主聊天循环"""
        if max_iterations:
            self.max_iterations = max_iterations
        
        # 在开始对话前注册Agent信息
        if not self._agent_registered:
            await self._register_agent_info()
            self._agent_registered = True
        
        # 初始化对话
        self.conversation_history = [
            Message(role="system", content=self.system_prompt)
        ]
        self.conversation_history.append(
            Message(role="user", content=user_prompt)
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
                
                # 🔧 直接解析响应（保证与ENV通信的可靠性）
                choice = response["choices"][0]
                message = choice["message"]
                finish_reason = choice["finish_reason"]
                
                # 🎯 优化的日志输出
                self._log_llm_response(message, finish_reason)
                
                # 将助手响应添加到历史
                assistant_message = Message(
                    role="assistant",
                    content=message.get("content", ""),
                    tool_calls=message.get("tool_calls")
                )
                self.conversation_history.append(assistant_message)
                
                # 🚀 异步策略检测（不阻塞主流程）
                if self.response_config.enable_strategy_detection:
                    asyncio.create_task(self._async_strategy_detection(message.get("content", "")))
                
                # 检测基于文本的工具调用
                tool_calls_to_use = message.get("tool_calls", [])
                if not tool_calls_to_use and message.get("content"):
                    parsed_tool_calls = self._parse_text_based_tool_calls(message["content"])
                    if parsed_tool_calls:
                        console.print("🔧 检测到文本格式的工具调用，转换为标准格式", style="cyan")
                        self.conversation_history.append(
                            Message(
                                role="user", 
                                content="Note: You should not put the tool call information in the `content` field. You must follow the tool call format."
                            )
                        )
                        continue

                # 处理工具调用
                if message.get("tool_calls"):
                    await self._handle_tool_calls(message["tool_calls"])
                    if iterations == 10 or iterations == 70:
                        self.conversation_history.append(
                            Message(role="user", content="你在获取敌方坐标之后，操作自己的所有单位向敌方移动，进入到攻击范围内后攻击敌人。")
                        )
                    continue

                # 处理不同的完成原因
                if finish_reason == "length":
                    self.conversation_history.append(
                        Message(
                            role="user", 
                            content="Note: If you need to call tools, please call them directly or with only critical explanation."
                        )
                    )
                    continue

                if finish_reason in ("stop"):
                    self.conversation_history.append(
                        Message(
                            role="user", 
                            content="Note: You are the commander. You decide the strategy and the action. Do not ask for confirmation. After you get the enemy's coordinates, you should move all your units to the enemy's position and attack them."
                        )
                    )
                    continue

                if finish_reason in ("content_filter"):
                    print(f"success: True, response: {message.get('content', '')}, iterations: {iterations}, finish_reason: {finish_reason}")
                    break

                # 意外的完成原因
                console.print(f"意外的完成原因: {finish_reason}", style="red")
                return {
                    "success": False,
                    "error": f"Unexpected finish reason: {finish_reason}",
                    "iterations": iterations
                }
                
            except Exception as e:
                # 使用全局错误日志功能
                error_details = create_error_details(e, iteration=iterations, function_name="OptimizedStandaloneChatAgent.chat")
                
                # 检查是否为上下文溢出错误
                if _is_context_overflow_error(e, error_details):
                    await self._shrink_history(window=40)
                    console.print("🧹 检测到上下文超限，已裁剪历史并继续", style="yellow")
                    continue                
                
                # 记录错误日志
                log_file = log_error_to_file(error_details, display_console=True)
                
                return {
                    "success": False,
                    "error": str(e),
                    "error_details": error_details,
                    "iterations": iterations,
                    "error_log_file": log_file
                }
        
        # 达到最大迭代次数
        return {
            "success": False,
            "error": "Max iterations reached",
            "iterations": iterations
        }
    
    async def _handle_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        """处理工具调用"""
        console.print(f"🔧 处理 {len(tool_calls)} 个工具调用", style="cyan")
        
        # 支持并行执行多个工具调用
        parallel_execution = len(tool_calls) > 1 and all(
            tool_call["function"]["name"] == "perform_action" 
            for tool_call in tool_calls
        )
        
        if parallel_execution:
            console.print("⚡ 检测到多个perform_action调用，使用并行执行模式", style="cyan")
            await self._handle_tool_calls_parallel(tool_calls)
        else:
            console.print("🔄 使用顺序执行模式", style="cyan")
            await self._handle_tool_calls_sequential(tool_calls)
    
    async def _handle_tool_calls_sequential(self, tool_calls: List[Dict[str, Any]]):
        """顺序执行工具调用"""
        for tool_call in tool_calls:
            await self._execute_single_tool_call(tool_call)
    
    async def _handle_tool_calls_parallel(self, tool_calls: List[Dict[str, Any]]):
        """并行执行工具调用"""
        tasks = []
        for tool_call in tool_calls:
            task = asyncio.create_task(self._execute_single_tool_call(tool_call))
            tasks.append(task)
        
        await asyncio.gather(*tasks)
    
    async def _execute_single_tool_call(self, tool_call: Dict[str, Any]):
        """执行单个工具调用"""
        tool_call_id = tool_call["id"]
        function_name = tool_call["function"]["name"]
        arguments_str = tool_call["function"]["arguments"]
        
        console.print(f"╭──────────────────────────────────────── 执行工具 '{function_name}' ────────────────────────────────────────╮", style="green")
        console.print(f"│ {arguments_str}", style="green", highlight=False)
        console.print(f"╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯", style="green")
        
        try:
            # 解析参数
            arguments = json.loads(arguments_str) if arguments_str else {}
            
            # 处理双重编码的JSON
            if 'params' in arguments and isinstance(arguments['params'], str):
                console.print("⚠️ 'params' 是字符串，尝试再次解码...", style="yellow")
                try:
                    arguments['params'] = json.loads(arguments['params'])
                except json.JSONDecodeError as e:
                    raise ValueError(f"LLM生成了无效的JSON字符串: {arguments['params']}. 错误: {e}")
            
            # 执行工具
            result = await self.tool_manager.execute_tool(function_name, arguments)
            
            console.print(f"╭──────────────────────────────────────── 工具 '{function_name}' 结果 ────────────────────────────────────────╮", style="yellow")
            console.print(f"│ {json.dumps(result, indent=2, ensure_ascii=False)}", style="green", highlight=False)
            console.print(f"╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯", style="yellow")
            
            # 过滤工具结果
            filtered_result = self._filter_tool_result(function_name, result)
            
            # 将结果添加到对话历史（使用锁保护）
            tool_message = Message(
                role="tool",
                content=json.dumps(filtered_result, ensure_ascii=False),
                tool_call_id=tool_call_id
            )
            async with self._history_lock:
                self.conversation_history.append(tool_message)
            
        except Exception as e:
            console.print(f"工具执行错误: {e}", style="red")
            # 添加错误信息到对话历史
            error_message = Message(
                role="tool",
                content=json.dumps({"error": str(e)}, ensure_ascii=False),
                tool_call_id=tool_call_id
            )
            async with self._history_lock:
                self.conversation_history.append(error_message)
    
    def _filter_tool_result(self, function_name: str, result: Any) -> Any:
        """过滤工具结果，保持对话历史精炼"""
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
        """过滤 observation 结果"""
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
                        "units": tile.get("units", [])
                    }
                    
                    movement_access = tile.get("movement_accessibility", {})
                    if isinstance(movement_access, dict) and "reachable" in movement_access:
                        filtered_tile["reachable"] = movement_access["reachable"]
                    
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
        return result
    
    def _filter_move_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """过滤 move 结果"""
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
        """过滤 attack 结果"""
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
        """裁剪对话历史"""
        system_msgs = [m for m in self.conversation_history if m.role == "system"][:1]
        user_msgs = [m for m in self.conversation_history if m.role == "user"][:1]
        non_system_msgs = [m for m in self.conversation_history if m.role != "system"]
        tail = non_system_msgs[-window:]
        
        self.conversation_history = system_msgs + user_msgs + tail

    async def _register_agent_info(self):
        """注册Agent信息到环境"""
        try:
            config = self.llm_client.config
            
            registration_params = {
                "faction":  self.faction,
                "provider": config.provider,
                "model_id": config.model_id,
                "base_url": config.base_url or "unknown",
                "agent_id": getattr(self, 'agent_id', 'unknown'),
                "version": "2.0.0",  # 优化版本
                "note": f"Optimized Agent using {config.provider}"
            }        
            
            result = await self.tool_manager.execute_tool("perform_action", {
                "action": "register_agent_info",
                "params": registration_params
            })
            if result.get("success"):
                console.print(f"✅ Agent信息注册成功: {self.faction}阵营 - {config.provider}:{config.model_id} (优化版)", style="green")
            else:
                console.print(f"⚠️ Agent信息注册失败: {result.get('message', 'unknown error')}", style="yellow")
        
        except Exception as e:
            console.print(f"❌ Agent信息注册出错: {e}", style="red")

    async def stop(self):
        """停止代理"""
        await self.llm_client.close()

# ==================== 其他辅助函数（保持与原版兼容）====================

# 这里保留原版的错误处理和其他辅助函数
def create_error_details(exception: Exception, **extra_context) -> Dict[str, Any]:
    """创建详细的错误信息字典"""
    import traceback
    import httpx
    
    error_details = {
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "timestamp": datetime.now().isoformat()
    }
    
    error_details.update(extra_context)
    
    tb_lines = traceback.format_exception(type(exception), exception, exception.__traceback__)
    error_details["full_traceback"] = "".join(tb_lines)
    
    if isinstance(exception, httpx.HTTPStatusError):
        error_details["http_status_code"] = exception.response.status_code
        error_details["response_headers"] = dict(exception.response.headers)
        try:
            error_details["response_body"] = exception.response.text
        except:
            error_details["response_body"] = "无法读取响应体"
            
    elif isinstance(exception, httpx.ConnectError):
        error_details["connection_error"] = "无法连接到服务器"
        error_details["request_url"] = str(exception.request.url) if hasattr(exception, 'request') and exception.request else "未知"
        
    elif isinstance(exception, httpx.TimeoutException):
        error_details["timeout_error"] = "请求超时"
        error_details["request_url"] = str(exception.request.url) if hasattr(exception, 'request') and exception.request else "未知"
        
    elif isinstance(exception, httpx.RequestError):
        error_details["request_error"] = "请求错误"
        error_details["request_url"] = str(exception.request.url) if hasattr(exception, 'request') and exception.request else "未知"
        
    elif isinstance(exception, TimeoutError):
        error_details["timeout_error"] = "操作超时"
        
    elif "JSON" in str(exception) or "json" in str(exception):
        error_details["json_error"] = "JSON解析错误，可能是API返回格式不正确"
    
    return error_details

def log_error_to_file(error_details: Dict[str, Any], display_console: bool = True) -> Optional[str]:
    """将错误详情保存到文件"""
    if display_console:
        console.print("=" * 80, style="red")
        console.print("🚨 详细错误信息", style="red bold")
        console.print("=" * 80, style="red")
        console.print(f"📍 异常类型: {error_details.get('exception_type', 'Unknown')}", style="red")
        console.print(f"📝 错误消息: {error_details.get('exception_message', 'Unknown')}", style="red") 
        console.print(f"⏰ 发生时间: {error_details.get('timestamp', 'Unknown')}", style="red")
        
        if "function_name" in error_details:
            console.print(f"🔧 发生函数: {error_details['function_name']}", style="red")
        if "iteration" in error_details:
            console.print(f"🔄 当前迭代: {error_details['iteration']}", style="red")
        
        if "http_status_code" in error_details:
            console.print(f"🌐 HTTP状态码: {error_details['http_status_code']}", style="red")
            console.print(f"📤 响应头: {error_details['response_headers']}", style="yellow")
            console.print(f"📥 响应体: {error_details['response_body'][:500]}...", style="yellow")
            
        if "connection_error" in error_details:
            console.print(f"🔌 连接错误: {error_details['connection_error']}", style="red")
            console.print(f"🎯 请求URL: {error_details['request_url']}", style="yellow")
            
        if "timeout_error" in error_details:
            console.print(f"⏱️ 超时错误: {error_details['timeout_error']}", style="red")
            if "request_url" in error_details:
                console.print(f"🎯 请求URL: {error_details['request_url']}", style="yellow")
            
        if "json_error" in error_details:
            console.print(f"📋 JSON错误: {error_details['json_error']}", style="red")
        
        console.print("\n🔍 完整堆栈跟踪:", style="red")
        console.print(error_details.get("full_traceback", ""), style="dim red")
    
    try:
        error_log_file = f"error_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(error_log_file, 'w', encoding='utf-8') as f:
            json.dump(error_details, f, ensure_ascii=False, indent=2)
        
        if display_console:
            console.print(f"💾 错误详情已保存到: {error_log_file}", style="blue")
            console.print("=" * 80, style="red")
        
        return error_log_file
    except Exception as log_error:
        if display_console:
            console.print(f"⚠️ 无法保存错误日志: {log_error}", style="yellow")
        return None

def handle_error_with_logging(exception: Exception, **extra_context) -> Dict[str, Any]:
    """处理异常并生成错误日志的便捷函数"""
    error_details = create_error_details(exception, **extra_context)
    log_file = log_error_to_file(error_details, display_console=True)
    
    return {
        "success": False,
        "error": str(exception),
        "error_details": error_details,
        "error_log_file": log_file
    }

def _is_context_overflow_error(exc: Exception, error_details: dict | None = None) -> bool:
    """检测是否为上下文/token超限错误"""
    import json
    txt = str(exc) if exc else ""
    blob = txt
    if error_details:
        try:
            blob += " " + json.dumps(error_details, ensure_ascii=False)
        except Exception:
            pass
    s = blob.lower()

    triggers = [
        "maximum context length",
        "max context length",
        "context length is",
        "context window",
        "prompt is too long",
        "too many tokens",
        "exceeds the maximum",
        "requested",
        "tokens"
    ]
    if any(k in s for k in triggers):
        return True

    try:
        rsp = (error_details or {}).get("response_json") or {}
        msg = (rsp.get("error") or {}).get("message", "")
        if msg and any(k in msg.lower() for k in ["context", "token", "too long"]):
            return True
    except Exception:
        pass

    return False

# ==================== 远程上下文和其他兼容性代码 ====================

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

async def get_env_response(request_id, timeout_seconds: float =60.0):
    """获取动作执行的响应，带超时和ID冲突检测"""
    import time
    
    start_time = time.time()
    console.print(f"⏳ 等待响应 ID: {request_id}，超时设置: {timeout_seconds}s", style="cyan")
    
    while True:
        response = RemoteContext.get_id_map().get(request_id, None)
        if response is not None:
            RemoteContext.get_id_map().pop(request_id, None)
            elapsed = time.time() - start_time
            console.print(f"✅ 收到响应 ID: {request_id}，耗时: {elapsed:.2f}s", style="green")
            return response
        
        elapsed = time.time() - start_time
        if elapsed >= timeout_seconds:
            console.print(f"⏰ 响应超时 ID: {request_id}，已等待: {elapsed:.2f}s", style="red")
            console.print(f"🔍 当前ID映射状态: {dict(RemoteContext.get_id_map())}", style="yellow")
            timeout_error = TimeoutError(f"等待响应超时: ID {request_id}，超时时间: {timeout_seconds}s")
            timeout_error.request_id = request_id
            timeout_error.elapsed_time = elapsed
            timeout_error.timeout_seconds = timeout_seconds
            raise timeout_error
        
        await asyncio.sleep(0.1)

async def perform_action(action: str, params: Any):
    """执行动作"""
    try:
        client = RemoteContext.get_client()
        request_id = await client.send_action(action, params)
        response = await get_env_response(request_id, timeout_seconds=15.0)
        
        delay_time = _calculate_action_delay(action, params, response)
        if delay_time > 0:
            console.print(f"⏳ 等待 {delay_time}s 让动作完成...", style="cyan")
            await asyncio.sleep(delay_time)

        return response
        
    except TimeoutError as e:
        console.print(f"⏰ 动作执行超时: {e}", style="red")
        return handle_error_with_logging(
            e, 
            function_name="perform_action",
            action=action,
            params=params,
            request_id=getattr(e, 'request_id', 'unknown'),
            elapsed_time=getattr(e, 'elapsed_time', 'unknown'),
            timeout_seconds=getattr(e, 'timeout_seconds', 'unknown')
        )
    except Exception as e:
        console.print(f"❌ 动作执行错误: {e}", style="red")
        return handle_error_with_logging(
            e, 
            function_name="perform_action",
            action=action,
            params=params
        )

async def get_available_actions() -> list[Dict[str, Any]]:
    """获取当前可用的动作"""
    result = await perform_action("get_action_list", {})
    return result

def _calculate_action_delay(action: str, params: Any, response: Any) -> float:
    """根据动作类型计算延迟时间"""
    if not isinstance(response, dict) or not response.get("success", False):
        return 0.0
    
    if action == "move":
        return _calculate_move_delay(params, response)
    elif action == "attack":
        return 0.2
    elif action in ["get_faction_state", "observation", "get_action_list"]:
        return 0.0
    else:
        return 0.1

def _calculate_move_delay(params: Any, response: Any) -> float:
    """计算移动动作的延迟时间"""
    try:
        if isinstance(response, dict) and "movement_details" in response:
            estimated_duration = response["movement_details"].get("estimated_duration_seconds", 0)
            if estimated_duration > 0:
                return estimated_duration * 1.1
        
        if isinstance(response, dict) and "movement_details" in response:
            path_length = response["movement_details"].get("path_length", 0)
            if path_length > 0:
                return path_length / 2.0 + 0.2
        
        if isinstance(params, dict) and "target_position" in params:
            return 1.0
        
        return 1.0
    
    except Exception as e:
        console.print(f"⚠️ 计算移动延迟时出错: {e}", style="yellow")
        return 1.0

# ==================== Demo 类和主函数 ====================

class OptimizedAgentDemo:
    """优化版Agent演示类"""

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
        self.agent_client = AgentClient(self.hub_url, self.env_id, self.agent_id)
        self.setup_hub_listeners()
        RemoteContext.set_client(self.agent_client)
        RemoteContext.set_status({"self_status": {}, "env_status": {}})

    def setup_hub_listeners(self):
        """设置事件监听器"""

        def on_connect(data):
            message = f"✅ Agent 连接成功: {data}"
            console.print(message, style="green")
            self.messages.append(message)

        def on_message(data):
            message = f"📨 Agent 收到消息: {data}"
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
        console.print("🤖 创建 Agent 客户端 (优化版)", style="bold blue")
        console.print(f"📡 服务器: {self.hub_url}")
        console.print(f"🌍 环境ID: {self.env_id}")
        console.print(f"🆔 Agent ID: {self.agent_id}")
        console.print("=" * 50)

        console.print("🔗 正在连接到服务器...", style="yellow")
        try:
            await self.agent_client.connect()
            console.print("✅ Agent 连接成功！", style="bold green")

            await asyncio.sleep(1)
            return True
        except Exception as e:
            console.print(f"❌ 连接失败: {e}", style="bold red")
            return False

    def get_faction_from_env(self) -> str:
        """从环境变量获取势力"""
        return os.environ.get("AGENT_FACTION", "wei").lower()

    def get_faction_info(self, faction: str) -> dict:
        """获取势力基本信息"""
        faction_configs = {
            "wei": {"name": "魏", "enemy": "蜀 (shu)"},
            "shu": {"name": "蜀", "enemy": "魏 (wei)"},
            "wu": {"name": "吴", "enemy": "魏 (wei)"}
        }
        return faction_configs.get(faction, faction_configs["wei"])

    async def interactive_demo(self):
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
            console.print(f"🔄 Launch {count}th expedition (优化版)...", style="bold red")
            try:
                await asyncio.create_task(create_optimized_agent(faction, system_prompt, user_prompt))
                await asyncio.sleep(0.1)

            except KeyboardInterrupt:
                print("\n👋 User interrupted, exiting")
                break
            except Exception as e:
                print(f"❌ Command execution error: {e}")

    def show_summary(self):
        """显示演示摘要"""
        console.print("\n📊 Agent demo summary (优化版)", style="bold cyan")
        console.print("=" * 25)
        console.print(f"📈 Total messages: {len(self.messages)}")
        console.print(f"🆔 Agent ID: {self.agent_id}")
        console.print(f"🌍 Environment ID: {self.env_id}")

        if self.messages:
            console.print("\n📝 Message history (last 10):")
            for i, msg in enumerate(self.messages[-10:], 1):
                console.print(f"   {i}. {msg}")

    async def cleanup(self):
        """清理资源"""
        console.print("\n🧹 Cleaning up connection...", style="yellow")
        try:
            if self.agent_client:
                await self.agent_client.disconnect()
                console.print("✅ Agent connection closed", style="green")
        except Exception as e:
            console.print(f"⚠️ Error closing connection: {e}", style="yellow")

    async def run_interactive_demo(self):
        """运行交互式演示"""
        console.print(f"🎮 Agent interactive demo (优化版)", style="bold cyan")
        console.print("🎯 You can manually control the Agent to perform various actions", style="cyan")
        console.print("=" * 50)

        try:
            if not await self.connect():
                return
            await self.interactive_demo()
            self.show_summary()

        except KeyboardInterrupt:
            print("\n⚠️ User interrupted demo")
        except Exception as e:
            print(f"\n❌ Error during demo: {e}")
        finally:
            await self.cleanup()

def load_config(config_path: str = ".configs.toml", provider: str = "vllm") -> LLMConfig:
    """加载LLM配置"""
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

async def create_optimized_agent(faction: str = "wei", system_prompt: str = "", user_prompt: str = ""):
    """创建优化版Agent"""
    try:
        config_path = os.path.join(os.getcwd(), ".configs.toml")
        console.print(f"在当前工作目录找到配置文件: {config_path}")
        console.print("尝试加载配置文件")
        console.print(config_path)
        
        provider = os.environ.get("LLM_PROVIDER", "openai")
        llm_config = load_config(config_path, provider=provider)
        agent = OptimizedStandaloneChatAgent(llm_config, faction, system_prompt)
        
        # 注册工具
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
            """检测到游戏结束时停止运行"""
            return {"message": "You chose to stop running. Take a reset and start again."}
        
        agent.register_tool(
            name="stop_running",
            function=stop_running,
            description="暂停一回合以恢复行动力。行动力已恢复，请继续进行。",
            parameters={"type": "object", "properties": {}, "required": []},
        )

        # 执行聊天任务
        result = await agent.chat(user_prompt)
        console.print(f"聊天任务完成: {result}")
        
        # 清理资源
        await agent.stop()
        
    except Exception as e:
        console.print(f"聊天过程中发生错误: {e}", style="red")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="优化版 Agent 演示程序")

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
        help="控制的势力 (default: wei)"
    )

    args = parser.parse_args()

    console.print(f"📡 Hub: {args.hub_url}")
    console.print(f"🌍 Environment ID: {args.env_id}")
    console.print(f"🆔 Agent ID: {args.agent_id}")
    console.print(f"🔧 Provider: {args.provider}")
    console.print(f"⚔️ Faction: {args.faction}")
    console.print("🚀 使用优化版架构", style="bold green")
    console.print("=" * 60)

    # 设置环境变量
    os.environ["LLM_PROVIDER"] = args.provider
    os.environ["AGENT_FACTION"] = args.faction

    # 创建优化版演示实例
    demo = OptimizedAgentDemo(args.hub_url, args.env_id, args.agent_id)
    console.print("🎮 Interactive mode (优化版)", style="bold cyan")
    await demo.run_interactive_demo()

if __name__ == "__main__":
    asyncio.run(main())
