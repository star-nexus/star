"""
六边形地图工具模块
提供六边形坐标系统和地图相关的工具函数
"""

import math
from typing import List, Tuple, Set
from ..prefabs.config import GameConfig, HexOrientation


class HexMath:
    """六边形数学工具类"""

    @staticmethod
    def cube_to_axial(q: int, r: int, s: int) -> Tuple[int, int]:
        """立方坐标转轴坐标"""
        return q, r

    @staticmethod
    def axial_to_cube(q: int, r: int) -> Tuple[int, int, int]:
        """轴坐标转立方坐标"""
        return q, r, -q - r

    @staticmethod
    def hex_distance(pos1: Tuple[int, int], pos2: Tuple[int, int]) -> int:
        """计算两个六边形之间的距离"""
        q1, r1 = pos1
        q2, r2 = pos2
        s1 = -q1 - r1
        s2 = -q2 - r2
        return (abs(q1 - q2) + abs(r1 - r2) + abs(s1 - s2)) // 2

    @staticmethod
    def hex_neighbors(q: int, r: int) -> List[Tuple[int, int]]:
        """获取六边形的6个邻居"""
        # 六边形的6个方向向量
        directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
        return [(q + dq, r + dr) for dq, dr in directions]

    @staticmethod
    def hex_ring(center_q: int, center_r: int, radius: int) -> List[Tuple[int, int]]:
        """获取指定半径的六边形环"""
        if radius == 0:
            return [(center_q, center_r)]

        results = []
        q, r = center_q + radius, center_r - radius

        # 六个方向
        directions = [(-1, 1), (-1, 0), (0, -1), (1, -1), (1, 0), (0, 1)]

        for i, (dq, dr) in enumerate(directions):
            for j in range(radius):
                results.append((q, r))
                q += dq
                r += dr

        return results

    @staticmethod
    def hex_spiral(center_q: int, center_r: int, radius: int) -> List[Tuple[int, int]]:
        """获取指定半径内的所有六边形（螺旋顺序）"""
        results = [(center_q, center_r)]
        for r in range(1, radius + 1):
            results.extend(HexMath.hex_ring(center_q, center_r, r))
        return results

    @staticmethod
    def hex_in_range(
        center_q: int, center_r: int, range_val: int
    ) -> Set[Tuple[int, int]]:
        """获取指定范围内的所有六边形"""
        results = set()
        for q in range(center_q - range_val, center_q + range_val + 1):
            for r in range(
                max(center_r - range_val, -q - range_val),
                min(center_r + range_val, -q + range_val) + 1,
            ):
                if HexMath.hex_distance((center_q, center_r), (q, r)) <= range_val:
                    results.add((q, r))
        return results

    @staticmethod
    def line_of_sight(
        start: Tuple[int, int], end: Tuple[int, int]
    ) -> List[Tuple[int, int]]:
        """计算两点间的视线路径"""
        q1, r1 = start
        q2, r2 = end

        distance = HexMath.hex_distance(start, end)
        if distance == 0:
            return [start]

        results = []
        for i in range(distance + 1):
            t = i / distance
            q = int(round(q1 + (q2 - q1) * t))
            r = int(round(r1 + (r2 - r1) * t))
            results.append((q, r))

        return results


class HexConverter:
    """六边形坐标转换工具类"""

    def __init__(
        self, hex_size: int = GameConfig.HEX_SIZE, orientation: HexOrientation = None
    ):
        self.size = hex_size
        self.orientation = orientation or GameConfig.HEX_ORIENTATION
        self.width = math.sqrt(3) * hex_size
        self.height = 2 * hex_size

    def hex_to_pixel(self, q: int, r: int) -> Tuple[float, float]:
        """六边形坐标转屏幕像素坐标"""
        sqrt3 = 1.7320508075688772  # math.sqrt(3)

        if self.orientation == HexOrientation.POINTY_TOP:
            # 尖顶向上布局
            x = self.size * (sqrt3 * q + sqrt3 / 2.0 * r)
            y = self.size * (3.0 / 2.0 * r)
        else:  # FLAT_TOP
            # 平顶向上布局
            x = self.size * (3.0 / 2.0 * q)
            y = self.size * (sqrt3 / 2.0 * q + sqrt3 * r)

        return x, y

    def pixel_to_hex(self, x: float, y: float) -> Tuple[int, int]:
        """屏幕像素坐标转六边形坐标"""
        sqrt3 = 1.7320508075688772  # math.sqrt(3)

        if self.orientation == HexOrientation.POINTY_TOP:
            # 尖顶向上布局的逆变换
            q = (sqrt3 / 3.0 * x - 1.0 / 3.0 * y) / self.size
            r = (2.0 / 3.0 * y) / self.size
        else:  # FLAT_TOP
            # 平顶向上布局的逆变换
            q = (2.0 / 3.0 * x) / self.size
            r = (-1.0 / 3.0 * x + sqrt3 / 3.0 * y) / self.size

        return self.hex_round(q, r)

    @staticmethod
    def hex_round(q: float, r: float) -> Tuple[int, int]:
        """六边形坐标四舍五入 - 高精度版本"""
        s = -q - r

        # 精确舍入
        rq = round(q)
        rr = round(r)
        rs = round(s)

        # 计算误差
        q_diff = abs(rq - q)
        r_diff = abs(rr - r)
        s_diff = abs(rs - s)

        # 保证立方坐标约束 q + r + s = 0
        if q_diff > r_diff and q_diff > s_diff:
            rq = -rr - rs
        elif r_diff > s_diff:
            rr = -rq - rs
        else:
            rs = -rq - rr

        return rq, rr

    def get_hex_corners(self, q: int, r: int) -> List[Tuple[float, float]]:
        """获取六边形的6个顶点坐标"""
        center_x, center_y = self.hex_to_pixel(q, r)
        corners = []

        if self.orientation == HexOrientation.POINTY_TOP:
            # 尖顶向上布局：从-30度开始，每次旋转60度
            start_angle = -30
        else:  # FLAT_TOP
            # 平顶向上布局：从0度开始，每次旋转60度
            start_angle = 0

        for i in range(6):
            angle_deg = 60 * i + start_angle
            angle_rad = math.radians(angle_deg)
            x = center_x + self.size * math.cos(angle_rad)
            y = center_y + self.size * math.sin(angle_rad)
            corners.append((x, y))

        return corners


class PathFinding:
    """A*寻路算法实现"""

    @staticmethod
    def find_path(
        start: Tuple[int, int],
        goal: Tuple[int, int],
        obstacles: Set[Tuple[int, int]],
        max_distance: int = None,
    ) -> List[Tuple[int, int]]:
        """使用A*算法寻找路径"""
        if start == goal:
            return [start]

        if goal in obstacles:
            return []

        # A*算法实现
        from heapq import heappush, heappop

        frontier = [(0, start)]
        came_from = {start: None}
        cost_so_far = {start: 0}

        while frontier:
            current_cost, current = heappop(frontier)

            if current == goal:
                # 重建路径
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

                # 如果有最大距离限制
                if max_distance and new_cost > max_distance:
                    continue

                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    priority = new_cost + HexMath.hex_distance(neighbor, goal)
                    heappush(frontier, (priority, neighbor))
                    came_from[neighbor] = current

        return []  # 找不到路径

    @staticmethod
    def get_movement_range(
        start: Tuple[int, int], movement_points: int, obstacles: Set[Tuple[int, int]]
    ) -> Set[Tuple[int, int]]:
        """获取移动范围内的所有可达位置"""
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
