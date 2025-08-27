#!/usr/bin/env python3
"""
简化的单元测试：直接测试过滤器逻辑，避免导入依赖问题
"""

import json
import copy
from typing import Dict, Any


def filter_observation_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    从qwen3_agent.py中提取的_filter_observation_result方法
    过滤 observation 结果，移除冗余字段
    """
    # 创建结果的深拷贝以避免修改原始数据
    filtered_result = copy.deepcopy(result)
    
    # 过滤 unit_info 字段，移除无用的噪声关键字
    if "unit_info" in filtered_result and isinstance(filtered_result["unit_info"], dict):
        unit_info = filtered_result["unit_info"]
        
        # 过滤 status 字段中的噪声关键字
        if "status" in unit_info and isinstance(unit_info["status"], dict):
            status = unit_info["status"]
            # 移除 morale 和 fatigue 字段
            status.pop("morale", None)
            status.pop("fatigue", None)
        
        # 过滤 capabilities 字段中的噪声关键字
        if "capabilities" in unit_info and isinstance(unit_info["capabilities"], dict):
            capabilities = unit_info["capabilities"]
            # 移除无用的能力字段
            noise_capabilities = ["attack_points", "construction_points", "skill_points"]
            for noise_key in noise_capabilities:
                capabilities.pop(noise_key, None)
        
        # 移除 available_skills 字段
        unit_info.pop("available_skills", None)
    
    # 过滤 visible_environment 字段
    if "visible_environment" in filtered_result and isinstance(filtered_result["visible_environment"], list):
        filtered_env = []
        for tile in filtered_result["visible_environment"]:
            if isinstance(tile, dict):
                # 保留核心信息，移除噪声字段
                filtered_tile = {
                    "position": tile.get("position"),
                    "terrain": tile.get("terrain"),
                }
                
                # 只在有单位时才包含 units 字段
                units = tile.get("units", [])
                if units:
                    filtered_tile["units"] = units
                
                # 简化 movement_accessibility - 只保留是否可达
                movement_access = tile.get("movement_accessibility", {})
                if isinstance(movement_access, dict) and "reachable" in movement_access:
                    filtered_tile["reachable"] = movement_access["reachable"]
                
                # 简化 attack_range_info - 只保留是否在攻击范围内
                attack_info = tile.get("attack_range_info")
                if isinstance(attack_info, dict) and "in_attack_range" in attack_info:
                    filtered_tile["attackable"] = attack_info["in_attack_range"]
                elif attack_info is True or attack_info is False:
                    filtered_tile["attackable"] = attack_info
                
                filtered_env.append(filtered_tile)
        
        filtered_result["visible_environment"] = filtered_env
    
    return filtered_result


def test_filter_with_noise_keywords():
    """测试过滤包含噪声关键字的观察结果"""
    print("🧪 测试1: 过滤包含噪声关键字的观察结果")
    
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
                "movement_accessibility": {"reachable": True, "cost": 1},
                "attack_range_info": {"in_attack_range": False, "distance": 2}
            }
        ]
    }

    print("\n📥 原始结果:")
    print(json.dumps(original_result, indent=2, ensure_ascii=False))

    # 调用过滤方法
    filtered_result = filter_observation_result(original_result)

    print("\n📤 过滤后结果:")
    print(json.dumps(filtered_result, indent=2, ensure_ascii=False))

    # 验证噪声关键字被移除
    unit_info = filtered_result["unit_info"]
    status = unit_info["status"]
    capabilities = unit_info["capabilities"]

    # 检查噪声字段是否被移除
    noise_removed = []
    if "morale" not in status:
        noise_removed.append("status.morale")
    if "fatigue" not in status:
        noise_removed.append("status.fatigue")
    if "attack_points" not in capabilities:
        noise_removed.append("capabilities.attack_points")
    if "construction_points" not in capabilities:
        noise_removed.append("capabilities.construction_points")
    if "skill_points" not in capabilities:
        noise_removed.append("capabilities.skill_points")
    if "available_skills" not in unit_info:
        noise_removed.append("unit_info.available_skills")

    print(f"\n✅ 成功移除的噪声字段: {', '.join(noise_removed)}")

    # 检查重要字段是否保留
    important_kept = []
    if "current_count" in status:
        important_kept.append("status.current_count")
    if "health_percentage" in status:
        important_kept.append("status.health_percentage")
    if "movement" in capabilities:
        important_kept.append("capabilities.movement")
    if "attack_range" in capabilities:
        important_kept.append("capabilities.attack_range")
    if "action_points" in capabilities:
        important_kept.append("capabilities.action_points")

    print(f"✅ 保留的重要字段: {', '.join(important_kept)}")

    # 验证环境过滤
    env = filtered_result["visible_environment"][0]
    if "reachable" in env and "attackable" in env:
        print("✅ visible_environment 过滤正常")
    
    return len(noise_removed) == 6  # 应该移除6个噪声字段


def test_filter_without_noise():
    """测试过滤不包含噪声关键字的干净结果"""
    print("\n🧪 测试2: 过滤干净的观察结果（无噪声字段）")
    
    clean_result = {
        "success": True,
        "unit_info": {
            "unit_id": 123,
            "unit_type": "infantry",
            "status": {
                "current_count": 100,
                "health_percentage": 1.0
            },
            "capabilities": {
                "movement": 10,
                "attack_range": 1,
                "action_points": 2
            }
        },
        "visible_environment": []
    }

    print("\n📥 原始干净结果:")
    print(json.dumps(clean_result, indent=2, ensure_ascii=False))

    filtered_result = filter_observation_result(clean_result)

    print("\n📤 过滤后结果:")
    print(json.dumps(filtered_result, indent=2, ensure_ascii=False))

    # 验证结果基本一致（因为没有噪声字段需要移除）
    success = (
        filtered_result["unit_info"]["unit_id"] == 123 and
        "movement" in filtered_result["unit_info"]["capabilities"] and
        len(filtered_result["visible_environment"]) == 0
    )
    
    print("✅ 干净结果过滤正常" if success else "❌ 干净结果过滤异常")
    return success


def test_preserve_original():
    """测试原始数据不被修改"""
    print("\n🧪 测试3: 验证原始数据不被修改")
    
    original = {
        "success": True,
        "unit_info": {
            "unit_id": 789,
            "status": {"morale": "high", "current_count": 50},
            "capabilities": {"attack_points": 5, "movement": 15},
            "available_skills": ["charge"]
        }
    }

    # 保存原始副本
    original_copy = json.loads(json.dumps(original))
    
    # 调用过滤方法
    filtered_result = filter_observation_result(original)
    
    # 验证原始数据没有被修改
    original_unchanged = (original == original_copy)
    
    # 验证过滤结果确实不同
    result_changed = (filtered_result != original)
    
    print(f"✅ 原始数据未被修改: {original_unchanged}")
    print(f"✅ 过滤结果已改变: {result_changed}")
    
    return original_unchanged and result_changed


def main():
    """运行所有测试"""
    print("🚀 开始测试 _filter_observation_result 方法")
    print("=" * 60)
    
    test_results = []
    
    # 运行测试
    test_results.append(test_filter_with_noise_keywords())
    test_results.append(test_filter_without_noise())
    test_results.append(test_preserve_original())
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 测试总结:")
    print(f"✅ 通过测试: {sum(test_results)}/{len(test_results)}")
    
    if all(test_results):
        print("🎉 所有测试通过！过滤器工作正常。")
    else:
        print("❌ 部分测试失败，需要检查过滤器逻辑。")
    
    return all(test_results)


if __name__ == "__main__":
    main()
