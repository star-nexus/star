from abc import ABC


def singleton(cls):
    class Wrapper:
        _instance = None

        def __new__(cls, *args, **kwargs):
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.__init__(*args, **kwargs)
            return cls._instance

    return Wrapper


class Component(ABC):
    """
    组件：纯数据容器，不包含游戏逻辑
    在ECS架构中，组件只存储数据，不实现行为逻辑
    系统负责处理包含特定组件的实体，从而实现功能和行为

    组件应该被设计为只包含与特定功能相关的数据属性
    推荐使用dataclass装饰器来简化组件的定义
    """

    def __init__(self):
        """
        初始化组件
        组件应该只包含数据，不应该包含对实体的引用

        示例:
            @dataclass
            class Position(Component):
                x: float = 0.0
                y: float = 0.0
        """
        pass  # 具体组件类应该继承此类并定义自己的数据属性
