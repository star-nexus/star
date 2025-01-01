from typing import Dict, Tuple, Optional
import numpy as np

class MovementController:
    """
    Handles movement validation, terrain rules, and movement execution.
    Coordinates with PathPlanner for path following.
    """
    
    def __init__(self, environment_map: np.ndarray, unit_manager, path_planner, combat_system):
        """
        Initialize movement controller.
        
        Args:
            environment_map: 2D array of terrain
            unit_manager: Reference to UnitManager for unit queries
            path_planner: Reference to PathPlanner for path following
            combat_system: Reference to CombatSystem for combat handling
        """
        self.environment_map = environment_map
        self.unit_manager = unit_manager
        self.path_planner = path_planner
        self.combat_system = combat_system
        self.height, self.width = environment_map.shape

    def can_enter(self, unit_type: str, terrain: str) -> bool:
        """
        Check if a unit type can enter a specific terrain.
        
        Args:
            unit_type: Type of unit (e.g., 'R_ping')
            terrain: Terrain type
        """
        _, u_kind = unit_type.split("_", 1)
        if terrain in ["city", "plain", "forest", "bridge"]:
            return True
        if u_kind == "shan" and terrain in ["mountain"]:
            return True
        if u_kind == "shui" and terrain in ["river"]:
            return True
        return False

    def move(self, unit_id: int, direction: str) -> bool:
        """
        Move a unit in the specified direction.
        
        Args:
            unit_id: ID of unit to move
            direction: One of 'up', 'down', 'left', 'right'
        """
        # Get current unit info
        unit_info = self.unit_manager.get_unit_info(id=unit_id)
        if not unit_info:
            return False

        # Get current position and info
        _, y, x, utype, _ = unit_info

        # Calculate new position
        direction_deltas = {
            "up": (-1, 0),
            "down": (1, 0),
            "left": (0, -1),
            "right": (0, 1),
        }

        if direction not in direction_deltas:
            return False

        dy, dx = direction_deltas[direction]
        new_y, new_x = y + dy, x + dx

        # Check map boundaries
        if not (0 <= new_y < self.height and 0 <= new_x < self.width):
            return False

        # Check terrain
        terrain = self.environment_map[new_y][new_x]
        if not self.can_enter(utype, terrain):
            return False

        # Check for other units
        target_unit = self.unit_manager.get_unit_info(pos=(new_y, new_x))
        if target_unit:
            if self.combat_system.is_enemy(utype, target_unit[3]):
                self.combat_system.combat(unit_id, (new_y, new_x))
                return True
            return False

        return self.unit_manager.update_unit_position(unit_id, new_y, new_x)

    def step(self, unit_id: int) -> None:
        """
        Execute the next step in a unit's planned path.
        
        Args:
            unit_id: ID of unit to move
        """
        path = self.path_planner.get_path(unit_id)
        if not path:
            return

        unit_info = self.unit_manager.get_unit_info(id=unit_id)
        if not unit_info:
            return

        _, sy, sx, utype, _ = unit_info
        ny, nx = path[0]

        if (ny, nx) == (sy, sx):
            self.path_planner.unit_paths[unit_id].popleft()
            if not self.path_planner.unit_paths[unit_id]:
                return
            ny, nx = self.path_planner.unit_paths[unit_id][0]

        target_unit = self.unit_manager.get_unit_info(pos=(ny, nx))
        target_info = self.path_planner.destinations.get(unit_id, {"action": "move"})
        current_action = target_info["action"]

        if target_unit:
            if self.combat_system.is_enemy(utype, target_unit[3]):
                if current_action == "attack":
                    self.combat_system.execute_combat(unit_id, (ny, nx))
                else:
                    # move遇敌随机决定战或绕路
                    if random.random() < 0.5:
                        self.combat_system.execute_combat(unit_id, (ny, nx))
                    else:
                        self.path_planner.reroute(unit_id)
            else:
                self.path_planner.reroute(unit_id)
        else:
            # 空格子，检查可进入地形
            terrain = self.environment_map[ny, nx]
            if self.can_enter(utype, terrain):
                self.unit_manager.update_unit_position(unit_id, ny, nx)
                self.path_planner.unit_paths[unit_id].popleft()
            else:
                self.path_planner.reroute(unit_id) 