import pygame
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.renders import RenderManager
from game.components import MapTile, Terrain, TerrainType


class MapRenderSystem(System):
    """地图渲染系统，负责渲染地图"""

    def __init__(self, render_manager: RenderManager):
        super().__init__([MapTile, Terrain], priority=4)  # 在角色渲染之前渲染地图
        self.render_manager = render_manager
        self.tile_size = 32  # 每个格子的大小
        self.terrain_colors = {
            TerrainType.PLAIN: (124, 252, 0),  # 浅绿色
            TerrainType.MOUNTAIN: (139, 137, 137),  # 灰色
            TerrainType.RIVER: (30, 144, 255),  # 蓝色
            TerrainType.FOREST: (34, 139, 34),  # 深绿色
            TerrainType.LAKE: (0, 191, 255),  # 浅蓝色
        }

    def update(self, world: World, delta_time: float) -> None:
        """渲染地图格子"""
        # 获取所有地图格子实体
        tile_entities = world.get_entities_with_components(MapTile, Terrain)

        for entity in tile_entities:
            tile = world.get_component(entity, MapTile)
            terrain = world.get_component(entity, Terrain)

            # 计算格子在屏幕上的位置
            x = tile.x * self.tile_size
            y = tile.y * self.tile_size

            # 获取对应地形的颜色
            color = self.terrain_colors.get(terrain.type, (200, 200, 200))

            # 创建表面并绘制格子
            surface = pygame.Surface((self.tile_size, self.tile_size))
            surface.fill(color)

            # 如果地形不可通过，添加标记
            if not terrain.passable:
                pygame.draw.line(
                    surface, (255, 0, 0), (0, 0), (self.tile_size, self.tile_size), 2
                )
                pygame.draw.line(
                    surface, (255, 0, 0), (0, self.tile_size), (self.tile_size, 0), 2
                )

            # 如果地形不可建造，添加标记
            if not terrain.buildable:
                pygame.draw.circle(
                    surface,
                    (255, 0, 0),
                    (self.tile_size // 2, self.tile_size // 2),
                    self.tile_size // 4,
                    1,
                )

            # 渲染格子
            self.render_manager.draw(
                surface, pygame.Rect(x, y, self.tile_size, self.tile_size)
            )
