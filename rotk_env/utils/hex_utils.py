"""
Hexagonal map utilities.
Provides hex coordinate system and map-related helper functions.
"""

import math
from collections import deque
from heapq import heappop, heappush
from typing import Callable, List, Optional, Set, Tuple

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
    def anti_diagonal_mirror(col: int, row: int) -> Tuple[int, int]:
        """River-split map symmetry: (x, y) ↔ (-y, -x) across x + y = 0."""
        return (-row, -col)

    @staticmethod
    def formation_cells(
        center_col: int, center_row: int, count: int
    ) -> List[Tuple[int, int]]:
        """Place `count` units by BFS from center using offset hex neighbors.

        Spiral-in-axial-space is not a valid walk on this odd-column offset
        grid (rings can repeat the center). BFS matches movement adjacency.
        """
        if count <= 0:
            return []
        start = (center_col, center_row)
        cells: List[Tuple[int, int]] = []
        seen = {start}
        queue: deque[Tuple[int, int]] = deque([start])
        while queue and len(cells) < count:
            cur = queue.popleft()
            cells.append(cur)
            for nb in HexMath.hex_neighbors(*cur):
                if nb not in seen:
                    seen.add(nb)
                    queue.append(nb)
        return cells[:count]

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
        """Return the translation-invariant hex disk around an offset cell.

        Iterate *relative* axial deltas and translate them by the center so the
        disk is independent of the center's absolute coordinates.
        """
        radius = max(0, int(range_val))
        center_q, center_r = HexMath.offset_to_axial(center_col, center_row)
        results: Set[Tuple[int, int]] = set()

        for dq in range(-radius, radius + 1):
            dr_min = max(-radius, -dq - radius)
            dr_max = min(radius, -dq + radius)
            for dr in range(dr_min, dr_max + 1):
                results.add(
                    HexMath.axial_to_offset(center_q + dq, center_r + dr)
                )
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
        self._corner_offsets_key: Optional[Tuple[object, object]] = None
        self._corner_offsets: Tuple[Tuple[float, float], ...] = ()

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

    def rotate_180(self, col: int, row: int) -> Tuple[int, int]:
        """Point-symmetric partner through the origin, in pixel space.

        Odd-column offset stagger means neither (-col, -row) nor (-row, -col)
        matches what the player sees. Convert to pixels, rotate, snap back.
        """
        x, y = self.hex_to_pixel(col, row)
        return self.pixel_to_hex(-x, -y)

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
        key = (self.size, self.orientation)
        if self._corner_offsets_key != key:
            self._corner_offsets = self._build_corner_offsets()
            self._corner_offsets_key = key

        return [
            (center_x + offset_x, center_y + offset_y)
            for offset_x, offset_y in self._corner_offsets
        ]

    def _build_corner_offsets(self) -> Tuple[Tuple[float, float], ...]:
        start_angle = -30 if self.orientation == HexOrientation.POINTY_TOP else 0
        offsets = []
        for i in range(6):
            angle_deg = 60 * i + start_angle
            angle_rad = math.radians(angle_deg)
            offsets.append(
                (
                    self.size * math.cos(angle_rad),
                    self.size * math.sin(angle_rad),
                )
            )
        return tuple(offsets)

class PathFinding:
    """A* pathfinding (offset coordinates)."""

    @staticmethod
    def find_path(
        start: Tuple[int, int],
        goal: Tuple[int, int],
        obstacles: Set[Tuple[int, int]],
        max_distance: int = None,
        walkable: Optional[Set[Tuple[int, int]]] = None,
        step_cost: Optional[Callable[[Tuple[int, int]], int]] = None,
    ) -> List[Tuple[int, int]]:
        """Find a path with A* (offset coordinates).

        ``walkable`` is the board: neighbors not in it are off-map.
        ``step_cost(hex)`` is the cost of *entering* that hex (default 1).
        ``max_distance`` caps cumulative enter-cost, not hex count.
        """
        if start == goal:
            return [start]

        if goal in obstacles:
            return []
        if walkable is not None and goal not in walkable:
            return []

        def cost_of(pos: Tuple[int, int]) -> int:
            return 1 if step_cost is None else int(step_cost(pos))

        frontier = [(0, start)]
        came_from = {start: None}
        cost_so_far = {start: 0}

        while frontier:
            _, current = heappop(frontier)

            if current == goal:
                path = []
                while current is not None:
                    path.append(current)
                    current = came_from[current]
                path.reverse()
                return path

            for neighbor in HexMath.hex_neighbors(*current):
                if neighbor in obstacles:
                    continue
                if walkable is not None and neighbor not in walkable:
                    continue

                new_cost = cost_so_far[current] + cost_of(neighbor)
                if max_distance is not None and new_cost > max_distance:
                    continue

                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    priority = new_cost + HexMath.hex_distance(neighbor, goal)
                    heappush(frontier, (priority, neighbor))
                    came_from[neighbor] = current

        return []

    @staticmethod
    def get_movement_range(
        start: Tuple[int, int],
        movement_points: int,
        obstacles: Set[Tuple[int, int]],
        walkable: Optional[Set[Tuple[int, int]]] = None,
        step_cost: Optional[Callable[[Tuple[int, int]], int]] = None,
    ) -> Set[Tuple[int, int]]:
        """Return all reachable hexes within movement range (offset coordinates)."""

        def cost_of(pos: Tuple[int, int]) -> int:
            return 1 if step_cost is None else int(step_cost(pos))

        reachable = {start}
        cost_so_far = {start: 0}
        frontier = [(0, start)]

        while frontier:
            current_cost, current = heappop(frontier)
            if current_cost > cost_so_far.get(current, current_cost):
                continue
            for neighbor in HexMath.hex_neighbors(*current):
                if neighbor in obstacles:
                    continue
                if walkable is not None and neighbor not in walkable:
                    continue
                new_cost = current_cost + cost_of(neighbor)
                if new_cost > movement_points:
                    continue
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    reachable.add(neighbor)
                    heappush(frontier, (new_cost, neighbor))

        return reachable
