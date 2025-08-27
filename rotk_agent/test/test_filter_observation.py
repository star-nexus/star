#!/usr/bin/env python3
"""
单元测试：测试 qwen3_agent.py 中的 _filter_observation_result 方法
"""

import sys
import os
import json
import unittest
from typing import Dict, Any

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# 导入需要测试的类
from rotk_agent.qwen3_agent import StandaloneChatAgent, LLMConfig


class TestFilterObservationResult(unittest.TestCase):
    """测试观察结果过滤器"""

    def setUp(self):
        """设置测试环境"""
        # 创建一个简单的配置，用于初始化Agent
        self.llm_config = LLMConfig(
            provider="test",
            model_id="test-model",
            api_key="test-key"
        )
        self.agent = StandaloneChatAgent(self.llm_config)

    def test_filter_observation_result_with_noise_keywords(self):
        """测试过滤包含噪声关键字的观察结果"""
        # 模拟从ENV返回的原始observation结果（包含噪声关键字）
        original_result = {
            "success": True,
            "unit_info": {
                "unit_id": 232,
                "unit_type": "archer",
                "faction": "wei",
                "position": {
                    "col": 3,
                    "row": -1
                },
                "status": {
                    "current_count": 85,
                    "max_count": 100,
                    "health_percentage": 0.85,
                    "morale": "normal",        # 应该被移除
                    "fatigue": "none"          # 应该被移除
                },
                "capabilities": {
                    "movement": 10,
                    "attack_range": 3,
                    "vision_range": 4,
                    "action_points": 2,
                    "max_action_points": 2,
                    "attack_points": 1,        # 应该被移除
                    "construction_points": 1,  # 应该被移除
                    "skill_points": 1          # 应该被移除
                },
                "available_skills": []         # 应该被移除
            },
            "visible_environment": [
                {
                    "position": {"col": 2, "row": -1},
                    "terrain": "plain",
                    "units": [],
                    "movement_accessibility": {"reachable": True},
                    "attack_range_info": {"in_attack_range": False}
                },
                {
                    "position": {"col": 4, "row": -1},
                    "terrain": "forest",
                    "movement_accessibility": {"reachable": False},
                    "attack_range_info": True
                }
            ]
        }

        # 调用过滤方法
        filtered_result = self.agent._filter_observation_result(original_result)

        # 验证基本结构保持不变
        self.assertTrue(filtered_result["success"])
        self.assertIn("unit_info", filtered_result)
        self.assertIn("visible_environment", filtered_result)

        # 验证unit_info的基本信息保持不变
        unit_info = filtered_result["unit_info"]
        self.assertEqual(unit_info["unit_id"], 232)
        self.assertEqual(unit_info["unit_type"], "archer")
        self.assertEqual(unit_info["faction"], "wei")
        self.assertEqual(unit_info["position"]["col"], 3)
        self.assertEqual(unit_info["position"]["row"], -1)

        # 验证status字段中的噪声关键字被移除
        status = unit_info["status"]
        self.assertEqual(status["current_count"], 85)
        self.assertEqual(status["max_count"], 100)
        self.assertEqual(status["health_percentage"], 0.85)
        self.assertNotIn("morale", status)      # 应该被移除
        self.assertNotIn("fatigue", status)     # 应该被移除

        # 验证capabilities字段中的噪声关键字被移除
        capabilities = unit_info["capabilities"]
        self.assertEqual(capabilities["movement"], 10)
        self.assertEqual(capabilities["attack_range"], 3)
        self.assertEqual(capabilities["vision_range"], 4)
        self.assertEqual(capabilities["action_points"], 2)
        self.assertEqual(capabilities["max_action_points"], 2)
        self.assertNotIn("attack_points", capabilities)        # 应该被移除
        self.assertNotIn("construction_points", capabilities)  # 应该被移除
        self.assertNotIn("skill_points", capabilities)         # 应该被移除

        # 验证available_skills字段被移除
        self.assertNotIn("available_skills", unit_info)  # 应该被移除

        # 验证visible_environment被正确过滤
        visible_env = filtered_result["visible_environment"]
        self.assertEqual(len(visible_env), 2)
        
        # 验证第一个tile
        tile1 = visible_env[0]
        self.assertEqual(tile1["position"]["col"], 2)
        self.assertEqual(tile1["terrain"], "plain")
        self.assertEqual(tile1["units"], [])
        self.assertEqual(tile1["reachable"], True)
        self.assertEqual(tile1["attackable"], False)
        
        # 验证第二个tile
        tile2 = visible_env[1]
        self.assertEqual(tile2["position"]["col"], 4)
        self.assertEqual(tile2["terrain"], "forest")
        self.assertEqual(tile2["reachable"], False)
        self.assertEqual(tile2["attackable"], True)

    def test_filter_observation_result_without_noise_keywords(self):
        """测试过滤不包含噪声关键字的观察结果"""
        # 模拟一个已经很干净的结果
        clean_result = {
            "success": True,
            "unit_info": {
                "unit_id": 123,
                "unit_type": "infantry",
                "faction": "shu",
                "position": {"col": 0, "row": 0},
                "status": {
                    "current_count": 100,
                    "max_count": 100,
                    "health_percentage": 1.0
                },
                "capabilities": {
                    "movement": 10,
                    "attack_range": 1,
                    "vision_range": 2,
                    "action_points": 2,
                    "max_action_points": 2
                }
            },
            "visible_environment": []
        }

        # 调用过滤方法
        filtered_result = self.agent._filter_observation_result(clean_result)

        # 验证结果结构完整性
        self.assertEqual(filtered_result["success"], True)
        self.assertEqual(filtered_result["unit_info"]["unit_id"], 123)
        self.assertEqual(filtered_result["unit_info"]["unit_type"], "infantry")
        self.assertEqual(len(filtered_result["visible_environment"]), 0)
        
        # 验证没有意外删除有用字段
        self.assertIn("movement", filtered_result["unit_info"]["capabilities"])
        self.assertIn("attack_range", filtered_result["unit_info"]["capabilities"])
        self.assertIn("vision_range", filtered_result["unit_info"]["capabilities"])

    def test_filter_observation_result_missing_fields(self):
        """测试处理缺少某些字段的观察结果"""
        incomplete_result = {
            "success": True,
            "unit_info": {
                "unit_id": 456,
                "unit_type": "cavalry"
                # 缺少其他字段
            },
            "visible_environment": []
        }

        # 调用过滤方法（不应该报错）
        filtered_result = self.agent._filter_observation_result(incomplete_result)
        
        # 验证基本结构
        self.assertEqual(filtered_result["success"], True)
        self.assertEqual(filtered_result["unit_info"]["unit_id"], 456)
        self.assertEqual(filtered_result["unit_info"]["unit_type"], "cavalry")

    def test_filter_observation_result_preserves_original(self):
        """测试过滤不会修改原始数据"""
        original_result = {
            "success": True,
            "unit_info": {
                "unit_id": 789,
                "status": {"morale": "high", "fatigue": "tired"},
                "capabilities": {"attack_points": 5, "skill_points": 3},
                "available_skills": ["charge"]
            },
            "visible_environment": []
        }

        # 保存原始数据的副本以供比较
        original_copy = json.loads(json.dumps(original_result))
        
        # 调用过滤方法
        filtered_result = self.agent._filter_observation_result(original_result)
        
        # 验证原始数据没有被修改
        self.assertEqual(original_result, original_copy)
        
        # 验证过滤结果确实不同
        self.assertNotEqual(filtered_result, original_result)
        
        # 验证噪声字段在过滤结果中被移除
        self.assertNotIn("morale", filtered_result["unit_info"]["status"])
        self.assertNotIn("available_skills", filtered_result["unit_info"])

    def test_filter_result_json_serializable(self):
        """测试过滤后的结果可以JSON序列化"""
        test_result = {
            "success": True,
            "unit_info": {
                "unit_id": 999,
                "status": {"morale": "normal", "current_count": 50},
                "capabilities": {"attack_points": 2, "movement": 15},
                "available_skills": ["stealth"]
            },
            "visible_environment": []
        }

        filtered_result = self.agent._filter_observation_result(test_result)
        
        # 验证可以JSON序列化（不会抛出异常）
        try:
            json_str = json.dumps(filtered_result, ensure_ascii=False)
            # 验证可以反序列化
            parsed_back = json.loads(json_str)
            self.assertEqual(parsed_back["unit_info"]["unit_id"], 999)
        except (TypeError, ValueError) as e:
            self.fail(f"过滤结果无法JSON序列化: {e}")


def print_test_example():
    """打印测试示例，展示过滤前后的对比"""
    print("\n" + "="*80)
    print("过滤器测试示例")
    print("="*80)
    
    # 创建测试agent
    config = LLMConfig(provider="test", model_id="test", api_key="test")
    agent = StandaloneChatAgent(config)
    
    # 原始结果
    original = {
        "success": True,
        "unit_info": {
            "unit_id": 232,
            "unit_type": "archer",
            "status": {
                "current_count": 85,
                "health_percentage": 0.85,
                "morale": "normal",        # 噪声
                "fatigue": "none"          # 噪声
            },
            "capabilities": {
                "movement": 10,
                "attack_range": 3,
                "action_points": 2,
                "attack_points": 1,        # 噪声
                "construction_points": 1,  # 噪声
                "skill_points": 1          # 噪声
            },
            "available_skills": []         # 噪声
        }
    }
    
    print("\n原始结果:")
    print(json.dumps(original, indent=2, ensure_ascii=False))
    
    # 过滤后结果
    filtered = agent._filter_observation_result(original)
    
    print("\n过滤后结果:")
    print(json.dumps(filtered, indent=2, ensure_ascii=False))
    
    print("\n" + "="*80)


if __name__ == "__main__":
    # 运行测试示例
    print_test_example()
    
    # 运行单元测试
    print("\n开始运行单元测试...")
    unittest.main(verbosity=2)
