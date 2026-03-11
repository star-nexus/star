"""
Encounter Map Generator - Extends MapSystem to support Encounter-style maps.
"""

from typing import Dict, Tuple, List
from ..components import HexPosition, Terrain, MapData
from ..prefabs.config import TerrainType, GameConfig

class Tile:
    """Temporary tile class for compatibility with existing code."""

    def __init__(self, position):
        self.position = position


class EncounterMapMixin:
    """Encounter map generation mixin that adds Encounter-style map generation to MapSystem."""

    def _generate_encounter_map(self):
        """Generate an Encounter-style map with a three-lane battle layout."""
        # Check that world is initialized
        if not hasattr(self, 'world') or self.world is None:
            raise RuntimeError(
                "MapSystem.world is not initialized. "
                "Make sure initialize() sets a valid World reference."
            )
        
        map_data = MapData(
            width=GameConfig.MAP_WIDTH,
            height=GameConfig.MAP_HEIGHT,
            tiles={}
        )

        # Define map boundaries based on the hexagonal coordinate system,
        # using the same calculation approach as other map systems.
        map_radius = GameConfig.MAP_WIDTH // 2  # Map radius, consistent with GameConfig

        print("[Encounter Map] 🏟️ Generating Encounter-style map...")

        # Fill base terrain first using the same rectangular traversal as other map systems.
        for q in range(GameConfig.MAP_WIDTH):
            for r in range(GameConfig.MAP_HEIGHT):
                # Convert to center-origin coordinates
                center_q = q - map_radius
                center_r = r - map_radius
                
                # Default to jungle terrain
                # terrain_type = TerrainType.JUNGLE # no texture
                terrain_type = TerrainType.FOREST # with texture
                
                # Create tile entity
                tile_entity = self.world.create_entity()
                self.world.add_component(tile_entity, HexPosition(center_q, center_r))
                self.world.add_component(tile_entity, Terrain(terrain_type))
                
                # Add Tile component for compatibility with existing code
                self.world.add_component(tile_entity, Tile((center_q, center_r)))
                
                # Add to map data
                map_data.tiles[(center_q, center_r)] = tile_entity

        # Build the key MOBA map structures
        self._create_encounter_lanes(map_data)        # Create three lanes
        self._create_encounter_river(map_data)        # Create central river
        self._create_encounter_bases(map_data)        # Create team bases
        self._create_encounter_towers(map_data)       # Create towers
        self._create_encounter_jungle_areas(map_data) # Finalize jungle areas

        # Register as a singleton component
        self.world.add_singleton_component(map_data)
        
        print("[Encounter Map] ✅ Encounter map generated.")
        self._print_encounter_map_summary()

    def _create_encounter_lanes(self, map_data: MapData):
        """Create the three MOBA lane paths."""
        print("[Encounter Map] 🛣️ Creating three lanes...")
        
        # Define lane waypoints for a 15x15 map (radius 7)
        # Top Lane: diagonal from upper-left to lower-right
        top_lane = [
            (-6, 2), (-5, 1), (-4, 0), (-3, -1), (-2, -2), (-1, -3), (0, -4),
            (1, -5), (2, -6)
        ]
        
        # Mid Lane: horizontal from left to right
        mid_lane = [
            (-6, 0), (-5, 0), (-4, 0), (-3, 0), (-2, 0), (-1, 0), (0, 0),
            (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0)
        ]
        
        # Bot Lane: diagonal from lower-left to upper-right
        bot_lane = [
            (-2, 6), (-1, 5), (0, 4), (1, 3), (2, 2), (3, 1), (4, 0),
            (5, -1), (6, -2)
        ]
        
        # Apply lane terrain
        for lane_points in [top_lane, mid_lane, bot_lane]:
            for (q, r) in lane_points:
                if (q, r) in map_data.tiles:
                    entity = map_data.tiles[(q, r)]
                    # Update terrain type to lane
                    terrain_comp = self.world.get_component(entity, Terrain)
                    if terrain_comp:
                        # terrain_comp.terrain_type = TerrainType.LANE # no texture
                        terrain_comp.terrain_type = TerrainType.PLAIN # use plain texture

    def _create_encounter_river(self, map_data: MapData):
        """Create the central river that divides the two team sides."""
        print("[Encounter Map] 🌊 Creating central river...")
        
        # The river runs across the map center, forming a dividing line.
        river_points = []
        
        # Slightly diagonal river through the center, separating teams - fits a 15x15 map
        for q in range(-6, 7):  # Fits map_radius = 7
            for r_offset in [-1, 0, 1]:  # River width: 3 tiles
                r = -q // 2 + r_offset  # Slightly tilted river
                # Ensure within 15x15 map boundaries
                if -7 <= q <= 7 and -7 <= r <= 7:
                    river_points.append((q, r))
        
        # Add a special area at the river center (similar to a Roshan/Baron pit)
        boss_area = [(0, -1), (0, 0), (0, 1), (-1, 0), (1, -1)]
        
        for (q, r) in river_points:
            if (q, r) in map_data.tiles:
                entity = map_data.tiles[(q, r)]
                terrain_comp = self.world.get_component(entity, Terrain)
                if terrain_comp:
                    if (q, r) in boss_area:
                        terrain_comp.terrain_type = TerrainType.WATER  # Boss area is deep water
                    else:
                        # terrain_comp.terrain_type = TerrainType.RIVER # no texture
                        terrain_comp.terrain_type = TerrainType.WATER # use water texture

    def _create_encounter_bases(self, map_data: MapData):
        """Create team bases and main strongholds."""
        print("[Encounter Map] 🏰 Creating team bases...")
        
        # Team 1 base (left side, SHU) - fits 15x15 map
        team1_base_area = [(-7, 1), (-7, 0), (-6, 1), (-6, 0), (-5, 1)]
        team1_ancient = (-7, -1)  # Main stronghold position, kept within map boundaries
        
        # Team 2 base (right side, WEI) - fits 15x15 map
        team2_base_area = [(7, -1), (7, 0), (6, -1), (6, 0), (5, -1)]
        team2_ancient = (7, 1)  # Main stronghold position, kept within map boundaries
        
        # Create base area tiles
        for (q, r) in team1_base_area + team2_base_area:
            if (q, r) in map_data.tiles:
                entity = map_data.tiles[(q, r)]
                terrain_comp = self.world.get_component(entity, Terrain)
                if terrain_comp:
                    # terrain_comp.terrain_type = TerrainType.BASE # no texture
                    terrain_comp.terrain_type = TerrainType.URBAN # use urban texture
        
        # Create strongholds, ensuring they are within map boundaries
        for ancient_pos in [team1_ancient, team2_ancient]:
            q, r = ancient_pos
            # Ensure stronghold is within 15x15 map boundaries
            if -7 <= q <= 7 and -7 <= r <= 7:
                if (q, r) in map_data.tiles:
                    # Update existing tile to stronghold
                    entity = map_data.tiles[(q, r)]
                    terrain_comp = self.world.get_component(entity, Terrain)
                    if terrain_comp:
                        terrain_comp.terrain_type = TerrainType.CITY  # Use CITY instead of ANCIENT
                else:
                    # Tile does not exist - create a new stronghold tile (should not happen in practice)
                    tile_entity = self.world.create_entity()
                    self.world.add_component(tile_entity, HexPosition(q, r))
                    self.world.add_component(tile_entity, Terrain(TerrainType.CITY))
                    self.world.add_component(tile_entity, Tile((q, r)))
                    map_data.tiles[(q, r)] = tile_entity

    def _create_encounter_towers(self, map_data: MapData):
        """Create the tower layout along each lane."""
        print("[Encounter Map] 🗼 Creating defensive towers...")
        
        # Tower positions along each lane (in advance order) - fits 15x15 map
        # Top lane towers: from upper-left base to lower-right base
        top_towers = [(-5, 1), (-3, -1), (-1, -3), (1, -5)]
        
        # Mid lane towers: from left base to right base
        mid_towers = [(-4, 0), (-2, 0), (0, 0), (2, 0), (4, 0)]
        
        # Bot lane towers: from lower-left to upper-right
        bot_towers = [(-1, 5), (1, 3), (3, 1), (5, -1)]
        
        all_towers = top_towers + mid_towers + bot_towers
        
        for (q, r) in all_towers:
            if (q, r) in map_data.tiles:
                entity = map_data.tiles[(q, r)]
                terrain_comp = self.world.get_component(entity, Terrain)
                if terrain_comp:
                    # terrain_comp.terrain_type = TerrainType.TOWER  # Use TOWER type (if texture available)
                    terrain_comp.terrain_type = TerrainType.URBAN  # Temporarily using URBAN texture

    def _create_encounter_jungle_areas(self, map_data: MapData):
        """Finalize the jungle layout by adding special terrain features."""
        print("[Encounter Map] 🌲 Refining jungle layout...")
        
        # Add special terrain in the jungle for tactical variety - fits 15x15 map
        # Forest areas (provide cover and ambush opportunities)
        forest_areas = [
            (-4, 2), (-3, 3), (-2, 4),  # Upper jungle forest
            (2, -2), (3, -3), (4, -4),  # Lower jungle forest
            (-3, -1), (-2, -2),         # Left jungle forest
            (2, 2), (3, 1),             # Right jungle forest
        ]
        
        # Hill areas (provide high-ground advantage)
        hill_areas = [
            (-5, 3), (-4, 4),           # Upper hills
            (4, -3), (5, -4),           # Lower hills
        ]
        
        # Apply forest terrain
        for (q, r) in forest_areas:
            if (q, r) in map_data.tiles:
                entity = map_data.tiles[(q, r)]
                terrain_comp = self.world.get_component(entity, Terrain)
                if terrain_comp and terrain_comp.terrain_type == TerrainType.JUNGLE:
                    terrain_comp.terrain_type = TerrainType.FOREST
        
        # Apply hill terrain
        for (q, r) in hill_areas:
            if (q, r) in map_data.tiles:
                entity = map_data.tiles[(q, r)]
                terrain_comp = self.world.get_component(entity, Terrain)
                if terrain_comp and terrain_comp.terrain_type == TerrainType.JUNGLE:
                    terrain_comp.terrain_type = TerrainType.HILL

    def _print_encounter_map_summary(self):
        """Print a summary of the generated Encounter map."""
        print("\n" + "=" * 50)
        print("🏟️ Encounter Map Generation Summary")
        print("=" * 50)
        print("📍 Layout:")
        print("  🛣️ Three lanes: top / mid / bot")
        print("  🌊 Central river: strategic divider and boss area")
        print("  🌲 Four jungle zones: resources and tactical positions")
        print("  🗼 Defensive towers: 12 towers protecting lane progression")
        print("  🏰 Team bases: symmetric placement on left and right sides")
        print("  ⭐ Main base: primary victory objective")
        print("\n🎯 Strategic highlights:")
        print("  • Three lanes enable diverse macro and rotation options")
        print("  • River control drives boss contests")
        print("  • Jungle zones provide economy and flank routes")
        print("  • Towers shape the push/tempo of engagements")
        print("  • Symmetric design supports fair competitive play")
        print("  • Terrain variety increases tactical depth")
        print("=" * 50)
