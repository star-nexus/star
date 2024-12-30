import numpy as np
from typing import List, Tuple, Optional

class VisibilitySystem:
    """
    Handles vision and fog of war calculations.
    Determines which tiles are visible to each faction.
    """
    
    def __init__(self, map_shape: Tuple[int, int]):
        """
        Initialize the visibility system.
        
        Args:
            map_shape: Tuple of (height, width) of the game map
        """
        self.height, self.width = map_shape
        
    def compute_visibility(self, 
                         unit_positions: List[Tuple[Tuple[int, int], str]], 
                         faction: str,
                         vision_range: int = 1) -> np.ndarray:
        """
        Calculate visible tiles for a faction based on unit positions.
        
        Args:
            unit_positions: List of ((y, x), unit_type) tuples
            faction: Faction identifier ('R' or 'W')
            vision_range: How far units can see (default: 1)
            
        Returns:
            Boolean numpy array where True indicates visible tiles
        """
        visible = np.full((self.height, self.width), False, dtype=bool)
        
        for (y, x), unit_type in unit_positions:
            if unit_type.startswith(faction + "_"):
                # Calculate vision range for this unit
                for dy in range(-vision_range, vision_range + 1):
                    for dx in range(-vision_range, vision_range + 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < self.height and 0 <= nx < self.width:
                            visible[ny][nx] = True
                            
        return visible

    def get_visible_units(self,
                         unit_positions: List[Tuple[Tuple[int, int], str]],
                         faction: str,
                         vision_range: int = 1) -> List[Tuple[Tuple[int, int], str]]:
        """
        Get list of units that are visible to a faction.
        
        Args:
            unit_positions: List of ((y, x), unit_type) tuples
            faction: Faction identifier ('R' or 'W')
            vision_range: How far units can see (default: 1)
            
        Returns:
            List of visible units with their positions
        """
        visible_map = self.compute_visibility(unit_positions, faction, vision_range)
        visible_units = []
        
        for pos, unit_type in unit_positions:
            y, x = pos
            if visible_map[y, x]:
                visible_units.append((pos, unit_type))
                
        return visible_units

    def is_position_visible(self,
                          position: Tuple[int, int],
                          unit_positions: List[Tuple[Tuple[int, int], str]],
                          faction: str,
                          vision_range: int = 1) -> bool:
        """
        Check if a specific position is visible to a faction.
        
        Args:
            position: (y, x) position to check
            unit_positions: List of ((y, x), unit_type) tuples
            faction: Faction identifier ('R' or 'W')
            vision_range: How far units can see (default: 1)
            
        Returns:
            Boolean indicating if position is visible
        """
        y, x = position
        if not (0 <= y < self.height and 0 <= x < self.width):
            return False
            
        visible_map = self.compute_visibility(unit_positions, faction, vision_range)
        return visible_map[y, x] 