from typing import Dict, Tuple, Optional, List, Any

class Unit:
    """
    An agent class that can be controlled by a large language model.
    Manages unit data, state, and basic operations.
    Responsible for maintaining the game's unit information and state.
    """
    
    def __init__(self, unit_map):
        """
        Initialize the unit manager.
        
        Args:
            unit_map: 2D numpy array containing unit positions and types
        """
        # Unit/Agent properties. 
        # ============ To do ==============
        self.name = "Guan Yu"; # Zhang Fei, Zhao Yun, Lv Bu, Liu Bei
        self.model = "gpt-4o";
        self.instructions = "You are a Troop than can pass water in this game.";
        self.skills = [] # tools used by LLM
        self.shared_memory = ""
        self.knowledge = ""
        # ============ To do ==============

        # Unit/Agent states
        self.unit_map = unit_map
        self.unit_all_info: Dict[int, Tuple[int, int, str, str]] = {}  # id: (y, x, type, state)
        self._selected_unit_id: int = -1

        # Initialize
        self._initialize_units()
        
    def _initialize_units(self) -> None:
        """Scan unit_map and initialize unit data"""
        h, w = self.unit_map.shape
        index = 0
        for i in range(h):
            for j in range(w):
                if self.unit_map[i][j] is not None:
                    self.unit_all_info[index] = (i, j, self.unit_map[i][j], "idle")
                    index += 1

    @property
    def selected_unit_id(self) -> Optional[int]:
        """Get currently selected unit ID"""
        return None if self._selected_unit_id < 0 else self._selected_unit_id

    @selected_unit_id.setter
    def selected_unit_id(self, value: int) -> None:
        """Set currently selected unit ID"""
        self._selected_unit_id = value

    @property
    def selected_unit_info(self) -> Optional[Tuple[int, int, str, str]]:
        """Get information about currently selected unit"""
        if self._selected_unit_id < 0:
            return None
        return self.unit_all_info.get(self._selected_unit_id)

    @property
    def selected_unit_pos(self) -> Optional[Tuple[int, int]]:
        """Get position of currently selected unit"""
        if self._selected_unit_id < 0:
            return None
        info = self.unit_all_info.get(self._selected_unit_id)
        return info[:2] if info else None

    def get_all_units_info(self) -> List[Tuple[int, int, int, str, str]]:
        """
        Get information about all units.
        
        Returns:
            List of tuples (unit_id, y, x, unit_type, state)
        """
        return [
            (uid, y, x, utype, state)
            for uid, (y, x, utype, state) in self.unit_all_info.items()
        ]

    def get_unit_info(self, id: Optional[int] = None, 
                     pos: Optional[Tuple[int, int]] = None
                     ) -> Optional[Tuple[int, int, int, str, str]]:
        """
        Get unit information by either ID or position.
        
        Args:
            id: Unit ID to look up
            pos: Position tuple (y, x) to look up
            
        Returns:
            Tuple of (id, y, x, unit_type, state) if found, None otherwise
        """
        if id is not None and id in self.unit_all_info:
            return (id, *self.unit_all_info[id])

        if pos is not None:
            try:
                y, x = pos
                for uid, (uy, ux, utype, state) in self.unit_all_info.items():
                    if (uy, ux) == (y, x):
                        return (uid, uy, ux, utype, state)
            except (TypeError, ValueError):
                return None

        return None

    def get_faction_unit_counts(self) -> Dict[str, Dict[str, int]]:
        """
        Get unit counts by faction and type.
        
        Returns:
            Dictionary of format:
            {
                'R': {'ping': count, 'shui': count, 'shan': count},
                'W': {'ping': count, 'shui': count, 'shan': count}
            }
        """
        counts = {
            "R": {"ping": 0, "shui": 0, "shan": 0},
            "W": {"ping": 0, "shui": 0, "shan": 0},
        }
        for _, (_, _, ut, _) in self.unit_all_info.items():
            faction, utype = ut.split("_", 1)
            if faction in counts and utype in counts[faction]:
                counts[faction][utype] += 1
        return counts

    def update_unit_position(self, uid: int, new_y: int, new_x: int, 
                           new_utype: Optional[str] = None) -> bool:
        """
        Update a unit's position and optionally its type.
        
        Args:
            uid: Unit ID to update
            new_y: New Y coordinate
            new_x: New X coordinate
            new_utype: Optional new unit type
            
        Returns:
            bool: True if update successful, False otherwise
        """
        if uid not in self.unit_all_info:
            return False

        old_y, old_x, old_utype, state = self.unit_all_info[uid]

        h, w = self.unit_map.shape
        if not (0 <= new_y < h and 0 <= new_x < w):
            return False

        self.unit_map[old_y, old_x] = None
        self.unit_map[new_y, new_x] = new_utype if new_utype else old_utype

        self.unit_all_info[uid] = (
            new_y,
            new_x,
            new_utype if new_utype else old_utype,
            state,
        )
        return True

    def remove_unit(self, uid: int) -> None:
        """
        Remove a unit from the game.
        
        Args:
            uid: ID of unit to remove
        """
        if uid in self.unit_all_info:
            y, x, _, _ = self.unit_all_info[uid]
            self.unit_map[y, x] = None
            self.unit_all_info.pop(uid)
            if self._selected_unit_id == uid:
                self._selected_unit_id = -1

    def update_unit_state(self, uid: int, new_state: str) -> bool:
        """
        Update a unit's state.
        
        Args:
            uid: Unit ID to update
            new_state: New state string
            
        Returns:
            bool: True if update successful, False otherwise
        """
        if uid not in self.unit_all_info:
            return False
            
        y, x, utype, _ = self.unit_all_info[uid]
        self.unit_all_info[uid] = (y, x, utype, new_state)
        return True 