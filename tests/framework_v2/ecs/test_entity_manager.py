import unittest
from framework_v2.ecs.entity import Entity
from framework_v2.ecs.world import EntityManager

class TestEntityManager(unittest.TestCase):
    def setUp(self):
        self.entity_manager = EntityManager()
        
    def test_create_entity(self):
        """测试创建实体功能"""
        entity = self.entity_manager.create_entity()
        self.assertIsInstance(entity, Entity)
        self.assertEqual(entity.id, 0)
        self.assertIn(entity, self.entity_manager.entities)
        
        # 测试创建多个实体
        entity2 = self.entity_manager.create_entity()
        self.assertEqual(entity2.id, 1)
        self.assertEqual(len(self.entity_manager.entities), 2)
        
    def test_remove_entity(self):
        """测试移除实体功能"""
        entity = self.entity_manager.create_entity()
        self.entity_manager.remove_entity(entity)
        self.assertNotIn(entity, self.entity_manager.entities)
        
        # 测试移除不存在的实体
        non_existent_entity = Entity(999)
        self.entity_manager.remove_entity(non_existent_entity)  # 不应该抛出异常

if __name__ == '__main__':
    unittest.main()