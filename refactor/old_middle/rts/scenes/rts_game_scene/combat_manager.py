import pygame


class RTSCombatManager:
    """
    RTS游戏战斗管理器：负责处理战斗效果和事件
    """

    def __init__(self, scene):
        self.scene = scene
        self.combat_effects = []  # 战斗效果列表 (位置, 颜色, 持续时间)

    def update(self, delta_time):
        """更新战斗效果"""
        for effect in self.combat_effects[:]:
            effect["time_left"] -= delta_time
            if effect["time_left"] <= 0:
                self.combat_effects.remove(effect)

    def process_combat_events(self, combat_system):
        """处理战斗事件"""
        combat_events = combat_system.get_combat_events()
        for event in combat_events:
            if event["type"] == "attack":
                # 添加攻击效果
                pos = event["position"]
                # 根据伤害大小确定颜色强度
                damage = event["damage"]
                color_intensity = min(255, 100 + damage * 5)  # 伤害越高，颜色越亮
                self.combat_effects.append(
                    {
                        "position": (pos.x, pos.y),
                        "color": (255, 255 - color_intensity, 0),  # 红到黄色渐变
                        "duration": 0.5,  # 持续0.5秒
                        "size": 20 + damage,  # 尺寸随伤害增加
                        "time_left": 0.5,
                    }
                )
            elif event["type"] == "death":
                # 添加死亡效果
                pos = event["position"]
                self.combat_effects.append(
                    {
                        "position": (pos.x, pos.y),
                        "color": (200, 0, 0),  # 红色
                        "duration": 1.0,  # 持续1秒
                        "size": 40,  # 较大尺寸
                        "time_left": 1.0,
                    }
                )

    def render(self, screen):
        """渲染战斗效果"""
        for effect in self.combat_effects:
            # 计算当前透明度
            alpha = int(255 * effect["time_left"] / effect["duration"])
            color = effect["color"] + (alpha,)  # 添加alpha通道

            # 创建一个临时surface来绘制半透明效果
            effect_surface = pygame.Surface(
                (effect["size"], effect["size"]), pygame.SRCALPHA
            )
            pygame.draw.circle(
                effect_surface,
                color,
                (effect["size"] // 2, effect["size"] // 2),
                effect["size"] // 2,
            )

            # 将效果绘制到屏幕
            screen.blit(
                effect_surface,
                (
                    effect["position"][0] - effect["size"] // 2,
                    effect["position"][1] - effect["size"] // 2,
                ),
            )
