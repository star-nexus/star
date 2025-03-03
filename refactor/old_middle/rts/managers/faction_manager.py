class FactionManager:
    """
    阵营管理器：管理游戏中的阵营定义和配置
    """

    def __init__(self):
        # 预定义的阵营配置
        self.faction_templates = {
            "red": {
                "id": "red",
                "name": "红方阵营",
                "color": (220, 60, 60),
                "resources": {
                    "gold": 500,
                    "weapons": 200,
                    "food": 300,
                    "supplies": 250,
                },
                "bonuses": {"attack": 1.1, "defense": 1.0, "speed": 1.0},  # 攻击力+10%
            },
            "blue": {
                "id": "blue",
                "name": "蓝方阵营",
                "color": (60, 60, 220),
                "resources": {
                    "gold": 500,
                    "weapons": 200,
                    "food": 300,
                    "supplies": 250,
                },
                "bonuses": {"attack": 1.0, "defense": 1.1, "speed": 1.0},  # 防御力+10%
            },
            "green": {
                "id": "green",
                "name": "绿方阵营",
                "color": (60, 220, 60),
                "resources": {
                    "gold": 500,
                    "weapons": 200,
                    "food": 300,
                    "supplies": 250,
                },
                "bonuses": {"attack": 1.0, "defense": 1.0, "speed": 1.1},  # 速度+10%
            },
        }

    def get_faction_definition(self, faction_id, is_player=False):
        """获取指定ID的阵营定义"""
        if faction_id in self.faction_templates:
            # 创建一个模板的副本
            faction_def = self.faction_templates[faction_id].copy()
            # 设置是否为玩家阵营
            faction_def["is_player"] = is_player
            return faction_def
        return None

    def get_faction_definitions(self, player_faction_id="red", ai_faction_ids=None):
        """获取一组阵营定义，用于游戏初始化"""
        if ai_faction_ids is None:
            # 默认AI阵营
            ai_faction_ids = ["blue"]

        faction_definitions = []

        # 添加玩家阵营
        player_def = self.get_faction_definition(player_faction_id, True)
        if player_def:
            faction_definitions.append(player_def)

        # 添加AI阵营
        for ai_id in ai_faction_ids:
            ai_def = self.get_faction_definition(ai_id, False)
            if ai_def:
                faction_definitions.append(ai_def)

        return faction_definitions
