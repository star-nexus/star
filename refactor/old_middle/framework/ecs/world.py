from framework.ecs.entity import Entity


class World:
    """
    ECS的世界容器，管理所有实体和系统
    是整个实体-组件-系统架构的中心点，负责协调实体和系统之间的交互
    """

    def __init__(self):
        """
        初始化游戏世界
        创建实体字典、系统列表和实体ID计数器
        """
        self.entities = {}  # 存储所有实体的字典，键为实体ID，值为实体对象
        self.systems = []  # 存储所有已注册系统的列表
        self.next_entity_id = 0  # 实体ID生成器，每创建一个实体递增

    def create_entity(self):
        """
        创建一个新实体

        返回:
            Entity: 新创建的实体对象
        """
        # 使用当前的ID创建新实体
        entity = Entity(self.next_entity_id, self)
        # 将新实体添加到实体字典
        self.entities[self.next_entity_id] = entity
        # ID递增，为下一个实体准备
        self.next_entity_id += 1
        return entity

    def destroy_entity(self, entity_id):
        """
        销毁一个实体

        参数:
            entity_id: 要销毁的实体ID
        """
        if entity_id in self.entities:
            # 获取实体对象
            entity = self.entities[entity_id]

            # 通知所有系统该实体被销毁，以便系统可以做相应清理
            for system in self.systems:
                system.entity_destroyed(entity)

            # 从世界中移除实体
            del self.entities[entity_id]

    def register_system(self, system):
        """
        注册一个系统到世界中

        参数:
            system: 要注册的系统对象

        返回:
            System: 被注册的系统对象
        """
        # 将系统添加到系统列表
        self.systems.append(system)
        # 设置系统的世界引用
        system.world = self

        # 检查现有实体，将符合系统要求的实体添加到系统中
        for entity_id, entity in self.entities.items():
            if system.is_interested_in(entity):
                system.add_entity(entity)

        return system

    def unregister_system(self, system):
        """
        注销一个系统

        参数:
            system: 要注销的系统对象
        """
        if system in self.systems:
            # 从系统列表移除
            self.systems.remove(system)
            # 清除系统的世界引用
            system.world = None

    def update(self, delta_time):
        """
        更新所有系统

        参数:
            delta_time: 帧间时间差，用于基于时间的更新
        """
        # 按顺序更新每个系统
        for system in self.systems:
            system.update(delta_time)

    def component_added(self, entity, component_class):
        """
        当组件被添加到实体时通知相关系统

        参数:
            entity: 添加了组件的实体
            component_class: 被添加的组件类型
        """
        # 检查每个系统是否对添加了新组件的实体感兴趣
        for system in self.systems:
            # 如果系统对这个实体感兴趣，但实体还不在系统中，则添加
            if system.is_interested_in(entity):
                if entity not in system.entities:
                    system.add_entity(entity)

    def component_removed(self, entity, component_class):
        """
        当组件从实体移除时通知相关系统

        参数:
            entity: 移除了组件的实体
            component_class: 被移除的组件类型
        """
        # 检查每个系统，如果实体不再满足系统的要求，则从系统中移除
        for system in self.systems:
            if entity in system.entities and not system.is_interested_in(entity):
                system.remove_entity(entity)
