"""
完整游戏示例 - 三国策略小游戏

这个示例演示了：
1. 完整的游戏循环
2. 多系统协作
3. 游戏引擎的使用
4. 场景管理
5. 用户交互
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from dataclasses import dataclass
from framework.engine.engine import Engine
from framework.engine.scenes import Scene
from framework.ecs.component import Component
from framework.ecs.system import System
from framework.engine.events import EventType
import pygame
import random
import math


# 游戏组件
@dataclass
class PositionComponent(Component):
    """位置组件"""

    x: float = 0.0
    y: float = 0.0


@dataclass
class RenderComponent(Component):
    """渲染组件"""

    color: tuple = (255, 255, 255)
    size: int = 20
    shape: str = "circle"  # circle, rect


@dataclass
class NameComponent(Component):
    """名称组件"""

    name: str = "Unknown"


@dataclass
class HealthComponent(Component):
    """生命值组件"""

    max_health: int = 100
    current_health: int = 100

    def is_alive(self) -> bool:
        return self.current_health > 0

    def take_damage(self, damage: int):
        self.current_health = max(0, self.current_health - damage)
        return not self.is_alive()


@dataclass
class VelocityComponent(Component):
    """速度组件"""

    x: float = 0.0
    y: float = 0.0
    max_speed: float = 100.0


@dataclass
class AIComponent(Component):
    """AI组件"""

    behavior: str = "wander"  # wander, chase, flee
    target_entity: int = -1
    state_timer: float = 0.0
    direction_change_interval: float = 3.0


@dataclass
class FactionComponent(Component):
    """阵营组件"""

    faction: str = "neutral"  # player, enemy, neutral


@dataclass
class SelectableComponent(Component):
    """可选择组件"""

    selected: bool = False
    selectable: bool = True


# 游戏系统
class RenderSystem(System):
    """渲染系统"""

    def __init__(self):
        super().__init__([PositionComponent, RenderComponent])

    def update(self, delta_time: float):
        if not self.context or not hasattr(self.context, "render_manager"):
            return

        entities = self.context.query_manager.query_entities(self.required_components)

        for entity in entities:
            pos = self.context.component_manager.get_component(
                entity, PositionComponent
            )
            render = self.context.component_manager.get_component(
                entity, RenderComponent
            )
            selectable = self.context.component_manager.get_component(
                entity, SelectableComponent
            )

            # 如果被选中，添加选中框
            if selectable and selectable.selected:
                selection_color = (255, 255, 0)  # 黄色选中框
                pygame.draw.circle(
                    self.context.render_manager.screen,
                    selection_color,
                    (int(pos.x), int(pos.y)),
                    render.size + 5,
                    2,
                )

            # 渲染实体
            if render.shape == "circle":
                pygame.draw.circle(
                    self.context.render_manager.screen,
                    render.color,
                    (int(pos.x), int(pos.y)),
                    render.size,
                )
            elif render.shape == "rect":
                pygame.draw.rect(
                    self.context.render_manager.screen,
                    render.color,
                    (
                        pos.x - render.size // 2,
                        pos.y - render.size // 2,
                        render.size,
                        render.size,
                    ),
                )


class MovementSystem(System):
    """移动系统"""

    def __init__(self):
        super().__init__([PositionComponent, VelocityComponent])

    def update(self, delta_time: float):
        if not self.context:
            return

        entities = self.context.query_manager.query_entities(self.required_components)

        for entity in entities:
            pos = self.context.component_manager.get_component(
                entity, PositionComponent
            )
            vel = self.context.component_manager.get_component(
                entity, VelocityComponent
            )

            # 更新位置
            pos.x += vel.x * delta_time
            pos.y += vel.y * delta_time

            # 边界检查
            pos.x = max(20, min(780, pos.x))
            pos.y = max(20, min(580, pos.y))


class AISystem(System):
    """AI系统"""

    def __init__(self):
        super().__init__([PositionComponent, VelocityComponent, AIComponent])

    def update(self, delta_time: float):
        if not self.context:
            return

        entities = self.context.query_manager.query_entities(self.required_components)

        for entity in entities:
            pos = self.context.component_manager.get_component(
                entity, PositionComponent
            )
            vel = self.context.component_manager.get_component(
                entity, VelocityComponent
            )
            ai = self.context.component_manager.get_component(entity, AIComponent)

            ai.state_timer += delta_time

            if ai.behavior == "wander":
                self._wander_behavior(entity, pos, vel, ai, delta_time)
            elif ai.behavior == "chase":
                self._chase_behavior(entity, pos, vel, ai, delta_time)

    def _wander_behavior(self, entity, pos, vel, ai, delta_time):
        """漫游行为"""
        if ai.state_timer >= ai.direction_change_interval:
            ai.state_timer = 0.0
            # 随机改变方向
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(20, 50)
            vel.x = math.cos(angle) * speed
            vel.y = math.sin(angle) * speed

    def _chase_behavior(self, entity, pos, vel, ai, delta_time):
        """追逐行为"""
        if ai.target_entity == -1:
            # 寻找最近的敌人
            target = self._find_nearest_enemy(entity, pos)
            if target:
                ai.target_entity = target

        if ai.target_entity != -1:
            target_pos = self.context.component_manager.get_component(
                ai.target_entity, PositionComponent
            )
            if target_pos:
                # 向目标移动
                dx = target_pos.x - pos.x
                dy = target_pos.y - pos.y
                distance = math.sqrt(dx * dx + dy * dy)

                if distance > 5:
                    vel.x = (dx / distance) * vel.max_speed
                    vel.y = (dy / distance) * vel.max_speed
                else:
                    vel.x = 0
                    vel.y = 0

    def _find_nearest_enemy(self, entity, pos):
        """寻找最近的敌人"""
        my_faction = self.context.component_manager.get_component(
            entity, FactionComponent
        )
        if not my_faction:
            return None

        all_entities = self.context.query_manager.query_entities(
            [PositionComponent, FactionComponent]
        )
        nearest_enemy = None
        nearest_distance = float("inf")

        for other_entity in all_entities:
            if other_entity == entity:
                continue

            other_faction = self.context.component_manager.get_component(
                other_entity, FactionComponent
            )
            other_pos = self.context.component_manager.get_component(
                other_entity, PositionComponent
            )

            if other_faction.faction != my_faction.faction:
                distance = math.sqrt(
                    (pos.x - other_pos.x) ** 2 + (pos.y - other_pos.y) ** 2
                )
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_enemy = other_entity

        return nearest_enemy


class SelectionSystem(System):
    """选择系统"""

    def __init__(self):
        super().__init__([PositionComponent, SelectableComponent])

    def initialize(self, context):
        super().initialize(context)
        # 订阅鼠标点击事件
        if hasattr(context, "event_manager"):
            context.event_manager.subscribe(
                EventType.MOUSEBUTTON_DOWN, self._on_mouse_click
            )

    def _on_mouse_click(self, event):
        """处理鼠标点击"""
        if event.button == 1:  # 左键
            mouse_pos = pygame.mouse.get_pos()
            self._select_entity_at_position(mouse_pos[0], mouse_pos[1])

    def _select_entity_at_position(self, x, y):
        """选择指定位置的实体"""
        entities = self.context.query_manager.query_entities(self.required_components)

        # 先取消所有选择
        for entity in entities:
            selectable = self.context.component_manager.get_component(
                entity, SelectableComponent
            )
            selectable.selected = False

        # 查找点击位置的实体
        for entity in entities:
            pos = self.context.component_manager.get_component(
                entity, PositionComponent
            )
            selectable = self.context.component_manager.get_component(
                entity, SelectableComponent
            )
            render = self.context.component_manager.get_component(
                entity, RenderComponent
            )

            if not selectable.selectable:
                continue

            # 检查点击是否在实体范围内
            distance = math.sqrt((x - pos.x) ** 2 + (y - pos.y) ** 2)
            if distance <= (render.size if render else 20):
                selectable.selected = True
                name = self.context.component_manager.get_component(
                    entity, NameComponent
                )
                print(f"选中了: {name.name if name else f'实体{entity}'}")
                break

    def update(self, delta_time: float):
        # 选择系统主要通过事件驱动
        pass


class UISystem(System):
    """UI系统"""

    def __init__(self):
        super().__init__([])
        self.font = None

    def initialize(self, context):
        super().initialize(context)
        pygame.font.init()
        self.font = pygame.font.Font(None, 24)

    def update(self, delta_time: float):
        if not self.context or not self.font:
            return

        screen = self.context.render_manager.screen

        # 显示游戏信息
        self._draw_game_info(screen)
        self._draw_entity_info(screen)

    def _draw_game_info(self, screen):
        """绘制游戏信息"""
        texts = [
            "三国策略小游戏",
            "左键点击选择单位",
            "蓝色=刘备军, 红色=曹操军, 绿色=孙权军",
        ]

        for i, text in enumerate(texts):
            color = (255, 255, 255) if i == 0 else (200, 200, 200)
            surface = self.font.render(text, True, color)
            screen.blit(surface, (10, 10 + i * 25))

    def _draw_entity_info(self, screen):
        """绘制实体信息"""
        selected_entities = []
        all_entities = self.context.query_manager.query_entities([SelectableComponent])

        for entity in all_entities:
            selectable = self.context.component_manager.get_component(
                entity, SelectableComponent
            )
            if selectable.selected:
                selected_entities.append(entity)

        if selected_entities:
            y_offset = 100
            for entity in selected_entities:
                name = self.context.component_manager.get_component(
                    entity, NameComponent
                )
                health = self.context.component_manager.get_component(
                    entity, HealthComponent
                )
                faction = self.context.component_manager.get_component(
                    entity, FactionComponent
                )

                info_text = f"选中: {name.name if name else f'实体{entity}'}"
                if health:
                    info_text += (
                        f" - 生命值: {health.current_health}/{health.max_health}"
                    )
                if faction:
                    info_text += f" - 阵营: {faction.faction}"

                surface = self.font.render(info_text, True, (255, 255, 0))
                screen.blit(surface, (10, y_offset))
                y_offset += 25


# 游戏场景
class GameScene(Scene):
    """主游戏场景"""

    def enter(self, **kwargs):
        super().enter(**kwargs)
        print("进入游戏场景")

        # 添加系统
        self.world.add_system(MovementSystem())
        self.world.add_system(AISystem())
        self.world.add_system(SelectionSystem())
        self.world.add_system(RenderSystem())
        self.world.add_system(UISystem())

        # 创建游戏实体
        self._create_game_entities()

    def _create_game_entities(self):
        """创建游戏实体"""
        # 刘备军（蓝色）
        liu_bei_units = [
            ("刘备", 400, 300, (0, 100, 255)),
            ("关羽", 380, 280, (0, 80, 200)),
            ("张飞", 420, 280, (0, 80, 200)),
            ("赵云", 400, 320, (0, 80, 200)),
        ]

        for name, x, y, color in liu_bei_units:
            entity = self._create_unit(name, x, y, color, "player", "wander")

        # 曹操军（红色）
        cao_cao_units = [
            ("曹操", 200, 150, (255, 0, 0)),
            ("许褚", 180, 130, (200, 0, 0)),
            ("典韦", 220, 130, (200, 0, 0)),
            ("夏侯惇", 200, 170, (200, 0, 0)),
        ]

        for name, x, y, color in cao_cao_units:
            entity = self._create_unit(name, x, y, color, "enemy", "chase")

        # 孙权军（绿色）
        sun_quan_units = [
            ("孙权", 600, 450, (0, 255, 0)),
            ("周瑜", 580, 430, (0, 200, 0)),
            ("黄盖", 620, 430, (0, 200, 0)),
            ("甘宁", 600, 470, (0, 200, 0)),
        ]

        for name, x, y, color in sun_quan_units:
            entity = self._create_unit(name, x, y, color, "neutral", "wander")

    def _create_unit(self, name, x, y, color, faction, ai_behavior):
        """创建单位"""
        entity = self.world.create_entity()

        self.world.add_component(entity, NameComponent(name=name))
        self.world.add_component(entity, PositionComponent(x=x, y=y))
        self.world.add_component(entity, RenderComponent(color=color, size=15))
        self.world.add_component(
            entity, HealthComponent(max_health=100, current_health=100)
        )
        self.world.add_component(entity, VelocityComponent(max_speed=50))
        self.world.add_component(entity, AIComponent(behavior=ai_behavior))
        self.world.add_component(entity, FactionComponent(faction=faction))
        self.world.add_component(entity, SelectableComponent(selectable=True))

        return entity

    def update(self, delta_time: float):
        """更新场景"""
        # 更新ECS世界
        self.world.update(delta_time)


def main():
    print("=== 完整游戏示例 ===")
    print("三国策略小游戏")
    print("使用鼠标点击选择单位，观察不同阵营的AI行为")

    # 创建游戏引擎
    engine = Engine(title="三国策略小游戏", width=800, height=600, fps=60)

    # 注册场景
    engine.scene_manager.add_scene("game", GameScene)

    # 加载游戏场景
    engine.scene_manager.load_scene("game")

    # 启动游戏
    engine.start()


if __name__ == "__main__":
    main()
