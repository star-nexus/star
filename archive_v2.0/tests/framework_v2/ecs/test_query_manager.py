import unittest
from framework_v2.ecs.entity import Entity
from framework_v2.ecs.component import Component
from framework_v2.ecs.world import EntityManager, ComponentManager
from framework_v2.ecs.query import QueryManager

class PositionComponent(Component):
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

class VelocityComponent(Component):
    def __init__(self, vx=0, vy=0):
        self.vx = vx
        self.vy = vy

class HealthComponent(Component):
    def __init__(self, health=100):
        self.health = health

class TestQueryManager(unittest.TestCase):
    def setUp(self):
        self.entity_manager = EntityManager()
        self.component_manager = ComponentManager()
        self.query_manager = QueryManager(self.entity_manager, self.component_manager)
        
        # 创建一些实体和组件用于测试
        self.entity1 = self.entity_manager.create_entity()
        self.entity2 = self.entity_manager.create_entity()
        self.entity3 = self.entity_manager.create_entity()
        
        # 添加组件
        self.component_manager.add_component(self.entity1, PositionComponent(1, 2))
        self.component_manager.add_component(self.entity1, VelocityComponent(3, 4))
        
        self.component_manager.add_component(self.entity2, PositionComponent(5, 6))
        self.component_manager.add_component(self.entity2, HealthComponent(80))
        
        self.component_manager.add_component(self.entity3, VelocityComponent(7, 8))
        self.component_manager.add_component(self.entity3, HealthComponent(60))
        
    def test_query_with_all(self):
        """测试查询同时拥有所有指定组件的实体"""
        # 查询同时拥有位置和速度组件的实体
        entities = self.query_manager.query_with_all([PositionComponent, VelocityComponent])
        self.assertEqual(len(entities), 1)
        self.assertIn(self.entity1, entities)
        
        # 查询同时拥有位置和生命值组件的实体
        entities = self.query_manager.query_with_all([PositionComponent, HealthComponent])
        self.assertEqual(len(entities), 1)
        self.assertIn(self.entity2, entities)
        
    def test_query_with_any(self):
        """测试查询拥有任意指定组件的实体"""
        # 查询拥有位置或速度组件的实体
        entities = self.query_manager.query_with_any([PositionComponent, VelocityComponent])
        self.assertEqual(len(entities), 3)
        self.assertIn(self.entity1, entities)
        self.assertIn(self.entity2, entities)
        self.assertIn(self.entity3, entities)
        
        # 查询拥有生命值组件的实体
        entities = self.query_manager.query_with_any([HealthComponent])
        self.assertEqual(len(entities), 2)
        self.assertIn(self.entity2, entities)
        self.assertIn(self.entity3, entities)

if __name__ == '__main__':
    unittest.main()