import unittest
from framework_v2.ecs.system import System
from framework_v2.ecs.world import SystemManager, ECSContext

class TestSystem(System):
    def __init__(self, priority=0):
        super().__init__(priority)
        self.update_called = False
        
    def update(self, context, delta_time):
        self.update_called = True
        self.last_delta_time = delta_time

class AnotherTestSystem(System):
    def __init__(self, priority=0):
        super().__init__(priority)
        self.update_called = False
        
    def update(self, context, delta_time):
        self.update_called = True

class TestSystemManager(unittest.TestCase):
    def setUp(self):
        self.system_manager = SystemManager()
        
    def test_add_system(self):
        """测试添加系统功能"""
        system = TestSystem()
        self.system_manager.add_system(system)
        
        self.assertIn(system, self.system_manager.systems)
        self.assertEqual(self.system_manager.get_system_count(), 1)
        self.assertEqual(self.system_manager.get_system(TestSystem), system)
        
    def test_remove_system(self):
        """测试移除系统功能"""
        system = TestSystem()
        self.system_manager.add_system(system)
        result = self.system_manager.remove_system(system)
        
        self.assertTrue(result)
        self.assertNotIn(system, self.system_manager.systems)
        self.assertEqual(self.system_manager.get_system_count(), 0)
        self.assertIsNone(self.system_manager.get_system(TestSystem))
        
    def test_priority_sorting(self):
        """测试系统优先级排序功能"""
        system1 = TestSystem(priority=1)
        system2 = TestSystem(priority=2)
        system3 = TestSystem(priority=0)
        
        self.system_manager.add_system(system1)
        self.system_manager.add_system(system2)
        self.system_manager.add_system(system3)
        
        # 系统应该按优先级降序排列
        self.assertEqual(self.system_manager.systems[0], system2)
        self.assertEqual(self.system_manager.systems[1], system1)
        self.assertEqual(self.system_manager.systems[2], system3)

if __name__ == '__main__':
    unittest.main()