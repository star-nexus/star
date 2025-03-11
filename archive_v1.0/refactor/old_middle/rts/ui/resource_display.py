import pygame
from framework.ui.ui_element import UIElement


class ResourceDisplay(UIElement):
    """资源显示面板：显示玩家资源状态"""

    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self.resources = {"gold": 0, "weapons": 0, "food": 0, "supplies": 0}
        self.max_resources = {
            "gold": 1000,
            "weapons": 1000,
            "food": 1000,
            "supplies": 1000,
        }
        self.resource_colors = {
            "gold": (255, 215, 0),  # 金色
            "weapons": (150, 150, 150),  # 银色
            "food": (50, 180, 50),  # 绿色
            "supplies": (180, 120, 30),  # 棕色
        }
        self.font = None
        self.icon_size = 24
        self.padding = 5

    def set_font(self, font):
        """设置字体"""
        self.font = font

    def update_resources(self, resource_comp):
        """更新资源数据"""
        self.resources["gold"] = resource_comp.gold
        self.resources["weapons"] = resource_comp.weapons
        self.resources["food"] = resource_comp.food
        self.resources["supplies"] = resource_comp.supplies

        self.max_resources["gold"] = resource_comp.max_gold
        self.max_resources["weapons"] = resource_comp.max_weapons
        self.max_resources["food"] = resource_comp.max_food
        self.max_resources["supplies"] = resource_comp.max_supplies

    def render(self, surface):
        """渲染资源面板"""
        # 绘制背景
        panel_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(surface, (40, 40, 40), panel_rect)
        pygame.draw.rect(surface, (80, 80, 80), panel_rect, 2)

        if not self.font:
            return

        # 渲染资源信息
        y_offset = self.padding
        x_spacing = self.width / 4

        resource_names = {
            "gold": "Gold",
            "weapons": "Weapons",
            "food": "Food",
            "supplies": "Supplies",
        }

        for i, (res_key, res_name) in enumerate(resource_names.items()):
            x_pos = self.x + x_spacing * i + self.padding

            # 绘制资源图标
            icon_rect = pygame.Rect(
                x_pos, self.y + y_offset, self.icon_size, self.icon_size
            )
            pygame.draw.rect(surface, self.resource_colors[res_key], icon_rect)
            pygame.draw.rect(surface, (200, 200, 200), icon_rect, 1)

            # 绘制资源数量
            amount = int(self.resources[res_key])
            max_amount = self.max_resources[res_key]
            text = f"{amount}/{max_amount}"
            text_surf = self.font.render(text, True, (255, 255, 255))
            text_rect = text_surf.get_rect(
                topleft=(x_pos + self.icon_size + 5, self.y + y_offset)
            )
            surface.blit(text_surf, text_rect)

            # 绘制资源名称
            name_surf = self.font.render(res_name, True, (200, 200, 200))
            name_rect = name_surf.get_rect(
                topleft=(x_pos, self.y + y_offset + self.icon_size + 5)
            )
            surface.blit(name_surf, name_rect)

        super().render(surface)
