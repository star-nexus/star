import pygame
from rotk.logics.components import TerrainType, TERRAIN_COLORS


class TerrainRenderer:
    """地形渲染工具，为不同地形类型提供可视化表示"""

    @staticmethod
    def render_terrain(surface, terrain_type, rect):
        """渲染地形到指定表面

        Args:
            surface: 要渲染到的表面
            terrain_type: 地形类型
            rect: 要渲染的矩形区域
        """
        # 先用地形基本颜色填充整个区域
        color = TERRAIN_COLORS.get(terrain_type, (100, 100, 100))
        pygame.draw.rect(surface, color, rect)

        # 根据地形类型添加特殊标识
        if terrain_type == TerrainType.FOREST:
            # 绘制树木
            TerrainRenderer._draw_tree(surface, rect)
        elif terrain_type == TerrainType.MOUNTAIN:
            # 绘制山峰
            TerrainRenderer._draw_mountain(surface, rect)
        elif terrain_type == TerrainType.HILL:
            # 绘制丘陵
            TerrainRenderer._draw_hill(surface, rect)
        elif terrain_type == TerrainType.RIVER:
            # 绘制河流
            TerrainRenderer._draw_river(surface, rect)
        elif terrain_type == TerrainType.LAKE:
            # 绘制湖泊
            TerrainRenderer._draw_lake(surface, rect)
        elif terrain_type == TerrainType.URBAN:
            # 绘制城市
            TerrainRenderer._draw_city(surface, rect)
        elif terrain_type == TerrainType.DESERT:
            # 绘制沙漠
            TerrainRenderer._draw_desert(surface, rect)
        elif terrain_type == TerrainType.SWAMP:
            # 绘制沼泽
            TerrainRenderer._draw_swamp(surface, rect)

    @staticmethod
    def _draw_tree(surface, rect):
        """绘制树木标志"""
        # 树干
        trunk_width = max(2, int(rect.width / 8))
        trunk_height = int(rect.height / 2)
        trunk_left = rect.centerx - trunk_width // 2
        trunk_top = rect.centery
        trunk_rect = pygame.Rect(trunk_left, trunk_top, trunk_width, trunk_height)
        pygame.draw.rect(surface, (101, 67, 33), trunk_rect)  # 棕色树干

        # 树冠
        crown_radius = int(rect.width / 3)
        pygame.draw.circle(
            surface,
            (0, 100, 0),
            (rect.centerx, rect.centery - crown_radius // 2),
            crown_radius,
        )  # 深绿色树冠

    @staticmethod
    def _draw_mountain(surface, rect):
        """绘制山峰标志"""
        # 画一个三角形表示山
        points = [
            (rect.left + rect.width // 4, rect.bottom - rect.height // 4),  # 左下
            (rect.centerx, rect.top + rect.height // 4),  # 顶部
            (rect.right - rect.width // 4, rect.bottom - rect.height // 4),  # 右下
        ]
        pygame.draw.polygon(surface, (90, 77, 65), points)  # 灰褐色山

        # 雪顶
        snow_height = rect.height // 4
        snow_points = [
            (rect.centerx - rect.width // 8, rect.top + rect.height // 3),  # 左
            (rect.centerx, rect.top + rect.height // 4),  # 顶部
            (rect.centerx + rect.width // 8, rect.top + rect.height // 3),  # 右
        ]
        pygame.draw.polygon(surface, (240, 240, 240), snow_points)  # 白色雪顶

    @staticmethod
    def _draw_hill(surface, rect):
        """绘制丘陵标志"""
        # 画一个弧形表示丘陵
        pygame.draw.arc(
            surface,
            (110, 139, 61),
            [rect.left, rect.centery - rect.height // 4, rect.width, rect.height],
            3.14,
            0,
            3,
        )

    @staticmethod
    def _draw_river(surface, rect):
        """绘制河流标志"""
        # 绘制波浪线
        wave_points = []
        segments = 4
        amplitude = rect.height / 10
        for i in range(segments + 1):
            x = rect.left + (rect.width * i / segments)
            y = rect.centery + amplitude * (-1 if i % 2 == 0 else 1)
            wave_points.append((x, y))

        if len(wave_points) >= 2:
            pygame.draw.lines(
                surface, (173, 216, 230), False, wave_points, 2
            )  # 淡蓝色波浪线

    @staticmethod
    def _draw_lake(surface, rect):
        """绘制湖泊标志"""
        # 绘制同心圆表示湖泊
        pygame.draw.circle(
            surface, (173, 216, 230), rect.center, rect.width // 3
        )  # 外圈
        pygame.draw.circle(
            surface, (135, 206, 235), rect.center, rect.width // 5
        )  # 内圈

    @staticmethod
    def _draw_city(surface, rect):
        """绘制城市标志"""
        # 绘制简单的建筑轮廓
        building_width = rect.width // 3
        building_height = rect.height // 2

        # 主楼
        main_building = pygame.Rect(
            rect.centerx - building_width // 2,
            rect.centery - building_height // 2,
            building_width,
            building_height,
        )
        pygame.draw.rect(surface, (150, 150, 150), main_building)

        # 屋顶
        roof_points = [
            (main_building.left - 2, main_building.top),
            (main_building.centerx, main_building.top - rect.height // 6),
            (main_building.right + 2, main_building.top),
        ]
        pygame.draw.polygon(surface, (200, 0, 0), roof_points)  # 红色屋顶

        # 窗户
        window_size = max(2, building_width // 3)
        window = pygame.Rect(
            main_building.centerx - window_size // 2,
            main_building.centery - window_size // 2,
            window_size,
            window_size,
        )
        pygame.draw.rect(surface, (255, 255, 200), window)  # 黄色窗户

    @staticmethod
    def _draw_desert(surface, rect):
        """绘制沙漠标志"""
        # 绘制沙丘
        pygame.draw.arc(
            surface,
            (227, 196, 141),
            [rect.left, rect.centery, rect.width, rect.height // 2],
            3.14,
            0,
            3,
        )

        # 绘制小仙人掌
        cactus_width = max(2, rect.width // 8)
        cactus_height = int(rect.height / 2)
        cactus_left = rect.centerx - cactus_width // 2
        cactus_top = rect.centery - cactus_height // 2

        # 主干
        pygame.draw.rect(
            surface,
            (0, 100, 0),
            pygame.Rect(cactus_left, cactus_top, cactus_width, cactus_height),
        )

        # 侧枝
        arm_width = cactus_height // 3
        arm_height = cactus_width
        pygame.draw.rect(
            surface,
            (0, 100, 0),
            pygame.Rect(
                cactus_left - arm_height // 2,
                cactus_top + cactus_height // 4,
                arm_height,
                arm_width,
            ),
        )

    @staticmethod
    def _draw_swamp(surface, rect):
        """绘制沼泽标志"""
        # 绘制沼泽水面
        pygame.draw.ellipse(surface, (80, 125, 80), rect)

        # 绘制几个小圆点表示气泡
        bubble_radius = max(1, rect.width // 12)
        positions = [
            (rect.centerx - rect.width // 4, rect.centery),
            (rect.centerx + rect.width // 4, rect.centery - rect.height // 4),
            (rect.centerx, rect.centery + rect.height // 4),
        ]

        for pos in positions:
            pygame.draw.circle(surface, (150, 180, 150), pos, bubble_radius)
