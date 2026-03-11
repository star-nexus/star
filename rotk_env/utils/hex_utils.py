"""
Hexagonal map utilities.
Provides hex coordinate system and map-related helper functions.
"""

import math
from typing import List, Tuple, Set
from ..prefabs.config import GameConfig, HexOrientation


class HexMath:
    """Hexagonal math utilities."""

    @staticmethod
    def cube_to_axial(q: int, r: int, s: int) -> Tuple[int, int]:
        """Convert cube coordinates to axial coordinates."""
        return q, r

    @staticmethod
    def axial_to_cube(q: int, r: int) -> Tuple[int, int, int]:
        """Convert axial coordinates to cube coordinates."""
        return q, r, -q - r

    @staticmethod
    def offset_to_axial(col: int, row: int) -> Tuple[int, int]:
        """Convert offset coordinates to axial (odd-column offset layout)."""
        q = col
        r = row - (col - (col & 1)) // 2
        return q, r

    @staticmethod
    def axial_to_offset(q: int, r: int) -> Tuple[int, int]:
        """Convert axial coordinates to offset (odd-column offset layout)."""
        col = q
        row = r + (q - (q & 1)) // 2
        return col, row

    @staticmethod
    def hex_distance(pos1: Tuple[int, int], pos2: Tuple[int, int]) -> int:
        """Distance between two hex cells (supports offset coordinates)."""
        # Convert offset to axial first if input is offset
        q1, r1 = HexMath.offset_to_axial(*pos1)
        q2, r2 = HexMath.offset_to_axial(*pos2)
        s1 = -q1 - r1
        s2 = -q2 - r2
        return (abs(q1 - q2) + abs(r1 - r2) + abs(s1 - s2)) // 2

    @staticmethod
    def hex_neighbors(col: int, row: int) -> List[Tuple[int, int]]:
        """Return the 6 neighbors of a hex (offset coords; definition validated via pixel coords)."""
        # Neighbor pattern differs for even vs odd columns
        if col % 2 == 0:  # even column
            directions = [
                (1, -1),   # top-right
                (0, -1),   # top
                (-1, -1),  # top-left
                (-1, 0),   # left
                (0, 1),    # bottom
                (1, 0),    # right
            ]
        else:  # odd column
            directions = [
                (1, 0),    # right
                (0, -1),   # top
                (-1, 0),   # left
                (-1, 1),   # bottom-left
                (0, 1),    # bottom
                (1, 1),    # bottom-right
            ]
        return [(col + dc, row + dr) for dc, dr in directions]

    @staticmethod
    def hex_ring(
        center_col: int, center_row: int, radius: int
    ) -> List[Tuple[int, int]]:
        """Return the hex ring at the given radius (offset coordinates)."""
        if radius == 0:
            return [(center_col, center_row)]

        # Convert to axial for computation
        center_q, center_r = HexMath.offset_to_axial(center_col, center_row)
        results = []
        q, r = center_q + radius, center_r - radius

        # Six axial directions
        directions = [(-1, 1), (-1, 0), (0, -1), (1, -1), (1, 0), (0, 1)]

        for i, (dq, dr) in enumerate(directions):
            for j in range(radius):
                # Convert back to offset
                col, row = HexMath.axial_to_offset(q, r)
                results.append((col, row))
                q += dq
                r += dr

        return results

    @staticmethod
    def hex_spiral(
        center_col: int, center_row: int, radius: int
    ) -> List[Tuple[int, int]]:
        """Return all hexes within the given radius in spiral order (offset coordinates)."""
        results = [(center_col, center_row)]
        for r in range(1, radius + 1):
            results.extend(HexMath.hex_ring(center_col, center_row, r))
        return results

    @staticmethod
    def hex_in_range(
        center_col: int, center_row: int, range_val: int
    ) -> Set[Tuple[int, int]]:
        """Return all hexes within the given range (offset coordinates)."""
        results = set()
        center_q, center_r = HexMath.offset_to_axial(center_col, center_row)

        for q in range(center_q - range_val, center_q + range_val + 1):
            for r in range(
                max(center_r - range_val, -q - range_val),
                min(center_r + range_val, -q + range_val) + 1,
            ):
                if (
                    HexMath.hex_distance(
                        (center_col, center_row), HexMath.axial_to_offset(q, r)
                    )
                    <= range_val
                ):
                    col, row = HexMath.axial_to_offset(q, r)
                    results.add((col, row))
        return results

    @staticmethod
    def line_of_sight(
        start: Tuple[int, int], end: Tuple[int, int]
    ) -> List[Tuple[int, int]]:
        """Line-of-sight path between two hexes (offset coordinates)."""
        # Convert to axial for computation
        q1, r1 = HexMath.offset_to_axial(*start)
        q2, r2 = HexMath.offset_to_axial(*end)

        distance = HexMath.hex_distance(start, end)
        if distance == 0:
            return [start]

        results = []
        for i in range(distance + 1):
            t = i / distance
            q = int(round(q1 + (q2 - q1) * t))
            r = int(round(r1 + (r2 - r1) * t))
            # Convert back to offset
            col, row = HexMath.axial_to_offset(q, r)
            results.append((col, row))

        return results


class HexConverter:
    """Hex-to-pixel and pixel-to-hex conversion utilities."""

    def __init__(
        self, hex_size: int = GameConfig.HEX_SIZE, orientation: HexOrientation = None
    ):
        self.size = hex_size
        self.orientation = orientation or GameConfig.HEX_ORIENTATION
        self.width = math.sqrt(3) * hex_size
        self.height = 2 * hex_size

    def hex_to_pixel(self, col: int, row: int) -> Tuple[float, float]:
        """Convert hex (offset) to screen pixel coordinates; increasing row goes up on screen."""
        sqrt3 = 1.7320508075688772  # math.sqrt(3)
        if self.orientation == HexOrientation.POINTY_TOP:
            # Pointy-top layout, odd-column offset
            x = self.size * sqrt3 * (col + 0.5 * (row & 1))
            y = -self.size * 3 / 2 * row  # row up -> y decreases (screen up)
        else:  # FLAT_TOP
            # Flat-top layout, odd-column offset
            x = self.size * 3 / 2 * col
            y = (
                -self.size * sqrt3 * (row + 0.5 * (col & 1))
            )  # row up -> y decreases (screen up)

        return x, y

    def pixel_to_hex(self, x: float, y: float) -> Tuple[int, int]:
        """Convert screen pixel to hex (returns offset coordinates)."""
        sqrt3 = 1.7320508075688772  # math.sqrt(3)

        if self.orientation == HexOrientation.POINTY_TOP:
            # Inverse of pointy-top; note Y flip
            q = (sqrt3 / 3.0 * x - 1.0 / 3.0 * (-y)) / self.size
            r = (2.0 / 3.0 * (-y)) / self.size
        else:  # FLAT_TOP
            # Inverse of flat-top; note Y flip
            q = (2.0 / 3.0 * x) / self.size
            r = (-1.0 / 3.0 * x + sqrt3 / 3.0 * (-y)) / self.size

        # Round to axial first
        rq, rr = self.hex_round(q, r)
        # Then convert to offset
        return HexMath.axial_to_offset(rq, rr)

    @staticmethod
    def hex_round(q: float, r: float) -> Tuple[int, int]:
        """Round to nearest hex (axial) - high-precision version."""
        s = -q - r

        # Round each axis
        rq = round(q)
        rr = round(r)
        rs = round(s)

        # Rounding errors
        q_diff = abs(rq - q)
        r_diff = abs(rr - r)
        s_diff = abs(rs - s)

        # Enforce cube constraint q + r + s = 0
        if q_diff > r_diff and q_diff > s_diff:
            rq = -rr - rs
        elif r_diff > s_diff:
            rr = -rq - rs
        else:
            rs = -rq - rr

        return rq, rr

    def get_hex_corners(self, col: int, row: int) -> List[Tuple[float, float]]:
        """Return the 6 corner coordinates of a hex (offset coords, Cartesian)."""
        center_x, center_y = self.hex_to_pixel(col, row)
        corners = []

        if self.orientation == HexOrientation.POINTY_TOP:
            # Pointy-top: start at -30°, step 60°
            start_angle = -30
        else:  # FLAT_TOP
            # Flat-top: start at 0°, step 60°
            start_angle = 0

        for i in range(6):
            angle_deg = 60 * i + start_angle
            angle_rad = math.radians(angle_deg)
            x = center_x + self.size * math.cos(angle_rad)
            # Y flip is already applied in hex_to_pixel; keep consistent
            y = center_y + self.size * math.sin(angle_rad)
            corners.append((x, y))

        return corners


class PathFinding:
    """A* pathfinding (offset coordinates)."""

    @staticmethod
    def find_path(
        start: Tuple[int, int],
        goal: Tuple[int, int],
        obstacles: Set[Tuple[int, int]],
        max_distance: int = None,
    ) -> List[Tuple[int, int]]:
        """Find path with A* (offset coordinates)."""
        if start == goal:
            return [start]

        if goal in obstacles:
            return []

        # A* implementation
        from heapq import heappush, heappop

        frontier = [(0, start)]
        came_from = {start: None}
        cost_so_far = {start: 0}

        while frontier:
            current_cost, current = heappop(frontier)

            if current == goal:
                # Reconstruct path
                path = []
                while current is not None:
                    path.append(current)
                    current = came_from[current]
                path.reverse()
                return path

            for neighbor in HexMath.hex_neighbors(*current):
                if neighbor in obstacles:
                    continue

                new_cost = cost_so_far[current] + 1

                # Honor max distance if set
                if max_distance and new_cost > max_distance:
                    continue

                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    priority = new_cost + HexMath.hex_distance(neighbor, goal)
                    heappush(frontier, (priority, neighbor))
                    came_from[neighbor] = current

        return []  # No path found

    @staticmethod
    def get_movement_range(
        start: Tuple[int, int], movement_points: int, obstacles: Set[Tuple[int, int]]
    ) -> Set[Tuple[int, int]]:
        """Return all reachable hexes within movement range (offset coordinates)."""
        reachable = set()
        visited = set()
        queue = [(start, 0)]  # (position, cost)

        while queue:
            current_pos, current_cost = queue.pop(0)

            if current_pos in visited:
                continue

            visited.add(current_pos)

            if current_cost <= movement_points:
                reachable.add(current_pos)

            if current_cost < movement_points:
                for neighbor in HexMath.hex_neighbors(*current_pos):
                    if neighbor not in obstacles and neighbor not in visited:
                        queue.append((neighbor, current_cost + 1))

        return reachable
