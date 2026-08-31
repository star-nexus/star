"""Load a map file into MapData. One-shot: initialize() writes tiles, then idle."""

from typing import Dict, Tuple

from framework import System, World

from ..components import HexPosition, MapData, Terrain, Tile, formation_center
from ..prefabs.config import Faction, TerrainType


class MapSystem(System):
    """Loader: scenario name → rotk_env/maps/*.json → tile entities."""

    def __init__(
        self,
        competitive_mode: bool = True,
        symmetry_type: str = "river_split",
        seed: int = 42,
        scenario: str = "default",
    ):
        super().__init__(priority=100)
        self.competitive_mode = competitive_mode
        self.symmetry_type = symmetry_type
        self.seed = seed
        self.scenario = scenario
        self.map_id = ""

    def initialize(self, world: World) -> None:
        self.world = world
        from ..components import RngService

        rng_service = self.world.get_singleton_component(RngService)
        if rng_service is not None:
            self.seed = rng_service.get("map").randint(0, 2**31 - 1)
        self.load_map()
        self._save_map_info_to_stats()

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        pass

    def load_map(self):
        from ..maps.map_file import load_map as read_map_file, resolve_map_path

        path = resolve_map_path(self.scenario)
        doc = read_map_file(path)
        self.map_id = doc.id
        self.symmetry_type = doc.id

        map_data = MapData(
            width=doc.width,
            height=doc.height,
            tiles={},
            map_id=doc.id,
        )
        self._create_tiles(map_data, doc.terrain)
        map_data.formations = {}
        map_data.formation_unit_types = {}
        for name, cells in doc.formations.items():
            try:
                faction = Faction(name)
            except ValueError as exc:
                known = ", ".join(item.value for item in Faction)
                raise ValueError(
                    f"unknown faction {name!r} in map; expected one of: {known}"
                ) from exc
            map_data.formations[faction] = list(cells)
            map_data.formation_unit_types[faction] = list(
                doc.formation_types.get(name) or []
            )
        map_data.home_bases = {
            faction: formation_center(cells)
            for faction, cells in map_data.formations.items()
        }
        self.world.add_singleton_component(map_data)
        print(
            f"[MapSystem] Loaded {path.name} "
            f"{doc.width}x{doc.height} tiles={len(doc.terrain)} "
            f"formations={sorted(doc.formations)}"
        )

    def _create_tiles(
        self, map_data: MapData, terrain_map: Dict[Tuple[int, int], TerrainType]
    ):
        for (col, row), terrain_type in terrain_map.items():
            tile_entity = self.world.create_entity()
            self.world.add_component(tile_entity, HexPosition(col, row))
            self.world.add_component(tile_entity, Terrain(terrain_type))
            self.world.add_component(tile_entity, Tile((col, row)))
            map_data.tiles[(col, row)] = tile_entity

    def _save_map_info_to_stats(self):
        """Save map information to GameStats. Spawn cells come from home_bases."""
        import time

        from ..components import GameStats, RngService

        game_stats = self.world.get_singleton_component(GameStats)
        if not game_stats:
            print("[MapSystem] GameStats component not found, skipping map info save")
            return

        map_data = self.world.get_singleton_component(MapData)
        spawn_positions = {}
        if map_data and map_data.home_bases:
            spawn_positions = {
                (faction.value if hasattr(faction, "value") else str(faction)): pos
                for faction, pos in map_data.home_bases.items()
            }

        rng_service = self.world.get_singleton_component(RngService)
        root_seed = rng_service.seed if rng_service else None
        root_seed_source = rng_service.source if rng_service else "default"

        width = map_data.width if map_data else 0
        height = map_data.height if map_data else 0
        map_info = {
            "map_width": width,
            "map_height": height,
            "map_id": self.map_id,
            "map_type": self.symmetry_type,
            "competitive_mode": self.competitive_mode,
            "map_seed": self.seed,
            "root_seed": root_seed,
            "root_seed_source": root_seed_source,
            "spawn_positions": spawn_positions,
            "coordinate_system": "centered",
            "symmetry_type": self.symmetry_type,
            "generation_timestamp": time.time(),
        }
        game_stats.map_info = map_info
        print(
            f"[MapSystem] Map info saved: {width}x{height} "
            f"id={self.map_id} spawns={spawn_positions}"
        )
