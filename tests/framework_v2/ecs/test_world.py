import unittest
from framework_v2.ecs.entity import Entity
from framework_v2.ecs.component import Component
from framework_v2.ecs.system import System
from framework_v2.ecs.world import World

class PositionComponent(Component):
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

class MovementSystem(System):
    def __init__(self):
        super().__init__(priority=1)
        self.update_count = 0
        
    def update(self, context, delta_time):
        self.update_count += 1
        # 获取所有拥有位置组件的实体
        entities = context.query_manager.query_with_all([PositionComponent])
        # 更新位置
        for entity in entities:
            pos = context.component_manager.get_component(entity, PositionComponent)
            pos.x += 1 * delta_time
            pos.y += 1 * delta_time

class TestWorld(unittest.TestCase):
    def setUp(self):
        self.world = World()
        
    def test_world_initialization(self):
        """测试世界初始化"""
        self.assertIsNotNone(self.world.entity_manager)
        self.assertIsNotNone(self.world.component_manager)
        self.assertIsNotNone(self.world.system_manager)
        self.assertIsNotNone(self.world.query_manager)
        self.assertIsNotNone(self.world.context)
        
    def test_world_update(self):
        """测试世界更新功能"""
        # 创建实体和组件
        entity = self.world.entity_manager.create_entity()
        pos_component = PositionComponent(10, 20)
        self.world.component_manager.add_component(entity, pos_component)
        
        # 添加系统
        movement_system = MovementSystem()
        self.world.system_manager.add_system(movement_system)
        
        # 更新世界
        delta_time = 0.5
        self.world.update(delta_time)
        
        # 验证系统被调用
        self.assertEqual(movement_system.update_count, 1)
        
        # 验证组件被更新
        self.assertEqual(pos_component.x, 10.5)
        self.assertEqual(pos_component.y, 20.5)
        
    def test_entity_component_integration(self):
        """测试实体和组件的集成"""
        # 创建实体
        entity = self.world.entity_manager.create_entity()
        
        # 添加组件
        pos = PositionComponent(5, 10)
        self.world.component_manager.add_component(entity, pos)
        
        # 查询实体
        entities = self.world.query_manager.query_with_all([PositionComponent])
        self.assertEqual(len(entities), 1)
        self.assertIn(entity, entities)
        
        # 获取组件
        retrieved_pos = self.world.component_manager.get_component(entity, PositionComponent)
        self.assertEqual(retrieved_pos.x, 5)
        self.assertEqual(retrieved_pos.y, 10)
        
        # 移除实体
        self.world.entity_manager.remove_entity(entity)
        entities = self.world.query_manager.query_with_all([PositionComponent])
        self.assertEqual(len(entities), 0)

if __name__ == '__main__':
    unittest.main()