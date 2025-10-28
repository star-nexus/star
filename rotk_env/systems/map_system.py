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
from ..utils.hex_utils import HexMath
from .moba_map_generator import MOBAMapMixin
from .encounter_map_generator import EncounterMapMixin


class Tile:
    """临时地块类，用于兼容现有代码"""

    def __init__(self, position):
        self.position = position


class MapSystem(System, MOBAMapMixin, EncounterMapMixin):
    """地图系统 - 管理地图生成和地形，支持MOBA风格地图"""

    def __init__(
        self, competitive_mode: bool = True, symmetry_type: str = "river_split_offset"
    ):
        super().__init__(priority=100)
        self.competitive_mode = competitive_mode
        self.symmetry_type = symmetry_type  # "horizontal", "diagonal", "river_split", "river_split_offset", "square", "moba", "encounter"
        self.seed = 42

    def initialize(self, world: World) -> None:
        self.world = world
        self.generate_map()
        # 生成地图后，保存地图信息到GameStats
        self._save_map_info_to_stats()

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
                print("[MapSystem] 🏆 生成河流分割对角线竞技地图（偏移坐标）")
                self._generate_river_split_diagonal_map()
            elif self.symmetry_type == "river_split_offset":
                print("[MapSystem] 🏆 生成河流分割对角线竞技地图（偏移坐标）")
                self._generate_river_split_diagonal_map_offset_revised()
            elif self.symmetry_type == "diagonal":
                print("[MapSystem] 🏆 生成对角线对称竞技地图")
                self._generate_competitive_map_diagonal()
            elif self.symmetry_type == "square":
                print("[MapSystem] 🏆 生成正方形竞技地图")
                self._generate_square_map()
            elif self.symmetry_type == "moba":
                print("[MapSystem] 🏟️ 生成MOBA风格地图")
                self._generate_moba_map()
            elif self.symmetry_type == "encounter":
                print("[MapSystem] 🏟️ 生成Encounter风格地图")
                self._generate_encounter_map()
            else:
                print("[MapSystem] 🏆 生成水平轴对称竞技地图")
                self._generate_competitive_map_v2()
        else:
            print("[MapSystem] 🌍 生成标准随机地图")
            self._generate_standard_map()

    def _generate_square_map(self):
        """生成地图 - 生成视觉上为正方形的六边形地图（使用偏移坐标）"""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        # 使用偏移坐标系直接生成矩形区域
        for col in range(GameConfig.MAP_WIDTH):
            for row in range(GameConfig.MAP_HEIGHT):
                # 生成地形
                terrain_type = self._generate_terrain_offset(col, row)

                # 创建地块实体
                tile_entity = self.world.create_entity()
                self.world.add_component(tile_entity, HexPosition(col, row))
                self.world.add_component(tile_entity, Terrain(terrain_type))
                self.world.add_component(tile_entity, Tile((col, row)))

                # 添加到地图数据
                map_data.tiles[(col, row)] = tile_entity

        self.world.add_singleton_component(map_data)

    def _generate_competitive_map_v2(self):
        """🏆 生成竞技对抗地图 V2.0 - 使用偏移坐标系统"""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        print(
            f"[MapSystem] 生成 {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} 真正对称竞技地图（偏移坐标）"
        )

        # 直接使用偏移坐标生成地图
        terrain_map = self._generate_symmetric_terrain_map_offset()

        # 创建ECS实体
        self._create_competitive_map_entities_offset(map_data, terrain_map)

        # 添加到世界
        self.world.add_singleton_component(map_data)

        # 打印分析报告
        self._print_competitive_map_analysis_v2_offset(terrain_map)

    def _generate_symmetric_terrain_map_offset(
        self,
    ) -> Dict[Tuple[int, int], TerrainType]:
        """生成完全对称的地形地图（偏移坐标）"""
        terrain_map = {}

        # 遍历整个地图
        for col in range(GameConfig.MAP_WIDTH):
            for row in range(GameConfig.MAP_HEIGHT):
                # 🔥 核心：使用保证对称的地形生成函数
                terrain = self._generate_symmetric_terrain_offset(col, row)
                terrain_map[(col, row)] = terrain

        return terrain_map

    def _generate_symmetric_terrain_offset(self, col: int, row: int) -> TerrainType:
        """🎯 生成绝对对称的地形 - 偏移坐标版本"""
        # 计算地图中心
        center_col = GameConfig.MAP_WIDTH // 2
        center_row = GameConfig.MAP_HEIGHT // 2

        # 转换为以中心为原点的坐标
        center_based_col = col - center_col
        center_based_row = row - center_row

        # 🔥 关键：使用abs(row)确保水平对称性
        abs_row = abs(center_based_row)
        distance_from_center = math.sqrt(
            center_based_col * center_based_col + abs_row * abs_row
        )

        # 使用对称的种子：对于(col,row)和(col,-row)产生相同的随机数
        symmetric_seed = center_based_col * 10007 + abs_row * 10009 + self.seed
        rand = random.Random(symmetric_seed)
        value = rand.random()

        # === Zone A: 出生点/大本营区域 ===
        if abs_row >= 6:  # 地图的南北两端
            return self._generate_spawn_area_terrain_offset(
                center_based_col, abs_row, value
            )

        # === Zone B: 中央战略区 ===
        elif distance_from_center <= 1.5:  # 正中心
            return self._generate_central_zone_terrain_offset(
                center_based_col, abs_row, value
            )

        # === Zone C: 战术缓冲带 ===
        elif distance_from_center <= 4.5:
            return self._generate_tactical_buffer_terrain_offset(
                center_based_col, abs_row, value
            )

        # === Zone D: 对抗主路 ===
        else:  # 外围区域
            return self._generate_outer_zone_terrain_offset(
                center_based_col, abs_row, value
            )

    def _generate_spawn_area_terrain_offset(
        self, col: int, abs_row: int, value: float
    ) -> TerrainType:
        """生成出生点区域地形 - 偏移坐标版本"""
        abs_col = abs(col)

        # 出生点核心：纯平原，便于初期部署
        if abs_col <= 1 and abs_row >= 6:
            return TerrainType.PLAIN

        # 出生点周围：混合平原、丘陵、少量森林
        if value < 0.6:
            return TerrainType.PLAIN  # 60% 平原
        elif value < 0.8:
            return TerrainType.HILL  # 20% 丘陵
        else:
            return TerrainType.FOREST  # 20% 森林

    def _generate_central_zone_terrain_offset(
        self, col: int, abs_row: int, value: float
    ) -> TerrainType:
        """生成中央战略区地形 - 偏移坐标版本"""

        # 正中心点：唯一的城市
        if col == 0 and abs_row == 0:
            return TerrainType.URBAN

        # 中心周围：高价值地形
        if value < 0.4:
            return TerrainType.PLAIN  # 40% 平原
        elif value < 0.7:
            return TerrainType.HILL  # 30% 丘陵 (高地优势)
        else:
            return TerrainType.FOREST  # 30% 森林 (战术掩护)

    def _generate_tactical_buffer_terrain_offset(
        self, col: int, abs_row: int, value: float
    ) -> TerrainType:
        """生成战术缓冲带地形 - 偏移坐标版本"""
        abs_col = abs(col)

        # 接近中轴线：相对开阔的主要通道
        if abs_col <= 2:
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

    def _generate_outer_zone_terrain_offset(
        self, col: int, abs_row: int, value: float
    ) -> TerrainType:
        """生成外围区域地形 - 偏移坐标版本"""

        # 边缘地带：更多山地和水域作为天然边界
        if abs(col) >= 6 or abs_row >= 5:
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

    def _create_competitive_map_entities_offset(
        self, map_data: MapData, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """创建竞技地图的实体 - 偏移坐标版本"""
        # 计算出生点位置（使用偏移坐标）
        center_row = GameConfig.MAP_HEIGHT // 2
        spawn_distance = min(GameConfig.MAP_WIDTH, GameConfig.MAP_HEIGHT) // 2 - 1
        spawn_points = {
            Faction.SHU: (
                GameConfig.MAP_WIDTH // 2,
                center_row + spawn_distance,
            ),  # 上方出生点
            Faction.WEI: (
                GameConfig.MAP_WIDTH // 2,
                center_row - spawn_distance,
            ),  # 下方出生点
        }

        for (col, row), terrain_type in terrain_map.items():
            # 创建地块实体
            tile_entity = self.world.create_entity()
            self.world.add_component(tile_entity, HexPosition(col, row))
            self.world.add_component(tile_entity, Terrain(terrain_type))
            self.world.add_component(tile_entity, Tile((col, row)))

            # 在出生点附近设置初始领土控制
            controlling_faction = self._get_initial_territory_control(
                (col, row), spawn_points
            )
            if controlling_faction:
                self.world.add_component(
                    tile_entity,
                    TerritoryControl(
                        controlling_faction=controlling_faction,
                        being_captured=False,
                        capturing_unit=None,
                        capture_progress=0.0,
                        capture_time_required=5.0,
                        fortified=False,
                        fortification_level=0,
                        captured_time=0.0,
                        is_city=(terrain_type == TerrainType.URBAN),
                    ),
                )

            # 添加到地图数据
            map_data.tiles[(col, row)] = tile_entity

    def _print_competitive_map_analysis_v2_offset(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """打印竞技地图分析报告 V2.0 - 偏移坐标版本"""
        terrain_count = {}
        for terrain in terrain_map.values():
            terrain_count[terrain] = terrain_count.get(terrain, 0) + 1

        print("\n" + "=" * 70)
        print("🏆 竞技对抗地图分析报告 V2.0 (偏移坐标系)")
        print("=" * 70)
        print(f"📐 地图尺寸: {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT}")
        print(f"🎯 设计原则: 水平对称，直观坐标系")
        print(f"⚖️  对称轴: 水平中轴线 (row={GameConfig.MAP_HEIGHT//2})")
        print(f"🗂️  坐标系: 偏移坐标（更直观的行列布局）")
        print(f"🔢 固定种子: {self.seed} (确保可重现)")

        print("\n🌍 地形分布统计:")
        total_tiles = len(terrain_map)
        for terrain, count in sorted(
            terrain_count.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / total_tiles * 100
            print(f"  {terrain.value:10} {count:3d} 块 ({percentage:5.1f}%)")

        # 详细地图可视化打印
        self._print_terrain_map_visual_offset(terrain_map)

        # 严格的对称性验证
        self._verify_map_symmetry_v2_offset(terrain_map)

        # 出生点信息
        center_row = GameConfig.MAP_HEIGHT // 2
        spawn_distance = min(GameConfig.MAP_WIDTH, GameConfig.MAP_HEIGHT) // 2 - 1
        print(f"\n🚀 阵营出生点:")
        print(
            f"  SHU (蜀): ({GameConfig.MAP_WIDTH//2}, {center_row + spawn_distance})  - 地图上方"
        )
        print(
            f"  WEI (魏): ({GameConfig.MAP_WIDTH//2}, {center_row - spawn_distance}) - 地图下方"
        )
        print(f"  📏 出生点距离: {2 * spawn_distance} 格")

        print("=" * 70)

    def _print_terrain_map_visual_offset(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """🗺️ 打印地图的可视化表示 - 偏移坐标版本"""
        print("\n🗺️ 地形地图可视化 (行从上到下, 列从左到右):")
        print("   地形符号: P=平原 F=森林 H=丘陵 M=山地 W=水域 U=城市")

        terrain_chars = {
            TerrainType.PLAIN: "P",
            TerrainType.FOREST: "F",
            TerrainType.HILL: "H",
            TerrainType.MOUNTAIN: "M",
            TerrainType.WATER: "W",
            TerrainType.URBAN: "U",
        }

        print("\n   ", end="")

        # 打印列标题 (col坐标)
        for col in range(GameConfig.MAP_WIDTH):
            print(f"{col:2}", end=" ")
        print()

        # 打印每一行
        for row in range(GameConfig.MAP_HEIGHT):
            print(f"{row:2}:", end=" ")
            for col in range(GameConfig.MAP_WIDTH):
                if (col, row) in terrain_map:
                    terrain = terrain_map[(col, row)]
                    char = terrain_chars.get(terrain, "?")
                    print(f" {char}", end=" ")
                else:
                    print("  ", end=" ")
            print(f" :{row}")

        # 再次打印底部列标题
        print("   ", end="")
        for col in range(GameConfig.MAP_WIDTH):
            print(f"{col:2}", end=" ")
        print()

    def _verify_map_symmetry_v2_offset(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """🔍 严格验证地图对称性 V2.0 - 偏移坐标版本"""
        print(f"\n🔍 对称性验证 V2.0 (偏移坐标):")

        asymmetric_pairs = []
        symmetric_pairs = 0
        total_checks = 0

        center_row = GameConfig.MAP_HEIGHT // 2

        # 检查每个位置与其镜像位置
        for col in range(GameConfig.MAP_WIDTH):
            for row in range(GameConfig.MAP_HEIGHT):
                if (col, row) in terrain_map:
                    # 计算镜像位置：相对于水平中轴线对称
                    mirror_row = 2 * center_row - row
                    mirror_pos = (col, mirror_row)
                    total_checks += 1

                    if mirror_pos in terrain_map:
                        if terrain_map[(col, row)] == terrain_map[mirror_pos]:
                            symmetric_pairs += 1
                        else:
                            asymmetric_pairs.append(
                                {
                                    "pos1": (col, row),
                                    "terrain1": terrain_map[(col, row)].value,
                                    "pos2": mirror_pos,
                                    "terrain2": terrain_map[mirror_pos].value,
                                }
                            )
                    else:
                        asymmetric_pairs.append(
                            {
                                "pos1": (col, row),
                                "terrain1": terrain_map[(col, row)].value,
                                "pos2": mirror_pos,
                                "terrain2": "缺失",
                            }
                        )

        if len(asymmetric_pairs) == 0:
            print(f"  ✅ 完美对称！{symmetric_pairs}/{total_checks} 个位置完全对称")
        else:
            print(f"  ❌ 发现 {len(asymmetric_pairs)} 个不对称位置:")
            for i, pair in enumerate(asymmetric_pairs[:5]):
                print(
                    f"    {pair['pos1']}={pair['terrain1']} ≠ {pair['pos2']}={pair['terrain2']}"
                )
            if len(asymmetric_pairs) > 5:
                print(f"    ... 还有 {len(asymmetric_pairs) - 5} 个不对称位置")

    def _get_initial_territory_control(
        self,
        pos: Tuple[int, int],
        spawn_points: Dict[Faction, Tuple[int, int]],
        control_radius: int = 2,
    ) -> Faction:
        """确定初始领土控制"""
        q, r = pos

        for faction, (spawn_q, spawn_r) in spawn_points.items():
            distance = math.sqrt((q - spawn_q) ** 2 + (r - spawn_r) ** 2)
            if distance <= control_radius:
                return faction

        return None

    def _print_competitive_map_analysis_v2(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """打印竞技地图分析报告 V2.0"""
        terrain_count = {}
        for terrain in terrain_map.values():
            terrain_count[terrain] = terrain_count.get(terrain, 0) + 1

        print("\n" + "=" * 70)
        print("🏆 竞技对抗地图分析报告 V2.0")
        print("=" * 70)
        print(f"📐 地图尺寸: {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT}")
        print(f"🎯 设计原则: 绝对水平轴对称，战略区域分层")
        print(f"⚖️  对称轴: 水平中轴线 (r=0)")
        print(f"🔢 固定种子: {self.seed} (确保可重现)")

        print("\n🌍 地形分布统计:")
        total_tiles = len(terrain_map)
        for terrain, count in sorted(
            terrain_count.items(), key=lambda x: x[1], reverse=True
        ):
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

        print("=" * 70)

    def _print_terrain_map_visual(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """🗺️ 打印地图的可视化表示"""
        print("\n🗺️ 地形地图可视化 (r从上到下, q从左到右):")
        print("   地形符号: P=平原 F=森林 H=丘陵 M=山地 W=水域 U=城市")

        terrain_chars = {
            TerrainType.PLAIN: "P",
            TerrainType.FOREST: "F",
            TerrainType.HILL: "H",
            TerrainType.MOUNTAIN: "M",
            TerrainType.WATER: "W",
            TerrainType.URBAN: "U",
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
                    char = terrain_chars.get(terrain, "?")
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
                            asymmetric_pairs.append(
                                {
                                    "pos1": (q, r),
                                    "terrain1": terrain_map[(q, r)].value,
                                    "pos2": mirror_pos,
                                    "terrain2": terrain_map[mirror_pos].value,
                                }
                            )
                    else:
                        asymmetric_pairs.append(
                            {
                                "pos1": (q, r),
                                "terrain1": terrain_map[(q, r)].value,
                                "pos2": mirror_pos,
                                "terrain2": "缺失",
                            }
                        )

        if len(asymmetric_pairs) == 0:
            print(f"  ✅ 完美对称！{symmetric_pairs}/{total_checks} 个位置完全对称")
        else:
            print(f"  ❌ 发现 {len(asymmetric_pairs)} 个不对称位置:")
            for i, pair in enumerate(asymmetric_pairs[:5]):
                print(
                    f"    {pair['pos1']}={pair['terrain1']} ≠ {pair['pos2']}={pair['terrain2']}"
                )
            if len(asymmetric_pairs) > 5:
                print(f"    ... 还有 {len(asymmetric_pairs) - 5} 个不对称位置")

    def _analyze_strategic_zones(self, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """分析战略区域分布"""
        print(f"\n🎯 战略区域分析:")

        zones = {"出生点区域": 0, "中央战略区": 0, "战术缓冲带": 0, "外围区域": 0}

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

        print(
            f"[MapSystem] 生成 {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} 对角线对称竞技地图"
        )

        # 生成对角线对称地图
        terrain_map = self._generate_diagonal_symmetric_terrain_map()

        # 创建ECS实体（使用对角线出生点）
        self._create_diagonal_competitive_map_entities(map_data, terrain_map)

        # 添加到世界
        self.world.add_singleton_component(map_data)

        # 打印分析报告
        self._print_diagonal_competitive_map_analysis(terrain_map)

    def _generate_diagonal_symmetric_terrain_map(
        self,
    ) -> Dict[Tuple[int, int], TerrainType]:
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

    def _generate_diagonal_spawn_area_terrain(
        self, q: int, r: int, value: float
    ) -> TerrainType:
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

    def _generate_diagonal_central_terrain(
        self, q: int, r: int, value: float
    ) -> TerrainType:
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

    def _generate_diagonal_buffer_terrain(
        self, q: int, r: int, value: float
    ) -> TerrainType:
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

    def _generate_diagonal_outer_terrain(
        self, q: int, r: int, value: float
    ) -> TerrainType:
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

    def _create_diagonal_competitive_map_entities(
        self, map_data: MapData, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """创建对角线对称竞技地图的实体"""
        # 对角线模式的出生点
        spawn_points = {
            Faction.SHU: (-6, 6),  # 左上角
            Faction.WEI: (6, -6),  # 右下角
        }

        for (q, r), terrain_type in terrain_map.items():
            # 创建地块实体
            tile_entity = self.world.create_entity()
            self.world.add_component(tile_entity, HexPosition(q, r))
            self.world.add_component(tile_entity, Terrain(terrain_type))
            self.world.add_component(tile_entity, Tile((q, r)))

            # 在出生点附近设置初始领土控制
            controlling_faction = self._get_initial_territory_control(
                (q, r), spawn_points, control_radius=3
            )
            if controlling_faction:
                self.world.add_component(
                    tile_entity,
                    TerritoryControl(
                        controlling_faction=controlling_faction,
                        being_captured=False,
                        capturing_unit=None,
                        capture_progress=0.0,
                        capture_time_required=5.0,
                        fortified=False,
                        fortification_level=0,
                        captured_time=0.0,
                        is_city=(terrain_type == TerrainType.URBAN),
                    ),
                )

            # 添加到地图数据
            map_data.tiles[(q, r)] = tile_entity

    def _print_diagonal_competitive_map_analysis(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """打印对角线竞技地图分析报告"""
        terrain_count = {}
        for terrain in terrain_map.values():
            terrain_count[terrain] = terrain_count.get(terrain, 0) + 1

        print("\n" + "=" * 70)
        print("🏆 对角线对称竞技地图分析报告")
        print("=" * 70)
        print(f"📐 地图尺寸: {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT}")
        print(f"🎯 设计原则: 对角线对称 (q=-r轴)，左上↔右下")
        print(f"⚖️  对称轴: 主对角线 (q + r = 0)")
        print(f"🔢 固定种子: {self.seed} (确保可重现)")

        print("\n🌍 地形分布统计:")
        total_tiles = len(terrain_map)
        for terrain, count in sorted(
            terrain_count.items(), key=lambda x: x[1], reverse=True
        ):
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

        print("=" * 70)

    def _verify_diagonal_symmetry(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
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
                            asymmetric_pairs.append(
                                {
                                    "pos1": (q, r),
                                    "terrain1": terrain_map[(q, r)].value,
                                    "pos2": mirror_pos,
                                    "terrain2": terrain_map[mirror_pos].value,
                                }
                            )
                    else:
                        asymmetric_pairs.append(
                            {
                                "pos1": (q, r),
                                "terrain1": terrain_map[(q, r)].value,
                                "pos2": mirror_pos,
                                "terrain2": "缺失",
                            }
                        )

        if len(asymmetric_pairs) == 0:
            print(
                f"  ✅ 完美对角线对称！{symmetric_pairs}/{total_checks} 个位置完全对称"
            )
        else:
            print(f"  ❌ 发现 {len(asymmetric_pairs)} 个不对称位置:")
            for i, pair in enumerate(asymmetric_pairs[:5]):
                print(
                    f"    {pair['pos1']}={pair['terrain1']} ≠ {pair['pos2']}={pair['terrain2']}"
                )
            if len(asymmetric_pairs) > 5:
                print(f"    ... 还有 {len(asymmetric_pairs) - 5} 个不对称位置")

    def _generate_standard_map(self):
        """生成标准随机地图（使用偏移坐标）"""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        # 生成地图
        for col in range(GameConfig.MAP_WIDTH):
            for row in range(GameConfig.MAP_HEIGHT):
                # 使用偏移坐标生成地形
                terrain_type = self._generate_terrain_offset(col, row)

                # 创建地块实体
                tile_entity = self.world.create_entity()
                self.world.add_component(tile_entity, HexPosition(col, row))
                self.world.add_component(tile_entity, Terrain(terrain_type))
                self.world.add_component(tile_entity, Tile((col, row)))

                # 添加到地图数据
                map_data.tiles[(col, row)] = tile_entity

        self.world.add_singleton_component(map_data)

    def get_competitive_spawn_positions(self) -> Dict[Faction, Tuple[int, int]]:
        """获取竞技模式的出生位置（偏移坐标）"""
        if not self.competitive_mode:
            return {}

        center_col = GameConfig.MAP_WIDTH // 2
        center_row = GameConfig.MAP_HEIGHT // 2
        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        if self.symmetry_type == "river_split_offset":
            return {
                Faction.SHU: (-half_width + 3, -half_height + 3),  # 左下区域前沿
                Faction.WEI: (half_width - 3, half_height - 3),   # 右上区域前沿
            }
        elif self.symmetry_type == "river_split":
            return {
                Faction.SHU: (center_col - 4, center_row + 4),
                Faction.WEI: (center_col + 4, center_row - 4),
            }
        elif self.symmetry_type == "diagonal":
            return {
                Faction.SHU: (center_col - 6, center_row + 6),  # 左上角
                Faction.WEI: (center_col + 6, center_row - 6),  # 右下角
            }
        else:
            # 水平对称模式
            spawn_distance = min(GameConfig.MAP_WIDTH, GameConfig.MAP_HEIGHT) // 2 - 1
            return {
                Faction.SHU: (center_col, center_row + spawn_distance),  # 上方出生点
                Faction.WEI: (center_col, center_row - spawn_distance),  # 下方出生点
            }

    def enable_competitive_mode(self, enabled: bool = True):
        """启用/禁用竞技模式"""
        self.competitive_mode = enabled
        print(f"[MapSystem] 竞技模式: {'启用' if enabled else '禁用'}")

    def _generate_terrain_offset(self, col: int, row: int) -> TerrainType:
        """生成地形类型 - 偏移坐标版本"""
        # 使用固定种子确保地形生成的一致性
        rand = random.Random(col * 10007 + row * 10009 + self.seed)
        value = rand.random()

        # 计算到地图中心的距离
        center_col = GameConfig.MAP_WIDTH // 2
        center_row = GameConfig.MAP_HEIGHT // 2
        distance = math.sqrt((col - center_col) ** 2 + (row - center_row) ** 2)
        max_distance = math.sqrt(center_col**2 + center_row**2)
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

    # 保留原有的地形生成方法以兼容性（立方/轴坐标系统）
    def _generate_terrain(self, q: int, r: int) -> TerrainType:
        """生成地形类型 - 立方坐标版本（已弃用，保留兼容性）"""
        # 使用固定种子确保地形生成的一致性
        rand = random.Random(q * 10007 + r * 10009)
        value = rand.random()

        # 距离中心的距离
        distance = math.sqrt(q * q + r * r)
        max_distance = math.sqrt(
            (GameConfig.MAP_WIDTH // 2) ** 2 + (GameConfig.MAP_HEIGHT // 2) ** 2
        )
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
        if symmetry_type in ["horizontal", "diagonal", "river_split", "river_split_offset", "square", "moba", "encounter"]:
            self.symmetry_type = symmetry_type
            print(f"[MapSystem] 对称类型设置为: {symmetry_type}")
        else:
            print(
                f"[MapSystem] 警告: 未知的对称类型 {symmetry_type}，使用默认值 'horizontal'"
            )
            self.symmetry_type = "horizontal"

    def _generate_river_split_diagonal_map(self):
        """🌊 生成河流分割的对角线对称竞技地图"""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        print(
            f"[MapSystem] 生成 {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} 河流分割竞技地图"
        )
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
        city1_dist = math.sqrt((q - 5) ** 2 + (r - 4) ** 2)
        city2_dist = math.sqrt((q + 5) ** 2 + (r + 4) ** 2)
        if city1_dist <= 1.5 or city2_dist <= 1.5:
            return TerrainType.PLAIN

        # ✨ 新增：中央区域的战略点 (中心对称) - 增加更多地形
        # 定义一半的特征，另一半通过代码对称生成
        central_hills = [(2, 2), (1, 3), (3, 3)]  # 原有  # 新增山丘，提供更深的火力点
        for hq, hr in central_hills:
            if (q == hq and r == hr) or (q == -hq and r == -hr):
                return TerrainType.HILL

        central_forests = [
            (3, 1),
            (2, -1),  # 原有
            (4, 2),  # 新增森林，提供侧翼掩护
            (1, 4),  # 新增森林，连接后方与前线
        ]
        for fq, fr in central_forests:
            if (q == fq and r == fr) or (q == -fq and r == -fr):
                return TerrainType.FOREST

        # === 第四优先级：外围的自然地形集群（保持对角线对称） ===

        # 🌲 森林集群：使用圆形/椭圆形分布，更自然
        forest_clusters = [
            # 只需定义一半，另一半通过对称自动生成
            ((-4, 6), 1.8),  # 后方森林
            ((-2, 3), 1.2),  # 前沿森林
            ((-6, 2), 1.0),  # 侧翼森林
        ]

        for (center_q, center_r), radius in forest_clusters:
            # 检查原始点
            distance1 = math.sqrt((q - center_q) ** 2 + (r - center_r) ** 2)
            # 检查对角线对称点
            distance2 = math.sqrt((q - (-center_r)) ** 2 + (r - (-center_q)) ** 2)
            if distance1 <= radius or distance2 <= radius:
                return TerrainType.FOREST

        # 🏔️ 山脉集群：战略高地，圆形分布
        mountain_clusters = [
            # 只需定义一半
            ((-3, 5), 1.0),  # 关键高地
            ((-6, 6), 0.8),  # 角落要塞
        ]

        for (center_q, center_r), radius in mountain_clusters:
            # 检查原始点和对角线对称点
            distance1 = math.sqrt((q - center_q) ** 2 + (r - center_r) ** 2)
            distance2 = math.sqrt((q - (-center_r)) ** 2 + (r - (-center_q)) ** 2)
            if distance1 <= radius or distance2 <= radius:
                return TerrainType.MOUNTAIN

        # 🏔️ 战略高地：精确的单点制高点
        strategic_hills = [
            # 只需定义一半
            (-1, 3),
            (-4, 2),
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

    def _create_river_split_map_entities(
        self, map_data: MapData, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """创建河流分割地图的实体"""
        # 出生点：在各自区域的前沿位置
        spawn_points = {
            Faction.SHU: (-4, 4),  # 左上区域前沿
            Faction.WEI: (4, -4),  # 右下区域前沿
        }

        for (q, r), terrain_type in terrain_map.items():
            # 创建地块实体
            tile_entity = self.world.create_entity()
            self.world.add_component(tile_entity, HexPosition(q, r))
            self.world.add_component(tile_entity, Terrain(terrain_type))
            self.world.add_component(tile_entity, Tile((q, r)))

            # 在出生点和城池附近设置领土控制
            controlling_faction = self._get_river_split_territory_control(
                (q, r), spawn_points
            )
            if controlling_faction:
                self.world.add_component(
                    tile_entity,
                    TerritoryControl(
                        controlling_faction=controlling_faction,
                        being_captured=False,
                        capturing_unit=None,
                        capture_progress=0.0,
                        capture_time_required=5.0,
                        fortified=False,
                        fortification_level=0,
                        captured_time=0.0,
                        is_city=(terrain_type == TerrainType.URBAN),
                    ),
                )

            # 添加到地图数据
            map_data.tiles[(q, r)] = tile_entity

    def _get_river_split_territory_control(
        self,
        pos: Tuple[int, int],
        spawn_points: Dict[Faction, Tuple[int, int]],
        control_radius: int = 2,
    ) -> Faction:
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

    def _print_river_split_map_analysis(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """打印河流分割地图分析报告"""
        terrain_count = {}
        for terrain in terrain_map.values():
            terrain_count[terrain] = terrain_count.get(terrain, 0) + 1

        print("\n" + "=" * 70)
        print("🌊 河流分割对角线竞技地图分析报告")
        print("=" * 70)
        print(f"📐 地图尺寸: {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT}")
        print(f"🎯 设计特色: 对角线河流分界，区域化布局")
        print(f"🌊 河流系统: 沿主对角线 (q + r = 0)")
        print(f"🏰 战略要点: 中心争夺点 + 后方双城池")
        print(f"🔢 固定种子: {self.seed} (确保可重现)")

        print("\n🌍 地形分布统计:")
        total_tiles = len(terrain_map)
        for terrain, count in sorted(
            terrain_count.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / total_tiles * 100
            print(f"  {terrain.value:10} {count:3d} 块 ({percentage:5.1f}%)")

        # 地图可视化
        self._print_terrain_map_visual(terrain_map)

        # 对称性验证
        self._verify_diagonal_symmetry(terrain_map)

        # 战略要点分析
        self._analyze_river_split_strategic_points(terrain_map)

        print("=" * 70)

    def _analyze_river_split_strategic_points(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """分析河流分割地图的战略要点"""
        print(f"\n🎯 战略要点分析:")

        # 统计各类地形簇
        shu_area_count = sum(1 for (q, r) in terrain_map.keys() if q <= -1 and r >= 1)
        wei_area_count = sum(1 for (q, r) in terrain_map.keys() if q >= 1 and r <= -1)
        river_count = sum(
            1 for terrain in terrain_map.values() if terrain == TerrainType.WATER
        )
        city_count = sum(
            1 for terrain in terrain_map.values() if terrain == TerrainType.URBAN
        )
        plain_count = sum(
            1 for terrain in terrain_map.values() if terrain == TerrainType.PLAIN
        )
        mountain_count = sum(
            1 for terrain in terrain_map.values() if terrain == TerrainType.MOUNTAIN
        )

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

    def _generate_river_split_diagonal_map_offset(self):
        """🌊 生成河流分割的对角线对称竞技地图 - 偏移坐标系版本"""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        print(
            f"[MapSystem] 生成 {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} 河流分割竞技地图（偏移坐标）"
        )
        print(f"[MapSystem] 设计特色: 对角线河流分界，左下右上对称，对角战略布局")

        # 生成河流分割地图（偏移坐标版本）
        terrain_map = self._generate_river_split_terrain_map_offset()

        # 创建ECS实体（偏移坐标版本）
        self._create_river_split_map_entities_offset(map_data, terrain_map)

        # 添加到世界
        self.world.add_singleton_component(map_data)

        # 打印分析报告（偏移坐标版本）
        self._print_river_split_map_analysis_offset(terrain_map)

    def _generate_river_split_terrain_map_offset(self) -> Dict[Tuple[int, int], TerrainType]:
        """生成河流分割的地形地图 - 以(0,0)为中心的坐标版本"""
        terrain_map = {}

        # 计算地图半径
        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        # 遍历整个地图（以(0,0)为中心的坐标）
        for x in range(-half_width, half_width + 1):
            for y in range(-half_height, half_height + 1):
                terrain = self._generate_river_split_terrain_centered(x, y)
                terrain_map[(x, y)] = terrain

        return terrain_map

    def _generate_river_split_terrain_centered(self, x: int, y: int) -> TerrainType:
        """🎯 完全确定性的河流分割地形 - 以(0,0)为中心的坐标版本，左下右上对角线对称"""
        
        # 计算地图半径
        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2
        
        # === 第一优先级：后方城池（对角线对称） ===
        # 左下角城池和右上角城池
        if (x == -half_width + 2 and y == -half_height + 2) or (x == half_width - 2 and y == half_height - 2):
            return TerrainType.URBAN

        # === 第二优先级：对角线河流系统 ===
        # 使用反对角线（从右上到左下），对角线方程：x + y = 0
        diagonal_distance = abs(x + y)
        
        if diagonal_distance == 0:
            # 正好在反对角线上
            if x == 0 and y == 0:
                return TerrainType.PLAIN  # 中心争夺点
            else:
                return TerrainType.WATER  # 河流
        elif diagonal_distance == 1:
            # 河流两侧
            # 在地图中心附近或特定位置设为平地，其他为河流
            if (abs(x) <= 1 and abs(y) <= 1) or ((x * x + y * y) % 5 == 0):
                return TerrainType.PLAIN
            else:
                return TerrainType.WATER

        # === 第三优先级：城池和中央区域的战略地形 ===
        
        # 🛡️ 城池防御区：确保城池周围是平地（对角线对称）
        # 左下城池防御区
        city1_dist = math.sqrt((x - (-half_width + 2)) ** 2 + (y - (-half_height + 2)) ** 2)
        # 右上城池防御区
        city2_dist = math.sqrt((x - (half_width - 2)) ** 2 + (y - (half_height - 2)) ** 2)
        if city1_dist <= 1.5 or city2_dist <= 1.5:
            return TerrainType.PLAIN

        # ✨ 中央区域的战略点（对角线对称）
        # 定义一半的战略丘陵，另一半通过对角线对称生成
        strategic_hills = [
            (-2, 1),   # 左下象限的丘陵
            (-1, 2),
            (-3, 2),
        ]
        
        for hx, hy in strategic_hills:
            # 检查原始点和对角线对称点 (x, y) ↔ (-y, -x)
            if (x == hx and y == hy) or (x == -hy and y == -hx):
                return TerrainType.HILL

        # 中央森林区域（对角线对称）
        central_forests = [
            (-1, -1),  # 左下象限的森林
            (1, 1),    # 右上象限的森林
            (-3, 1),   # 左下象限的森林
        ]
        
        for fx, fy in central_forests:
            # 检查原始点和对角线对称点 (x, y) ↔ (-y, -x)
            if (x == fx and y == fy) or (x == -fy and y == -fx):
                return TerrainType.FOREST

        # === 第四优先级：外围的自然地形集群（对角线对称） ===
        
        # 🌲 森林集群：使用圆形分布，更自然
        forest_clusters = [
            # 只需定义一半，另一半通过对角线对称自动生成
            ((-half_width + 3, -half_height + 2), 1.8),  # 左下后方森林
            ((-2, 2), 1.2),                              # 左下前沿森林
            ((-half_width + 2, -half_height + 4), 1.0),  # 左下侧翼森林
        ]

        for (center_fx, center_fy), radius in forest_clusters:
            # 检查原始点
            distance1 = math.sqrt((x - center_fx) ** 2 + (y - center_fy) ** 2)
            # 检查对角线对称点 (x, y) ↔ (-y, -x)
            sym_center_x = -center_fy
            sym_center_y = -center_fx
            distance2 = math.sqrt((x - sym_center_x) ** 2 + (y - sym_center_y) ** 2)
            if distance1 <= radius or distance2 <= radius:
                return TerrainType.FOREST

        # 🏔️ 山脉集群：战略高地，圆形分布
        mountain_clusters = [
            # 只需定义一半，另一半通过对角线对称自动生成
            ((-1, -3), 1.0),  # 左下关键高地
            ((-half_width + 1, -half_height + 1), 0.8),  # 左下角落要塞
        ]

        for (center_mx, center_my), radius in mountain_clusters:
            # 检查原始点和对角线对称点 (x, y) ↔ (-y, -x)
            distance1 = math.sqrt((x - center_mx) ** 2 + (y - center_my) ** 2)
            sym_center_x = -center_my
            sym_center_y = -center_mx
            distance2 = math.sqrt((x - sym_center_x) ** 2 + (y - sym_center_y) ** 2)
            if distance1 <= radius or distance2 <= radius:
                return TerrainType.MOUNTAIN

        # 🏔️ 战略高地：精确的单点制高点
        strategic_points = [
            # 只需定义一半，另一半通过对角线对称自动生成
            (1, 3),
            (-2, 4),
        ]

        for px, py in strategic_points:
            # 检查原始点和对角线对称点 (x, y) ↔ (-y, -x)
            if (x == px and y == py) or (x == -py and y == -px):
                return TerrainType.HILL

        # === 第五优先级：边界处理 ===
        # 🏔️ 地图边缘：稀疏的山脉边界
        if abs(x) == half_width or abs(y) == half_height:
            # 只在特定位置设置边界山脉，不是全部
            if (x + y) % 3 == 0:
                return TerrainType.MOUNTAIN
            else:
                return TerrainType.FOREST

        # === 第六优先级：默认地形 ===
        # 所有其他区域都是平地
        return TerrainType.PLAIN

    def _create_river_split_map_entities_offset(
        self, map_data: MapData, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """创建河流分割地图的实体 - 以(0,0)为中心的坐标版本"""
        # 计算地图半径
        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2
        
        # 出生点：在左下角和右上角的对称位置
        spawn_points = {
            Faction.SHU: (-half_width + 3, -half_height + 3),  # 左下区域前沿
            Faction.WEI: (half_width - 3, half_height - 3),   # 右上区域前沿
        }

        for (x, y), terrain_type in terrain_map.items():
            # 创建地块实体
            tile_entity = self.world.create_entity()
            self.world.add_component(tile_entity, HexPosition(x, y))
            self.world.add_component(tile_entity, Terrain(terrain_type))
            self.world.add_component(tile_entity, Tile((x, y)))

            # 在出生点和城池附近设置领土控制
            controlling_faction = self._get_river_split_territory_control_centered(
                (x, y), spawn_points
            )
            if controlling_faction:
                self.world.add_component(
                    tile_entity,
                    TerritoryControl(
                        controlling_faction=controlling_faction,
                        being_captured=False,
                        capturing_unit=None,
                        capture_progress=0.0,
                        capture_time_required=5.0,
                        fortified=False,
                        fortification_level=0,
                        captured_time=0.0,
                        is_city=(terrain_type == TerrainType.URBAN),
                    ),
                )

            # 添加到地图数据
            map_data.tiles[(x, y)] = tile_entity

    def _get_river_split_territory_control_centered(
        self,
        pos: Tuple[int, int],
        spawn_points: Dict[Faction, Tuple[int, int]],
        control_radius: int = 2,
    ) -> Faction:
        """确定河流分割地图的初始领土控制 - 以(0,0)为中心的坐标版本"""
        x, y = pos
        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        # 出生点周围控制
        for faction, (spawn_x, spawn_y) in spawn_points.items():
            distance = math.sqrt((x - spawn_x) ** 2 + (y - spawn_y) ** 2)
            if distance <= control_radius:
                return faction

        # 🏰 城池控制（对角线对称）
        # 左下城池 (-half_width+2, -half_height+2) 位于SHU的区域
        if math.sqrt((x - (-half_width + 2)) ** 2 + (y - (-half_height + 2)) ** 2) <= 2:
            return Faction.SHU

        # 右上城池 (half_width-2, half_height-2) 位于WEI的区域
        if math.sqrt((x - (half_width - 2)) ** 2 + (y - (half_height - 2)) ** 2) <= 2:
            return Faction.WEI

        return None

    def _print_river_split_map_analysis_offset(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """打印河流分割地图分析报告 - 以(0,0)为中心的坐标版本"""
        terrain_count = {}
        for terrain in terrain_map.values():
            terrain_count[terrain] = terrain_count.get(terrain, 0) + 1

        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        print("\n" + "=" * 70)
        print("🌊 河流分割对角线竞技地图分析报告（中心坐标）")
        print("=" * 70)
        print(f"📐 地图尺寸: {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT}")
        print(f"🎯 设计特色: 左下右上对角线对称，河流分界")
        print(f"🌊 河流系统: 沿反对角线 (x + y = 0)")
        print(f"🏰 战略要点: 中心争夺点(0,0) + 对角城池")
        print(f"🔢 固定种子: {self.seed} (确保可重现)")
        print(f"📍 坐标范围: x∈[{-half_width}, {half_width}], y∈[{-half_height}, {half_height}]")

        print("\n🌍 地形分布统计:")
        total_tiles = len(terrain_map)
        for terrain, count in sorted(
            terrain_count.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / total_tiles * 100
            print(f"  {terrain.value:10} {count:3d} 块 ({percentage:5.1f}%)")

        # 地图可视化
        self._print_terrain_map_visual_centered(terrain_map)

        # 对称性验证
        self._verify_diagonal_symmetry_centered(terrain_map)

        # 战略要点分析
        self._analyze_river_split_strategic_points_centered(terrain_map)

        print("=" * 70)

    def _print_terrain_map_visual_centered(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """🗺️ 打印地图的可视化表示 - 以(0,0)为中心的坐标版本"""
        print("\n🗺️ 地形地图可视化 (y从上到下, x从左到右, 中心(0,0)):")
        print("   地形符号: P=平原 F=森林 H=丘陵 M=山地 W=水域 U=城市")

        terrain_chars = {
            TerrainType.PLAIN: "P",
            TerrainType.FOREST: "F",
            TerrainType.HILL: "H",
            TerrainType.MOUNTAIN: "M",
            TerrainType.WATER: "W",
            TerrainType.URBAN: "U",
        }

        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        print("\n   ", end="")

        # 打印列标题 (x坐标)
        for x in range(-half_width, half_width + 1):
            print(f"{x:2}", end=" ")
        print()

        # 打印每一行 (y从高到低，即从上到下)
        for y in range(half_height, -half_height - 1, -1):
            print(f"{y:2}:", end=" ")
            for x in range(-half_width, half_width + 1):
                if (x, y) in terrain_map:
                    terrain = terrain_map[(x, y)]
                    char = terrain_chars.get(terrain, "?")
                    print(f" {char}", end=" ")
                else:
                    print("  ", end=" ")
            print(f" :{y}")

        # 再次打印底部列标题
        print("   ", end="")
        for x in range(-half_width, half_width + 1):
            print(f"{x:2}", end=" ")
        print()

    def _verify_diagonal_symmetry_centered(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """🔍 验证对角线对称性 - 以(0,0)为中心的坐标版本"""
        print(f"\n🔍 对角线对称性验证（中心坐标）:")

        asymmetric_pairs = []
        symmetric_pairs = 0
        total_checks = 0

        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        # 检查每个位置与其对角线镜像位置
        for x in range(-half_width, half_width + 1):
            for y in range(-half_height, half_height + 1):
                if (x, y) in terrain_map:
                    # 对角线镜像：(x, y) ↔ (-y, -x)
                    mirror_pos = (-y, -x)
                    total_checks += 1

                    if mirror_pos in terrain_map:
                        if terrain_map[(x, y)] == terrain_map[mirror_pos]:
                            symmetric_pairs += 1
                        else:
                            asymmetric_pairs.append(
                                {
                                    "pos1": (x, y),
                                    "terrain1": terrain_map[(x, y)].value,
                                    "pos2": mirror_pos,
                                    "terrain2": terrain_map[mirror_pos].value,
                                }
                            )
                    else:
                        asymmetric_pairs.append(
                            {
                                "pos1": (x, y),
                                "terrain1": terrain_map[(x, y)].value,
                                "pos2": mirror_pos,
                                "terrain2": "缺失",
                            }
                        )

        if len(asymmetric_pairs) == 0:
            print(
                f"  ✅ 完美对角线对称！{symmetric_pairs}/{total_checks} 个位置完全对称"
            )
        else:
            print(f"  ❌ 发现 {len(asymmetric_pairs)} 个不对称位置:")
            for i, pair in enumerate(asymmetric_pairs[:5]):
                print(
                    f"    {pair['pos1']}={pair['terrain1']} ≠ {pair['pos2']}={pair['terrain2']}"
                )
            if len(asymmetric_pairs) > 5:
                print(f"    ... 还有 {len(asymmetric_pairs) - 5} 个不对称位置")

    def _analyze_river_split_strategic_points_centered(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """分析河流分割地图的战略要点 - 以(0,0)为中心的坐标版本"""
        print(f"\n🎯 战略要点分析:")

        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        # 统计各类地形簇
        # 使用反对角线分割：x + y < 0 为左下区域，x + y > 0 为右上区域
        shu_area_count = sum(
            1 for (x, y) in terrain_map.keys() 
            if x + y < 0
        )
        wei_area_count = sum(
            1 for (x, y) in terrain_map.keys() 
            if x + y > 0
        )
        river_count = sum(
            1 for terrain in terrain_map.values() if terrain == TerrainType.WATER
        )
        city_count = sum(
            1 for terrain in terrain_map.values() if terrain == TerrainType.URBAN
        )
        plain_count = sum(
            1 for terrain in terrain_map.values() if terrain == TerrainType.PLAIN
        )
        mountain_count = sum(
            1 for terrain in terrain_map.values() if terrain == TerrainType.MOUNTAIN
        )

        print(f"  🔵 SHU控制区: {shu_area_count} 块 (左下区域, x+y<0)")
        print(f"  🔴 WEI控制区: {wei_area_count} 块 (右上区域, x+y>0)")
        print(f"  🌊 河流系统: {river_count} 块 (对角分界线, x+y=0)")
        print(f"  🏰 城池数量: {city_count} 座 (对角要塞)")
        print(f"  🌱 平地总数: {plain_count} 块 (主要活动区域)")
        print(f"  🏔️ 山脉总数: {mountain_count} 块 (战略高地)")
        print(f"  ⭐ 中心争夺点: (0, 0) - 平地")

        print(f"\n🚀 阵营部署:")
        shu_spawn_x = -half_width + 3
        shu_spawn_y = -half_height + 3
        shu_city_x = -half_width + 2
        shu_city_y = -half_height + 2
        wei_spawn_x = half_width - 3
        wei_spawn_y = half_height - 3
        wei_city_x = half_width - 2
        wei_city_y = half_height - 2
        
        print(f"  SHU (蜀): 出生点({shu_spawn_x}, {shu_spawn_y}), 城池({shu_city_x}, {shu_city_y}) - 左下区域")
        print(f"  WEI (魏): 出生点({wei_spawn_x}, {wei_spawn_y}), 城池({wei_city_x}, {wei_city_y}) - 右上区域")
        
        # 计算出生点间距离
        spawn_distance = math.sqrt((wei_spawn_x - shu_spawn_x)**2 + (wei_spawn_y - shu_spawn_y)**2)
        print(f"  📏 直线距离: {spawn_distance:.1f} 格")
        print(f"  🌊 需跨越对角河流才能到达对方区域")
        print(f"  🏰 城池位于后方，提供安全的战略纵深")

    def _save_map_info_to_stats(self):
        """保存地图信息到GameStats中"""
        import time
        from ..components import GameStats
        
        # 获取GameStats组件，如果不存在就暂时跳过
        game_stats = self.world.get_singleton_component(GameStats)
        if not game_stats:
            print("[MapSystem] GameStats组件不存在，跳过地图信息保存")
            return
        
        # 确定坐标系类型
        coordinate_system = "centered" if self.symmetry_type == "river_split_offset" else "offset"
        
        # 获取出生点位置
        spawn_positions = {}
        if self.competitive_mode:
            spawn_positions = self.get_competitive_spawn_positions()
        
        # 收集地图信息
        map_info = {
            "map_width": GameConfig.MAP_WIDTH,
            "map_height": GameConfig.MAP_HEIGHT,
            "map_type": self.symmetry_type,
            "competitive_mode": self.competitive_mode,
            "map_seed": self.seed,
            "spawn_positions": {faction.value: pos for faction, pos in spawn_positions.items()},
            "coordinate_system": coordinate_system,
            "symmetry_type": self.symmetry_type,
            "generation_timestamp": time.time(),
        }
        
        # 保存到GameStats
        game_stats.map_info = map_info
        
        print(f"[MapSystem] ✅ 地图信息已保存到GameStats:")
        print(f"  - 地图尺寸: {map_info['map_width']}x{map_info['map_height']}")
        print(f"  - 地图类型: {map_info['map_type']}")
        print(f"  - 竞技模式: {map_info['competitive_mode']}")
        print(f"  - 坐标系: {map_info['coordinate_system']}")
        print(f"  - 出生点: {map_info['spawn_positions']}")

    def _generate_river_split_diagonal_map_offset_revised(self):
        """
        🌊 (Revised) 生成河流分割的对角线对称竞技地图 - 偏移坐标系版本
        此版本修正了坐标系处理和对称性计算的根本问题，确保地图的几何正确性和真正的对称性。
        """
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        print(
            f"[MapSystem] ⚙️ (Revised) Generating {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} River-Split Map (Offset Coords)"
        )
        print(f"[MapSystem] ✨ Design: True point-symmetry across a diagonal river.")

        # 1. 使用修正后的、基于轴坐标的逻辑生成地形图
        terrain_map = self._generate_river_split_terrain_map_offset_revised()

        # 2. 创建ECS实体 (此步骤与原版兼容)
        self._create_river_split_map_entities_offset(map_data, terrain_map)

        # 3. 添加到世界
        self.world.add_singleton_component(map_data)

        # 4. 打印分析报告 (可以使用适用于中心坐标系的打印函数)
        self._print_river_split_map_analysis_offset(terrain_map)
        print("[MapSystem] ✅ Revised map generation complete.")

    def _generate_river_split_terrain_map_offset_revised(
        self,
    ) -> Dict[Tuple[int, int], TerrainType]:
        """
        (Revised) 生成地形地图。
        遍历所有偏移坐标，并调用基于轴坐标的生成函数来确保几何正确性。
        """
        terrain_map = {}
        # 保持与原版相同的中心化坐标系
        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        for col in range(-half_width, half_width + 1):
            for row in range(-half_height, half_height + 1):
                # 对每个坐标调用新的、基于轴坐标的逻辑函数
                terrain = self._generate_river_split_terrain_axial(col, row)
                terrain_map[(col, row)] = terrain

        terrain_map[(4, -2)] = TerrainType.PLAIN
        terrain_map[(5, -3)] = TerrainType.PLAIN
        terrain_map[(7, -4)] = TerrainType.WATER
        terrain_map[(-7, 3)] = TerrainType.WATER

        return terrain_map

    def _generate_river_split_terrain_axial(
        self, col: int, row: int
    ) -> TerrainType:
        """
        (Revised V5) 最终版本，修复城市消失的BUG，并增加河流细节和中轴线山脉。
        """
        # 核心：将偏移坐标转换为轴坐标进行所有几何计算
        q, r = HexMath.offset_to_axial(col, row)
        s = -q - r
        
        map_radius = GameConfig.MAP_WIDTH // 2

        # --- 地图设计元素 (所有坐标均为轴坐标) ---

        # 1. 城市位于对角线位置
        city_bl_offset = (-6, -6)
        city_bl_axial = HexMath.offset_to_axial(*city_bl_offset)
        city_tr_axial = (-city_bl_axial[0], -city_bl_axial[1])
        city_tr_offset = HexMath.axial_to_offset(*city_tr_axial)

        # 2. 丰富河流宽度的点
        river_thicken_points = [
            (3, -2), (4, -3), # 右上河岸加宽点
            (-1, 2) # 左下河岸加宽点
        ]

        # 3. 中轴线上的战略山脉 (偏移坐标)
        central_mountain_offset_1 = (0, 3)
        central_mountain_axial_1 = HexMath.offset_to_axial(*central_mountain_offset_1)
        
        # 4. 沿河森林
        riverside_forests = [
            (1, 0), (2, -1),
            (5, -4),
            (-2, 3), 
        ]

        # 5. 自然的山脉
        mountain_ridge = [
            (4, 1), (5, 1), (5, 0), (6, 0), (6, -1), 
            (2, 4), (2, 5), (3, 4) 
        ]

        # 6. 在河上开辟的陆桥 (axial coords)
        plain_bridges_axial = [
            (-1, 1), (1, -1), # from offset (-1,0), (1,-1)
            (3, -2),          # from offset (3,-1)
            (3, -3),          # from offset (3,-2)
            (4, -3),          # from offset (4,-1)
            (4, -4),          # from offset (4,-2)
        ]

        # 7. 最终微调的河流点
        final_river_blocks_axial = [
            (-4, 4), # from offset (-4,2)
            (-3, 3), # from offset (-3,1)
        ]

        # --- 地形生成优先级 ---

        # 优先级 1: 城市 (必须是最高优先级，防止被覆盖)
        if (q, r) == city_bl_axial or (q, r) == city_tr_axial:
            return TerrainType.URBAN

        # 优先级 2: 最终微调的河流块
        for fq, fr in final_river_blocks_axial:
            if (q, r) == (fq, fr) or (q, r) == (-fq, -fr):
                return TerrainType.WATER

        # 优先级 3: 河流上的陆桥
        for bq, br in plain_bridges_axial:
            if (q, r) == (bq, br) or (q, r) == (-bq, -br):
                return TerrainType.PLAIN

        # 优先级 4: 中轴线战略山脉
        if (q, r) == central_mountain_axial_1 or (q, r) == (-central_mountain_axial_1[0], -central_mountain_axial_1[1]):
             return TerrainType.MOUNTAIN

        # 优先级 5: 地图边界 - 用森林和山脉包围，并保持稀疏
        if max(abs(q), abs(r), abs(s)) >= map_radius:
            rand_val = (q * 13 + r * 31) % 100
            if rand_val < 60:  # 60% 森林
                return TerrainType.FOREST
            elif rand_val < 75: # 15% 山脉
                return TerrainType.MOUNTAIN
        
        # 优先级 6: 河流系统
        diagonal_sum = q + r
        if diagonal_sum == 0: # 主河道
            return TerrainType.PLAIN if q == 0 and r == 0 else TerrainType.WATER
        # 河道加宽
        for tq, tr in river_thicken_points:
            if (q, r) == (tq, tr) or (q, r) == (-tq, -tr):
                return TerrainType.WATER
        
        # 优先级 7: 沿河森林
        for fq, fr in riverside_forests:
            if (q, r) == (fq, fr) or (q, r) == (-fq, -fr):
                return TerrainType.FOREST

        # 优先级 8: 城市周围的防御地形
        dist_to_bl_city = HexMath.hex_distance((col, row), city_bl_offset)
        dist_to_tr_city = HexMath.hex_distance((col, row), city_tr_offset)

        # 紧邻城市的平原
        if dist_to_bl_city == 1 or dist_to_tr_city == 1:
            return TerrainType.PLAIN
        # 环绕平原的森林
        if dist_to_bl_city == 2 or dist_to_tr_city == 2:
            return TerrainType.FOREST

        # 优先级 9: 战略山脉 (使用新的山脊定义)
        for mq, mr in mountain_ridge:
            if (q, r) == (mq, mr) or (q, r) == (-mq, -mr):
                return TerrainType.MOUNTAIN

        # 优先级 10: 填充一些战略丘陵
        strategic_hills = [(2, 2), (1, 3), (3, 3)]
        for hq, hr in strategic_hills:
            if (q, r) == (hq, hr) or (q, r) == (-hq, -hr):
                return TerrainType.HILL

        # 优先级 11: 默认地形
        return TerrainType.PLAIN

    def _save_map_info_to_stats(self):
        """保存地图信息到GameStats中"""
        import time
        from ..components import GameStats
        
        # 获取GameStats组件，如果不存在就暂时跳过
        game_stats = self.world.get_singleton_component(GameStats)
        if not game_stats:
            print("[MapSystem] GameStats组件不存在，跳过地图信息保存")
            return
        
        # 确定坐标系类型
        coordinate_system = "centered" if self.symmetry_type == "river_split_offset" else "offset"
        
        # 获取出生点位置
        spawn_positions = {}
        if self.competitive_mode:
            spawn_positions = self.get_competitive_spawn_positions()
        
        # 收集地图信息
        map_info = {
            "map_width": GameConfig.MAP_WIDTH,
            "map_height": GameConfig.MAP_HEIGHT,
            "map_type": self.symmetry_type,
            "competitive_mode": self.competitive_mode,
            "map_seed": self.seed,
            "spawn_positions": {faction.value: pos for faction, pos in spawn_positions.items()},
            "coordinate_system": coordinate_system,
            "symmetry_type": self.symmetry_type,
            "generation_timestamp": time.time(),
        }
        
        # 保存到GameStats
        game_stats.map_info = map_info
        
        print(f"[MapSystem] ✅ 地图信息已保存到GameStats:")
        print(f"  - 地图尺寸: {map_info['map_width']}x{map_info['map_height']}")
        print(f"  - 地图类型: {map_info['map_type']}")
        print(f"  - 竞技模式: {map_info['competitive_mode']}")
        print(f"  - 坐标系: {map_info['coordinate_system']}")
        print(f"  - 出生点: {map_info['spawn_positions']}")
