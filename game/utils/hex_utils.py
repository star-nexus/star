import math
from typing import Tuple, List
from enum import Enum
import numpy as np


class HexOrientation(Enum):
    """六边形方向枚举"""

    POINTY_TOP = "pointy_top"  # 尖顶朝上
    FLAT_TOP = "flat_top"  # 平顶朝上


class HexCoordinate:
    """六边形坐标系统

    使用轴坐标系 (q, r, s) 其中 q + r + s = 0
    q: 左右方向 (x轴)
    r: 上下方向 (y轴)
    s: 对角线方向 (z轴)
    """

    def __init__(self, q: int, r: int, s: int = None):
        self.q = q
        self.r = r
        self.s = s if s is not None else -q - r

        # 验证坐标约束
        if self.q + self.r + self.s != 0:
            raise ValueError(
                f"Invalid hex coordinate: {q}, {r}, {self.s} (sum must be 0)"
            )

    def __eq__(self, other):
        return self.q == other.q and self.r == other.r and self.s == other.s

    def __hash__(self):
        return hash((self.q, self.r, self.s))

    def __repr__(self):
        return f"Hex({self.q}, {self.r}, {self.s})"

    def to_tuple(self) -> Tuple[int, int, int]:
        return (self.q, self.r, self.s)


def hex_to_pixel(
    hex_coord: HexCoordinate,
    hex_size: float,
    orientation: HexOrientation = HexOrientation.FLAT_TOP,
) -> Tuple[float, float]:
    """将六边形坐标转换为像素坐标"""
    if orientation == HexOrientation.FLAT_TOP:
        # 平顶六边形布局
        x = hex_size * (3.0 / 2.0 * hex_coord.q)
        y = hex_size * (
            (math.sqrt(3.0) / 2.0 * hex_coord.q) + (math.sqrt(3.0) * hex_coord.r)
        )
    else:  # POINTY_TOP
        # 尖顶六边形布局
        x = hex_size * (
            math.sqrt(3.0) * hex_coord.q + math.sqrt(3.0) / 2.0 * hex_coord.r
        )
        y = hex_size * (3.0 / 2.0 * hex_coord.r)

    return x, y


def pixel_to_hex(
    x: float,
    y: float,
    hex_size: float,
    orientation: HexOrientation = HexOrientation.FLAT_TOP,
) -> HexCoordinate:
    """将像素坐标转换为六边形坐标"""
    if orientation == HexOrientation.FLAT_TOP:
        # 平顶六边形布局的逆变换
        q = (2.0 / 3.0 * x) / hex_size
        r = (-1.0 / 3.0 * x + math.sqrt(3.0) / 3.0 * y) / hex_size
    else:  # POINTY_TOP
        # 尖顶六边形布局的逆变换
        q = (math.sqrt(3.0) / 3.0 * x - 1.0 / 3.0 * y) / hex_size
        r = (2.0 / 3.0 * y) / hex_size

    return hex_round(q, r)


def hex_round(q: float, r: float) -> HexCoordinate:
    """将浮点六边形坐标舍入到最近的整数坐标"""
    s = -q - r
    rq = round(q)
    rr = round(r)
    rs = round(s)

    q_diff = abs(rq - q)
    r_diff = abs(rr - r)
    s_diff = abs(rs - s)

    if q_diff > r_diff and q_diff > s_diff:
        rq = -rr - rs
    elif r_diff > s_diff:
        rr = -rq - rs
    else:
        rs = -rq - rr

    return HexCoordinate(rq, rr, rs)


def hex_distance(a: HexCoordinate, b: HexCoordinate) -> int:
    """计算两个六边形之间的距离"""
    return (abs(a.q - b.q) + abs(a.r - b.r) + abs(a.s - b.s)) // 2


def hex_neighbors(hex_coord: HexCoordinate) -> List[HexCoordinate]:
    """获取六边形的6个邻居"""
    directions = [
        HexCoordinate(1, 0, -1),  # 右
        HexCoordinate(1, -1, 0),  # 右上
        HexCoordinate(0, -1, 1),  # 左上
        HexCoordinate(-1, 0, 1),  # 左
        HexCoordinate(-1, 1, 0),  # 左下
        HexCoordinate(0, 1, -1),  # 右下
    ]

    neighbors = []
    for direction in directions:
        neighbor = HexCoordinate(
            hex_coord.q + direction.q,
            hex_coord.r + direction.r,
            hex_coord.s + direction.s,
        )
        neighbors.append(neighbor)

    return neighbors


def hex_ring(center: HexCoordinate, radius: int) -> List[HexCoordinate]:
    """获取指定半径的六边形环"""
    if radius == 0:
        return [center]

    results = []
    # 从一个方向开始
    current = HexCoordinate(center.q + radius, center.r, center.s - radius)

    # 沿着6个方向移动
    directions = [
        HexCoordinate(0, -1, 1),  # 左上
        HexCoordinate(-1, 0, 1),  # 左
        HexCoordinate(-1, 1, 0),  # 左下
        HexCoordinate(0, 1, -1),  # 右下
        HexCoordinate(1, 0, -1),  # 右
        HexCoordinate(1, -1, 0),  # 右上
    ]

    for direction in directions:
        for _ in range(radius):
            results.append(current)
            current = HexCoordinate(
                current.q + direction.q,
                current.r + direction.r,
                current.s + direction.s,
            )

    return results


def hex_spiral(center: HexCoordinate, radius: int) -> List[HexCoordinate]:
    """获取以中心为起点，指定半径内的所有六边形（螺旋顺序）"""
    results = [center]
    for r in range(1, radius + 1):
        results.extend(hex_ring(center, r))
    return results


def create_hex_map_coordinates(map_radius: int) -> List[HexCoordinate]:
    """创建六边形地图的所有坐标"""
    coordinates = []
    for q in range(-map_radius, map_radius + 1):
        r1 = max(-map_radius, -q - map_radius)
        r2 = min(map_radius, -q + map_radius)
        for r in range(r1, r2 + 1):
            coordinates.append(HexCoordinate(q, r))
    return coordinates


def hex_to_offset(hex_coord: HexCoordinate) -> Tuple[int, int]:
    """将六边形坐标转换为偏移坐标（用于数组索引）- 奇数行偏移"""
    col = hex_coord.q + (hex_coord.r - (hex_coord.r & 1)) // 2
    row = hex_coord.r
    return col, row


def offset_to_hex(col: int, row: int) -> HexCoordinate:
    """将偏移坐标转换为六边形坐标 - 奇数行偏移"""
    q = col - (row - (row & 1)) // 2
    r = row
    return HexCoordinate(q, r)
