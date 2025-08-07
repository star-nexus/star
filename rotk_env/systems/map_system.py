"""
地图系统 - 管理地图生成和地形 (重构版)
Map System - Managing map generation and terrain (Refactored)
"""

import random
import math
from typing import Dict, Tuple, List
from framework import System, World
from ..components import HexPosition, Terrain, MapData, TerritoryControl
from ..prefabs.config import GameConfig, TerrainType, Faction


class Tile:
    """临时地块类，用于兼容现有代码"""

    def __init__(self, position):
        self.position = position


class MapSystem(System):
    """地图系统 - 管理地图生成和地形"""

    def __init__(self, competitive_mode: bool = True, symmetry_type: str = "square"):
        super().__init__(priority=100)
        self.competitive_mode = competitive_mode
        self.symmetry_type = symmetry_type  # "horizontal", "diagonal", "river_split", "square"
        self.seed = 42

    def initialize(self, world: World) -> None:
        self.world = world
        self.generate_map()

    def subscribe_events(self):
        """订阅事件"""
        pass

    def update(self, delta_time: float) -> None:
        """更新地图系统"""
        pass

    def generate_map(self):
        """生成地图 - 根据模式选择生成方式"""
        if self.competitive_mode:
            if self.symmetry_type == "river_split":
                print("[MapSystem] 🏆 生成河流分割对角线竞技地图")
                self._generate_river_split_diagonal_map()
            elif self.symmetry_type == "diagonal":
                print("[MapSystem] 🏆 生成对角线对称竞技地图")
                self._generate_competitive_map_diagonal()
            elif self.symmetry_type == "square":
                print("[MapSystem] 🏆 生成正方形竞技地图")
                self._generate_square_map()
            else:
                print("[MapSystem] 🏆 生成水平轴对称竞技地图")
                self._generate_competitive_map_v2()
        else:
            print("[MapSystem] 🌍 生成标准随机地图")
            self._generate_standard_map()

    def _generate_square_map(self):
        """生成地图 - 生成视觉上为正方形的六边形地图"""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        # 计算地图的半径，使其能容纳正方形区域
        map_radius = max(GameConfig.MAP_WIDTH, GameConfig.MAP_HEIGHT) // 2

        # 使用矩形边界约束生成六边形地图，确保视觉上为正方形
        for q in range(-map_radius, map_radius + 1):
            for r in range(-map_radius, map_radius + 1):
                # 计算世界坐标来检查是否在正方形边界内
                from ..utils.hex_utils import HexConverter

                hex_converter = HexConverter(
                    GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
                )
                world_x, world_y = hex_converter.hex_to_pixel(q, r)

                # 定义正方形边界（基于世界坐标）
                half_width = (
                    GameConfig.MAP_WIDTH * GameConfig.HEX_SIZE * 0.75
                )  # 调整系数以获得更好的正方形效果
                half_height = GameConfig.MAP_HEIGHT * GameConfig.HEX_SIZE * 0.65

                # 检查当前六边形是否在正方形边界内
                if abs(world_x) <= half_width and abs(world_y) <= half_height:
                    # 随机生成地形
                    terrain_type = self._generate_terrain(q, r)

                    # 创建地块实体
                    tile_entity = self.world.create_entity()
                    self.world.add_component(tile_entity, HexPosition(q, r))
                    self.world.add_component(tile_entity, Terrain(terrain_type))
                    self.world.add_component(tile_entity, Tile((q, r)))

                    # 添加到地图数据
                    map_data.tiles[(q, r)] = tile_entity

        self.world.add_singleton_component(map_data)

    def _generate_competitive_map_v2(self):
        """🏆 生成竞技对抗地图 V2.0 - 真正的对称性"""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        print(f"[MapSystem] 生成 {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} 真正对称竞技地图")
        
        # 直接生成完整地图 - 每个坐标的地形由对称函数决定
        terrain_map = self._generate_symmetric_terrain_map()
        
        # 创建ECS实体
        self._create_competitive_map_entities(map_data, terrain_map)
        
        # 添加到世界
        self.world.add_singleton_component(map_data)
        
        # 打印分析报告
        self._print_competitive_map_analysis_v2(terrain_map)

    def _generate_symmetric_terrain_map(self) -> Dict[Tuple[int, int], TerrainType]:
        """生成完全对称的地形地图"""
        terrain_map = {}
        center = GameConfig.MAP_WIDTH // 2
        
        # 遍历整个地图
        for q in range(GameConfig.MAP_WIDTH):
            for r in range(GameConfig.MAP_HEIGHT):
                # 转换为以中心为原点的坐标
                center_q = q - center
                center_r = r - center
                
                # 🔥 核心：使用保证对称的地形生成函数
                terrain = self._generate_symmetric_terrain(center_q, center_r)
                terrain_map[(center_q, center_r)] = terrain
        
        return terrain_map

    def _generate_symmetric_terrain(self, q: int, r: int) -> TerrainType:
        """🎯 生成绝对对称的地形 - 核心算法"""
        
        # 🔥 关键：使用abs(r)确保对称性
        abs_r = abs(r)
        distance_from_center = math.sqrt(q * q + abs_r * abs_r)
        
        # 使用对称的种子：对于(q,r)和(q,-r)产生相同的随机数
        symmetric_seed = q * 10007 + abs_r * 10009 + self.seed
        rand = random.Random(symmetric_seed)
        value = rand.random()
        
        # === Zone A: 出生点/大本营区域 ===
        if abs_r >= 6:  # 地图的南北两端
            return self._generate_spawn_area_terrain(q, abs_r, value)
        
        # === Zone B: 中央战略区 ===
        elif distance_from_center <= 1.5:  # 正中心
            return self._generate_central_zone_terrain(q, abs_r, value)
        
        # === Zone C: 战术缓冲带 ===
        elif distance_from_center <= 4.5:
            return self._generate_tactical_buffer_terrain(q, abs_r, value)
        
        # === Zone D: 对抗主路 ===
        else:  # 外围区域
            return self._generate_outer_zone_terrain(q, abs_r, value)

    def _generate_spawn_area_terrain(self, q: int, abs_r: int, value: float) -> TerrainType:
        """生成出生点区域地形 - 安全且资源丰富"""
        abs_q = abs(q)
        
        # 出生点核心：纯平原，便于初期部署
        if abs_q <= 1 and abs_r >= 6:
            return TerrainType.PLAIN
        
        # 出生点周围：混合平原、丘陵、少量森林
        if value < 0.6:
            return TerrainType.PLAIN    # 60% 平原
        elif value < 0.8:
            return TerrainType.HILL     # 20% 丘陵
        else:
            return TerrainType.FOREST   # 20% 森林

    def _generate_central_zone_terrain(self, q: int, abs_r: int, value: float) -> TerrainType:
        """生成中央战略区地形 - 高价值目标"""
        
        # 正中心点：唯一的城市
        if q == 0 and abs_r == 0:
            return TerrainType.URBAN
        
        # 中心周围：高价值地形
        if value < 0.4:
            return TerrainType.PLAIN    # 40% 平原
        elif value < 0.7:
            return TerrainType.HILL     # 30% 丘陵 (高地优势)
        else:
            return TerrainType.FOREST   # 30% 森林 (战术掩护)

    def _generate_tactical_buffer_terrain(self, q: int, abs_r: int, value: float) -> TerrainType:
        """生成战术缓冲带地形 - 多样化战术选择"""
        abs_q = abs(q)
        
        # 接近中轴线：相对开阔的主要通道
        if abs_q <= 2:
            if value < 0.5:
                return TerrainType.PLAIN
            elif value < 0.8:
                return TerrainType.HILL
            else:
                return TerrainType.FOREST
        
        # 边缘区域：更多障碍和战术地形
        else:
            if value < 0.25:
                return TerrainType.PLAIN
            elif value < 0.5:
                return TerrainType.HILL
            elif value < 0.75:
                return TerrainType.FOREST
            elif value < 0.9:
                return TerrainType.MOUNTAIN
            else:
                return TerrainType.WATER  # 少量水域作为天然屏障

    def _generate_outer_zone_terrain(self, q: int, abs_r: int, value: float) -> TerrainType:
        """生成外围区域地形 - 平衡的多样化"""
        
        # 边缘地带：更多山地和水域作为天然边界
        if abs(q) >= 6 or abs_r >= 5:
            if value < 0.3:
                return TerrainType.MOUNTAIN
            elif value < 0.5:
                return TerrainType.WATER
            elif value < 0.8:
                return TerrainType.FOREST
            else:
                return TerrainType.HILL
        
        # 中等距离：平衡的混合地形
        else:
            if value < 0.35:
                return TerrainType.PLAIN
            elif value < 0.55:
                return TerrainType.HILL
            elif value < 0.75:
                return TerrainType.FOREST
            elif value < 0.85:
                return TerrainType.MOUNTAIN
            else:
                return TerrainType.WATER

    def _create_competitive_map_entities(self, map_data: MapData, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """创建竞技地图的实体"""
        spawn_distance = min(GameConfig.MAP_WIDTH, GameConfig.MAP_HEIGHT) // 2 - 1
        spawn_points = {
            Faction.SHU: (0, spawn_distance),      # 上方出生点
            Faction.WEI: (0, -spawn_distance),     # 下方出生点
        }
        
        for (q, r), terrain_type in terrain_map.items():
            # 创建地块实体
            tile_entity = self.world.create_entity()
            self.world.add_component(tile_entity, HexPosition(q, r))
            self.world.add_component(tile_entity, Terrain(terrain_type))
            self.world.add_component(tile_entity, Tile((q, r)))
            
            # 在出生点附近设置初始领土控制
            controlling_faction = self._get_initial_territory_control((q, r), spawn_points)
            if controlling_faction:
                self.world.add_component(tile_entity, TerritoryControl(
                    controlling_faction=controlling_faction,
                    being_captured=False,
                    capturing_unit=None,
                    capture_progress=0.0,
                    capture_time_required=5.0,
                    fortified=False,
                    fortification_level=0,
                    captured_time=0.0,
                    is_city=(terrain_type == TerrainType.URBAN)
                ))
            
            # 添加到地图数据
            map_data.tiles[(q, r)] = tile_entity

    def _get_initial_territory_control(self, pos: Tuple[int, int], 
                                     spawn_points: Dict[Faction, Tuple[int, int]], 
                                     control_radius: int = 2) -> Faction:
        """确定初始领土控制"""
        q, r = pos
        
        for faction, (spawn_q, spawn_r) in spawn_points.items():
            distance = math.sqrt((q - spawn_q) ** 2 + (r - spawn_r) ** 2)
            if distance <= control_radius:
                return faction
        
        return None

    def _print_competitive_map_analysis_v2(self, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """打印竞技地图分析报告 V2.0"""
        terrain_count = {}
        for terrain in terrain_map.values():
            terrain_count[terrain] = terrain_count.get(terrain, 0) + 1
        
        print("\n" + "="*70)
        print("🏆 竞技对抗地图分析报告 V2.0")
        print("="*70)
        print(f"📐 地图尺寸: {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT}")
        print(f"🎯 设计原则: 绝对水平轴对称，战略区域分层")
        print(f"⚖️  对称轴: 水平中轴线 (r=0)")
        print(f"🔢 固定种子: {self.seed} (确保可重现)")
        
        print("\n🌍 地形分布统计:")
        total_tiles = len(terrain_map)
        for terrain, count in sorted(terrain_count.items(), key=lambda x: x[1], reverse=True):
            percentage = count / total_tiles * 100
            print(f"  {terrain.value:10} {count:3d} 块 ({percentage:5.1f}%)")
        
        # 详细地图可视化打印
        self._print_terrain_map_visual(terrain_map)
        
        # 严格的对称性验证
        self._verify_map_symmetry_v2(terrain_map)
        
        # 战略区域分析
        self._analyze_strategic_zones(terrain_map)
        
        # 出生点信息
        spawn_distance = min(GameConfig.MAP_WIDTH, GameConfig.MAP_HEIGHT) // 2 - 1
        print(f"\n🚀 阵营出生点:")
        print(f"  SHU (蜀): (0, {spawn_distance})  - 地图上方")
        print(f"  WEI (魏): (0, {-spawn_distance}) - 地图下方")
        print(f"  📏 出生点距离: {2 * spawn_distance} 格")
        
        print("="*70)

    def _print_terrain_map_visual(self, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """🗺️ 打印地图的可视化表示"""
        print("\n🗺️ 地形地图可视化 (r从上到下, q从左到右):")
        print("   地形符号: P=平原 F=森林 H=丘陵 M=山地 W=水域 U=城市")
        
        terrain_chars = {
            TerrainType.PLAIN: 'P',
            TerrainType.FOREST: 'F', 
            TerrainType.HILL: 'H',
            TerrainType.MOUNTAIN: 'M',
            TerrainType.WATER: 'W',
            TerrainType.URBAN: 'U'
        }
        
        center = GameConfig.MAP_WIDTH // 2
        print("\n   ", end="")
        
        # 打印列标题 (q坐标)
        for q in range(-center, center + 1):
            print(f"{q:2}", end=" ")
        print()
        
        # 打印每一行
        for r in range(center, -center - 1, -1):  # 从上到下 (r=7到r=-7)
            print(f"{r:2}:", end=" ")
            for q in range(-center, center + 1):
                if (q, r) in terrain_map:
                    terrain = terrain_map[(q, r)]
                    char = terrain_chars.get(terrain, '?')
                    print(f" {char}", end=" ")
                else:
                    print("  ", end=" ")
            print(f" :{r}")
        
        # 再次打印底部列标题
        print("   ", end="")
        for q in range(-center, center + 1):
            print(f"{q:2}", end=" ")
        print()

    def _verify_map_symmetry_v2(self, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """🔍 严格验证地图对称性 V2.0"""
        print(f"\n🔍 对称性验证 V2.0:")
        
        asymmetric_pairs = []
        symmetric_pairs = 0
        total_checks = 0
        
        center = GameConfig.MAP_WIDTH // 2
        
        # 检查每个位置与其镜像位置
        for q in range(-center, center + 1):
            for r in range(-center, center + 1):
                if (q, r) in terrain_map:
                    mirror_pos = (q, -r)
                    total_checks += 1
                    
                    if mirror_pos in terrain_map:
                        if terrain_map[(q, r)] == terrain_map[mirror_pos]:
                            symmetric_pairs += 1
                        else:
                            asymmetric_pairs.append({
                                'pos1': (q, r), 
                                'terrain1': terrain_map[(q, r)].value,
                                'pos2': mirror_pos, 
                                'terrain2': terrain_map[mirror_pos].value
                            })
                    else:
                        asymmetric_pairs.append({
                            'pos1': (q, r), 
                            'terrain1': terrain_map[(q, r)].value,
                            'pos2': mirror_pos, 
                            'terrain2': '缺失'
                        })
        
        if len(asymmetric_pairs) == 0:
            print(f"  ✅ 完美对称！{symmetric_pairs}/{total_checks} 个位置完全对称")
        else:
            print(f"  ❌ 发现 {len(asymmetric_pairs)} 个不对称位置:")
            for i, pair in enumerate(asymmetric_pairs[:5]):
                print(f"    {pair['pos1']}={pair['terrain1']} ≠ {pair['pos2']}={pair['terrain2']}")
            if len(asymmetric_pairs) > 5:
                print(f"    ... 还有 {len(asymmetric_pairs) - 5} 个不对称位置")

    def _analyze_strategic_zones(self, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """分析战略区域分布"""
        print(f"\n🎯 战略区域分析:")
        
        zones = {
            "出生点区域": 0,
            "中央战略区": 0, 
            "战术缓冲带": 0,
            "外围区域": 0
        }
        
        center = GameConfig.MAP_WIDTH // 2
        
        for q in range(-center, center + 1):
            for r in range(-center, center + 1):
                if (q, r) in terrain_map:
                    abs_r = abs(r)
                    distance_from_center = math.sqrt(q * q + abs_r * abs_r)
                    
                    if abs_r >= 6:
                        zones["出生点区域"] += 1
                    elif distance_from_center <= 1.5:
                        zones["中央战略区"] += 1
                    elif distance_from_center <= 4.5:
                        zones["战术缓冲带"] += 1
                    else:
                        zones["外围区域"] += 1
        
        for zone_name, count in zones.items():
            print(f"  {zone_name}: {count} 块")

    def _generate_competitive_map_diagonal(self):
        """🏆 生成对角线对称竞技地图"""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        print(f"[MapSystem] 生成 {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} 对角线对称竞技地图")
        
        # 生成对角线对称地图
        terrain_map = self._generate_diagonal_symmetric_terrain_map()
        
        # 创建ECS实体（使用对角线出生点）
        self._create_diagonal_competitive_map_entities(map_data, terrain_map)
        
        # 添加到世界
        self.world.add_singleton_component(map_data)
        
        # 打印分析报告
        self._print_diagonal_competitive_map_analysis(terrain_map)

    def _generate_diagonal_symmetric_terrain_map(self) -> Dict[Tuple[int, int], TerrainType]:
        """生成对角线对称的地形地图"""
        terrain_map = {}
        center = GameConfig.MAP_WIDTH // 2
        
        # 只需要生成左上三角形，然后镜像到右下三角形
        for q in range(GameConfig.MAP_WIDTH):
            for r in range(GameConfig.MAP_HEIGHT):
                center_q = q - center
                center_r = r - center
                
                # 检查是否在左上三角形或对角线上
                if center_q <= -center_r:  # 左上三角形 + 对角线
                    terrain = self._generate_diagonal_terrain(center_q, center_r)
                    terrain_map[(center_q, center_r)] = terrain
                    
                    # 同时生成对角线对称点（如果不在对角线上）
                    if center_q != -center_r:  # 不在对角线上
                        mirror_q, mirror_r = -center_r, -center_q
                        terrain_map[(mirror_q, mirror_r)] = terrain
                
        return terrain_map

    def _generate_diagonal_terrain(self, q: int, r: int) -> TerrainType:
        """🎯 生成对角线对称地形的基础地形"""
        
        # 计算到对角线的距离（对角线方程：q + r = 0）
        distance_to_diagonal = abs(q + r) / math.sqrt(2)
        
        # 计算到地图中心的距离
        distance_from_center = math.sqrt(q * q + r * r)
        
        # 🔥 关键：使用对对角线对称的种子
        # 对于(q,r)和(-r,-q)，这个种子是相同的
        min_coord = min(q, -r)
        max_coord = max(q, -r)
        symmetric_seed = min_coord * 10007 + max_coord * 10009 + self.seed
        rand = random.Random(symmetric_seed)
        value = rand.random()
        
        # === Zone A: 出生点区域（左上角和右下角） ===
        if (q <= -5 and r >= 5) or (q >= 5 and r <= -5):
            return self._generate_diagonal_spawn_area_terrain(q, r, value)
        
        # === Zone B: 中央区域 ===
        elif distance_from_center <= 1.5:
            return self._generate_diagonal_central_terrain(q, r, value)
        
        # === Zone C: 对角线缓冲带 ===
        elif distance_to_diagonal <= 2.0:
            return self._generate_diagonal_buffer_terrain(q, r, value)
        
        # === Zone D: 外围区域 ===
        else:
            return self._generate_diagonal_outer_terrain(q, r, value)

    def _generate_diagonal_spawn_area_terrain(self, q: int, r: int, value: float) -> TerrainType:
        """生成对角线模式的出生点区域地形"""
        # 出生点核心：平原为主
        if abs(q + 6) <= 1 and abs(r - 6) <= 1:  # 左上出生点核心
            return TerrainType.PLAIN
        if abs(q - 6) <= 1 and abs(r + 6) <= 1:  # 右下出生点核心（对称）
            return TerrainType.PLAIN
        
        # 出生点周围：安全的混合地形
        if value < 0.5:
            return TerrainType.PLAIN
        elif value < 0.75:
            return TerrainType.HILL
        else:
            return TerrainType.FOREST

    def _generate_diagonal_central_terrain(self, q: int, r: int, value: float) -> TerrainType:
        """生成对角线模式的中央区域地形"""
        # 正中心：城市
        if q == 0 and r == 0:
            return TerrainType.URBAN
        
        # 中心周围：高价值地形
        if value < 0.4:
            return TerrainType.PLAIN
        elif value < 0.7:
            return TerrainType.HILL
        else:
            return TerrainType.FOREST

    def _generate_diagonal_buffer_terrain(self, q: int, r: int, value: float) -> TerrainType:
        """生成对角线缓冲带地形"""
        # 主对角线附近：相对开阔
        if value < 0.4:
            return TerrainType.PLAIN
        elif value < 0.65:
            return TerrainType.HILL
        elif value < 0.8:
            return TerrainType.FOREST
        else:
            return TerrainType.MOUNTAIN

    def _generate_diagonal_outer_terrain(self, q: int, r: int, value: float) -> TerrainType:
        """生成对角线模式的外围地形"""
        # 边缘：更多障碍
        if abs(q) >= 6 or abs(r) >= 6:
            if value < 0.3:
                return TerrainType.MOUNTAIN
            elif value < 0.5:
                return TerrainType.WATER
            else:
                return TerrainType.FOREST
        else:
            # 中等距离：平衡地形
            if value < 0.3:
                return TerrainType.PLAIN
            elif value < 0.5:
                return TerrainType.HILL
            elif value < 0.7:
                return TerrainType.FOREST
            elif value < 0.85:
                return TerrainType.MOUNTAIN
            else:
                return TerrainType.WATER

    def _create_diagonal_competitive_map_entities(self, map_data: MapData, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """创建对角线对称竞技地图的实体"""
        # 对角线模式的出生点
        spawn_points = {
            Faction.SHU: (-6, 6),   # 左上角
            Faction.WEI: (6, -6),   # 右下角
        }
        
        for (q, r), terrain_type in terrain_map.items():
            # 创建地块实体
            tile_entity = self.world.create_entity()
            self.world.add_component(tile_entity, HexPosition(q, r))
            self.world.add_component(tile_entity, Terrain(terrain_type))
            self.world.add_component(tile_entity, Tile((q, r)))
            
            # 在出生点附近设置初始领土控制
            controlling_faction = self._get_initial_territory_control((q, r), spawn_points, control_radius=3)
            if controlling_faction:
                self.world.add_component(tile_entity, TerritoryControl(
                    controlling_faction=controlling_faction,
                    being_captured=False,
                    capturing_unit=None,
                    capture_progress=0.0,
                    capture_time_required=5.0,
                    fortified=False,
                    fortification_level=0,
                    captured_time=0.0,
                    is_city=(terrain_type == TerrainType.URBAN)
                ))
            
            # 添加到地图数据
            map_data.tiles[(q, r)] = tile_entity

    def _print_diagonal_competitive_map_analysis(self, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """打印对角线竞技地图分析报告"""
        terrain_count = {}
        for terrain in terrain_map.values():
            terrain_count[terrain] = terrain_count.get(terrain, 0) + 1
        
        print("\n" + "="*70)
        print("🏆 对角线对称竞技地图分析报告")
        print("="*70)
        print(f"📐 地图尺寸: {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT}")
        print(f"🎯 设计原则: 对角线对称 (q=-r轴)，左上↔右下")
        print(f"⚖️  对称轴: 主对角线 (q + r = 0)")
        print(f"🔢 固定种子: {self.seed} (确保可重现)")
        
        print("\n🌍 地形分布统计:")
        total_tiles = len(terrain_map)
        for terrain, count in sorted(terrain_count.items(), key=lambda x: x[1], reverse=True):
            percentage = count / total_tiles * 100
            print(f"  {terrain.value:10} {count:3d} 块 ({percentage:5.1f}%)")
        
        # 地图可视化
        self._print_terrain_map_visual(terrain_map)
        
        # 对角线对称性验证
        self._verify_diagonal_symmetry(terrain_map)
        
        # 出生点信息
        print(f"\n🚀 阵营出生点:")
        print(f"  SHU (蜀): (-6, 6)  - 左上角")
        print(f"  WEI (魏): (6, -6)  - 右下角")
        print(f"  📏 出生点距离: {math.sqrt((12)**2 + (12)**2):.1f} 格")
        
        print("="*70)

    def _verify_diagonal_symmetry(self, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """🔍 验证对角线对称性"""
        print(f"\n🔍 对角线对称性验证:")
        
        asymmetric_pairs = []
        symmetric_pairs = 0
        total_checks = 0
        
        center = GameConfig.MAP_WIDTH // 2
        
        # 检查每个位置与其对角线镜像位置
        for q in range(-center, center + 1):
            for r in range(-center, center + 1):
                if (q, r) in terrain_map:
                    mirror_pos = (-r, -q)  # 对角线镜像
                    total_checks += 1
                    
                    if mirror_pos in terrain_map:
                        if terrain_map[(q, r)] == terrain_map[mirror_pos]:
                            symmetric_pairs += 1
                        else:
                            asymmetric_pairs.append({
                                'pos1': (q, r), 
                                'terrain1': terrain_map[(q, r)].value,
                                'pos2': mirror_pos, 
                                'terrain2': terrain_map[mirror_pos].value
                            })
                    else:
                        asymmetric_pairs.append({
                            'pos1': (q, r), 
                            'terrain1': terrain_map[(q, r)].value,
                            'pos2': mirror_pos, 
                            'terrain2': '缺失'
                        })
        
        if len(asymmetric_pairs) == 0:
            print(f"  ✅ 完美对角线对称！{symmetric_pairs}/{total_checks} 个位置完全对称")
        else:
            print(f"  ❌ 发现 {len(asymmetric_pairs)} 个不对称位置:")
            for i, pair in enumerate(asymmetric_pairs[:5]):
                print(f"    {pair['pos1']}={pair['terrain1']} ≠ {pair['pos2']}={pair['terrain2']}")
            if len(asymmetric_pairs) > 5:
                print(f"    ... 还有 {len(asymmetric_pairs) - 5} 个不对称位置")

    # 保留原有方法以兼容性
    def _generate_standard_map(self):
        """生成标准随机地图（原有逻辑）"""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        # 生成地图
        for q in range(GameConfig.MAP_WIDTH):
            for r in range(GameConfig.MAP_HEIGHT):
                # 转换为以中心为原点的坐标系
                center_q = q - GameConfig.MAP_WIDTH // 2
                center_r = r - GameConfig.MAP_HEIGHT // 2

                # 随机生成地形
                terrain_type = self._generate_terrain(center_q, center_r)

                # 创建地块实体
                tile_entity = self.world.create_entity()
                self.world.add_component(tile_entity, HexPosition(center_q, center_r))
                self.world.add_component(tile_entity, Terrain(terrain_type))
                self.world.add_component(tile_entity, Tile((center_q, center_r)))

                # 添加到地图数据
                map_data.tiles[(center_q, center_r)] = tile_entity

        self.world.add_singleton_component(map_data)

    def get_competitive_spawn_positions(self) -> Dict[Faction, Tuple[int, int]]:
        """获取竞技模式的出生位置"""
        if not self.competitive_mode:
            return {}
            
        if self.symmetry_type == "river_split":
            return {
                Faction.SHU: (-4, 4),   # 左上区域前沿
                Faction.WEI: (4, -4)    # 右下区域前沿
            }
        elif self.symmetry_type == "diagonal":
            return {
                Faction.SHU: (-6, 6),   # 左上角
                Faction.WEI: (6, -6)    # 右下角
            }
        else:
            # 水平对称模式
            spawn_distance = min(GameConfig.MAP_WIDTH, GameConfig.MAP_HEIGHT) // 2 - 1
            return {
                Faction.SHU: (0, spawn_distance),
                Faction.WEI: (0, -spawn_distance)
            }

    def enable_competitive_mode(self, enabled: bool = True):
        """启用/禁用竞技模式"""
        self.competitive_mode = enabled
        print(f"[MapSystem] 竞技模式: {'启用' if enabled else '禁用'}")

    # 保留原有的地形生成方法以兼容性
    def _generate_terrain(self, q: int, r: int) -> TerrainType:
        """生成地形类型 - 适配地图（原有方法保持不变）"""
        # 使用固定种子确保地形生成的一致性
        rand = random.Random(q * 10007 + r * 10009)
        value = rand.random()

        # 距离中心的距离
        distance = math.sqrt(q * q + r * r)
        max_distance = math.sqrt((GameConfig.MAP_WIDTH//2) ** 2 + (GameConfig.MAP_HEIGHT//2) ** 2)
        distance_ratio = distance / max_distance

        # 基于距离和随机值决定地形
        if distance < 3:
            # 中心区域：更多城池和平原
            if value < 0.2:
                return TerrainType.URBAN
            elif value < 0.7:
                return TerrainType.PLAIN
            elif value < 0.85:
                return TerrainType.HILL
            else:
                return TerrainType.FOREST
        elif distance_ratio > 0.8:
            # 边缘区域：更多山地和水域
            if value < 0.25:
                return TerrainType.MOUNTAIN
            elif value < 0.4:
                return TerrainType.WATER
            elif value < 0.7:
                return TerrainType.FOREST
            else:
                return TerrainType.HILL
        elif distance_ratio > 0.6:
            # 外围区域：混合地形
            if value < 0.3:
                return TerrainType.FOREST
            elif value < 0.5:
                return TerrainType.HILL
            elif value < 0.65:
                return TerrainType.MOUNTAIN
            elif value < 0.75:
                return TerrainType.WATER
            else:
                return TerrainType.PLAIN
        else:
            # 中间区域：平衡的多样化地形
            if value < 0.35:
                return TerrainType.PLAIN
            elif value < 0.55:
                return TerrainType.FOREST
            elif value < 0.75:
                return TerrainType.HILL
            elif value < 0.85:
                return TerrainType.MOUNTAIN
            elif value < 0.92:
                return TerrainType.WATER
            else:
                return TerrainType.URBAN

    def set_symmetry_type(self, symmetry_type: str):
        """设置对称类型"""
        if symmetry_type in ["horizontal", "diagonal", "river_split"]:
            self.symmetry_type = symmetry_type
            print(f"[MapSystem] 对称类型设置为: {symmetry_type}")
        else:
            print(f"[MapSystem] 警告: 未知的对称类型 {symmetry_type}，使用默认值 'horizontal'")
            self.symmetry_type = "horizontal"

    def _generate_river_split_diagonal_map(self):
        """🌊 生成河流分割的对角线对称竞技地图"""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        print(f"[MapSystem] 生成 {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} 河流分割竞技地图")
        print(f"[MapSystem] 设计特色: 对角线河流分界，中心平地争夺点，后方城池")
        
        # 生成河流分割地图
        terrain_map = self._generate_river_split_terrain_map()
        
        # 创建ECS实体
        self._create_river_split_map_entities(map_data, terrain_map)
        
        # 添加到世界
        self.world.add_singleton_component(map_data)
        
        # 打印分析报告
        self._print_river_split_map_analysis(terrain_map)

    def _generate_river_split_terrain_map(self) -> Dict[Tuple[int, int], TerrainType]:
        """生成河流分割的地形地图"""
        terrain_map = {}
        center = GameConfig.MAP_WIDTH // 2
        
        # 遍历整个地图
        for q in range(GameConfig.MAP_WIDTH):
            for r in range(GameConfig.MAP_HEIGHT):
                center_q = q - center
                center_r = r - center
                
                terrain = self._generate_river_split_terrain(center_q, center_r)
                terrain_map[(center_q, center_r)] = terrain
        
        return terrain_map

    def _generate_river_split_terrain(self, q: int, r: int) -> TerrainType:
        """🎯 完全确定性的河流分割地形 - V4: 增加中央区域战略元素"""

        # === 第一优先级：后方城池（中心对称） ===
        # 🏰 用户指定的新城池位置
        if (q == 5 and r == 4) or (q == -5 and r == -4):
            return TerrainType.URBAN

        # === 第二优先级：对角线河流系统 ===
        diagonal_distance = abs(q + r)
        if diagonal_distance == 0:
            return TerrainType.PLAIN if (q == 0 and r == 0) else TerrainType.WATER
        elif diagonal_distance == 1:
            if (abs(q) <= 1 and abs(r) <= 1) or ((q * q + r * r) % 5 == 0):
                return TerrainType.PLAIN
            else:
                return TerrainType.WATER

        # === 第三优先级：城池和中央区域的战略地形 ===

        # 🛡️ 城池防御区：确保城池周围是平地 (中心对称)
        city1_dist = math.sqrt((q - 5)**2 + (r - 4)**2)
        city2_dist = math.sqrt((q + 5)**2 + (r + 4)**2)
        if city1_dist <= 1.5 or city2_dist <= 1.5:
            return TerrainType.PLAIN

        # ✨ 新增：中央区域的战略点 (中心对称) - 增加更多地形
        # 定义一半的特征，另一半通过代码对称生成
        central_hills = [
            (2, 2), (1, 3),  # 原有
            (3, 3)           # 新增山丘，提供更深的火力点
        ]
        for hq, hr in central_hills:
            if (q == hq and r == hr) or (q == -hq and r == -hr):
                return TerrainType.HILL

        central_forests = [
            (3, 1), (2, -1), # 原有
            (4, 2),          # 新增森林，提供侧翼掩护
            (1, 4)           # 新增森林，连接后方与前线
        ]
        for fq, fr in central_forests:
            if (q == fq and r == fr) or (q == -fq and r == -fr):
                return TerrainType.FOREST

        # === 第四优先级：外围的自然地形集群（保持对角线对称） ===
        
        # 🌲 森林集群：使用圆形/椭圆形分布，更自然
        forest_clusters = [
            # 只需定义一半，另一半通过对称自动生成
            ((-4, 6), 1.8),    # 后方森林
            ((-2, 3), 1.2),    # 前沿森林
            ((-6, 2), 1.0),    # 侧翼森林
        ]
        
        for (center_q, center_r), radius in forest_clusters:
            # 检查原始点
            distance1 = math.sqrt((q - center_q)**2 + (r - center_r)**2)
            # 检查对角线对称点
            distance2 = math.sqrt((q - (-center_r))**2 + (r - (-center_q))**2)
            if distance1 <= radius or distance2 <= radius:
                return TerrainType.FOREST
        
        # 🏔️ 山脉集群：战略高地，圆形分布
        mountain_clusters = [
            # 只需定义一半
            ((-3, 5), 1.0),    # 关键高地
            ((-6, 6), 0.8),    # 角落要塞
        ]
        
        for (center_q, center_r), radius in mountain_clusters:
            # 检查原始点和对角线对称点
            distance1 = math.sqrt((q - center_q)**2 + (r - center_r)**2)
            distance2 = math.sqrt((q - (-center_r))**2 + (r - (-center_q))**2)
            if distance1 <= radius or distance2 <= radius:
                return TerrainType.MOUNTAIN
        
        # 🏔️ 战略高地：精确的单点制高点
        strategic_hills = [
             # 只需定义一半
            (-1, 3), (-4, 2),
        ]
        
        for hill_q, hill_r in strategic_hills:
            # 检查原始点和对角线对称点
            if (q == hill_q and r == hill_r) or (q == -hill_r and r == -hill_q):
                return TerrainType.HILL
        
        # === 第五优先级：边界处理 ===
        # 🏔️ 地图边缘：稀疏的山脉边界
        if abs(q) == 7 or abs(r) == 7:
            # 只在特定位置设置边界山脉，不是全部
            if (q + r) % 3 == 0:
                return TerrainType.MOUNTAIN
            else:
                return TerrainType.FOREST
        
        # === 第六优先级：默认地形 ===
        # 所有其他区域都是平地
        return TerrainType.PLAIN

    def _create_river_split_map_entities(self, map_data: MapData, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """创建河流分割地图的实体"""
        # 出生点：在各自区域的前沿位置
        spawn_points = {
            Faction.SHU: (-4, 4),   # 左上区域前沿
            Faction.WEI: (4, -4),   # 右下区域前沿
        }
        
        for (q, r), terrain_type in terrain_map.items():
            # 创建地块实体
            tile_entity = self.world.create_entity()
            self.world.add_component(tile_entity, HexPosition(q, r))
            self.world.add_component(tile_entity, Terrain(terrain_type))
            self.world.add_component(tile_entity, Tile((q, r)))
            
            # 在出生点和城池附近设置领土控制
            controlling_faction = self._get_river_split_territory_control((q, r), spawn_points)
            if controlling_faction:
                self.world.add_component(tile_entity, TerritoryControl(
                    controlling_faction=controlling_faction,
                    being_captured=False,
                    capturing_unit=None,
                    capture_progress=0.0,
                    capture_time_required=5.0,
                    fortified=False,
                    fortification_level=0,
                    captured_time=0.0,
                    is_city=(terrain_type == TerrainType.URBAN)
                ))
            
            # 添加到地图数据
            map_data.tiles[(q, r)] = tile_entity

    def _get_river_split_territory_control(self, pos: Tuple[int, int], 
                                     spawn_points: Dict[Faction, Tuple[int, int]], 
                                     control_radius: int = 2) -> Faction:
        """确定河流分割地图的初始领土控制"""
        q, r = pos
        
        # 出生点周围控制
        for faction, (spawn_q, spawn_r) in spawn_points.items():
            distance = math.sqrt((q - spawn_q) ** 2 + (r - spawn_r) ** 2)
            if distance <= control_radius:
                return faction
        
        # 🏰 城池控制 (中心对称)
        # (5, 4) 位于WEI的区域 (q+r > 0)
        if math.sqrt((q - 5) ** 2 + (r - 4) ** 2) <= 2:
            return Faction.WEI
        
        # (-5, -4) 位于SHU的区域 (q+r < 0)
        if math.sqrt((q + 5) ** 2 + (r + 4) ** 2) <= 2:
            return Faction.SHU
        
        return None

    def _print_river_split_map_analysis(self, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """打印河流分割地图分析报告"""
        terrain_count = {}
        for terrain in terrain_map.values():
            terrain_count[terrain] = terrain_count.get(terrain, 0) + 1
        
        print("\n" + "="*70)
        print("🌊 河流分割对角线竞技地图分析报告")
        print("="*70)
        print(f"📐 地图尺寸: {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT}")
        print(f"🎯 设计特色: 对角线河流分界，区域化布局")
        print(f"🌊 河流系统: 沿主对角线 (q + r = 0)")
        print(f"🏰 战略要点: 中心争夺点 + 后方双城池")
        print(f"🔢 固定种子: {self.seed} (确保可重现)")
        
        print("\n🌍 地形分布统计:")
        total_tiles = len(terrain_map)
        for terrain, count in sorted(terrain_count.items(), key=lambda x: x[1], reverse=True):
            percentage = count / total_tiles * 100
            print(f"  {terrain.value:10} {count:3d} 块 ({percentage:5.1f}%)")
        
        # 地图可视化
        self._print_terrain_map_visual(terrain_map)
        
        # 对称性验证
        self._verify_diagonal_symmetry(terrain_map)
        
        # 战略要点分析
        self._analyze_river_split_strategic_points(terrain_map)
        
        print("="*70)

    def _analyze_river_split_strategic_points(self, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """分析河流分割地图的战略要点"""
        print(f"\n🎯 战略要点分析:")
        
        # 统计各类地形簇
        shu_area_count = sum(1 for (q, r) in terrain_map.keys() if q <= -1 and r >= 1)
        wei_area_count = sum(1 for (q, r) in terrain_map.keys() if q >= 1 and r <= -1)
        river_count = sum(1 for terrain in terrain_map.values() if terrain == TerrainType.WATER)
        city_count = sum(1 for terrain in terrain_map.values() if terrain == TerrainType.URBAN)
        plain_count = sum(1 for terrain in terrain_map.values() if terrain == TerrainType.PLAIN)
        mountain_count = sum(1 for terrain in terrain_map.values() if terrain == TerrainType.MOUNTAIN)
        
        print(f"  🔵 SHU控制区: {shu_area_count} 块 (左上区域)")
        print(f"  🔴 WEI控制区: {wei_area_count} 块 (右下区域)")
        print(f"  🌊 河流系统: {river_count} 块 (天然分界线)")
        print(f"  🏰 城池数量: {city_count} 座 (后方要塞)")
        print(f"  🌱 平地总数: {plain_count} 块 (主要活动区域)")
        print(f"  🏔️ 山脉总数: {mountain_count} 块 (战略高地)")
        print(f"  ⭐ 中心争夺点: (0, 0) - 平地")
        
        print(f"\n🚀 阵营部署:")
        print(f"  SHU (蜀): 出生点(-4, 4), 城池(-5, -4) - 后方区域")
        print(f"  WEI (魏): 出生点(4, -4), 城池(5, 4) - 后方区域")
        print(f"  📏 直线距离: {math.sqrt(8**2 + 8**2):.1f} 格")
        print(f"  🌊 需跨越河流才能到达对方区域")
        print(f"  🏰 城池更靠后方，提供安全的战略纵深")