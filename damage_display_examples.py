"""
伤害显示系统使用示例和文档
"""

# 示例：在战斗系统中使用专门的显示方法


def example_combat_usage():
    """
    在战斗系统中使用新的伤害显示方法的示例
    """

    # 获取动画系统
    animation_system = get_animation_system()
    position = (100, 200)  # 世界坐标

    # 1. 显示伤害数字（红色，向上移动）
    damage = 25
    animation_system.create_damage_number(damage, position)

    # 2. 显示未命中（灰色，较慢移动）
    animation_system.create_miss_indicator(position)

    # 3. 显示暴击（黄色，更大字体，快速移动）
    animation_system.create_crit_indicator(position)

    # 4. 显示治疗（绿色，带+号）
    healing = 15
    animation_system.create_healing_number(healing, position)

    # 5. 自定义文本指示器
    animation_system.create_text_indicator(
        text="DODGE",
        world_pos=position,
        color=(0, 255, 255),  # 青色
        font_size=20,
        lifetime=1.5,
        velocity=(20, -40),  # 斜向移动
    )


def example_skill_system_usage():
    """
    在技能系统中使用文本指示器的示例
    """

    animation_system = get_animation_system()
    position = (150, 250)

    # 技能激活指示
    animation_system.create_text_indicator(
        text="SKILL!",
        world_pos=position,
        color=(255, 165, 0),  # 橙色
        font_size=26,
        lifetime=2.0,
    )

    # 状态效果指示
    animation_system.create_text_indicator(
        text="POISONED",
        world_pos=position,
        color=(128, 0, 128),  # 紫色
        font_size=18,
        lifetime=3.0,
        velocity=(0, -20),  # 慢速上升
    )


def example_level_up_usage():
    """
    在升级系统中使用指示器的示例
    """

    animation_system = get_animation_system()
    position = (200, 100)

    # 升级指示
    animation_system.create_text_indicator(
        text="LEVEL UP!",
        world_pos=position,
        color=(255, 215, 0),  # 金色
        font_size=32,
        lifetime=3.0,
        velocity=(0, -30),
    )


# 不同指示器类型的颜色和效果指南
INDICATOR_STYLES = {
    "damage": {
        "color": (255, 0, 0),  # 红色
        "font_size": 24,
        "lifetime": 2.0,
        "velocity": (0, -50),
    },
    "healing": {
        "color": (0, 255, 0),  # 绿色
        "font_size": 24,
        "lifetime": 2.0,
        "velocity": (0, -40),
    },
    "miss": {
        "color": (128, 128, 128),  # 灰色
        "font_size": 20,
        "lifetime": 1.5,
        "velocity": (0, -30),
    },
    "crit": {
        "color": (255, 255, 0),  # 黄色
        "font_size": 28,
        "lifetime": 2.5,
        "velocity": (0, -60),
    },
    "dodge": {
        "color": (0, 255, 255),  # 青色
        "font_size": 20,
        "lifetime": 1.5,
        "velocity": (20, -40),
    },
    "block": {
        "color": (0, 0, 255),  # 蓝色
        "font_size": 22,
        "lifetime": 1.8,
        "velocity": (-10, -45),
    },
    "skill": {
        "color": (255, 165, 0),  # 橙色
        "font_size": 26,
        "lifetime": 2.2,
        "velocity": (0, -35),
    },
    "status": {
        "color": (128, 0, 128),  # 紫色
        "font_size": 18,
        "lifetime": 3.0,
        "velocity": (0, -20),
    },
    "level_up": {
        "color": (255, 215, 0),  # 金色
        "font_size": 32,
        "lifetime": 3.0,
        "velocity": (0, -30),
    },
}


def create_styled_indicator(animation_system, style_name: str, text: str, position):
    """
    使用预定义样式创建指示器的便捷函数
    """
    if style_name not in INDICATOR_STYLES:
        style_name = "damage"  # 默认样式

    style = INDICATOR_STYLES[style_name]

    animation_system.create_text_indicator(
        text=text,
        world_pos=position,
        color=style["color"],
        font_size=style["font_size"],
        lifetime=style["lifetime"],
        velocity=style["velocity"],
    )


def get_animation_system():
    """获取动画系统的辅助函数（示例用）"""
    # 这里应该是实际获取动画系统的逻辑
    # 在实际使用中，通过world.systems查找
    pass


if __name__ == "__main__":
    print("伤害显示系统使用指南:")
    print("=" * 50)
    print("1. 使用专门的方法创建不同类型的指示器")
    print("2. 每种类型都有预设的颜色、大小和动画")
    print("3. 可以使用create_text_indicator自定义任意文本")
    print("4. 推荐使用INDICATOR_STYLES中的预定义样式")
    print("=" * 50)
