"""
Shared utilities for rotk_agent provider scripts.

Contains pieces that are byte-identical across the active agent scripts
(qwen3 / gpt_oss / nv_nemotron, real-time + turn-based variants):

- Message / ToolDefinition dataclasses
- RemoteContext: ContextVar-backed handle to the AgentClient, status, and id_map
- Error helpers: create_error_details / log_error_to_file / handle_error_with_logging
- Delay helpers: _calculate_action_delay / _calculate_move_delay / _rpm_limit_interval
- Error classifiers: _is_context_overflow_error / _is_account_balance_error /
  _is_network_unreachable_error

Provider-specific pieces (LLMClient, RoTKChatAgent, LLMConfig defaults, load_config,
ErrorStatsCollector, ToolManager, AgentDemo) remain in each agent script because
they diverge meaningfully across providers.
"""

from __future__ import annotations

import asyncio
import json
import os
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from rich.console import Console

from protocol import AgentClient


console = Console()
console_system = Console()


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


async def _rpm_limit_interval():
    """Limit the interval time based on the RPM limit"""
    interval = float(os.environ.get("INTERVAL", "0"))
    console_system.print(f"🕒 Interval: {interval}s", style="bold blue")
    await asyncio.sleep(interval)


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


def _is_network_unreachable_error(exc: Exception, error_details: dict | None = None) -> bool:
    """网络不可达类错误：ConnectError、Timeout、连接拒绝等，应终止进程避免无限重试。"""
    import httpx
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError)):
        return True
    d = error_details or {}
    if any(k in d for k in ("connection_error", "timeout_error", "request_error")):
        return True
    msg = (d.get("exception_message") or str(exc)).lower()
    for phrase in (
        "cannot connect", "connection refused", "getaddrinfo failed",
        "network is unreachable", "connection error", "timeout", "timed out",
        "connecterror", "timeoutexception"
    ):
        if phrase in msg:
            return True
    return False


__all__ = [
    "console",
    "console_system",
    "Message",
    "ToolDefinition",
    "RemoteContext",
    "create_error_details",
    "log_error_to_file",
    "handle_error_with_logging",
    "_rpm_limit_interval",
    "_calculate_action_delay",
    "_calculate_move_delay",
    "_is_context_overflow_error",
    "_is_account_balance_error",
    "_is_network_unreachable_error",
]
