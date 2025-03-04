from abc import ABC, abstractmethod
from typing import Type, List, Any


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
    def update(self, world: Any, delta_time: float) -> None:
        """
        更新系统逻辑，由子类实现
        这是系统的主要方法，在每一帧中被World调用，处理所有相关实体

        参数:
            world: 世界实例，包含实体和组件
            delta_time: 自上一帧以来经过的时间（秒），用于基于时间的更新
        """
        pass

    def render(self, render_manager: Any) -> None:
        """
        渲染系统，可由子类实现以提供可视化输出
        并非所有系统都需要渲染，默认为空实现

        参数:
            render_manager: 渲染管理器实例，提供绘图功能
        """
        pass
