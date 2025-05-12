import unittest
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# 导入测试模块
from tests.framework_v2.ecs.test_entity_manager import TestEntityManager
from tests.framework_v2.ecs.test_component_manager import TestComponentManager
from tests.framework_v2.ecs.test_system_manager import TestSystemManager
from tests.framework_v2.ecs.test_query_manager import TestQueryManager
from tests.framework_v2.ecs.test_world import TestWorld

if __name__ == '__main__':
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加测试用例
    test_suite.addTest(unittest.TestLoader.loadTestsFromTestCase(TestEntityManager))
    test_suite.addTest(unittest.TestLoader.loadTestsFromTestCase(TestComponentManager))
    test_suite.addTest(unittest.TestLoader.loadTestsFromTestCase(TestSystemManager))
    test_suite.addTest(unittest.TestLoader.loadTestsFromTestCase(TestQueryManager))
    test_suite.addTest(unittest.TestLoader.loadTestsFromTestCase(TestWorld))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(test_suite)