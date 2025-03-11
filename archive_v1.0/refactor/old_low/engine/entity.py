class Component:
    """组件基类"""

    def __init__(self, entity):
        self.entity = entity

    def update(self, delta_time):
        """更新组件状态"""
        pass

    def render(self, surface):
        """渲染组件"""
        pass


class Entity:
    """实体类，由多个组件组成"""

    def __init__(self, x=0, y=0, tag=""):
        self.x = x
        self.y = y
        self.components = {}
        self.tag = tag  # 添加标签属性，便于识别实体类型
        self.active = True  # 添加活动状态，便于暂时禁用实体

    def add_component(self, component_type, component):
        """添加组件到实体"""
        self.components[component_type] = component

    def get_component(self, component_type):
        """获取指定类型的组件"""
        return self.components.get(component_type)

    def has_component(self, component_type):
        """检查是否有指定类型的组件"""
        return component_type in self.components

    def remove_component(self, component_type):
        """移除指定类型的组件"""
        if component_type in self.components:
            del self.components[component_type]

    def set_active(self, active):
        """设置实体的活动状态"""
        self.active = active

    def is_active(self):
        """检查实体是否处于活动状态"""
        return self.active

    def update(self, delta_time):
        """更新实体的所有组件"""
        if not self.active:
            return

        for component in self.components.values():
            component.update(delta_time)

    def render(self, surface):
        """渲染实体的所有组件"""
        if not self.active:
            return

        for component in self.components.values():
            component.render(surface)
