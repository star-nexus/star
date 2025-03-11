from framework.ecs.component import Component


class PositionComponent(Component):
    def __init__(self, x=0, y=0):
        super().__init__()
        self.x = x
        self.y = y


class VelocityComponent(Component):
    def __init__(self, x=0, y=0):
        super().__init__()
        self.x = x
        self.y = y


class SpriteComponent(Component):
    def __init__(self, image_name):
        super().__init__()
        self.image_name = image_name
        self.width = 32
        self.height = 32
        self.is_glowing = False
        self.glow_timer = 0
        self.original_image_name = image_name


class InputComponent(Component):
    def __init__(self):
        super().__init__()
        self.up = False
        self.down = False
        self.left = False
        self.right = False


class ColliderComponent(Component):
    def __init__(self, width=32, height=32, is_trigger=False):
        super().__init__()
        self.width = width
        self.height = height
        self.is_trigger = is_trigger  # 是否只是触发器，而不是实体碰撞体
        self.is_colliding = False
        self.colliding_entities = set()


class ObstacleComponent(Component):
    def __init__(self):
        super().__init__()
        # 障碍物特性
        self.damage = 0


class EnemyComponent(Component):
    def __init__(self, speed=50, detection_radius=200):
        super().__init__()
        self.speed = speed
        self.detection_radius = detection_radius
        self.target = None
        self.state = "idle"  # idle, chase


class HealthComponent(Component):
    def __init__(self, max_health=100, regeneration_rate=0):
        super().__init__()
        self.max_health = max_health
        self.current_health = max_health
        self.regeneration_rate = regeneration_rate  # 每秒回复量
        self.is_dead = False

    def take_damage(self, amount):
        """受到伤害"""
        self.current_health = max(0, self.current_health - amount)
        if self.current_health <= 0:
            self.is_dead = True
        return self.is_dead

    def heal(self, amount):
        """回复生命值"""
        self.current_health = min(self.max_health, self.current_health + amount)

    def regenerate(self, delta_time):
        """随时间自动回复"""
        if self.regeneration_rate > 0 and self.current_health < self.max_health:
            self.heal(self.regeneration_rate * delta_time)
