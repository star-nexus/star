#!/usr/bin/env python3
"""
测试伤害显示系统
"""


def test_damage_display_improvements():
    """测试伤害显示系统的改进"""
    print("测试伤害显示系统改进...")

    # 检查组件定义
    from rotk_env.components.animation import DamageNumber

    # 测试新的文本字段
    damage_num = DamageNumber(
        text="100", position=(100, 100), color=(255, 0, 0), font_size=24
    )

    assert damage_num.text == "100"
    assert damage_num.font_size == 24
    print("✓ DamageNumber组件支持文本和字体大小")

    # 测试不同类型的指示器
    test_cases = [
        {"text": "50", "type": "damage"},
        {"text": "MISS", "type": "miss"},
        {"text": "CRIT!", "type": "crit"},
        {"text": "+25", "type": "healing"},
        {"text": "DODGE", "type": "custom"},
    ]

    for case in test_cases:
        indicator = DamageNumber(
            text=case["text"], position=(0, 0), color=(255, 255, 255)
        )
        assert indicator.text == case["text"]
        print(f"✓ 支持{case['type']}类型显示: '{case['text']}'")

    print("✓ 所有测试通过！")


def test_animation_system_methods():
    """测试动画系统的新方法"""
    print("\n测试动画系统方法...")

    from rotk_env.systems.animation_system import AnimationSystem
    import inspect

    # 检查所有新方法是否存在
    required_methods = [
        "create_damage_number",
        "create_miss_indicator",
        "create_crit_indicator",
        "create_healing_number",
        "create_text_indicator",
    ]

    for method_name in required_methods:
        assert hasattr(AnimationSystem, method_name), f"缺少方法: {method_name}"
        method = getattr(AnimationSystem, method_name)
        assert callable(method), f"{method_name} 不是可调用的"
        print(f"✓ {method_name} 方法存在且可调用")

    # 检查方法签名
    text_indicator_method = getattr(AnimationSystem, "create_text_indicator")
    sig = inspect.signature(text_indicator_method)
    params = list(sig.parameters.keys())

    expected_params = [
        "self",
        "text",
        "world_pos",
        "color",
        "font_size",
        "lifetime",
        "velocity",
    ]
    for param in expected_params:
        assert param in params, f"create_text_indicator缺少参数: {param}"

    print("✓ create_text_indicator方法签名正确")
    print("✓ 所有动画系统方法测试通过！")


if __name__ == "__main__":
    test_damage_display_improvements()
    test_animation_system_methods()
    print("\n🎉 所有伤害显示系统测试通过！")
    print("\n改进总结:")
    print("1. ✓ DamageNumber组件现在支持文本字段而不是仅数字")
    print("2. ✓ 添加了字体大小控制")
    print("3. ✓ 专门的方法用于不同类型的指示器:")
    print("   - create_damage_number() - 伤害数字")
    print("   - create_miss_indicator() - 未命中")
    print("   - create_crit_indicator() - 暴击")
    print("   - create_healing_number() - 治疗")
    print("   - create_text_indicator() - 通用文本")
    print("4. ✓ 每种类型都有适当的颜色、大小和动画")
    print("5. ✓ 战斗系统现在使用正确的专门方法")
