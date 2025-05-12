from abc import ABC, abstractmethod
from typing import Type, List, Any, Optional, Dict


class System(ABC):
    """
    系统：包含游戏逻辑，操作有特定组件的实体
    在ECS架构中，系统负责处理业务逻辑，通过选择性地处理包含特定组件的实体
    """

    def __init__(self, required_components: List[Type], priority: int = 0):
        """
        初始化系统

        参数:
            required_components: 系统关心的组件类型列表，只有同时拥有这些组件的实体才会被系统处理
            priority: 系统优先级，数值越小优先级越高，用于控制系统执行顺序
        """
        self.required_components = (
            required_components or []
        )  # 系统需要处理的组件类型列表
        self.priority = priority  # 系统优先级，用于排序系统执行顺序
        self.enabled = True  # 系统是否启用
        self.context = None  # ECS上下文，用于获取其他系统和管理器

    # def initialize(self, context: Any) -> None:
    #     """
    #     初始化系统，设置上下文
        
    #     参数:
    #         context: ECS上下文，包含实体、组件、系统管理器等
    #     """
    #     self.context = context

    def is_enabled(self) -> bool:
        """
        检查系统是否启用
        返回:
            bool: 如果系统启用，则返回True，否则返回False
        """
        return self.enabled

    def set_enabled(self, enabled: bool) -> None:
        """
        设置系统的启用状态
        参数:
            enabled: 要设置的启用状态，True表示启用，False表示禁用
        """
        self.enabled = enabled

    @abstractmethod
    def update(self, delta_time: float) -> None:
        """
        更新系统逻辑，由子类实现
        这是系统的主要方法，在每一帧中被World调用，处理所有相关实体

        参数:
            context: ECS上下文，包含实体、组件、系统管理器等
            delta_time: 自上一帧以来经过的时间（秒），用于基于时间的更新
        """
        pass
