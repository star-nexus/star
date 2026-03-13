"""
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
    """Temporary tile class for compatibility with existing code."""

    def __init__(self, position):
        self.position = position


class MapSystem(System, MOBAMapMixin, EncounterMapMixin):
    """Map system - manages map generation and terrain, supports MOBA-style maps."""

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
        # After generating the map, save map info to GameStats
        self._save_map_info_to_stats()

    def subscribe_events(self):
        """Subscribe to events."""
        pass

    def update(self, delta_time: float) -> None:
        """Update the map system."""
        pass

    def generate_map(self):
        """Generate the map - choose generation method based on mode."""
        if self.competitive_mode:
            if self.symmetry_type == "river_split":
                print("[MapSystem] 🏆 Generating river-split diagonal competitive map (offset coords)")
                self._generate_river_split_diagonal_map()
            elif self.symmetry_type == "river_split_offset":
                print("[MapSystem] 🏆 Generating river-split diagonal competitive map (offset coords)")
                self._generate_river_split_diagonal_map_offset_revised()
            elif self.symmetry_type == "diagonal":
                print("[MapSystem] 🏆 Generating diagonal-symmetric competitive map")
                self._generate_competitive_map_diagonal()
            elif self.symmetry_type == "square":
                print("[MapSystem] 🏆 Generating square competitive map")
                self._generate_square_map()
            elif self.symmetry_type == "moba":
                print("[MapSystem] 🏟️ Generating MOBA-style map")
                self._generate_moba_map()
            elif self.symmetry_type == "encounter":
                print("[MapSystem] 🏟️ Generating Encounter-style map")
                self._generate_encounter_map()
            else:
                print("[MapSystem] 🏆 Generating horizontal-axis symmetric competitive map")
                self._generate_competitive_map_v2()
        else:
            print("[MapSystem] 🌍 Generating standard random map")
            self._generate_standard_map()

    def _generate_square_map(self):
        """Generate the map - produce a visually square hexagonal map (using offset coordinates)."""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        # Use offset coordinate system to directly generate a rectangular region
        for col in range(GameConfig.MAP_WIDTH):
            for row in range(GameConfig.MAP_HEIGHT):
                # Generate terrain
                terrain_type = self._generate_terrain_offset(col, row)

                # Create tile entity
                tile_entity = self.world.create_entity()
                self.world.add_component(tile_entity, HexPosition(col, row))
                self.world.add_component(tile_entity, Terrain(terrain_type))
                self.world.add_component(tile_entity, Tile((col, row)))

                # Add to map data
                map_data.tiles[(col, row)] = tile_entity

        self.world.add_singleton_component(map_data)

    def _generate_competitive_map_v2(self):
        """Generate competitive map V2.0 - using offset coordinate system."""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        print(
            f"[MapSystem] Generating {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} truly symmetric competitive map (offset coords)"
        )

        # Directly generate map using offset coordinates
        terrain_map = self._generate_symmetric_terrain_map_offset()

        # Create ECS entities
        self._create_competitive_map_entities_offset(map_data, terrain_map)

        # Add to world
        self.world.add_singleton_component(map_data)

        # Print analysis report
        self._print_competitive_map_analysis_v2_offset(terrain_map)

    def _generate_symmetric_terrain_map_offset(
        self,
    ) -> Dict[Tuple[int, int], TerrainType]:
        """Generate a fully symmetric terrain map (offset coordinates)."""
        terrain_map = {}

        # Traverse entire map
        for col in range(GameConfig.MAP_WIDTH):
            for row in range(GameConfig.MAP_HEIGHT):
                # Core: use guaranteed-symmetric terrain generation function
                terrain = self._generate_symmetric_terrain_offset(col, row)
                terrain_map[(col, row)] = terrain

        return terrain_map

    def _generate_symmetric_terrain_offset(self, col: int, row: int) -> TerrainType:
        """Generate absolutely symmetric terrain - offset coordinate version."""
        # Calculate map center
        center_col = GameConfig.MAP_WIDTH // 2
        center_row = GameConfig.MAP_HEIGHT // 2

        # Convert to center-origin coordinates
        center_based_col = col - center_col
        center_based_row = row - center_row

        # Key: use abs(row) to ensure horizontal symmetry
        abs_row = abs(center_based_row)
        distance_from_center = math.sqrt(
            center_based_col * center_based_col + abs_row * abs_row
        )

        # Use symmetric seed: produces the same random number for (col,row) and (col,-row)
        symmetric_seed = center_based_col * 10007 + abs_row * 10009 + self.seed
        rand = random.Random(symmetric_seed)
        value = rand.random()

        # === Zone A: Spawn point / home base area ===
        if abs_row >= 6:  # Northern/southern ends of the map
            return self._generate_spawn_area_terrain_offset(
                center_based_col, abs_row, value
            )

        # === Zone B: Central strategic zone ===
        elif distance_from_center <= 1.5:  # Exact center
            return self._generate_central_zone_terrain_offset(
                center_based_col, abs_row, value
            )

        # === Zone C: Tactical buffer zone ===
        elif distance_from_center <= 4.5:
            return self._generate_tactical_buffer_terrain_offset(
                center_based_col, abs_row, value
            )

        # === Zone D: Main confrontation lane ===
        else:  # Outer region
            return self._generate_outer_zone_terrain_offset(
                center_based_col, abs_row, value
            )

    def _generate_spawn_area_terrain_offset(
        self, col: int, abs_row: int, value: float
    ) -> TerrainType:
        """Generate spawn area terrain - offset coordinate version."""
        abs_col = abs(col)

        # Spawn core: pure plains for easy early deployment
        if abs_col <= 1 and abs_row >= 6:
            return TerrainType.PLAIN

        # Around spawn: mixed plains, hills, sparse forest
        if value < 0.6:
            return TerrainType.PLAIN  # 60% plains
        elif value < 0.8:
            return TerrainType.HILL  # 20% hills
        else:
            return TerrainType.FOREST  # 20% forest

    def _generate_central_zone_terrain_offset(
        self, col: int, abs_row: int, value: float
    ) -> TerrainType:
        """Generate central strategic zone terrain - offset coordinate version."""

        # Exact center point: the only city
        if col == 0 and abs_row == 0:
            return TerrainType.URBAN

        # Around center: high-value terrain
        if value < 0.4:
            return TerrainType.PLAIN  # 40% plains
        elif value < 0.7:
            return TerrainType.HILL  # 30% hills (high ground advantage)
        else:
            return TerrainType.FOREST  # 30% forest (tactical cover)

    def _generate_tactical_buffer_terrain_offset(
        self, col: int, abs_row: int, value: float
    ) -> TerrainType:
        """Generate tactical buffer zone terrain - offset coordinate version."""
        abs_col = abs(col)

        # Near central axis: relatively open main corridor
        if abs_col <= 2:
            if value < 0.5:
                return TerrainType.PLAIN
            elif value < 0.8:
                return TerrainType.HILL
            else:
                return TerrainType.FOREST

        # Edge areas: more obstacles and tactical terrain
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
                return TerrainType.WATER  # Small water bodies as natural barriers

    def _generate_outer_zone_terrain_offset(
        self, col: int, abs_row: int, value: float
    ) -> TerrainType:
        """Generate outer zone terrain - offset coordinate version."""

        # Edges: more mountains and water as natural borders
        if abs(col) >= 6 or abs_row >= 5:
            if value < 0.3:
                return TerrainType.MOUNTAIN
            elif value < 0.5:
                return TerrainType.WATER
            elif value < 0.8:
                return TerrainType.FOREST
            else:
                return TerrainType.HILL

        # Mid-range: balanced mixed terrain
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
        """Create competitive map entities - offset coordinate version."""
        # Calculate spawn positions (using offset coordinates)
        center_row = GameConfig.MAP_HEIGHT // 2
        spawn_distance = min(GameConfig.MAP_WIDTH, GameConfig.MAP_HEIGHT) // 2 - 1
        spawn_points = {
            Faction.SHU: (
                GameConfig.MAP_WIDTH // 2,
                center_row + spawn_distance,
            ),  # Upper spawn point
            Faction.WEI: (
                GameConfig.MAP_WIDTH // 2,
                center_row - spawn_distance,
            ),  # Lower spawn point
        }

        for (col, row), terrain_type in terrain_map.items():
            # Create tile entity
            tile_entity = self.world.create_entity()
            self.world.add_component(tile_entity, HexPosition(col, row))
            self.world.add_component(tile_entity, Terrain(terrain_type))
            self.world.add_component(tile_entity, Tile((col, row)))

            # Set initial territory control near spawn points
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

            # Add to map data
            map_data.tiles[(col, row)] = tile_entity

    def _print_competitive_map_analysis_v2_offset(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Print competitive map analysis report V2.0 - offset coordinate version."""
        terrain_count = {}
        for terrain in terrain_map.values():
            terrain_count[terrain] = terrain_count.get(terrain, 0) + 1

        print("\n" + "=" * 70)
        print("🏆 Competitive Map Analysis Report V2.0 (Offset Coordinate System)")
        print("=" * 70)
        print(f"📐 Map size: {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT}")
        print(f"🎯 Design principle: Horizontal symmetry, intuitive coordinate system")
        print(f"⚖️  Axis of symmetry: Horizontal center line (row={GameConfig.MAP_HEIGHT//2})")
        print(f"🗂️  Coordinate system: Offset coordinates (intuitive row/column layout)")
        print(f"🔢 Fixed seed: {self.seed} (ensures reproducibility)")

        print("\n🌍 Terrain distribution:")
        total_tiles = len(terrain_map)
        for terrain, count in sorted(
            terrain_count.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / total_tiles * 100
            print(f"  {terrain.value:10} {count:3d} tiles ({percentage:5.1f}%)")

        # Detailed map visualization print
        self._print_terrain_map_visual_offset(terrain_map)

        # Strict symmetry verification
        self._verify_map_symmetry_v2_offset(terrain_map)

        # Spawn point info
        center_row = GameConfig.MAP_HEIGHT // 2
        spawn_distance = min(GameConfig.MAP_WIDTH, GameConfig.MAP_HEIGHT) // 2 - 1
        print(f"\n🚀 Faction spawn points:")
        print(
            f"  SHU: ({GameConfig.MAP_WIDTH//2}, {center_row + spawn_distance})  - top of map"
        )
        print(
            f"  WEI: ({GameConfig.MAP_WIDTH//2}, {center_row - spawn_distance}) - bottom of map"
        )
        print(f"  📏 Spawn distance: {2 * spawn_distance} tiles")

        print("=" * 70)

    def _print_terrain_map_visual_offset(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Print the visual representation of the map - offset coordinate version."""
        print("\n🗺️ Terrain map visualization (rows top-to-bottom, columns left-to-right):")
        print("   Terrain symbols: P=Plain F=Forest H=Hill M=Mountain W=Water U=Urban")

        terrain_chars = {
            TerrainType.PLAIN: "P",
            TerrainType.FOREST: "F",
            TerrainType.HILL: "H",
            TerrainType.MOUNTAIN: "M",
            TerrainType.WATER: "W",
            TerrainType.URBAN: "U",
        }

        print("\n   ", end="")

        # Print column headers (col coordinates)
        for col in range(GameConfig.MAP_WIDTH):
            print(f"{col:2}", end=" ")
        print()

        # Print each row
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

        # Print bottom column headers again
        print("   ", end="")
        for col in range(GameConfig.MAP_WIDTH):
            print(f"{col:2}", end=" ")
        print()

    def _verify_map_symmetry_v2_offset(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Strictly verify map symmetry V2.0 - offset coordinate version."""
        print(f"\n🔍 Symmetry verification V2.0 (offset coordinates):")

        asymmetric_pairs = []
        symmetric_pairs = 0
        total_checks = 0

        center_row = GameConfig.MAP_HEIGHT // 2

        # Check each position against its mirror
        for col in range(GameConfig.MAP_WIDTH):
            for row in range(GameConfig.MAP_HEIGHT):
                if (col, row) in terrain_map:
                    # Calculate mirror position: symmetric about the horizontal center axis
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
                                "terrain2": "missing",
                            }
                        )

        if len(asymmetric_pairs) == 0:
            print(f"  ✅ Perfect symmetry! {symmetric_pairs}/{total_checks} positions fully symmetric")
        else:
            print(f"  ❌ Found {len(asymmetric_pairs)} asymmetric positions:")
            for i, pair in enumerate(asymmetric_pairs[:5]):
                print(
                    f"    {pair['pos1']}={pair['terrain1']} ≠ {pair['pos2']}={pair['terrain2']}"
                )
            if len(asymmetric_pairs) > 5:
                print(f"    ... {len(asymmetric_pairs) - 5} more asymmetric positions")

    def _get_initial_territory_control(
        self,
        pos: Tuple[int, int],
        spawn_points: Dict[Faction, Tuple[int, int]],
        control_radius: int = 2,
    ) -> Faction:
        """Determine initial territory control."""
        q, r = pos

        for faction, (spawn_q, spawn_r) in spawn_points.items():
            distance = math.sqrt((q - spawn_q) ** 2 + (r - spawn_r) ** 2)
            if distance <= control_radius:
                return faction

        return None

    def _print_competitive_map_analysis_v2(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Print competitive map analysis report V2.0."""
        terrain_count = {}
        for terrain in terrain_map.values():
            terrain_count[terrain] = terrain_count.get(terrain, 0) + 1

        print("\n" + "=" * 70)
        print("🏆 Competitive Map Analysis Report V2.0")
        print("=" * 70)
        print(f"📐 Map size: {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT}")
        print("🎯 Design: strict horizontal symmetry with layered strategic zones")
        print("⚖️  Symmetry axis: horizontal center line (r=0)")
        print(f"🔢 Fixed seed: {self.seed} (reproducible)")

        print("\n🌍 Terrain distribution:")
        total_tiles = len(terrain_map)
        for terrain, count in sorted(
            terrain_count.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / total_tiles * 100
            print(f"  {terrain.value:10} {count:3d} tiles ({percentage:5.1f}%)")

        # Detailed map visualization print
        self._print_terrain_map_visual(terrain_map)

        # Strict symmetry verification
        self._verify_map_symmetry_v2(terrain_map)

        # Strategic zone analysis
        self._analyze_strategic_zones(terrain_map)

        # Spawn point info
        spawn_distance = min(GameConfig.MAP_WIDTH, GameConfig.MAP_HEIGHT) // 2 - 1
        print("\n🚀 Faction spawn points:")
        print(f"  SHU: (0, {spawn_distance})  - top of map")
        print(f"  WEI: (0, {-spawn_distance}) - bottom of map")
        print(f"  📏 Spawn distance: {2 * spawn_distance} tiles")

        print("=" * 70)

    def _print_terrain_map_visual(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Print the visual representation of the map."""
        print("\n🗺️ Terrain map visualization (r top-to-bottom, q left-to-right):")
        print("   Symbols: P=Plain F=Forest H=Hill M=Mountain W=Water U=Urban")

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

        # Print column headers (q coordinates)
        for q in range(-center, center + 1):
            print(f"{q:2}", end=" ")
        print()

        # Print each row
        for r in range(center, -center - 1, -1):  # top to bottom (r=7 to r=-7)
            print(f"{r:2}:", end=" ")
            for q in range(-center, center + 1):
                if (q, r) in terrain_map:
                    terrain = terrain_map[(q, r)]
                    char = terrain_chars.get(terrain, "?")
                    print(f" {char}", end=" ")
                else:
                    print("  ", end=" ")
            print(f" :{r}")

        # Print bottom column headers again
        print("   ", end="")
        for q in range(-center, center + 1):
            print(f"{q:2}", end=" ")
        print()

    def _verify_map_symmetry_v2(self, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """Strictly verify map symmetry V2.0."""
        print("\n🔍 Symmetry verification V2.0:")

        asymmetric_pairs = []
        symmetric_pairs = 0
        total_checks = 0

        center = GameConfig.MAP_WIDTH // 2

        # Check each position against its mirror
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
                                "terrain2": "missing",
                            }
                        )

        if len(asymmetric_pairs) == 0:
            print(f"  ✅ Perfect symmetry! {symmetric_pairs}/{total_checks} positions fully symmetric")
        else:
            print(f"  ❌ Found {len(asymmetric_pairs)} asymmetric positions:")
            for i, pair in enumerate(asymmetric_pairs[:5]):
                print(
                    f"    {pair['pos1']}={pair['terrain1']} ≠ {pair['pos2']}={pair['terrain2']}"
                )
            if len(asymmetric_pairs) > 5:
                print(f"    ... and {len(asymmetric_pairs) - 5} more asymmetric positions")

    def _analyze_strategic_zones(self, terrain_map: Dict[Tuple[int, int], TerrainType]):
        """Analyze strategic zone distribution."""
        print("\n🎯 Strategic zone analysis:")

        zones = {"Spawn Area": 0, "Central Strategic Zone": 0, "Tactical Buffer": 0, "Outer Region": 0}

        center = GameConfig.MAP_WIDTH // 2

        for q in range(-center, center + 1):
            for r in range(-center, center + 1):
                if (q, r) in terrain_map:
                    abs_r = abs(r)
                    distance_from_center = math.sqrt(q * q + abs_r * abs_r)

                    if abs_r >= 6:
                        zones["Spawn Area"] += 1
                    elif distance_from_center <= 1.5:
                        zones["Central Strategic Zone"] += 1
                    elif distance_from_center <= 4.5:
                        zones["Tactical Buffer"] += 1
                    else:
                        zones["Outer Region"] += 1

        for zone_name, count in zones.items():
            print(f"  {zone_name}: {count} tiles")

    def _generate_competitive_map_diagonal(self):
        """Generate diagonal-symmetric competitive map."""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        print(
            f"[MapSystem] Generating {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} diagonal-symmetric competitive map"
        )

        # Generate diagonal-symmetric map
        terrain_map = self._generate_diagonal_symmetric_terrain_map()

        # Create ECS entities (using diagonal spawn points)
        self._create_diagonal_competitive_map_entities(map_data, terrain_map)

        # Add to world
        self.world.add_singleton_component(map_data)

        # Print analysis report
        self._print_diagonal_competitive_map_analysis(terrain_map)

    def _generate_diagonal_symmetric_terrain_map(
        self,
    ) -> Dict[Tuple[int, int], TerrainType]:
        """Generate a diagonal-symmetric terrain map."""
        terrain_map = {}
        center = GameConfig.MAP_WIDTH // 2

        # Only generate the upper-left triangle, then mirror to the lower-right
        for q in range(GameConfig.MAP_WIDTH):
            for r in range(GameConfig.MAP_HEIGHT):
                center_q = q - center
                center_r = r - center

                # Check if in upper-left triangle or on diagonal
                if center_q <= -center_r:  # upper-left triangle + diagonal
                    terrain = self._generate_diagonal_terrain(center_q, center_r)
                    terrain_map[(center_q, center_r)] = terrain

                    # Also generate the diagonal mirror point (if not on the diagonal)
                    if center_q != -center_r:  # not on the diagonal
                        mirror_q, mirror_r = -center_r, -center_q
                        terrain_map[(mirror_q, mirror_r)] = terrain

        return terrain_map

    def _generate_diagonal_terrain(self, q: int, r: int) -> TerrainType:
        """Generate base terrain for the diagonal-symmetric map."""

        # Distance to diagonal (diagonal equation: q + r = 0)
        distance_to_diagonal = abs(q + r) / math.sqrt(2)

        # Distance to map center
        distance_from_center = math.sqrt(q * q + r * r)

        # Key: use a seed symmetric about the diagonal.
        # For (q,r) and (-r,-q), this seed is identical.
        min_coord = min(q, -r)
        max_coord = max(q, -r)
        symmetric_seed = min_coord * 10007 + max_coord * 10009 + self.seed
        rand = random.Random(symmetric_seed)
        value = rand.random()

        # === Zone A: Spawn area (upper-left and lower-right corners) ===
        if (q <= -5 and r >= 5) or (q >= 5 and r <= -5):
            return self._generate_diagonal_spawn_area_terrain(q, r, value)

        # === Zone B: Central area ===
        elif distance_from_center <= 1.5:
            return self._generate_diagonal_central_terrain(q, r, value)

        # === Zone C: Diagonal buffer zone ===
        elif distance_to_diagonal <= 2.0:
            return self._generate_diagonal_buffer_terrain(q, r, value)

        # === Zone D: Outer region ===
        else:
            return self._generate_diagonal_outer_terrain(q, r, value)

    def _generate_diagonal_spawn_area_terrain(
        self, q: int, r: int, value: float
    ) -> TerrainType:
        """Generate spawn area terrain for the diagonal map mode."""
        # Spawn core: primarily plains
        if abs(q + 6) <= 1 and abs(r - 6) <= 1:  # Upper-left spawn core
            return TerrainType.PLAIN
        if abs(q - 6) <= 1 and abs(r + 6) <= 1:  # Lower-right spawn core (symmetric)
            return TerrainType.PLAIN

        # Around spawn: safe mixed terrain
        if value < 0.5:
            return TerrainType.PLAIN
        elif value < 0.75:
            return TerrainType.HILL
        else:
            return TerrainType.FOREST

    def _generate_diagonal_central_terrain(
        self, q: int, r: int, value: float
    ) -> TerrainType:
        """Generate central area terrain for the diagonal map mode."""
        # Exact center: city
        if q == 0 and r == 0:
            return TerrainType.URBAN

        # Around center: high-value terrain
        if value < 0.4:
            return TerrainType.PLAIN
        elif value < 0.7:
            return TerrainType.HILL
        else:
            return TerrainType.FOREST

    def _generate_diagonal_buffer_terrain(
        self, q: int, r: int, value: float
    ) -> TerrainType:
        """Generate diagonal buffer zone terrain."""
        # Near the main diagonal: relatively open
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
        """Generate outer terrain for the diagonal map mode."""
        # Edges: more obstacles
        if abs(q) >= 6 or abs(r) >= 6:
            if value < 0.3:
                return TerrainType.MOUNTAIN
            elif value < 0.5:
                return TerrainType.WATER
            else:
                return TerrainType.FOREST
        else:
            # Mid-range: balanced terrain
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
        """Create diagonal-symmetric competitive map entities."""
        # Spawn points for diagonal mode
        spawn_points = {
            Faction.SHU: (-6, 6),  # Upper-left corner
            Faction.WEI: (6, -6),  # Lower-right corner
        }

        for (q, r), terrain_type in terrain_map.items():
            # Create tile entity
            tile_entity = self.world.create_entity()
            self.world.add_component(tile_entity, HexPosition(q, r))
            self.world.add_component(tile_entity, Terrain(terrain_type))
            self.world.add_component(tile_entity, Tile((q, r)))

            # Set initial territory control near spawn points
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

            # Add to map data
            map_data.tiles[(q, r)] = tile_entity

    def _print_diagonal_competitive_map_analysis(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Print diagonal competitive map analysis report."""
        terrain_count = {}
        for terrain in terrain_map.values():
            terrain_count[terrain] = terrain_count.get(terrain, 0) + 1

        print("\n" + "=" * 70)
        print("🏆 Diagonal-Symmetric Competitive Map Analysis Report")
        print("=" * 70)
        print(f"📐 Map size: {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT}")
        print("🎯 Design: diagonal symmetry (q=-r axis), upper-left ↔ lower-right")
        print("⚖️  Symmetry axis: main diagonal (q + r = 0)")
        print(f"🔢 Fixed seed: {self.seed} (reproducible)")

        print("\n🌍 Terrain distribution:")
        total_tiles = len(terrain_map)
        for terrain, count in sorted(
            terrain_count.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / total_tiles * 100
            print(f"  {terrain.value:10} {count:3d} tiles ({percentage:5.1f}%)")

        # Map visualization
        self._print_terrain_map_visual(terrain_map)

        # Diagonal symmetry verification
        self._verify_diagonal_symmetry(terrain_map)

        # Spawn point info
        print("\n🚀 Faction spawn points:")
        print("  SHU: (-6, 6)  - upper-left corner")
        print("  WEI: (6, -6)  - lower-right corner")
        print(f"  📏 Spawn distance: {math.sqrt((12)**2 + (12)**2):.1f} tiles")

        print("=" * 70)

    def _verify_diagonal_symmetry(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Verify diagonal symmetry."""
        print("\n🔍 Diagonal symmetry verification:")

        asymmetric_pairs = []
        symmetric_pairs = 0
        total_checks = 0

        center = GameConfig.MAP_WIDTH // 2

        # Check each position against its diagonal mirror
        for q in range(-center, center + 1):
            for r in range(-center, center + 1):
                if (q, r) in terrain_map:
                    mirror_pos = (-r, -q)  # diagonal mirror
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
                                "terrain2": "missing",
                            }
                        )

        if len(asymmetric_pairs) == 0:
            print(
                f"  ✅ Perfect diagonal symmetry! {symmetric_pairs}/{total_checks} positions fully symmetric"
            )
        else:
            print(f"  ❌ Found {len(asymmetric_pairs)} asymmetric positions:")
            for i, pair in enumerate(asymmetric_pairs[:5]):
                print(
                    f"    {pair['pos1']}={pair['terrain1']} ≠ {pair['pos2']}={pair['terrain2']}"
                )
            if len(asymmetric_pairs) > 5:
                print(f"    ... and {len(asymmetric_pairs) - 5} more asymmetric positions")

    def _generate_standard_map(self):
        """Generate a standard random map (using offset coordinates)."""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        # Generate map
        for col in range(GameConfig.MAP_WIDTH):
            for row in range(GameConfig.MAP_HEIGHT):
                # Generate terrain using offset coordinates
                terrain_type = self._generate_terrain_offset(col, row)

                # Create tile entity
                tile_entity = self.world.create_entity()
                self.world.add_component(tile_entity, HexPosition(col, row))
                self.world.add_component(tile_entity, Terrain(terrain_type))
                self.world.add_component(tile_entity, Tile((col, row)))

                # Add to map data
                map_data.tiles[(col, row)] = tile_entity

        self.world.add_singleton_component(map_data)

    def get_competitive_spawn_positions(self) -> Dict[Faction, Tuple[int, int]]:
        """Get spawn positions for competitive mode (offset coordinates)."""
        if not self.competitive_mode:
            return {}

        center_col = GameConfig.MAP_WIDTH // 2
        center_row = GameConfig.MAP_HEIGHT // 2
        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        if self.symmetry_type == "river_split_offset":
            return {
                Faction.SHU: (-half_width + 3, -half_height + 3),  # Lower-left front line
                Faction.WEI: (half_width - 3, half_height - 3),   # Upper-right front line
            }
        elif self.symmetry_type == "river_split":
            return {
                Faction.SHU: (center_col - 4, center_row + 4),
                Faction.WEI: (center_col + 4, center_row - 4),
            }
        elif self.symmetry_type == "diagonal":
            return {
                Faction.SHU: (center_col - 6, center_row + 6),  # Upper-left corner
                Faction.WEI: (center_col + 6, center_row - 6),  # Lower-right corner
            }
        else:
            # Horizontal symmetry mode
            spawn_distance = min(GameConfig.MAP_WIDTH, GameConfig.MAP_HEIGHT) // 2 - 1
            return {
                Faction.SHU: (center_col, center_row + spawn_distance),  # Upper spawn point
                Faction.WEI: (center_col, center_row - spawn_distance),  # Lower spawn point
            }

    def enable_competitive_mode(self, enabled: bool = True):
        """Enable or disable competitive mode."""
        self.competitive_mode = enabled
        print(f"[MapSystem] Competitive mode: {'enabled' if enabled else 'disabled'}")

    def _generate_terrain_offset(self, col: int, row: int) -> TerrainType:
        """Generate terrain type - offset coordinate version."""
        # Use a fixed seed for consistent terrain generation
        rand = random.Random(col * 10007 + row * 10009 + self.seed)
        value = rand.random()

        # Distance from map center
        center_col = GameConfig.MAP_WIDTH // 2
        center_row = GameConfig.MAP_HEIGHT // 2
        distance = math.sqrt((col - center_col) ** 2 + (row - center_row) ** 2)
        max_distance = math.sqrt(center_col**2 + center_row**2)
        distance_ratio = distance / max_distance

        # Determine terrain based on distance and random value
        if distance < 3:
            # Central area: more cities and plains
            if value < 0.2:
                return TerrainType.URBAN
            elif value < 0.7:
                return TerrainType.PLAIN
            elif value < 0.85:
                return TerrainType.HILL
            else:
                return TerrainType.FOREST
        elif distance_ratio > 0.8:
            # Edge area: more mountains and water
            if value < 0.25:
                return TerrainType.MOUNTAIN
            elif value < 0.4:
                return TerrainType.WATER
            elif value < 0.7:
                return TerrainType.FOREST
            else:
                return TerrainType.HILL
        elif distance_ratio > 0.6:
            # Outer area: mixed terrain
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
            # Middle area: balanced diverse terrain
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

    # Retain original terrain generation method for compatibility (cubic/axial coordinate system)
    def _generate_terrain(self, q: int, r: int) -> TerrainType:
        """Generate terrain type - cubic coordinate version (deprecated, kept for compatibility)."""
        # Use a fixed seed for consistent terrain generation
        rand = random.Random(q * 10007 + r * 10009)
        value = rand.random()

        # Distance from center
        distance = math.sqrt(q * q + r * r)
        max_distance = math.sqrt(
            (GameConfig.MAP_WIDTH // 2) ** 2 + (GameConfig.MAP_HEIGHT // 2) ** 2
        )
        distance_ratio = distance / max_distance

        # Determine terrain based on distance and random value
        if distance < 3:
            # Central area: more cities and plains
            if value < 0.2:
                return TerrainType.URBAN
            elif value < 0.7:
                return TerrainType.PLAIN
            elif value < 0.85:
                return TerrainType.HILL
            else:
                return TerrainType.FOREST
        elif distance_ratio > 0.8:
            # Edge area: more mountains and water
            if value < 0.25:
                return TerrainType.MOUNTAIN
            elif value < 0.4:
                return TerrainType.WATER
            elif value < 0.7:
                return TerrainType.FOREST
            else:
                return TerrainType.HILL
        elif distance_ratio > 0.6:
            # Outer area: mixed terrain
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
            # Middle area: balanced diverse terrain
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
        """Set symmetry type."""
        if symmetry_type in ["horizontal", "diagonal", "river_split", "river_split_offset", "square", "moba", "encounter"]:
            self.symmetry_type = symmetry_type
            print(f"[MapSystem] Symmetry type set to: {symmetry_type}")
        else:
            print(
                f"[MapSystem] Warning: unknown symmetry type {symmetry_type}; defaulting to 'horizontal'"
            )
            self.symmetry_type = "horizontal"

    def _generate_river_split_diagonal_map(self):
        """Generate a river-split diagonal-symmetric competitive map."""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        print(
            f"[MapSystem] Generating {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} river-split competitive map"
        )
        print("[MapSystem] Design: diagonal river divider, central contest area, rear cities")

        # Generate river-split map
        terrain_map = self._generate_river_split_terrain_map()

        # Create ECS entities
        self._create_river_split_map_entities(map_data, terrain_map)

        # Add to world
        self.world.add_singleton_component(map_data)

        # Print analysis report
        self._print_river_split_map_analysis(terrain_map)

    def _generate_river_split_terrain_map(self) -> Dict[Tuple[int, int], TerrainType]:
        """Generate the river-split terrain map."""
        terrain_map = {}
        center = GameConfig.MAP_WIDTH // 2

        # Traverse entire map
        for q in range(GameConfig.MAP_WIDTH):
            for r in range(GameConfig.MAP_HEIGHT):
                center_q = q - center
                center_r = r - center

                terrain = self._generate_river_split_terrain(center_q, center_r)
                terrain_map[(center_q, center_r)] = terrain

        return terrain_map

    def _generate_river_split_terrain(self, q: int, r: int) -> TerrainType:
        """Fully deterministic river-split terrain - V4: enhanced central strategic elements."""

        # === Priority 1: Rear cities (center-symmetric) ===
        # User-specified new city positions
        if (q == 5 and r == 4) or (q == -5 and r == -4):
            return TerrainType.URBAN

        # === Priority 2: Diagonal river system ===
        diagonal_distance = abs(q + r)
        if diagonal_distance == 0:
            return TerrainType.PLAIN if (q == 0 and r == 0) else TerrainType.WATER
        elif diagonal_distance == 1:
            if (abs(q) <= 1 and abs(r) <= 1) or ((q * q + r * r) % 5 == 0):
                return TerrainType.PLAIN
            else:
                return TerrainType.WATER

        # === Priority 3: Strategic terrain around cities and central area ===

        # City defense zone: ensure plains around cities (center-symmetric)
        city1_dist = math.sqrt((q - 5) ** 2 + (r - 4) ** 2)
        city2_dist = math.sqrt((q + 5) ** 2 + (r + 4) ** 2)
        if city1_dist <= 1.5 or city2_dist <= 1.5:
            return TerrainType.PLAIN

        # Central area strategic points (center-symmetric) - additional terrain variety
        # Define one half; the other half is generated symmetrically by code
        central_hills = [(2, 2), (1, 3), (3, 3)]  # existing  # new hills for deeper firing positions
        for hq, hr in central_hills:
            if (q == hq and r == hr) or (q == -hq and r == -hr):
                return TerrainType.HILL

        central_forests = [
            (3, 1),
            (2, -1),  # existing
            (4, 2),  # new forest for flank cover
            (1, 4),  # new forest connecting rear to front line
        ]
        for fq, fr in central_forests:
            if (q == fq and r == fr) or (q == -fq and r == -fr):
                return TerrainType.FOREST

        # === Priority 4: Peripheral natural terrain clusters (maintain diagonal symmetry) ===

        # Forest clusters: circular/elliptical distribution for a natural look
        forest_clusters = [
            # Define only one half; the other half is generated via symmetry
            ((-4, 6), 1.8),  # Rear forest
            ((-2, 3), 1.2),  # Front-line forest
            ((-6, 2), 1.0),  # Flank forest
        ]

        for (center_q, center_r), radius in forest_clusters:
            # Check original point
            distance1 = math.sqrt((q - center_q) ** 2 + (r - center_r) ** 2)
            # Check diagonal mirror point
            distance2 = math.sqrt((q - (-center_r)) ** 2 + (r - (-center_q)) ** 2)
            if distance1 <= radius or distance2 <= radius:
                return TerrainType.FOREST

        # Mountain clusters: strategic high ground, circular distribution
        mountain_clusters = [
            # Define only one half
            ((-3, 5), 1.0),  # Key high ground
            ((-6, 6), 0.8),  # Corner fortress
        ]

        for (center_q, center_r), radius in mountain_clusters:
            # Check original and diagonal mirror points
            distance1 = math.sqrt((q - center_q) ** 2 + (r - center_r) ** 2)
            distance2 = math.sqrt((q - (-center_r)) ** 2 + (r - (-center_q)) ** 2)
            if distance1 <= radius or distance2 <= radius:
                return TerrainType.MOUNTAIN

        # Strategic hills: precise single-point high ground
        strategic_hills = [
            # Define only one half
            (-1, 3),
            (-4, 2),
        ]

        for hill_q, hill_r in strategic_hills:
            # Check original and diagonal mirror points
            if (q == hill_q and r == hill_r) or (q == -hill_r and r == -hill_q):
                return TerrainType.HILL

        # === Priority 5: Boundary handling ===
        # Map edges: sparse mountain border
        if abs(q) == 7 or abs(r) == 7:
            # Only place border mountains at specific positions, not all
            if (q + r) % 3 == 0:
                return TerrainType.MOUNTAIN
            else:
                return TerrainType.FOREST

        # === Priority 6: Default terrain ===
        # All other areas are plains
        return TerrainType.PLAIN

    def _create_river_split_map_entities(
        self, map_data: MapData, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Create river-split map entities."""
        # Spawn points: at front-line positions in each faction's area
        spawn_points = {
            Faction.SHU: (-4, 4),  # Upper-left area front line
            Faction.WEI: (4, -4),  # Lower-right area front line
        }

        for (q, r), terrain_type in terrain_map.items():
            # Create tile entity
            tile_entity = self.world.create_entity()
            self.world.add_component(tile_entity, HexPosition(q, r))
            self.world.add_component(tile_entity, Terrain(terrain_type))
            self.world.add_component(tile_entity, Tile((q, r)))

            # Set territory control near spawn points and cities
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

            # Add to map data
            map_data.tiles[(q, r)] = tile_entity

    def _get_river_split_territory_control(
        self,
        pos: Tuple[int, int],
        spawn_points: Dict[Faction, Tuple[int, int]],
        control_radius: int = 2,
    ) -> Faction:
        """Determine initial territory control for the river-split map."""
        q, r = pos

        # Control around spawn points
        for faction, (spawn_q, spawn_r) in spawn_points.items():
            distance = math.sqrt((q - spawn_q) ** 2 + (r - spawn_r) ** 2)
            if distance <= control_radius:
                return faction

        # City control (center-symmetric)
        # (5, 4) is in WEI's area (q+r > 0)
        if math.sqrt((q - 5) ** 2 + (r - 4) ** 2) <= 2:
            return Faction.WEI

        # (-5, -4) is in SHU's area (q+r < 0)
        if math.sqrt((q + 5) ** 2 + (r + 4) ** 2) <= 2:
            return Faction.SHU

        return None

    def _print_river_split_map_analysis(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Print river-split map analysis report."""
        terrain_count = {}
        for terrain in terrain_map.values():
            terrain_count[terrain] = terrain_count.get(terrain, 0) + 1

        print("\n" + "=" * 70)
        print("🌊 River-Split Diagonal Competitive Map Analysis Report")
        print("=" * 70)
        print(f"📐 Map size: {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT}")
        print("🎯 Design: diagonal river boundary with zoned layout")
        print("🌊 River system: along the main diagonal (q + r = 0)")
        print("🏰 Strategic highlights: central contest point + two rear cities")
        print(f"🔢 Fixed seed: {self.seed} (reproducible)")

        print("\n🌍 Terrain distribution:")
        total_tiles = len(terrain_map)
        for terrain, count in sorted(
            terrain_count.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / total_tiles * 100
            print(f"  {terrain.value:10} {count:3d} tiles ({percentage:5.1f}%)")

        # Map visualization
        self._print_terrain_map_visual(terrain_map)

        # Symmetry verification
        self._verify_diagonal_symmetry(terrain_map)

        # Strategic point analysis
        self._analyze_river_split_strategic_points(terrain_map)

        print("=" * 70)

    def _analyze_river_split_strategic_points(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Analyze strategic points on the river-split map."""
        print("\n🎯 Strategic point analysis:")

        # Count terrain clusters by type
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

        print(f"  🔵 SHU control zone: {shu_area_count} tiles (upper-left)")
        print(f"  🔴 WEI control zone: {wei_area_count} tiles (lower-right)")
        print(f"  🌊 River system: {river_count} tiles (natural boundary)")
        print(f"  🏰 Cities: {city_count} (rear strongholds)")
        print(f"  🌱 Plains: {plain_count} tiles (main maneuver area)")
        print(f"  🏔️ Mountains: {mountain_count} tiles (strategic high ground)")
        print("  ⭐ Central contest point: (0, 0) - Plain")

        print("\n🚀 Faction deployment:")
        print("  SHU: spawn(-4, 4), city(-5, -4) - rear area")
        print("  WEI: spawn(4, -4), city(5, 4) - rear area")
        print(f"  📏 Straight-line distance: {math.sqrt(8**2 + 8**2):.1f} tiles")
        print("  🌊 A river crossing is required to reach the opponent area")
        print("  🏰 Cities are placed deeper in the rear, providing strategic depth")

    def _generate_river_split_diagonal_map_offset(self):
        """Generate a river-split diagonal-symmetric competitive map - offset coordinate version."""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        print(
            f"[MapSystem] Generating {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} river-split competitive map (offset coords)"
        )
        print("[MapSystem] Design: diagonal river boundary, symmetric across corners, diagonal strategic layout")

        # Generate river-split map (offset coordinate version)
        terrain_map = self._generate_river_split_terrain_map_offset()

        # Create ECS entities (offset coordinate version)
        self._create_river_split_map_entities_offset(map_data, terrain_map)

        # Add to world
        self.world.add_singleton_component(map_data)

        # Print analysis report (offset coordinate version)
        self._print_river_split_map_analysis_offset(terrain_map)

    def _generate_river_split_terrain_map_offset(self) -> Dict[Tuple[int, int], TerrainType]:
        """Generate the river-split terrain map - centered at (0,0) coordinate version."""
        terrain_map = {}

        # Calculate map radius
        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        # Traverse entire map ((0,0)-centered coordinates)
        for x in range(-half_width, half_width + 1):
            for y in range(-half_height, half_height + 1):
                terrain = self._generate_river_split_terrain_centered(x, y)
                terrain_map[(x, y)] = terrain

        return terrain_map

    def _generate_river_split_terrain_centered(self, x: int, y: int) -> TerrainType:
        """Fully deterministic river-split terrain - (0,0)-centered coordinates, lower-left/upper-right diagonal symmetry."""
        
        # Calculate map radius
        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2
        
        # === Priority 1: Rear cities (diagonal-symmetric) ===
        # Lower-left and upper-right corner cities
        if (x == -half_width + 2 and y == -half_height + 2) or (x == half_width - 2 and y == half_height - 2):
            return TerrainType.URBAN

        # === Priority 2: Diagonal river system ===
        # Anti-diagonal (upper-right to lower-left), equation: x + y = 0
        diagonal_distance = abs(x + y)
        
        if diagonal_distance == 0:
            # Exactly on the anti-diagonal
            if x == 0 and y == 0:
                return TerrainType.PLAIN  # Center contest point
            else:
                return TerrainType.WATER  # River
        elif diagonal_distance == 1:
            # River banks
            # Near center or specific positions become plains; others are river
            if (abs(x) <= 1 and abs(y) <= 1) or ((x * x + y * y) % 5 == 0):
                return TerrainType.PLAIN
            else:
                return TerrainType.WATER

        # === Priority 3: Strategic terrain around cities and central area ===
        
        # City defense zone: ensure plains around cities (diagonal-symmetric)
        # Lower-left city defense zone
        city1_dist = math.sqrt((x - (-half_width + 2)) ** 2 + (y - (-half_height + 2)) ** 2)
        # Upper-right city defense zone
        city2_dist = math.sqrt((x - (half_width - 2)) ** 2 + (y - (half_height - 2)) ** 2)
        if city1_dist <= 1.5 or city2_dist <= 1.5:
            return TerrainType.PLAIN

        # Central area strategic points (diagonal-symmetric)
        # Define one half of strategic hills; the other half is generated via diagonal symmetry
        strategic_hills = [
            (-2, 1),   # Hills in lower-left quadrant
            (-1, 2),
            (-3, 2),
        ]
        
        for hx, hy in strategic_hills:
            # Check original and diagonal mirror points (x, y) ↔ (-y, -x)
            if (x == hx and y == hy) or (x == -hy and y == -hx):
                return TerrainType.HILL

        # Central forest areas (diagonal-symmetric)
        central_forests = [
            (-1, -1),  # Forest in lower-left quadrant
            (1, 1),    # Forest in upper-right quadrant
            (-3, 1),   # Forest in lower-left quadrant
        ]
        
        for fx, fy in central_forests:
            # Check original and diagonal mirror points (x, y) ↔ (-y, -x)
            if (x == fx and y == fy) or (x == -fy and y == -fx):
                return TerrainType.FOREST

        # === Priority 4: Peripheral natural terrain clusters (diagonal-symmetric) ===
        
        # Forest clusters: circular distribution for a natural look
        forest_clusters = [
            # Define only one half; the other half is generated via diagonal symmetry
            ((-half_width + 3, -half_height + 2), 1.8),  # Lower-left rear forest
            ((-2, 2), 1.2),                              # Lower-left front-line forest
            ((-half_width + 2, -half_height + 4), 1.0),  # Lower-left flank forest
        ]

        for (center_fx, center_fy), radius in forest_clusters:
            # Check original point
            distance1 = math.sqrt((x - center_fx) ** 2 + (y - center_fy) ** 2)
            # Check diagonal mirror point (x, y) ↔ (-y, -x)
            sym_center_x = -center_fy
            sym_center_y = -center_fx
            distance2 = math.sqrt((x - sym_center_x) ** 2 + (y - sym_center_y) ** 2)
            if distance1 <= radius or distance2 <= radius:
                return TerrainType.FOREST

        # Mountain clusters: strategic high ground, circular distribution
        mountain_clusters = [
            # Define only one half; the other half is generated via diagonal symmetry
            ((-1, -3), 1.0),  # Lower-left key high ground
            ((-half_width + 1, -half_height + 1), 0.8),  # Lower-left corner fortress
        ]

        for (center_mx, center_my), radius in mountain_clusters:
            # Check original and diagonal mirror points (x, y) ↔ (-y, -x)
            distance1 = math.sqrt((x - center_mx) ** 2 + (y - center_my) ** 2)
            sym_center_x = -center_my
            sym_center_y = -center_mx
            distance2 = math.sqrt((x - sym_center_x) ** 2 + (y - sym_center_y) ** 2)
            if distance1 <= radius or distance2 <= radius:
                return TerrainType.MOUNTAIN

        # Strategic hills: precise single-point high ground
        strategic_points = [
            # Define only one half; the other half is generated via diagonal symmetry
            (1, 3),
            (-2, 4),
        ]

        for px, py in strategic_points:
            # Check original and diagonal mirror points (x, y) ↔ (-y, -x)
            if (x == px and y == py) or (x == -py and y == -px):
                return TerrainType.HILL

        # === Priority 5: Boundary handling ===
        # Map edges: sparse mountain border
        if abs(x) == half_width or abs(y) == half_height:
            # Only place border mountains at specific positions, not all
            if (x + y) % 3 == 0:
                return TerrainType.MOUNTAIN
            else:
                return TerrainType.FOREST

        # === Priority 6: Default terrain ===
        # All other areas are plains
        return TerrainType.PLAIN

    def _create_river_split_map_entities_offset(
        self, map_data: MapData, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Create river-split map entities - (0,0)-centered coordinate version."""
        # Calculate map radius
        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2
        
        # Spawn points: symmetric positions in lower-left and upper-right corners
        spawn_points = {
            Faction.SHU: (-half_width + 3, -half_height + 3),  # Lower-left front line
            Faction.WEI: (half_width - 3, half_height - 3),   # Upper-right front line
        }

        for (x, y), terrain_type in terrain_map.items():
            # Create tile entity
            tile_entity = self.world.create_entity()
            self.world.add_component(tile_entity, HexPosition(x, y))
            self.world.add_component(tile_entity, Terrain(terrain_type))
            self.world.add_component(tile_entity, Tile((x, y)))

            # Set territory control near spawn points and cities
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

            # Add to map data
            map_data.tiles[(x, y)] = tile_entity

    def _get_river_split_territory_control_centered(
        self,
        pos: Tuple[int, int],
        spawn_points: Dict[Faction, Tuple[int, int]],
        control_radius: int = 2,
    ) -> Faction:
        """Determine initial territory control for the river-split map - (0,0)-centered coordinate version."""
        x, y = pos
        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        # Control around spawn points
        for faction, (spawn_x, spawn_y) in spawn_points.items():
            distance = math.sqrt((x - spawn_x) ** 2 + (y - spawn_y) ** 2)
            if distance <= control_radius:
                return faction

        # City control (diagonal-symmetric)
        # Lower-left city (-half_width+2, -half_height+2) is in SHU's area
        if math.sqrt((x - (-half_width + 2)) ** 2 + (y - (-half_height + 2)) ** 2) <= 2:
            return Faction.SHU

        # Upper-right city (half_width-2, half_height-2) is in WEI's area
        if math.sqrt((x - (half_width - 2)) ** 2 + (y - (half_height - 2)) ** 2) <= 2:
            return Faction.WEI

        return None

    def _print_river_split_map_analysis_offset(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Print river-split map analysis report - (0,0)-centered coordinate version."""
        terrain_count = {}
        for terrain in terrain_map.values():
            terrain_count[terrain] = terrain_count.get(terrain, 0) + 1

        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        print("\n" + "=" * 70)
        print("🌊 River-Split Diagonal Competitive Map Analysis Report (Centered Coords)")
        print("=" * 70)
        print(f"📐 Map size: {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT}")
        print("🎯 Design: lower-left/upper-right diagonal symmetry with a river boundary")
        print("🌊 River system: along the anti-diagonal (x + y = 0)")
        print("🏰 Strategic highlights: central contest point (0,0) + diagonal cities")
        print(f"🔢 Fixed seed: {self.seed} (reproducible)")
        print(f"📍 Coordinate range: x∈[{-half_width}, {half_width}], y∈[{-half_height}, {half_height}]")

        print("\n🌍 Terrain distribution:")
        total_tiles = len(terrain_map)
        for terrain, count in sorted(
            terrain_count.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / total_tiles * 100
            print(f"  {terrain.value:10} {count:3d} tiles ({percentage:5.1f}%)")

        # Map visualization
        self._print_terrain_map_visual_centered(terrain_map)

        # Symmetry verification
        self._verify_diagonal_symmetry_centered(terrain_map)

        # Strategic point analysis
        self._analyze_river_split_strategic_points_centered(terrain_map)

        print("=" * 70)

    def _print_terrain_map_visual_centered(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Print the visual representation of the map - (0,0)-centered coordinate version."""
        print("\n🗺️ Terrain map visualization (y top→bottom, x left→right, center (0,0)):")
        print("   Legend: P=Plain F=Forest H=Hill M=Mountain W=Water U=City")

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

        # Print column headers (x coordinates)
        for x in range(-half_width, half_width + 1):
            print(f"{x:2}", end=" ")
        print()

        # Print each row (y from high to low, i.e., top to bottom)
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

        # Print bottom column headers again
        print("   ", end="")
        for x in range(-half_width, half_width + 1):
            print(f"{x:2}", end=" ")
        print()

    def _verify_diagonal_symmetry_centered(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Verify diagonal symmetry - (0,0)-centered coordinate version."""
        print("\n🔍 Diagonal symmetry verification (centered coords):")

        asymmetric_pairs = []
        symmetric_pairs = 0
        total_checks = 0

        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        # Check each position against its diagonal mirror
        for x in range(-half_width, half_width + 1):
            for y in range(-half_height, half_height + 1):
                if (x, y) in terrain_map:
                    # Diagonal mirror: (x, y) ↔ (-y, -x)
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
                                "terrain2": "missing",
                            }
                        )

        if len(asymmetric_pairs) == 0:
            print(
                f"  ✅ Perfect diagonal symmetry! {symmetric_pairs}/{total_checks} positions fully symmetric"
            )
        else:
            print(f"  ❌ Found {len(asymmetric_pairs)} asymmetric positions:")
            for i, pair in enumerate(asymmetric_pairs[:5]):
                print(
                    f"    {pair['pos1']}={pair['terrain1']} ≠ {pair['pos2']}={pair['terrain2']}"
                )
            if len(asymmetric_pairs) > 5:
                print(f"    ... {len(asymmetric_pairs) - 5} more asymmetric positions")

    def _analyze_river_split_strategic_points_centered(
        self, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        """Analyze strategic points on the river-split map - (0,0)-centered coordinate version."""
        print("\n🎯 Strategic point analysis:")

        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        # Count terrain clusters by type
        # Split by anti-diagonal: x + y < 0 is lower-left area, x + y > 0 is upper-right area
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

        print(f"  🔵 SHU control zone: {shu_area_count} tiles (lower-left, x+y<0)")
        print(f"  🔴 WEI control zone: {wei_area_count} tiles (upper-right, x+y>0)")
        print(f"  🌊 River system: {river_count} tiles (diagonal boundary, x+y=0)")
        print(f"  🏰 Cities: {city_count} (diagonal strongholds)")
        print(f"  🌱 Plains: {plain_count} tiles (main maneuver area)")
        print(f"  🏔️ Mountains: {mountain_count} tiles (strategic high ground)")
        print("  ⭐ Central contest point: (0, 0) - Plain")

        print("\n🚀 Faction deployment:")
        shu_spawn_x = -half_width + 3
        shu_spawn_y = -half_height + 3
        shu_city_x = -half_width + 2
        shu_city_y = -half_height + 2
        wei_spawn_x = half_width - 3
        wei_spawn_y = half_height - 3
        wei_city_x = half_width - 2
        wei_city_y = half_height - 2
        
        print(f"  SHU: spawn({shu_spawn_x}, {shu_spawn_y}), city({shu_city_x}, {shu_city_y}) - lower-left")
        print(f"  WEI: spawn({wei_spawn_x}, {wei_spawn_y}), city({wei_city_x}, {wei_city_y}) - upper-right")
        
        # Calculate spawn point distance
        spawn_distance = math.sqrt((wei_spawn_x - shu_spawn_x)**2 + (wei_spawn_y - shu_spawn_y)**2)
        print(f"  📏 Straight-line distance: {spawn_distance:.1f} tiles")
        print("  🌊 A diagonal river crossing is required to reach the opponent area")
        print("  🏰 Cities are placed in the rear, providing strategic depth")

    def _save_map_info_to_stats(self):
        """Save map information to GameStats."""
        import time
        from ..components import GameStats
        
        # Get GameStats component; skip if it doesn't exist yet
        game_stats = self.world.get_singleton_component(GameStats)
        if not game_stats:
            print("[MapSystem] GameStats component not found, skipping map info save")
            return
        
        # Determine coordinate system type
        coordinate_system = "centered" if self.symmetry_type == "river_split_offset" else "offset"
        
        # Get spawn positions
        spawn_positions = {}
        if self.competitive_mode:
            spawn_positions = self.get_competitive_spawn_positions()
        
        # Collect map info
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
        
        # Save to GameStats
        game_stats.map_info = map_info
        
        print("[MapSystem] ✅ Map info saved to GameStats:")
        print(f"  - Map size: {map_info['map_width']}x{map_info['map_height']}")
        print(f"  - Map type: {map_info['map_type']}")
        print(f"  - Competitive mode: {map_info['competitive_mode']}")
        print(f"  - Coordinate system: {map_info['coordinate_system']}")
        print(f"  - Spawn positions: {map_info['spawn_positions']}")

    def _generate_river_split_diagonal_map_offset_revised(self):
        """
        (Revised) Generate the river-split diagonal-symmetric competitive map - offset coordinate version.
        This version fixes fundamental issues with coordinate system handling and symmetry calculation,
        ensuring geometric correctness and true symmetry.
        """
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        print(
            f"[MapSystem] ⚙️ (Revised) Generating {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} River-Split Map (Offset Coords)"
        )
        print(f"[MapSystem] ✨ Design: True point-symmetry across a diagonal river.")

        # 1. Generate terrain map using the revised axial-coordinate-based logic
        terrain_map = self._generate_river_split_terrain_map_offset_revised()

        # 2. Create ECS entities (compatible with the original version)
        self._create_river_split_map_entities_offset(map_data, terrain_map)

        # 3. Add to world
        self.world.add_singleton_component(map_data)

        # 4. Print analysis report (use the centered-coordinate print function)
        self._print_river_split_map_analysis_offset(terrain_map)
        print("[MapSystem] ✅ Revised map generation complete.")

    def _generate_river_split_terrain_map_offset_revised(
        self,
    ) -> Dict[Tuple[int, int], TerrainType]:
        """
        (Revised) Generate the terrain map.
        Iterates over all offset coordinates and calls the axial-coordinate-based
        generation function to ensure geometric correctness.
        """
        terrain_map = {}
        # Use the same centered coordinate system as the original version
        half_width = GameConfig.MAP_WIDTH // 2
        half_height = GameConfig.MAP_HEIGHT // 2

        for col in range(-half_width, half_width + 1):
            for row in range(-half_height, half_height + 1):
                # Call the new axial-coordinate-based logic for each position
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
        (Revised V5) Final version: fixes the disappearing-city bug and adds river detail and central-axis mountains.
        """
        # Core: convert offset coordinates to axial coordinates for all geometric calculations
        q, r = HexMath.offset_to_axial(col, row)
        s = -q - r
        
        map_radius = GameConfig.MAP_WIDTH // 2

        # --- Map design elements (all coordinates in axial space) ---

        # 1. Cities placed at diagonal positions
        city_bl_offset = (-6, -6)
        city_bl_axial = HexMath.offset_to_axial(*city_bl_offset)
        city_tr_axial = (-city_bl_axial[0], -city_bl_axial[1])
        city_tr_offset = HexMath.axial_to_offset(*city_tr_axial)

        # 2. Points that widen the river
        river_thicken_points = [
            (3, -2), (4, -3), # Upper-right bank widening points
            (-1, 2) # Lower-left bank widening point
        ]

        # 3. Strategic mountains on the central axis (offset coordinates)
        central_mountain_offset_1 = (0, 3)
        central_mountain_axial_1 = HexMath.offset_to_axial(*central_mountain_offset_1)
        
        # 4. Riverside forests
        riverside_forests = [
            (1, 0), (2, -1),
            (5, -4),
            (-2, 3), 
        ]

        # 5. Natural mountain ridges
        mountain_ridge = [
            (4, 1), (5, 1), (5, 0), (6, 0), (6, -1), 
            (2, 4), (2, 5), (3, 4) 
        ]

        # 6. Land bridges across the river (axial coords)
        plain_bridges_axial = [
            (-1, 1), (1, -1), # from offset (-1,0), (1,-1)
            (3, -2),          # from offset (3,-1)
            (3, -3),          # from offset (3,-2)
            (4, -3),          # from offset (4,-1)
            (4, -4),          # from offset (4,-2)
        ]

        # 7. Final fine-tuned river blocks
        final_river_blocks_axial = [
            (-4, 4), # from offset (-4,2)
            (-3, 3), # from offset (-3,1)
        ]

        # --- Terrain generation priority ---

        # Priority 1: Cities (must be highest priority to prevent being overwritten)
        if (q, r) == city_bl_axial or (q, r) == city_tr_axial:
            return TerrainType.URBAN

        # Priority 2: Final fine-tuned river blocks
        for fq, fr in final_river_blocks_axial:
            if (q, r) == (fq, fr) or (q, r) == (-fq, -fr):
                return TerrainType.WATER

        # Priority 3: Land bridges across the river
        for bq, br in plain_bridges_axial:
            if (q, r) == (bq, br) or (q, r) == (-bq, -br):
                return TerrainType.PLAIN

        # Priority 4: Central-axis strategic mountains
        if (q, r) == central_mountain_axial_1 or (q, r) == (-central_mountain_axial_1[0], -central_mountain_axial_1[1]):
             return TerrainType.MOUNTAIN

        # Priority 5: Map border - surrounded by forest and mountains, kept sparse
        if max(abs(q), abs(r), abs(s)) >= map_radius:
            rand_val = (q * 13 + r * 31) % 100
            if rand_val < 60:  # 60% forest
                return TerrainType.FOREST
            elif rand_val < 75: # 15% mountain
                return TerrainType.MOUNTAIN
        
        # Priority 6: River system
        diagonal_sum = q + r
        if diagonal_sum == 0: # Main river channel
            return TerrainType.PLAIN if q == 0 and r == 0 else TerrainType.WATER
        # River channel widening
        for tq, tr in river_thicken_points:
            if (q, r) == (tq, tr) or (q, r) == (-tq, -tr):
                return TerrainType.WATER
        
        # Priority 7: Riverside forests
        for fq, fr in riverside_forests:
            if (q, r) == (fq, fr) or (q, r) == (-fq, -fr):
                return TerrainType.FOREST

        # Priority 8: Defense terrain around cities
        dist_to_bl_city = HexMath.hex_distance((col, row), city_bl_offset)
        dist_to_tr_city = HexMath.hex_distance((col, row), city_tr_offset)

        # Plains immediately adjacent to city
        if dist_to_bl_city == 1 or dist_to_tr_city == 1:
            return TerrainType.PLAIN
        # Forest surrounding the plains
        if dist_to_bl_city == 2 or dist_to_tr_city == 2:
            return TerrainType.FOREST

        # Priority 9: Strategic mountain ridges (using new ridge definition)
        for mq, mr in mountain_ridge:
            if (q, r) == (mq, mr) or (q, r) == (-mq, -mr):
                return TerrainType.MOUNTAIN

        # Priority 10: Strategic hills
        strategic_hills = [(2, 2), (1, 3), (3, 3)]
        for hq, hr in strategic_hills:
            if (q, r) == (hq, hr) or (q, r) == (-hq, -hr):
                return TerrainType.HILL

        # Priority 11: Default terrain
        return TerrainType.PLAIN

    def _save_map_info_to_stats(self):
        """Save map information to GameStats."""
        import time
        from ..components import GameStats
        
        # Get GameStats component; skip if it doesn't exist yet
        game_stats = self.world.get_singleton_component(GameStats)
        if not game_stats:
            print("[MapSystem] GameStats component not found, skipping map info save")
            return
        
        # Determine coordinate system type
        coordinate_system = "centered" if self.symmetry_type == "river_split_offset" else "offset"
        
        # Get spawn positions
        spawn_positions = {}
        if self.competitive_mode:
            spawn_positions = self.get_competitive_spawn_positions()
        
        # Collect map info
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
        
        # Save to GameStats
        game_stats.map_info = map_info
        
        print("[MapSystem] ✅ Map info saved to GameStats:")
        print(f"  - Map size: {map_info['map_width']}x{map_info['map_height']}")
        print(f"  - Map type: {map_info['map_type']}")
        print(f"  - Competitive mode: {map_info['competitive_mode']}")
        print(f"  - Coordinate system: {map_info['coordinate_system']}")
        print(f"  - Spawn positions: {map_info['spawn_positions']}")
