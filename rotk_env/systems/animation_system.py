"""
动画系统 - 处理单位移动动画和视觉效果
"""

import pygame
from typing import Tuple, Optional
from framework import System, World, RMS
from ..components import (
    HexPosition,
    MovementAnimation,
    UnitStatus,
    DamageNumber,
    Camera,
)
from ..utils.hex_utils import HexConverter
from ..prefabs.config import GameConfig, HexOrientation


class AnimationSystem(System):
    """动画系统"""

    def __init__(self):
        super().__init__(priority=15)  # 在渲染前处理动画
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )
        self.damage_font = None

    def initialize(self, world: World) -> None:
        self.world = world
        # 初始化字体
        pygame.font.init()
        self.damage_font = pygame.font.Font(None, 24)

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """更新动画系统"""
        self._update_movement_animations(delta_time)
        self._update_unit_status(delta_time)
        self._update_damage_numbers(delta_time)

    def _update_movement_animations(self, delta_time: float):
        """更新移动动画"""
        for entity in (
            self.world.query().with_all(HexPosition, MovementAnimation).entities()
        ):
            pos = self.world.get_component(entity, HexPosition)
            anim = self.world.get_component(entity, MovementAnimation)

            if not pos or not anim or not anim.is_moving:
                continue

            if not anim.path or anim.current_target_index >= len(anim.path):
                # 移动完成
                anim.is_moving = False
                anim.progress = 0.0
                anim.current_target_index = 0
                anim.path.clear()
                continue

            # 更新移动进度
            anim.progress += anim.speed * delta_time

            if anim.progress >= 1.0:
                # 到达当前目标点
                target_hex = anim.path[anim.current_target_index]
                pos.col, pos.row = target_hex
                anim.current_target_index += 1
                anim.progress = 0.0

                if anim.current_target_index >= len(anim.path):
                    # 全部路径完成
                    anim.is_moving = False
                else:
                    # 设置下一段移动的起始和目标像素坐标
                    self._setup_movement_segment(anim, pos)

    def _setup_movement_segment(self, anim: MovementAnimation, pos: HexPosition):
        """设置移动片段的像素坐标"""
        if anim.current_target_index < len(anim.path):
            # 当前位置
            start_x, start_y = self.hex_converter.hex_to_pixel(pos.col, pos.row)
            anim.start_pixel_pos = (start_x, start_y)

            # 目标位置
            target_hex = anim.path[anim.current_target_index]
            target_x, target_y = self.hex_converter.hex_to_pixel(
                target_hex[0], target_hex[1]
            )
            anim.target_pixel_pos = (target_x, target_y)

    def _update_unit_status(self, delta_time: float):
        """更新单位状态"""
        for entity in self.world.query().with_all(UnitStatus).entities():
            status = self.world.get_component(entity, UnitStatus)
            if not status:
                continue

            status.status_duration += delta_time

            # 检查移动状态
            anim = self.world.get_component(entity, MovementAnimation)
            if anim and anim.is_moving:
                status.current_status = "moving"
            elif status.current_status == "moving" and (not anim or not anim.is_moving):
                status.current_status = "idle"

    def _update_damage_numbers(self, delta_time: float):
        """更新伤害数字显示"""
        entities_to_remove = []

        for entity in self.world.query().with_all(DamageNumber).entities():
            damage_num = self.world.get_component(entity, DamageNumber)
            if not damage_num:
                continue

            damage_num.elapsed_time += delta_time

            if damage_num.elapsed_time >= damage_num.lifetime:
                entities_to_remove.append(entity)
                continue

            # 更新位置
            new_x = damage_num.position[0] + damage_num.velocity[0] * delta_time
            new_y = damage_num.position[1] + damage_num.velocity[1] * delta_time
            damage_num.position = (new_x, new_y)

        # 移除过期的伤害数字
        for entity in entities_to_remove:
            self.world.destroy_entity(entity)

    def render_damage_numbers(self):
        """渲染伤害数字"""
        if not self.damage_font:
            return

        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        camera_offset = camera.get_offset()

        for entity in self.world.query().with_all(DamageNumber).entities():
            damage_num = self.world.get_component(entity, DamageNumber)
            if not damage_num:
                continue

            # 计算透明度（随时间淡出）
            alpha_ratio = 1.0 - (damage_num.elapsed_time / damage_num.lifetime)
            alpha = int(255 * alpha_ratio)

            if alpha <= 0:
                continue

            # 创建带透明度的颜色
            color = (*damage_num.color, alpha)

            # 渲染文字
            text = f"-{damage_num.damage}"
            text_surface = self.damage_font.render(text, True, damage_num.color)

            # 应用透明度
            if alpha < 255:
                text_surface.set_alpha(alpha)

            # 计算屏幕位置
            screen_x = damage_num.position[0] + camera_offset[0]
            screen_y = damage_num.position[1] + camera_offset[1]

            RMS.draw(text_surface, (screen_x, screen_y))

    def get_unit_render_position(self, entity: int) -> Optional[Tuple[float, float]]:
        """获取单位的渲染位置（考虑移动动画）"""
        pos = self.world.get_component(entity, HexPosition)
        anim = self.world.get_component(entity, MovementAnimation)

        if not pos:
            return None

        if (
            not anim
            or not anim.is_moving
            or not anim.start_pixel_pos
            or not anim.target_pixel_pos
        ):
            # 没有动画，返回静态位置
            return self.hex_converter.hex_to_pixel(pos.col, pos.row)

        # 插值计算当前渲染位置
        start_x, start_y = anim.start_pixel_pos
        target_x, target_y = anim.target_pixel_pos

        current_x = start_x + (target_x - start_x) * anim.progress
        current_y = start_y + (target_y - start_y) * anim.progress

        return (current_x, current_y)

    def start_unit_movement(self, entity: int, path: list):
        """开始单位移动动画"""
        if not path or len(path) < 2:
            return

        pos = self.world.get_component(entity, HexPosition)
        if not pos:
            return

        # 获取或创建移动动画组件
        anim = self.world.get_component(entity, MovementAnimation)
        if not anim:
            anim = MovementAnimation()
            self.world.add_component(entity, anim)

        # 设置路径（跳过起始点）
        anim.path = path[1:]  # 跳过当前位置
        anim.current_target_index = 0
        anim.progress = 0.0
        anim.is_moving = True

        # 设置第一段移动
        self._setup_movement_segment(anim, pos)

    def create_damage_number(self, damage: int, world_pos: Tuple[float, float]):
        """创建伤害数字显示"""
        entity = self.world.create_entity()

        damage_num = DamageNumber(
            damage=damage,
            position=world_pos,
            lifetime=2.0,
            velocity=(0, -50),  # 向上移动
            color=(255, 0, 0) if damage > 0 else (0, 255, 0),  # 红色伤害，绿色治疗
        )

        self.world.add_component(entity, damage_num)
