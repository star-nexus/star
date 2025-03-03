import pygame
from .entity import Component


class SpriteComponent(Component):
    """精灵渲染组件"""

    def __init__(self, entity, image, width=None, height=None):
        super().__init__(entity)
        self.image = image
        if width and height:
            self.image = pygame.transform.scale(self.image, (width, height))
        self.width = self.image.get_width()
        self.height = self.image.get_height()

    def render(self, surface):
        """渲染精灵到指定表面"""
        surface.blit(self.image, (self.entity.x, self.entity.y))


class MovementComponent(Component):
    """移动组件"""

    def __init__(self, entity, speed=100):
        super().__init__(entity)
        self.speed = speed
        self.velocity_x = 0
        self.velocity_y = 0

    def update(self, delta_time):
        """根据速度更新实体位置"""
        self.entity.x += self.velocity_x * self.speed * delta_time
        self.entity.y += self.velocity_y * self.speed * delta_time

    def set_velocity(self, x, y):
        """设置移动速度"""
        self.velocity_x = x
        self.velocity_y = y


class CollisionComponent(Component):
    """碰撞组件"""

    def __init__(self, entity, width, height):
        super().__init__(entity)
        self.width = width
        self.height = height

    def get_rect(self):
        """获取碰撞矩形"""
        return pygame.Rect(self.entity.x, self.entity.y, self.width, self.height)

    def is_colliding(self, other_collision):
        """检测与其他碰撞组件是否碰撞"""
        return self.get_rect().colliderect(other_collision.get_rect())


class AnimationComponent(Component):
    """精灵动画组件"""

    def __init__(self, entity, sprite_component):
        super().__init__(entity)
        self.sprite_component = sprite_component
        self.animations = {}  # 存储不同动画序列
        self.current_animation = None
        self.current_frame = 0
        self.animation_speed = 0.1  # 动画帧之间的时间（秒）
        self.timer = 0

    def add_animation(self, name, frames):
        """添加动画序列

        Args:
            name: 动画名称
            frames: 包含动画帧的图像列表
        """
        self.animations[name] = frames
        if self.current_animation is None:
            self.play(name)

    def play(self, name, reset=True):
        """播放指定的动画序列

        Args:
            name: 要播放的动画名称
            reset: 是否重置到动画的第一帧
        """
        if name in self.animations:
            self.current_animation = name
            if reset:
                self.current_frame = 0
                self.timer = 0

    def update(self, delta_time):
        """更新动画状态"""
        if self.current_animation is None:
            return

        frames = self.animations[self.current_animation]
        if not frames:
            return

        # 更新动画计时器
        self.timer += delta_time
        if self.timer >= self.animation_speed:
            self.timer = 0
            self.current_frame = (self.current_frame + 1) % len(frames)

            # 更新精灵图像
            if self.sprite_component:
                self.sprite_component.image = frames[self.current_frame]
