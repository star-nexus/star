from rotk.logics.components import TerrainType, TERRAIN_COLORS


class TerrainUtility:
    """地形工具类，提供地形相关的实用功能"""

    def __init__(self):
        """初始化地形工具类"""
        # 各类地形的移动消耗
        self.terrain_movement_cost = {
            TerrainType.PLAIN: 1.0,      # 平原 - 基础移动消耗
            TerrainType.FOREST: 1.5,      # 森林 - 稍高移动消耗
            TerrainType.MOUNTAIN: 3.0,    # 山地 - 高移动消耗
            TerrainType.HILL: 2.0,        # 丘陵 - 较高移动消耗
            TerrainType.RIVER: 2.5,       # 河流 - 较高移动消耗
            TerrainType.LAKE: 4.0,        # 湖泊 - 很高移动消耗
            TerrainType.BRIDGE: 1.0,      # 桥梁 - 基础移动消耗
            TerrainType.PLATEAU: 1.5,     # 高原 - 稍高移动消耗
            TerrainType.BASIN: 1.2,       # 盆地 - 稍高移动消耗
            TerrainType.SWAMP: 2.5,       # 湿地 - 较高移动消耗
            TerrainType.DESERT: 1.7,      # 沙漠 - 较高移动消耗
            TerrainType.VALLEY: 1.3,      # 山谷 - 稍高移动消耗
            TerrainType.OCEAN: 5.0,       # 海洋 - 极高移动消耗
            TerrainType.COAST: 2.0,       # 海岸 - 较高移动消耗
            TerrainType.URBAN: 0.8,        # 城市 - 低移动消耗
        }
        
        # 地形对应的颜色已在组件中定义为TERRAIN_COLORS
        
        # 地形通行性 - 某些单位可能无法通过某些地形
        self.terrain_passability = {
            # 陆地单位的通行性
            "land": {
                TerrainType.PLAIN: True,
                TerrainType.FOREST: True,
                TerrainType.MOUNTAIN: True,
                TerrainType.HILL: True,
                TerrainType.RIVER: False,
                TerrainType.LAKE: False,
                TerrainType.BRIDGE: True,
                TerrainType.PLATEAU: True,
                TerrainType.BASIN: True,
                TerrainType.SWAMP: True,
                TerrainType.DESERT: True,
                TerrainType.VALLEY: True,
                TerrainType.OCEAN: False,
                TerrainType.COAST: True,
                TerrainType.URBAN: True,
            },
            # 水军单位的通行性
            "naval": {
                TerrainType.PLAIN: False,
                TerrainType.FOREST: False,
                TerrainType.MOUNTAIN: False,
                TerrainType.HILL: False,
                TerrainType.RIVER: True,
                TerrainType.LAKE: True,
                TerrainType.BRIDGE: False,
                TerrainType.PLATEAU: False,
                TerrainType.BASIN: False,
                TerrainType.SWAMP: False,
                TerrainType.DESERT: False,
                TerrainType.VALLEY: False,
                TerrainType.OCEAN: True,
                TerrainType.COAST: True,
                TerrainType.URBAN: False,
            },
            # 骑兵单位的通行性
            "cavalry": {
                TerrainType.PLAIN: True,
                TerrainType.FOREST: False,
                TerrainType.MOUNTAIN: False,
                TerrainType.HILL: True,
                TerrainType.RIVER: False,
                TerrainType.LAKE: False,
                TerrainType.BRIDGE: True,
                TerrainType.PLATEAU: True,
                TerrainType.BASIN: True,
                TerrainType.SWAMP: False,
                TerrainType.DESERT: True,
                TerrainType.VALLEY: True,
                TerrainType.OCEAN: False,
                TerrainType.COAST: False,
                TerrainType.URBAN: True,
            },
        }
        
        # 地形对战斗的影响系数
        self.terrain_combat_modifiers = {
            # 防御加成
            "defense_bonus": {
                TerrainType.PLAIN: 0.0,      # 平原没有防御加成
                TerrainType.FOREST: 0.2,      # 森林提供20%防御加成
                TerrainType.MOUNTAIN: 0.5,    # 山地提供50%防御加成
                TerrainType.HILL: 0.3,        # 丘陵提供30%防御加成
                TerrainType.RIVER: -0.1,      # 河流降低10%防御
                TerrainType.LAKE: -0.2,       # 湖泊降低20%防御
                TerrainType.BRIDGE: 0.0,      # 桥梁没有防御加成
                TerrainType.PLATEAU: 0.25,    # 高原提供25%防御加成
                TerrainType.BASIN: 0.1,       # 盆地提供10%防御加成
                TerrainType.SWAMP: -0.1,      # 湿地降低10%防御
                TerrainType.DESERT: 0.0,      # 沙漠没有防御加成
                TerrainType.VALLEY: 0.15,     # 山谷提供15%防御加成
                TerrainType.OCEAN: -0.3,      # 海洋降低30%防御
                TerrainType.COAST: -0.15,     # 海岸降低15%防御
                TerrainType.URBAN: 0.4,        # 城市提供40%防御加成
            },
            
            # 远程攻击精度修正
            "ranged_accuracy": {
                TerrainType.PLAIN: 0.0,      # 平原没有精度修正
                TerrainType.FOREST: -0.15,    # 森林降低15%精度
                TerrainType.MOUNTAIN: -0.3,   # 山地降低30%精度
                TerrainType.HILL: -0.1,       # 丘陵降低10%精度
                TerrainType.RIVER: 0.0,       # 河流没有精度修正
                TerrainType.LAKE: 0.05,       # 湖泊增加5%精度
                TerrainType.BRIDGE: 0.0,      # 桥梁没有精度修正
                TerrainType.PLATEAU: -0.1,    # 高原降低10%精度
                TerrainType.BASIN: 0.0,       # 盆地没有精度修正
                TerrainType.SWAMP: -0.05,     # 湿地降低5%精度
                TerrainType.DESERT: 0.05,     # 沙漠增加5%精度
                TerrainType.VALLEY: -0.2,     # 山谷降低20%精度
                TerrainType.OCEAN: 0.1,       # 海洋增加10%精度
                TerrainType.COAST: 0.05,      # 海岸增加5%精度
                TerrainType.URBAN: -0.2,       # 城市降低20%精度
            },
        }
        
    def get_movement_cost(self, terrain_type):
        """获取地形的移动消耗
        
        Args:
            terrain_type: 地形类型
            
        Returns:
            float: 移动消耗值
        """
        return self.terrain_movement_cost.get(terrain_type, 1.0)
        
    def get_terrain_color(self, terrain_type):
        """获取地形的颜色
        
        Args:
            terrain_type: 地形类型
            
        Returns:
            tuple: RGB颜色值
        """
        return TERRAIN_COLORS.get(terrain_type, (200, 200, 200))
        
    def can_pass_terrain(self, unit_type, terrain_type):
        """检查特定单位类型是否可以通过指定地形
        
        Args:
            unit_type: 单位类型 ("land", "naval", "cavalry")
            terrain_type: 地形类型
            
        Returns:
            bool: 是否可通行
        """
        if unit_type not in self.terrain_passability:
            return False
            
        return self.terrain_passability[unit_type].get(terrain_type, False)
        
    def get_defense_bonus(self, terrain_type):
        """获取地形提供的防御加成
        
        Args:
            terrain_type: 地形类型
            
        Returns:
            float: 防御加成系数
        """
        return self.terrain_combat_modifiers["defense_bonus"].get(terrain_type, 0.0)
        
    def get_ranged_accuracy_modifier(self, terrain_type):
        """获取地形对远程攻击精度的修正
        
        Args:
            terrain_type: 地形类型
            
        Returns:
            float: 精度修正系数
        """
        return self.terrain_combat_modifiers["ranged_accuracy"].get(terrain_type, 0.0)
        
    def is_water(self, terrain_type):
        """检查地形是否为水域
        
        Args:
            terrain_type: 地形类型
            
        Returns:
            bool: 是否为水域
        """
        return terrain_type in [
            TerrainType.RIVER,
            TerrainType.LAKE,
            TerrainType.OCEAN
        ]
        
    def is_rough_terrain(self, terrain_type):
        """检查地形是否为崎岖地形
        
        Args:
            terrain_type: 地形类型
            
        Returns:
            bool: 是否为崎岖地形
        """
        return terrain_type in [
            TerrainType.MOUNTAIN,
            TerrainType.HILL,
            TerrainType.FOREST,
            TerrainType.SWAMP
        ] 