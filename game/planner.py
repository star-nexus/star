from collections import deque
import numpy as np


class PathPlanner:
    def __init__(self, environment_map, unit_controller):
        """
        Initialize the path planner

        Args:
            environment_map: 2D array of terrain
            unit_controller: Reference to UnitController for unit position queries
        """
        self.environment_map = environment_map
        self.unit_controller = unit_controller
        self.unit_paths = {}  # {unit_id: deque(path)}
        self.destinations = {}  # {unit_id: {"pos": (y,x), "action": action}}

    def get_path(self, unit_id):
        """Get current path for a unit"""
        return list(self.unit_paths.get(unit_id, []))

    def plan_path(self, unit_id, unit_type, start_pos, target_pos, action="move"):
        """Plan a path for a unit from start to target"""
        path = self.find_path(unit_type, start_pos, target_pos, action)
        if not path:
            # Try finding closest reachable point if direct path not found
            path = self.find_closest_reachable_point(unit_type, start_pos, target_pos)

        self.unit_paths[unit_id] = deque(path) if path else deque()
        self.destinations[unit_id] = {"pos": target_pos, "action": action}
        return bool(path)

    def find_path(self, unit_type, start, goal, action="move"):
        """Find path using BFS"""
        sy, sx = start
        gy, gx = goal
        h, w = self.environment_map.shape
        visited = np.full((h, w), False, dtype=bool)
        parent = dict()

        queue = deque([(sy, sx)])
        visited[sy, sx] = True

        while queue:
            y, x = queue.popleft()
            if (y, x) == (gy, gx):
                return self.reconstruct_path(parent, start, goal)

            for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                ny, nx = y + dy, x + dx
                if (
                    0 <= ny < h
                    and 0 <= nx < w
                    and not visited[ny, nx]
                    and self.unit_controller.can_enter(
                        unit_type, self.environment_map[ny, nx]
                    )
                    and self.is_tile_free(ny, nx, action)
                ):
                    visited[ny, nx] = True
                    parent[(ny, nx)] = (y, x)
                    queue.append((ny, nx))
        return None

    def find_closest_reachable_point(self, unit_type, start, goal):
        """Find closest reachable point to goal"""
        sy, sx = start
        gy, gx = goal
        h, w = self.environment_map.shape
        visited = np.full((h, w), False, dtype=bool)
        parent = dict()

        queue = deque([(sy, sx)])
        visited[sy, sx] = True
        reachable_points = []

        while queue:
            y, x = queue.popleft()
            reachable_points.append((y, x))
            for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                ny, nx = y + dy, x + dx
                if (
                    0 <= ny < h
                    and 0 <= nx < w
                    and not visited[ny, nx]
                    and self.unit_controller.can_enter(
                        unit_type, self.environment_map[ny, nx]
                    )
                    and self.is_tile_free(ny, nx)
                ):
                    visited[ny, nx] = True
                    parent[(ny, nx)] = (y, x)
                    queue.append((ny, nx))

        best_point = min(
            reachable_points,
            key=lambda p: abs(p[0] - gy) + abs(p[1] - gx),
            default=None,
        )

        if best_point and best_point != start:
            return self.reconstruct_path(parent, start, best_point)
        return None

    def reconstruct_path(self, parent, start, goal):
        """Reconstruct path from parent dictionary"""
        path = []
        cur = goal
        while cur != start:
            path.append(cur)
            cur = parent[cur]
        path.append(start)
        path.reverse()
        return path

    def is_tile_free(self, y, x, action="move"):
        """Check if a tile is free to move into"""
        unit_info = self.unit_controller.get_unit_info(pos=(y, x))
        if not unit_info:
            return True

        current_unit = self.unit_controller.selected_unit_info
        if not current_unit:
            return False

        # Allow moving to own position
        if (y, x) == current_unit[:2]:
            return True

        # For attack actions, allow moving to enemy positions
        if action == "attack":
            return self.unit_controller.combat_system.is_enemy(
                current_unit[2], unit_info[3]
            )

        return False

    def reroute(self, unit_id):
        """Recalculate path for a unit"""
        if unit_id not in self.destinations:
            self.unit_paths.pop(unit_id, None)
            return

        unit_info = self.unit_controller.get_unit_info(id=unit_id)
        if not unit_info:
            return

        _, y, x, unit_type, _ = unit_info
        target = self.destinations[unit_id]
        self.plan_path(unit_id, unit_type, (y, x), target["pos"], target["action"])
