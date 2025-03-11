import pygame
from framework.ui.ui_element import UIElement
from rts.components import (
    UnitComponent,
    BuildingComponent,
    DefenseComponent,
    AttackComponent,
    FactionComponent,
)


class EntityInfoPanel(UIElement):
    """实体信息面板：显示选中单位或建筑的详细信息"""

    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self.entity = None
        self.font = None
        self.title_font = None
        self.padding = 10
        self.line_spacing = 22

    def set_fonts(self, title_font, regular_font):
        """设置字体"""
        self.title_font = title_font
        self.font = regular_font

    def set_entity(self, entity):
        """设置要显示信息的实体"""
        self.entity = entity

    def render(self, surface):
        """渲染信息面板"""
        # 绘制背景
        panel_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(surface, (40, 40, 40, 200), panel_rect)
        pygame.draw.rect(surface, (80, 80, 80), panel_rect, 2)

        # 如果没有选中实体或没有设置字体，则不显示内容
        if not self.entity or not self.font:
            # 显示未选中提示
            if self.font:
                text = self.font.render(
                    "No unit/building selected", True, (180, 180, 180)
                )
                text_rect = text.get_rect(
                    center=(self.x + self.width // 2, self.y + 30)
                )
                surface.blit(text, text_rect)
            return

        # 获取实体组件
        faction_comp = self.entity.get_component(FactionComponent)
        unit_comp = self.entity.get_component(UnitComponent)
        building_comp = self.entity.get_component(BuildingComponent)
        defense_comp = self.entity.get_component(DefenseComponent)
        attack_comp = self.entity.get_component(AttackComponent)

        # 绘制实体标题
        y_offset = self.y + self.padding
        title = ""

        # 根据实体类型显示不同信息
        if unit_comp:
            title = unit_comp.unit_name or f"{unit_comp.unit_type} unit"
        elif building_comp:
            title = (
                building_comp.building_name or f"{building_comp.building_type} building"
            )
        else:
            title = "Unknown Entity"

        # 显示标题和阵营
        if self.title_font:
            title_surf = self.title_font.render(title, True, (255, 255, 255))
            surface.blit(title_surf, (self.x + self.padding, y_offset))
            y_offset += title_surf.get_height() + 5

            # 显示阵营
            if faction_comp:
                faction_text = f"Faction: {faction_comp.faction_name}"
                faction_surf = self.font.render(
                    faction_text, True, faction_comp.faction_color
                )
                surface.blit(faction_surf, (self.x + self.padding, y_offset))
                y_offset += self.line_spacing

        # 分隔线
        pygame.draw.line(
            surface,
            (100, 100, 100),
            (self.x + self.padding, y_offset),
            (self.x + self.width - self.padding, y_offset),
            1,
        )
        y_offset += 5

        # 显示生命值
        if defense_comp:
            health_percent = defense_comp.health / defense_comp.max_health
            health_text = (
                f"Health: {int(defense_comp.health)}/{defense_comp.max_health}"
            )
            health_surf = self.font.render(health_text, True, (255, 255, 255))
            surface.blit(health_surf, (self.x + self.padding, y_offset))

            # 生命值条
            bar_width = self.width - self.padding * 2
            bar_rect = pygame.Rect(
                self.x + self.padding,
                y_offset + health_surf.get_height() + 2,
                bar_width,
                8,
            )
            pygame.draw.rect(surface, (50, 50, 50), bar_rect)  # 背景

            health_bar_width = int(bar_width * health_percent)
            health_bar_rect = pygame.Rect(
                self.x + self.padding,
                y_offset + health_surf.get_height() + 2,
                health_bar_width,
                8,
            )

            # 根据生命值百分比确定颜色
            if health_percent > 0.6:
                health_color = (50, 200, 50)  # 绿色
            elif health_percent > 0.3:
                health_color = (200, 200, 50)  # 黄色
            else:
                health_color = (200, 50, 50)  # 红色

            pygame.draw.rect(surface, health_color, health_bar_rect)
            pygame.draw.rect(surface, (100, 100, 100), bar_rect, 1)  # 边框

            y_offset += self.line_spacing + 10

        # 显示单位特有属性
        if unit_comp:
            # Unit type
            type_text = f"Type: {self._get_unit_type_name(unit_comp.unit_type)}"
            type_surf = self.font.render(type_text, True, (200, 200, 200))
            surface.blit(type_surf, (self.x + self.padding, y_offset))
            y_offset += self.line_spacing

            # 攻击力
            if attack_comp:
                attack_text = f"Attack: {attack_comp.damage}"
                attack_surf = self.font.render(attack_text, True, (200, 200, 200))
                surface.blit(attack_surf, (self.x + self.padding, y_offset))
                y_offset += self.line_spacing

                # Attack range
                range_text = f"Range: {attack_comp.range} tiles"
                range_surf = self.font.render(range_text, True, (200, 200, 200))
                surface.blit(
                    range_surf,
                    (self.x + self.padding + 100, y_offset - self.line_spacing),
                )

            # 防御值
            if defense_comp:
                defense_text = f"Defense: {defense_comp.armor}"
                defense_surf = self.font.render(defense_text, True, (200, 200, 200))
                surface.blit(defense_surf, (self.x + self.padding, y_offset))
                y_offset += self.line_spacing

            # 状态
            status = []
            if unit_comp.is_moving:
                status.append("Moving")
            if unit_comp.is_attacking:
                status.append("Attacking")

            status_text = f"Status: {', '.join(status) if status else 'Idle'}"
            status_surf = self.font.render(status_text, True, (200, 200, 200))
            surface.blit(status_surf, (self.x + self.padding, y_offset))
            y_offset += self.line_spacing

        # 显示建筑特有属性
        elif building_comp:
            # Building type
            type_text = (
                f"Type: {self._get_building_type_name(building_comp.building_type)}"
            )
            type_surf = self.font.render(type_text, True, (200, 200, 200))
            surface.blit(type_surf, (self.x + self.padding, y_offset))
            y_offset += self.line_spacing

            # 建造进度
            if not building_comp.is_completed:
                progress_text = (
                    f"Construction: {int(building_comp.construction_progress)}%"
                )
                progress_surf = self.font.render(progress_text, True, (200, 200, 200))
                surface.blit(progress_surf, (self.x + self.padding, y_offset))

                # 进度条
                bar_width = self.width - self.padding * 2
                bar_rect = pygame.Rect(
                    self.x + self.padding,
                    y_offset + progress_surf.get_height() + 2,
                    bar_width,
                    8,
                )
                pygame.draw.rect(surface, (50, 50, 50), bar_rect)  # 背景

                progress_width = int(
                    bar_width * building_comp.construction_progress / 100
                )
                progress_rect = pygame.Rect(
                    self.x + self.padding,
                    y_offset + progress_surf.get_height() + 2,
                    progress_width,
                    8,
                )
                pygame.draw.rect(surface, (50, 150, 250), progress_rect)
                pygame.draw.rect(surface, (100, 100, 100), bar_rect, 1)  # 边框

                y_offset += self.line_spacing + 10

            # 生产进度
            if building_comp.is_producing and building_comp.production_target:
                target_info = building_comp.production_target
                target_type = target_info.get("type", "unknown")
                target_time = target_info.get("time", 0)

                if target_time > 0:
                    progress_percent = (
                        building_comp.production_progress / target_time * 100
                    )
                    prod_text = f"生产 {target_type}: {int(progress_percent)}%"
                    prod_surf = self.font.render(prod_text, True, (200, 200, 200))
                    surface.blit(prod_surf, (self.x + self.padding, y_offset))

                    # 进度条
                    bar_width = self.width - self.padding * 2
                    bar_rect = pygame.Rect(
                        self.x + self.padding,
                        y_offset + prod_surf.get_height() + 2,
                        bar_width,
                        8,
                    )
                    pygame.draw.rect(surface, (50, 50, 50), bar_rect)  # 背景

                    progress_width = int(bar_width * progress_percent / 100)
                    progress_rect = pygame.Rect(
                        self.x + self.padding,
                        y_offset + prod_surf.get_height() + 2,
                        progress_width,
                        8,
                    )
                    pygame.draw.rect(surface, (50, 200, 50), progress_rect)
                    pygame.draw.rect(surface, (100, 100, 100), bar_rect, 1)  # 边框

                    y_offset += self.line_spacing + 10

            # 资源生产
            if building_comp.resource_generation:
                res_text = "Resource Production:"
                res_surf = self.font.render(res_text, True, (200, 200, 200))
                surface.blit(res_surf, (self.x + self.padding, y_offset))
                y_offset += self.line_spacing

                res_names = {
                    "gold": "Gold",
                    "weapons": "Weapons",
                    "food": "Food",
                    "supplies": "Supplies",
                }
                for res_type, rate in building_comp.resource_generation.items():
                    if rate > 0:
                        name = res_names.get(res_type, res_type)
                        rate_text = f"  {name}: +{rate}/秒"
                        rate_surf = self.font.render(rate_text, True, (180, 180, 180))
                        surface.blit(rate_surf, (self.x + self.padding, y_offset))
                        y_offset += self.line_spacing

        super().render(surface)

    def _get_unit_type_name(self, unit_type):
        """获取单位类型的显示名称"""
        type_names = {
            UnitComponent.TYPE_SUPPLY: "Supply Unit",
            UnitComponent.TYPE_PLAINS: "Plains Unit",
            UnitComponent.TYPE_MOUNTAIN: "Mountain Unit",
            UnitComponent.TYPE_WATER: "Water Unit",
            UnitComponent.TYPE_RANGED: "Ranged Unit",
            UnitComponent.TYPE_AIR: "Air Unit",
        }
        return type_names.get(unit_type, unit_type)

    def _get_building_type_name(self, building_type):
        """获取建筑类型的显示名称"""
        type_names = {
            BuildingComponent.TYPE_HEADQUARTERS: "Headquarters",
            BuildingComponent.TYPE_SUPPLY_DEPOT: "Supply Depot",
            BuildingComponent.TYPE_FORTIFICATION: "Fortification",
        }
        return type_names.get(building_type, building_type)
