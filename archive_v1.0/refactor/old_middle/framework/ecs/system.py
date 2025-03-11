class System:
    """
    系统：包含游戏逻辑，操作有特定组件的实体
    在ECS架构中，系统负责处理业务逻辑，通过选择性地处理包含特定组件的实体
    """

    def __init__(self, required_components=None):
        """
        初始化系统

        参数:
            required_components: 系统关心的组件类型列表，只有同时拥有这些组件的实体才会被系统处理
        """
        self.required_components = (
            required_components or []
        )  # 系统需要处理的组件类型列表
        self.entities = []  # 系统当前处理的实体列表
        self.world = None  # 系统所属的世界引用，由World.register_system设置

    def is_interested_in(self, entity):
        """
        检查系统是否对实体感兴趣（实体是否有系统需要的所有组件）

        参数:
            entity: 要检查的实体

        返回:
            bool: 如果实体具有系统所需的所有组件，则返回True，否则返回False
        """
        return entity.has_components(self.required_components)

    def add_entity(self, entity):
        """
        将实体添加到系统的处理列表中

        参数:
            entity: 要添加的实体
        """
        if entity not in self.entities:
            self.entities.append(entity)

    def remove_entity(self, entity):
        """
        从系统的处理列表中移除实体

        参数:
            entity: 要移除的实体
        """
        if entity in self.entities:
            self.entities.remove(entity)

    def entity_destroyed(self, entity):
        """
        处理实体被销毁的情况
        当实体从世界中被删除时，系统会收到通知并调用此方法

        参数:
            entity: 被销毁的实体
        """
        self.remove_entity(entity)

    def update(self, delta_time):
        """
        更新系统逻辑，由子类实现
        这是系统的主要方法，在每一帧中被World调用，处理所有相关实体

        参数:
            delta_time: 自上一帧以来经过的时间（秒），用于基于时间的更新
        """
        pass
