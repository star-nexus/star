class FactionManager:
    def __init__(self, engine):
        self.engine = engine
        self.factions = {}  # 阵营ID -> 阵营对象
        self.player_faction_id = None  # 玩家阵营ID
        self.faction_colors = [
            (255, 0, 0),    # 红色 - 魏
            (0, 0, 255),    # 蓝色 - 蜀
            (0, 255, 0),    # 绿色 - 吴
            (255, 255, 0),  # 黄色 - 黄巾
            (128, 0, 128)   # 紫色 - 其他
        ]
        
    def create_faction(self, name, is_player=False):
        """创建新阵营"""
        from rotk_v2.components.faction import Faction
        
        faction_id = len(self.factions)
        color = self.faction_colors[faction_id % len(self.faction_colors)]
        
        faction = Faction(faction_id, name, color)
        faction.is_player = is_player
        
        self.factions[faction_id] = faction
        
        if is_player:
            self.player_faction_id = faction_id
            
        return faction_id
        
    def get_faction(self, faction_id):
        """获取阵营对象"""
        return self.factions.get(faction_id)
        
    def get_player_faction(self):
        """获取玩家阵营"""
        if self.player_faction_id is not None:
            return self.factions.get(self.player_faction_id)
        return None
        
    def add_unit_to_faction(self, faction_id, unit_id):
        """将单位添加到阵营"""
        faction = self.get_faction(faction_id)
        if faction:
            faction.add_unit(unit_id)
            
    def remove_unit_from_faction(self, faction_id, unit_id):
        """从阵营移除单位"""
        faction = self.get_faction(faction_id)
        if faction:
            faction.remove_unit(unit_id)
            
    def get_faction_units(self, faction_id):
        """获取阵营的所有单位"""
        faction = self.get_faction(faction_id)
        if faction:
            return faction.units
        return []
        
    def check_victory_conditions(self):
        """检查胜利条件"""
        player_faction = self.get_player_faction()
        if not player_faction:
            return False, None
            
        # 检查玩家是否失败（没有单位）
        if len(player_faction.units) == 0:
            return True, "defeat"
            
        # 检查是否所有敌对阵营都被消灭
        all_enemies_defeated = True
        for faction_id, faction in self.factions.items():
            if faction_id != self.player_faction_id and len(faction.units) > 0:
                all_enemies_defeated = False
                break
                
        if all_enemies_defeated:
            return True, "victory"
            
        return False, None
        
    def create_initial_factions(self):
        """创建初始阵营"""
        # 创建玩家阵营（蜀）
        player_faction_id = self.create_faction("蜀", is_player=True)
        
        # 创建AI阵营
        self.create_faction("魏")
        self.create_faction("吴")
        
        return player_faction_id