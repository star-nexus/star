"""
日志配置模块，使用rich格式化输出日志
"""

import logging
import os
import sys
from rich.logging import RichHandler
from rich.console import Console
from rich.theme import Theme
from typing import Dict, Optional, Union

# 定义自定义日志级别MSG
MSG = 25
logging.addLevelName(MSG, "MSG")


class LogConfig:
    """
    日志配置类，用于配置日志输出
    """

    _instance = None  # 单例模式

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LogConfig, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # 默认配置
        self.level = logging.INFO
        self.enable_output = True
        self.log_to_file = False
        self.log_file = "game.log"
        self.rich_console = None
        self.handler = None
        self.file_handler = None
        self._initialized = True

    def configure(
        self,
        level: Union[str, int] = None,
        enable_output: bool = None,
        log_to_file: bool = None,
        log_file: str = None,
    ) -> None:
        """
        配置日志

        参数:
            level: 日志级别，可以是字符串('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
                  或者对应的整数值
            enable_output: 是否启用日志输出
            log_to_file: 是否将日志输出到文件
            log_file: 日志文件路径
        """
        # 更新配置
        if level is not None:
            if isinstance(level, str):
                # 特殊处理MSG级别
                if level.upper() == "MSG":
                    self.level = MSG
                else:
                    self.level = getattr(logging, level.upper())
            else:
                self.level = level

        if enable_output is not None:
            self.enable_output = enable_output

        if log_to_file is not None:
            self.log_to_file = log_to_file

        if log_file is not None:
            self.log_file = log_file

        # 重置日志配置
        self._reset_logging()

        # 如果启用输出，设置日志处理器
        if self.enable_output:
            self._setup_logging()

    def _reset_logging(self) -> None:
        """重置日志配置"""
        # 移除所有处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    def _setup_logging(self) -> None:
        """设置日志处理器"""
        # 创建rich控制台
        theme = Theme(
            {
                "info": "green",
                "msg": "cyan",  # 自定义MSG级别的颜色为青色
                "warning": "yellow",
                "error": "bold red",
                "critical": "bold white on red",
            }
        )
        self.rich_console = Console(theme=theme)

        # 设置日志格式
        log_format = "%(name)s: [%(levelname)s] %(message)s"

        # 创建RichHandler
        self.handler = RichHandler(
            console=self.rich_console,
            rich_tracebacks=True,
            show_time=True,
            show_path=False,
            markup=True,
            log_time_format="[%X]",
        )
        self.handler.setLevel(self.level)
        self.handler.setFormatter(logging.Formatter(log_format))

        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(self.level)
        root_logger.addHandler(self.handler)

        # 如果需要，添加文件处理器
        if self.log_to_file:
            self.file_handler = logging.FileHandler(
                self.log_file, mode="w", encoding="utf-8"
            )
            self.file_handler.setLevel(self.level)
            self.file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            root_logger.addHandler(self.file_handler)

        # 设置特定模块的日志级别
        logging.getLogger("pygame").setLevel(logging.WARNING)

    def get_logger(self, name: str) -> logging.Logger:
        """
        获取指定名称的日志记录器

        参数:
            name: 日志记录器名称

        返回:
            logging.Logger: 日志记录器
        """
        logger = logging.getLogger(name)

        # 为Logger添加msg方法
        def msg(message, *args, **kwargs):
            logger.log(MSG, message, *args, **kwargs)

        # 将msg方法添加到logger实例
        logger.msg = msg

        return logger


# 全局单例
log_config = LogConfig()


def configure(
    level: Union[str, int] = None,
    enable_output: bool = None,
    log_to_file: bool = None,
    log_file: str = None,
) -> None:
    """
    配置日志的便捷方法
    参数:
        level: 日志级别，可以是字符串('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
              或者对应的整数值
        enable_output: 是否启用日志输出
        log_to_file: 是否将日志输出到文件
        log_file: 日志文件路径
    """
    log_config.configure(level, enable_output, log_to_file, log_file)


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器的便捷方法

    参数:
        name: 日志记录器名称

    返回:
        logging.Logger: 日志记录器
    """
    return log_config.get_logger(name)
