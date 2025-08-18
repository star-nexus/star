"""
Encounter地图生成器 - 扩展MapSystem以支持Encounter风格地图
Encounter Map Generator - Extension for MapSystem to support Encounter-style maps
"""

from typing import Dict, Tuple, List
from ..components import HexPosition, Terrain, MapData
from ..prefabs.config import TerrainType, GameConfig

class Tile:
    """临时地块类，用于兼容现有代码"""

    def __init__(self, position):
        self.position = position


class EncounterMapMixin:
    """Encounter地图生成混入类，为MapSystem添加Encounter地图生成功能"""

    def _generate_encounter_map(self):
        """生成Encounter风格地图 - 三线对战格局"""
        # 检查world是否已初始化
        if not hasattr(self, 'world') or self.world is None:
            raise RuntimeError("MapSystem.world未初始化。请确保在initialize()方法中正确设置了world引用。")
        
        map_data = MapData(
            width=GameConfig.MAP_WIDTH,
            height=GameConfig.MAP_HEIGHT,
            tiles={}
        )

        # 定义地图边界（基于六边形坐标系）
        # 使用与其他地图系统一致的计算方式
        map_radius = GameConfig.MAP_WIDTH // 2  # 地图半径，与GameConfig保持一致

        print("[Encounter Map] 🏟️ 开始生成Encounter风格地图...")

        # 先填充基础地形 - 使用与其他地图系统一致的矩形遍历方式
        for q in range(GameConfig.MAP_WIDTH):
            for r in range(GameConfig.MAP_HEIGHT):
                # 转换为以中心为原点的坐标
                center_q = q - map_radius
                center_r = r - map_radius
                
                # 默认为野区地形
                # terrain_type = TerrainType.JUNGLE # no texture
                terrain_type = TerrainType.FOREST # with texture
                
                # 创建地块实体
                tile_entity = self.world.create_entity()
                self.world.add_component(tile_entity, HexPosition(center_q, center_r))
                self.world.add_component(tile_entity, Terrain(terrain_type))
                
                # 兼容现有代码，添加Tile组件
                self.world.add_component(tile_entity, Tile((center_q, center_r)))
                
                # 添加到地图数据
                map_data.tiles[(center_q, center_r)] = tile_entity

        # 定义MOBA地图的关键结构
        self._create_encounter_lanes(map_data)       # 创建三条兵线
        self._create_encounter_river(map_data)       # 创建中央河流
        self._create_encounter_bases(map_data)       # 创建队伍基地
        self._create_encounter_towers(map_data)      # 创建防御塔
        self._create_encounter_jungle_areas(map_data) # 完善野区布局

        # 设置为单例组件
        self.world.add_singleton_component(map_data)
        
        print("[Encounter Map] ✅ Encounter地图生成完成!")
        self._print_encounter_map_summary()

    def _create_encounter_lanes(self, map_data: MapData):
        """创建三条MOBA兵线路径"""
        print("[Encounter Map] 🛣️ 创建三条兵线...")
        
        # 定义三条兵线的路径点 - 适应15x15地图（半径7）
        # 上路 (Top Lane): 左上到右下对角线
        top_lane = [
            (-6, 2), (-5, 1), (-4, 0), (-3, -1), (-2, -2), (-1, -3), (0, -4),
            (1, -5), (2, -6)
        ]
        
        # 中路 (Mid Lane): 左到右水平线
        mid_lane = [
            (-6, 0), (-5, 0), (-4, 0), (-3, 0), (-2, 0), (-1, 0), (0, 0),
            (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0)
        ]
        
        # 下路 (Bot Lane): 左下到右上对角线
        bot_lane = [
            (-2, 6), (-1, 5), (0, 4), (1, 3), (2, 2), (3, 1), (4, 0),
            (5, -1), (6, -2)
        ]
        
        # 创建兵线地形
        for lane_points in [top_lane, mid_lane, bot_lane]:
            for (q, r) in lane_points:
                if (q, r) in map_data.tiles:
                    entity = map_data.tiles[(q, r)]
                    # 更新地形为兵线
                    terrain_comp = self.world.get_component(entity, Terrain)
                    if terrain_comp:
                        # terrain_comp.terrain_type = TerrainType.LANE # no texture
                        terrain_comp.terrain_type = TerrainType.PLAIN # use plain texture

    def _create_encounter_river(self, map_data: MapData):
        """创建中央河流分割区域"""
        print("[Encounter Map] 🌊 创建中央河流...")
        
        # 河流横穿地图中央，形成分界线
        river_points = []
        
        # 倾斜河流穿过中央，分隔上下队伍 - 适应15x15地图
        for q in range(-6, 7):  # 适应map_radius = 7
            for r_offset in [-1, 0, 1]:  # 河流宽度为3格
                r = -q // 2 + r_offset  # 稍微倾斜的河流
                # 确保在15x15地图边界内
                if -7 <= q <= 7 and -7 <= r <= 7:
                    river_points.append((q, r))
        
        # 在河流中央添加特殊区域（类似Roshan坑/Baron坑）
        boss_area = [(0, -1), (0, 0), (0, 1), (-1, 0), (1, -1)]
        
        for (q, r) in river_points:
            if (q, r) in map_data.tiles:
                entity = map_data.tiles[(q, r)]
                terrain_comp = self.world.get_component(entity, Terrain)
                if terrain_comp:
                    if (q, r) in boss_area:
                        terrain_comp.terrain_type = TerrainType.WATER  # Boss区域为深水
                    else:
                        # terrain_comp.terrain_type = TerrainType.RIVER # no texture
                        terrain_comp.terrain_type = TerrainType.WATER # use water texture

    def _create_encounter_bases(self, map_data: MapData):
        """创建队伍基地和主堡"""
        print("[Encounter Map] 🏰 创建队伍基地...")
        
        # 队伍1基地 (左侧，SHU蜀) - 适应15x15地图
        team1_base_area = [(-7, 1), (-7, 0), (-6, 1), (-6, 0), (-5, 1)]
        team1_ancient = (-7, -1)  # 主堡位置，确保在地图边界内
        
        # 队伍2基地 (右侧，WEI魏) - 适应15x15地图 
        team2_base_area = [(7, -1), (7, 0), (6, -1), (6, 0), (5, -1)]
        team2_ancient = (7, 1)  # 主堡位置，确保在地图边界内
        
        # 创建基地区域
        for (q, r) in team1_base_area + team2_base_area:
            if (q, r) in map_data.tiles:
                entity = map_data.tiles[(q, r)]
                terrain_comp = self.world.get_component(entity, Terrain)
                if terrain_comp:
                    # terrain_comp.terrain_type = TerrainType.BASE # no texture
                    terrain_comp.terrain_type = TerrainType.URBAN # use urban texture
        
        # 创建主堡（确保在地图边界内）
        for ancient_pos in [team1_ancient, team2_ancient]:
            q, r = ancient_pos
            # 确保主堡在15x15地图边界内
            if -7 <= q <= 7 and -7 <= r <= 7:
                if (q, r) in map_data.tiles:
                    # 更新现有地块为主堡
                    entity = map_data.tiles[(q, r)]
                    terrain_comp = self.world.get_component(entity, Terrain)
                    if terrain_comp:
                        terrain_comp.terrain_type = TerrainType.CITY  # 使用CITY类型代替ANCIENT
                else:
                    # 如果地块不存在，创建新的主堡地块（理论上不应该发生）
                    tile_entity = self.world.create_entity()
                    self.world.add_component(tile_entity, HexPosition(q, r))
                    self.world.add_component(tile_entity, Terrain(TerrainType.CITY))
                    self.world.add_component(tile_entity, Tile((q, r)))
                    map_data.tiles[(q, r)] = tile_entity

    def _create_encounter_towers(self, map_data: MapData):
        """创建防御塔布局"""
        print("[Encounter Map] 🗼 创建防御塔...")
        
        # 每条兵线上的防御塔位置（按照推进顺序）- 适应15x15地图
        # 上路防御塔：从左上基地到右下基地
        top_towers = [(-5, 1), (-3, -1), (-1, -3), (1, -5)]
        
        # 中路防御塔：从左基地到右基地
        mid_towers = [(-4, 0), (-2, 0), (0, 0), (2, 0), (4, 0)]
        
        # 下路防御塔：从左下到右上
        bot_towers = [(-1, 5), (1, 3), (3, 1), (5, -1)]
        
        all_towers = top_towers + mid_towers + bot_towers
        
        for (q, r) in all_towers:
            if (q, r) in map_data.tiles:
                entity = map_data.tiles[(q, r)]
                terrain_comp = self.world.get_component(entity, Terrain)
                if terrain_comp:
                    # terrain_comp.terrain_type = TerrainType.TOWER  # 使用TOWER类型（如果有纹理）
                    terrain_comp.terrain_type = TerrainType.URBAN  # 临时使用URBAN纹理

    def _create_encounter_jungle_areas(self, map_data: MapData):
        """完善野区布局，添加特殊地形"""
        print("[Encounter Map] 🌲 完善野区布局...")
        
        # 在野区中添加一些特殊地形提供战术多样性 - 适应15x15地图
        # 森林区域（提供隐蔽和伏击机会）
        forest_areas = [
            (-4, 2), (-3, 3), (-2, 4),  # 上方野区森林
            (2, -2), (3, -3), (4, -4),  # 下方野区森林
            (-3, -1), (-2, -2),         # 左侧野区森林
            (2, 2), (3, 1),             # 右侧野区森林
        ]
        
        # 丘陵区域（提供高地优势）
        hill_areas = [
            (-5, 3), (-4, 4),           # 上方丘陵
            (4, -3), (5, -4),           # 下方丘陵
        ]
        
        # 应用森林地形
        for (q, r) in forest_areas:
            if (q, r) in map_data.tiles:
                entity = map_data.tiles[(q, r)]
                terrain_comp = self.world.get_component(entity, Terrain)
                if terrain_comp and terrain_comp.terrain_type == TerrainType.JUNGLE:
                    terrain_comp.terrain_type = TerrainType.FOREST
        
        # 应用丘陵地形
        for (q, r) in hill_areas:
            if (q, r) in map_data.tiles:
                entity = map_data.tiles[(q, r)]
                terrain_comp = self.world.get_component(entity, Terrain)
                if terrain_comp and terrain_comp.terrain_type == TerrainType.JUNGLE:
                    terrain_comp.terrain_type = TerrainType.HILL

    def _print_encounter_map_summary(self):
        """输出MOBA地图生成摘要"""
        print("\n" + "=" * 50)
        print("🏟️ Encounter地图生成摘要")
        print("=" * 50)
        print("📍 地图布局:")
        print("  🛣️ 三条兵线: 上路、中路、下路")
        print("  🌊 中央河流: 战略分界线与Boss区域")
        print("  🌲 四个野区: 提供资源和战术位置")
        print("  🗼 防御塔: 12座塔保护兵线推进")
        print("  🏰 队伍基地: 左右两侧对称分布")
        print("  ⭐ 主堡: 游戏胜负关键目标")
        print("\n🎯 战略要点:")
        print("  • 上中下三路提供多样化战术选择")
        print("  • 河流区域控制Boss争夺")
        print("  • 野区提供经济来源和绕后机会") 
        print("  • 防御塔形成推进节奏控制")
        print("  • 对称设计确保公平竞技")
        print("  • 地形多样性增加战术深度")
        print("=" * 50)
