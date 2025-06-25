"""
自定义异常类
"""


class AgentClientError(Exception):
    """SDK 基础异常类"""
    pass


class ConnectionError(AgentClientError):
    """连接相关异常"""
    pass


class MessageError(AgentClientError):
    """消息处理相关异常"""
    pass


class AuthenticationError(AgentClientError):
    """认证相关异常"""
    pass


class TimeoutError(AgentClientError):
    """超时异常"""
    pass
