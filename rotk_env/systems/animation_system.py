"""
动画系统 - 处理单位移动动画和视觉效果
"""

import pygame
from typing import Tuple, Optional
from framework import System, World, RMS
from ..components import (
    HexPosition,
    MovementAnimation,
    AttackAnimation,
    EffectAnimation,
    ProjectileAnimation,
    UnitStatus,
    DamageNumber,
    Camera,
    Unit,
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
        self._update_attack_animations(delta_time)
        self._update_projectile_animations(delta_time)
        self._update_effect_animations(delta_time)
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
            text = damage_num.text

            # 根据字体大小创建字体（如果需要）
            font_to_use = self.damage_font
            if hasattr(damage_num, "font_size") and damage_num.font_size != 24:
                try:
                    import pygame

                    font_to_use = pygame.font.Font(None, damage_num.font_size)
                except:
                    font_to_use = self.damage_font

            text_surface = font_to_use.render(text, True, damage_num.color)

            # 应用透明度
            if alpha < 255:
                text_surface.set_alpha(alpha)

            # 计算屏幕位置
            screen_x = damage_num.position[0] + camera_offset[0]
            screen_y = damage_num.position[1] + camera_offset[1]

            RMS.draw(text_surface, (screen_x, screen_y))

    def get_unit_render_position(self, entity: int) -> Optional[Tuple[float, float]]:
        """获取单位的渲染位置（考虑移动和攻击动画）"""
        pos = self.world.get_component(entity, HexPosition)
        if not pos:
            return None

        # 优先检查攻击动画
        attack_anim = self.world.get_component(entity, AttackAnimation)
        if attack_anim and attack_anim.is_attacking and attack_anim.current_render_pos:
            return attack_anim.current_render_pos

        # 检查移动动画
        move_anim = self.world.get_component(entity, MovementAnimation)
        if (
            not move_anim
            or not move_anim.is_moving
            or not move_anim.start_pixel_pos
            or not move_anim.target_pixel_pos
        ):
            # 没有动画，返回静态位置
            return self.hex_converter.hex_to_pixel(pos.col, pos.row)

        # 插值计算当前渲染位置
        start_x, start_y = move_anim.start_pixel_pos
        target_x, target_y = move_anim.target_pixel_pos

        current_x = start_x + (target_x - start_x) * move_anim.progress
        current_y = start_y + (target_y - start_y) * move_anim.progress

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

    def start_attack_animation(
        self, attacker_entity: int, target_entity: int, attack_type: str = "melee"
    ):
        """开始攻击动画"""
        attacker_pos = self.world.get_component(attacker_entity, HexPosition)
        target_pos = self.world.get_component(target_entity, HexPosition)

        if not attacker_pos or not target_pos:
            return

        # 获取或创建攻击动画组件
        anim = self.world.get_component(attacker_entity, AttackAnimation)
        if not anim:
            anim = AttackAnimation()
            self.world.add_component(attacker_entity, anim)

        # 设置目标位置
        anim.target_position = (target_pos.col, target_pos.row)
        anim.attack_type = attack_type
        anim.is_attacking = True
        anim.progress = 0.0
        anim.phase = "prepare"
        anim.show_aim_line = False
        anim.aim_line_alpha = 0.0

        # 计算世界像素坐标
        start_x, start_y = self.hex_converter.hex_to_pixel(
            attacker_pos.col, attacker_pos.row
        )
        target_x, target_y = self.hex_converter.hex_to_pixel(
            target_pos.col, target_pos.row
        )

        anim.start_pixel_pos = (start_x, start_y)
        anim.target_pixel_pos = (target_x, target_y)
        anim.current_render_pos = (start_x, start_y)

        # 根据攻击类型调整动画参数
        if attack_type == "ranged":
            anim.speed = 5.0  # 远程攻击稍慢
            anim.total_duration = 1.0
            anim.prepare_ratio = 0.15
            anim.aim_ratio = 0.25  # 更长的瞄准时间
            anim.strike_ratio = 0.45
            anim.return_ratio = 0.15
            anim.aim_line_color = (255, 100, 100)  # 红色瞄准线
        else:  # melee
            anim.speed = 8.0
            anim.total_duration = 0.8
            anim.prepare_ratio = 0.2
            anim.aim_ratio = 0.15  # 较短的瞄准时间
            anim.strike_ratio = 0.45
            anim.return_ratio = 0.2
            anim.aim_line_color = (255, 255, 100)  # 黄色瞄准线

        # 重置投射物创建标志
        if hasattr(anim, "_projectile_created"):
            delattr(anim, "_projectile_created")

    def create_attack_effect(
        self, world_pos: Tuple[float, float], effect_type: str = "slash"
    ):
        """创建攻击特效"""
        entity = self.world.create_entity()

        effect = EffectAnimation(
            effect_type=effect_type,
            effect_position=world_pos,
            effect_size=1.0,
            effect_color=(255, 255, 255),
            duration=0.5,
            is_playing=True,
            progress=0.0,
            elapsed_time=0.0,
        )

        self.world.add_component(entity, effect)

    def _update_attack_animations(self, delta_time: float):
        """更新攻击动画"""
        entities_to_complete = []

        for entity in (
            self.world.query().with_all(HexPosition, AttackAnimation).entities()
        ):
            pos = self.world.get_component(entity, HexPosition)
            anim = self.world.get_component(entity, AttackAnimation)

            if not pos or not anim or not anim.is_attacking:
                continue

            # 更新动画进度
            anim.progress += anim.speed * delta_time

            if anim.progress >= anim.total_duration:
                # 攻击动画完成
                anim.is_attacking = False
                anim.progress = 0.0
                anim.phase = "prepare"
                anim.current_render_pos = None
                entities_to_complete.append(entity)
                continue

            # 计算当前阶段和在该阶段的进度
            self._update_attack_phase(anim)

        # 移除完成的攻击动画组件
        for entity in entities_to_complete:
            if self.world.has_component(entity, AttackAnimation):
                self.world.remove_component(entity, AttackAnimation)

    def _update_attack_phase(self, anim: AttackAnimation):
        """更新攻击动画的阶段和位置"""
        progress_ratio = anim.progress / anim.total_duration

        if progress_ratio <= anim.prepare_ratio:
            # 准备阶段：轻微向目标移动
            anim.phase = "prepare"
            phase_progress = progress_ratio / anim.prepare_ratio
            if anim.attack_type == "melee":
                self._calculate_attack_position(anim, phase_progress * 0.1)  # 轻微移动
            else:
                # 远程攻击不移动，只是准备姿态
                self._calculate_attack_position(anim, 0)
            anim.show_aim_line = False

        elif progress_ratio <= anim.prepare_ratio + anim.aim_ratio:
            # 瞄准阶段：显示攻击指示线
            anim.phase = "aim"
            aim_start = anim.prepare_ratio
            phase_progress = (progress_ratio - aim_start) / anim.aim_ratio

            # 显示瞄准线，透明度渐增
            anim.show_aim_line = True
            anim.aim_line_alpha = min(1.0, phase_progress * 2.0)

            if anim.attack_type == "melee":
                self._calculate_attack_position(anim, 0.1)  # 保持准备位置
            else:
                self._calculate_attack_position(anim, 0)

        elif progress_ratio <= anim.prepare_ratio + anim.aim_ratio + anim.strike_ratio:
            # 打击/射击阶段
            anim.phase = "strike" if anim.attack_type == "melee" else "shoot"
            strike_start = anim.prepare_ratio + anim.aim_ratio
            phase_progress = (progress_ratio - strike_start) / anim.strike_ratio

            anim.show_aim_line = False  # 隐藏瞄准线

            if anim.attack_type == "melee":
                # 近战：快速冲向目标
                eased_progress = self._ease_out_back(phase_progress)
                self._calculate_attack_position(
                    anim, 0.1 + eased_progress * 0.7
                )  # 从10%到80%
            else:
                # 远程：创建投射物并保持位置
                if phase_progress == 0 or not hasattr(anim, "_projectile_created"):
                    self._create_projectile(anim)
                    anim._projectile_created = True
                self._calculate_attack_position(anim, 0)

        else:
            # 返回阶段：回到原位
            anim.phase = "return"
            return_start = anim.prepare_ratio + anim.aim_ratio + anim.strike_ratio
            phase_progress = (progress_ratio - return_start) / anim.return_ratio

            anim.show_aim_line = False

            if anim.attack_type == "melee":
                # 使用缓动函数使返回更平滑
                eased_progress = self._ease_in_out(phase_progress)
                self._calculate_attack_position(
                    anim, 0.8 - eased_progress * 0.8
                )  # 从80%回到0%
            else:
                self._calculate_attack_position(anim, 0)

    def _calculate_attack_position(self, anim: AttackAnimation, progress: float):
        """计算攻击动画的当前位置"""
        if not anim.start_pixel_pos or not anim.target_pixel_pos:
            return

        start_x, start_y = anim.start_pixel_pos
        target_x, target_y = anim.target_pixel_pos

        # 根据进度插值计算位置
        current_x = start_x + (target_x - start_x) * progress
        current_y = start_y + (target_y - start_y) * progress

        anim.current_render_pos = (current_x, current_y)

    def _ease_out_back(self, t: float) -> float:
        """回弹缓动函数（适合打击效果）"""
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)

    def _ease_in_out(self, t: float) -> float:
        """平滑缓动函数"""
        return t * t * (3.0 - 2.0 * t)

    def _update_effect_animations(self, delta_time: float):
        """更新特效动画"""
        entities_to_remove = []

        for entity in self.world.query().with_all(EffectAnimation).entities():
            effect = self.world.get_component(entity, EffectAnimation)
            if not effect or not effect.is_playing:
                continue

            effect.elapsed_time += delta_time
            effect.progress = min(effect.elapsed_time / effect.duration, 1.0)

            if effect.elapsed_time >= effect.duration:
                entities_to_remove.append(entity)

        # 移除完成的特效
        for entity in entities_to_remove:
            self.world.destroy_entity(entity)

    def _update_projectile_animations(self, delta_time: float):
        """更新投射物动画"""
        entities_to_remove = []

        for entity in self.world.query().with_all(ProjectileAnimation).entities():
            projectile = self.world.get_component(entity, ProjectileAnimation)
            if not projectile or not projectile.is_flying:
                continue

            # 计算飞行距离
            start_x, start_y = projectile.start_pos
            target_x, target_y = projectile.target_pos
            total_distance = (
                (target_x - start_x) ** 2 + (target_y - start_y) ** 2
            ) ** 0.5

            if total_distance <= 0:
                entities_to_remove.append(entity)
                continue

            # 更新飞行进度
            distance_per_second = projectile.flight_speed
            progress_per_second = distance_per_second / total_distance
            projectile.flight_progress += progress_per_second * delta_time

            if projectile.flight_progress >= 1.0:
                # 投射物到达目标
                projectile.is_flying = False
                entities_to_remove.append(entity)
                continue

            # 计算当前位置（带抛物线效果）
            self._calculate_projectile_position(projectile)

        # 移除完成的投射物
        for entity in entities_to_remove:
            self.world.destroy_entity(entity)

    def _calculate_projectile_position(self, projectile: ProjectileAnimation):
        """计算投射物的当前位置（包含抛物线效果）"""
        start_x, start_y = projectile.start_pos
        target_x, target_y = projectile.target_pos
        progress = projectile.flight_progress

        # 线性插值基础位置
        current_x = start_x + (target_x - start_x) * progress
        current_y = start_y + (target_y - start_y) * progress

        # 添加抛物线效果（在飞行中点达到最高）
        arc_offset = projectile.arc_height * 4 * progress * (1 - progress)
        current_y -= arc_offset

        projectile.current_pos = (current_x, current_y)

        # 计算旋转角度（面向飞行方向）
        import math

        if progress < 1.0:
            # 计算下一帧的位置来确定方向
            next_progress = min(1.0, progress + 0.01)
            next_x = start_x + (target_x - start_x) * next_progress
            next_y = (
                start_y
                + (target_y - start_y) * next_progress
                - projectile.arc_height * 4 * next_progress * (1 - next_progress)
            )

            dx = next_x - current_x
            dy = next_y - current_y
            projectile.rotation = math.atan2(dy, dx)

    def _create_projectile(self, attack_anim: AttackAnimation):
        """创建投射物实体"""
        if not attack_anim.start_pixel_pos or not attack_anim.target_pixel_pos:
            return

        entity = self.world.create_entity()

        # 根据攻击类型确定投射物属性
        if attack_anim.attack_type == "ranged":
            projectile_type = "arrow"
            color = (139, 69, 19)  # 棕色箭矢
            arc_height = 30.0
            speed = 600.0
        else:
            projectile_type = "bolt"
            color = (192, 192, 192)  # 银色弩箭
            arc_height = 20.0
            speed = 800.0

        projectile = ProjectileAnimation(
            start_pos=attack_anim.start_pixel_pos,
            target_pos=attack_anim.target_pixel_pos,
            current_pos=attack_anim.start_pixel_pos,
            flight_progress=0.0,
            flight_speed=speed,
            is_flying=True,
            projectile_type=projectile_type,
            arc_height=arc_height,
            size=1.0,
            color=color,
            rotation=0.0,
        )

        self.world.add_component(entity, projectile)

    def create_damage_number(self, damage: int, world_pos: Tuple[float, float]):
        """创建伤害数字显示"""
        entity = self.world.create_entity()

        damage_num = DamageNumber(
            text=str(damage),
            position=world_pos,
            lifetime=2.0,
            velocity=(0, -50),  # 向上移动
            color=(255, 0, 0) if damage > 0 else (0, 255, 0),  # 红色伤害，绿色治疗
            font_size=24,
        )

        self.world.add_component(entity, damage_num)

    def create_miss_indicator(self, world_pos: Tuple[float, float]):
        """创建未命中指示"""
        entity = self.world.create_entity()

        miss_indicator = DamageNumber(
            text="MISS",
            position=world_pos,
            lifetime=1.5,
            velocity=(0, -30),  # 稍慢的向上移动
            color=(128, 128, 128),  # 灰色
            font_size=20,
        )

        self.world.add_component(entity, miss_indicator)

    def create_crit_indicator(self, world_pos: Tuple[float, float]):
        """创建暴击指示"""
        entity = self.world.create_entity()

        crit_indicator = DamageNumber(
            text="CRIT!",
            position=world_pos,
            lifetime=2.5,
            velocity=(0, -60),  # 更快的向上移动
            color=(255, 255, 0),  # 黄色
            font_size=28,
        )

        self.world.add_component(entity, crit_indicator)

    def create_healing_number(self, healing: int, world_pos: Tuple[float, float]):
        """创建治疗数字显示"""
        entity = self.world.create_entity()

        healing_num = DamageNumber(
            text=f"+{healing}",
            position=world_pos,
            lifetime=2.0,
            velocity=(0, -40),  # 向上移动
            color=(0, 255, 0),  # 绿色治疗
            font_size=24,
        )

        self.world.add_component(entity, healing_num)

    def create_text_indicator(
        self,
        text: str,
        world_pos: Tuple[float, float],
        color: Tuple[int, int, int] = (255, 255, 255),
        font_size: int = 24,
        lifetime: float = 2.0,
        velocity: Tuple[float, float] = (0, -50),
    ):
        """创建通用文本指示器"""
        entity = self.world.create_entity()

        text_indicator = DamageNumber(
            text=text,
            position=world_pos,
            lifetime=lifetime,
            velocity=velocity,
            color=color,
            font_size=font_size,
        )

        self.world.add_component(entity, text_indicator)
