import pygame
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.renders import RenderManager
from game.components import Position, Renderable, Collider, Obstacle


class RenderSystem(System):
    """渲染系统"""

    def __init__(self, render_manager: RenderManager):
        super().__init__([Position, Renderable], priority=5)
        self.render_manager = render_manager

    def update(self, world: World, delta_time: float) -> None:
        """更新游戏逻辑"""

        # 渲染所有可渲染实体
        entities = world.get_entities_with_components(Position, Renderable)
        for entity in entities:
            pos = world.get_component(entity, Position)
            renderable = world.get_component(entity, Renderable)

            # 如果实体有碰撞组件且处于发光状态，先渲染发光效果
            if world.has_component(entity, Collider):
                collider = world.get_component(entity, Collider)
                if collider.is_glowing:
                    glow_radius = renderable.radius * 1.5
                    glow_surface = pygame.Surface(
                        (glow_radius * 2, glow_radius * 2), pygame.SRCALPHA
                    )
                    # 根据实体类型选择不同的发光颜色
                    glow_color = (
                        (154, 205, 50, 64)
                        if world.has_component(entity, Obstacle)
                        else (255, 255, 0, 100)
                    )
                    pygame.draw.circle(
                        glow_surface,
                        glow_color,
                        (glow_radius, glow_radius),
                        glow_radius,
                    )
                    self.render_manager.draw(
                        glow_surface,
                        pygame.Rect(
                            pos.x - glow_radius,
                            pos.y - glow_radius,
                            glow_radius * 2,
                            glow_radius * 2,
                        ),
                    )

            # 创建表面并绘制实体
            surface = pygame.Surface(
                (renderable.radius * 2, renderable.radius * 2), pygame.SRCALPHA
            )
            pygame.draw.circle(
                surface,
                renderable.color,
                (renderable.radius, renderable.radius),
                renderable.radius,
            )

            # 渲染实体
            self.render_manager.draw(
                surface,
                pygame.Rect(
                    pos.x - renderable.radius,
                    pos.y - renderable.radius,
                    renderable.radius * 2,
                    renderable.radius * 2,
                ),
            )
