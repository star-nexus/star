class Entity:
    """
    实体：游戏对象的唯一标识，包含组件的容器
    在ECS架构中表示单个游戏对象，通过添加不同组件来赋予对象特定功能和属性
    """

    def __init__(self, entity_id, world):
        """
        初始化实体对象

        参数:
            entity_id: 实体的唯一标识符
            world: 实体所属的世界引用
        """
        self.id = entity_id  # 实体的唯一ID
        self.world = world  # 对所属World的引用，用于通信
        self.components = {}  # 组件字典：组件类型 -> 组件实例

    def add_component(self, component):
        """
        添加组件到实体

        参数:
            component: 要添加的组件实例

        返回:
            Entity: 返回实体自身，支持链式调用
        """
        # 获取组件类型
        component_class = component.__class__
        # 将组件存储到组件字典中
        self.components[component_class] = component
        # 设置组件的实体引用
        component.entity = self

        # 通知世界组件被添加，世界会通知相关系统
        if self.world:
            self.world.component_added(self, component_class)

        return self  # 返回自身支持链式调用

    def remove_component(self, component_class):
        """
        从实体移除组件

        参数:
            component_class: 要移除的组件类型
        """
        if component_class in self.components:
            # 获取组件实例
            component = self.components[component_class]
            # 清除组件的实体引用
            component.entity = None
            # 从组件字典中移除组件
            del self.components[component_class]

            # 通知世界组件被移除，世界会通知相关系统
            if self.world:
                self.world.component_removed(self, component_class)

    def get_component(self, component_class):
        """
        获取指定类型的组件

        参数:
            component_class: 要获取的组件类型

        返回:
            Component: 请求的组件实例，如果不存在则返回None
        """
        return self.components.get(component_class)

    def has_component(self, component_class):
        """
        检查实体是否有指定类型的组件

        参数:
            component_class: 要检查的组件类型

        返回:
            bool: 如果实体拥有该类型组件则返回True，否则返回False
        """
        return component_class in self.components

    def has_components(self, component_classes):
        """
        检查实体是否有指定的所有类型的组件

        参数:
            component_classes: 要检查的组件类型列表或集合

        返回:
            bool: 如果实体拥有所有指定类型的组件则返回True，否则返回False
        """
        return all(
            component_class in self.components for component_class in component_classes
        )
