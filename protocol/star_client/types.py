"""
类型定义模块
"""

from typing import Dict, List, Any, Callable, Optional, Union
from dataclasses import dataclass
from enum import Enum


class ClientType(Enum):
    """客户端类型枚举"""

    AGENT = "agent"
    ENVIRONMENT = "env"
    HUMAN = "human"


class MessageInstruction(Enum):
    """消息指令枚举"""

    BROADCAST = "broadcast"
    # 消息指令
    MESSAGE = "message"
    # 心跳指令
    HEARTBEAT = "heartbeat"
    # 连接状态
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    # 错误指令
    ERROR = "error"


@dataclass
class ClientInfo:
    """客户端信息"""

    role_type: str
    env_id: int
    agent_id: Optional[int] = None
    human_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """将客户端信息转换为字典"""
        d = {
            "role_type": self.role_type,
            "env_id": self.env_id,
        }
        if self.agent_id is not None:
            d["agent_id"] = self.agent_id
        if self.human_id is not None:
            d["human_id"] = self.human_id
        return d


@dataclass
class MessageData:
    """消息数据结构"""

    instruction: str
    msg_from: ClientInfo
    msg_to: ClientInfo
    data: Dict[str, Any]
    timestamp: float


# 事件处理器类型
EventHandler = Callable[[Dict[str, Any]], Any]
AsyncEventHandler = Callable[[Dict[str, Any]], Any]

# 消息目标类型
MessageTarget = Union[str, Dict[str, Any], ClientInfo]
