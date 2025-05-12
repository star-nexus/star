import unittest
from framework_v2.ecs.entity import Entity
from framework_v2.ecs.component import Component
from framework_v2.ecs.world import ComponentManager

class TestComponent(Component):
    def __init__(self, value):
        self.value = value

class AnotherTestComponent(Component):
    def __init__(self, name):
        self.name = name

class TestComponentManager(unittest.TestCase):
    def setUp(self):
        self.component_manager = ComponentManager()
        self.entity = Entity(0)
        
    def test_add_component(self):
        """测试添加组件功能"""
        component = TestComponent(42)
        self.component_manager.add_component(self.entity, component)
        
        self.assertTrue(self.component_manager.has_component(self.entity, TestComponent))
        self.assertEqual(self.component_manager.get_component(self.entity, TestComponent), component)
        
    def test_remove_component(self):
        """测试移除组件功能"""
        component = TestComponent(42)
        self.component_manager.add_component(self.entity, component)
        self.component_manager.remove_component(self.entity, TestComponent)
        
        self.assertFalse(self.component_manager.has_component(self.entity, TestComponent))
        self.assertIsNone(self.component_manager.get_component(self.entity, TestComponent))
        
    def test_get_all_component(self):
        """测试获取实体所有组件功能"""
        component1 = TestComponent(42)
        component2 = AnotherTestComponent("test")
        
        self.component_manager.add_component(self.entity, component1)
        self.component_manager.add_component(self.entity, component2)
        
        all_components = self.component_manager.get_all_component(self.entity)
        self.assertEqual(len(all_components), 2)
        self.assertIn(component1, all_components)
        self.assertIn(component2, all_components)

if __name__ == '__main__':
    unittest.main()