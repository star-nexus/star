import pygame
from framework.ui.ui_text import UIText
from rts.ui.resource_display import ResourceDisplay
from rts.ui.minimap import Minimap
from rts.ui.entity_info_panel import EntityInfoPanel


class RTSUIManager:
    """
    RTS游戏UI管理器：负责创建和更新游戏中的UI元素
    """

    def __init__(self, scene):
        self.scene = scene
        self.game = scene.game

        # UI引用
        self.resource_display = None
        self.minimap = None
        self.entity_info_panel = None
        self.faction_info = None
        self.resource_info = None

        # 创建字体
        self.normal_font = pygame.font.SysFont("arial", 16)
        self.title_font = pygame.font.SysFont("arial", 20, bold=True)

    def create_ui(self):
        """创建游戏UI元素"""
        screen_width = self.game.width
        screen_height = self.game.height

        # 创建基本信息文本UI (仍然保留用于调试)
        self.faction_info = self.scene.add_ui_element(
            UIText(
                10,
                10,
                "Faction: None",
                self.normal_font,
                (255, 255, 200),
                centered=False,
            )
        )

        self.resource_info = self.scene.add_ui_element(
            UIText(
                10,
                30,
                "Resources: Gold=0 Weapons=0 Food=0 Supplies=0",
                self.normal_font,
                (255, 255, 200),
                centered=False,
            )
        )

        # 创建使用说明指南
        instructions = self.scene.add_ui_element(
            UIText(
                10,
                screen_height - 25,
                "WASD/Arrow Keys: Move View | Middle Mouse: Drag View | +/-: Zoom | Space: Regenerate Map",
                self.normal_font,
                (200, 200, 200),
                centered=False,
            )
        )

        # 创建资源显示面板
        resource_panel_height = 60
        self.resource_display = ResourceDisplay(
            0, 0, screen_width, resource_panel_height
        )
        self.resource_display.set_font(self.normal_font)
        self.scene.add_ui_element(self.resource_display)

        # 创建小地图
        minimap_size = 200
        minimap_padding = 10
        minimap_x = screen_width - minimap_size - minimap_padding
        minimap_y = screen_height - minimap_size - minimap_padding
        self.minimap = Minimap(minimap_x, minimap_y, minimap_size, minimap_size)
        if self.scene.map_manager and self.scene.map_manager.map_data:
            self.minimap.set_map_data(
                self.scene.map_manager.map_data, self.scene.map_manager.map_renderer
            )
        self.scene.add_ui_element(self.minimap)

        # 创建实体信息面板
        info_panel_width = 250
        info_panel_height = 300
        info_panel_x = 10
        info_panel_y = screen_height - info_panel_height - 30  # 30为底部说明文本的高度
        self.entity_info_panel = EntityInfoPanel(
            info_panel_x, info_panel_y, info_panel_width, info_panel_height
        )
        self.entity_info_panel.set_fonts(self.title_font, self.normal_font)
        self.scene.add_ui_element(self.entity_info_panel)

    def update_faction_ui(self, faction_system):
        """更新阵营和资源信息UI"""
        player_faction = faction_system.get_player_faction()
        if player_faction:
            from rts.components import FactionComponent, ResourceComponent

            faction_comp = player_faction.get_component(FactionComponent)
            self.faction_info.set_text(f"Faction: {faction_comp.faction_name}")

            if player_faction.has_component(ResourceComponent):
                res_comp = player_faction.get_component(ResourceComponent)
                # 更新文本资源信息 (用于调试)
                self.resource_info.set_text(
                    f"Resources: Gold={int(res_comp.gold)} Weapons={int(res_comp.weapons)} "
                    f"Food={int(res_comp.food)} Supplies={int(res_comp.supplies)}"
                )

                # 更新资源显示面板
                if self.resource_display:
                    self.resource_display.update_resources(res_comp)

    def update_minimap(self, offset_x, offset_y, viewport_width, viewport_height):
        """更新小地图视口信息"""
        if self.minimap:
            self.minimap.update_viewport(
                offset_x, offset_y, viewport_width, viewport_height
            )

            # 如果地图数据改变，重新设置小地图
            if self.scene.map_manager and self.scene.map_manager.map_data:
                if self.minimap.need_redraw:
                    self.minimap.set_map_data(
                        self.scene.map_manager.map_data,
                        self.scene.map_manager.map_renderer,
                    )

    def set_selected_entity(self, entity):
        """设置当前选中的实体"""
        if self.entity_info_panel:
            self.entity_info_panel.set_entity(entity)

    def handle_minimap_click(self, pos):
        """处理小地图点击，返回地图坐标或None"""
        if self.minimap:
            return self.minimap.handle_click(pos)
        return None
