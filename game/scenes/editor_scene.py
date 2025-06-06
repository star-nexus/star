import os
import pygame
from framework.engine.scenes import Scene
from framework.ui import (
    UITransformComponent,
    ButtonComponent,
    PanelComponent,
    TextComponent,
)
from framework.ui.systems import UISystem
from framework.utils.logging_tool import get_logger
from framework.engine.events import EventType, EventMessage

from game.components import MapComponent, UnitComponent, CameraComponent, TileComponent
from game.systems import (
    MapSystem,
    MapRenderSystem,
    FogOfWarSystem,
    CameraSystem,
    UnitSystem,
    UnitRenderSystem,
    UnitMovementSystem,
    FogOfWarRenderSystem,
    UnitControlSystem,
    UnitAttackSystem,
    GameStatsSystem,
    TerrainEffectSystem,
)
from game.systems.unit.unit_health_system import UnitHealthSystem
from game.utils.game_types import UnitType, TerrainType
from game.prefab.prefab_factory import PrefabFactory


class EditorScene(Scene):
    def __init__(self, engine):
        super().__init__(engine)
        self.logger = get_logger("EditorScene")
        # 编辑场景所需的属性
        self.map_entity = None
        self.camera_entity = None
        self.units = []
        self.selected_units = []
        self.ui_entities = []
        self.status_entities = []  # 状态显示UI实体

        # 系统引用
        self.map_system = None
        self.camera_system = None
        self.map_render_system = None
        self.fog_of_war_system = None
        self.movement_system = None
        self.unit_system = None
        self.unit_render_system = None
        self.ui_system = None

        # 编辑器状态
        self.fog_of_war_enabled = True
        self.current_unit_type = UnitType.INFANTRY  # 默认为步兵单位
        self.current_faction = 0  # 默认为玩家阵营(0)
        self.edit_mode = "none"  # none, unit, map

    def enter(self, **kwargs):
        self.logger.info("进入编辑测试场景")
        super().enter(**kwargs)

        self.prefab_factory = PrefabFactory(self.world)

        _, map_component = self.prefab_factory.create_map("default")

        self.prefab_factory.create_camera("default")

        self.prefab_factory.create_fog_of_war(
            "default", map_component.width, map_component.height
        )

        self.prefab_factory.create_benchmark_unit(2)

        # 注册系统
        self.register_systems()

        # 创建UI实体
        self.create_ui_entities()

        # 创建状态显示
        self._create_status_display()

        # 订阅事件
        self.subscribe_events()

        self.logger.info("编辑测试场景初始化完成")

    def register_systems(self):
        """注册编辑场景所需的系统"""
        self.logger.debug("注册编辑场景系统")

        # 创建组件工厂
        # self.component_factory = PrefabFactory(self.world)

        # 创建地图系统
        self.map_system = MapSystem()
        self.map_system.initialize(self.world.context)
        self.world.add_system(self.map_system)

        # 创建摄像机系统
        self.camera_system = CameraSystem()
        self.camera_system.initialize(self.world.context)
        self.world.add_system(self.camera_system)

        # 创建地图渲染系统
        self.map_render_system = MapRenderSystem()
        self.map_render_system.initialize(self.world.context)
        self.world.add_system(self.map_render_system)

        # # 创建战争迷雾系统
        # self.fog_of_war_system = FogOfWarSystem()
        # self.fog_of_war_system.initialize(self.world.context)
        # self.world.add_system(self.fog_of_war_system)

        # # 创建战争迷雾渲染系统
        # self.fog_of_war_render_system = FogOfWarRenderSystem()
        # self.fog_of_war_render_system.initialize(self.world.context)
        # self.world.add_system(self.fog_of_war_render_system)

        # 创建移动系统
        self.movement_system = UnitMovementSystem()
        self.movement_system.initialize(self.world.context)
        self.world.add_system(self.movement_system)

        self.attack_system = UnitAttackSystem()
        self.attack_system.initialize(self.world.context)
        self.world.add_system(self.attack_system)

        # 创建单位系统
        self.unit_system = UnitSystem()
        self.unit_system.initialize(self.world.context)
        self.world.add_system(self.unit_system)

        # 创建单位渲染系统
        self.unit_render_system = UnitRenderSystem()
        self.unit_render_system.initialize(self.world.context)
        self.world.add_system(self.unit_render_system)

        self.unit_control_system = UnitControlSystem()
        self.unit_control_system.initialize(self.world.context)
        self.world.add_system(self.unit_control_system)

        # 统计
        self.game_stats_system = GameStatsSystem()
        self.game_stats_system.initialize(self.world.context)
        self.world.add_system(self.game_stats_system)

        # 地形效果系统
        self.terrain_effect_system = TerrainEffectSystem()
        self.terrain_effect_system.initialize(self.world.context)
        self.world.add_system(self.terrain_effect_system)

        # 单位生命值系统
        self.unit_health_system = UnitHealthSystem()
        self.unit_health_system.initialize(self.world.context)
        self.world.add_system(self.unit_health_system)

        # 创建UI系统
        self.ui_system = UISystem()
        self.ui_system.initialize(self.world.context)
        self.world.add_system(self.ui_system)

        self.logger.debug("编辑场景系统注册完成")

        # # 使用组件工厂创建地图
        # self.map_entity, map_component = self.component_factory.create_map("default")

        # # 设置地图系统的地图实体引用
        # self.map_system.set_map_entity(self.map_entity)

        # # 使用组件工厂创建相机
        # self.camera_entity, camera_component = self.component_factory.create_camera(
        #     "default"
        # )

        # # 设置相机系统的相机实体引用
        # if hasattr(self.camera_system, "set_camera_entity"):
        #     self.camera_system.set_camera_entity(self.camera_entity)

        # # 创建战争迷雾
        # self._create_fog_of_war()

        # 创建单位
        # self._create_units()

        # 设置摄像机与地图的关联
        # self.camera_system.set_map(self.map_entity)

    def _create_units(self):
        """创建单位"""
        self.logger.info("开始创建单位")
        self.units = []

        self.component_factory.create_unit(
            UnitType.INFANTRY,
            0,
            100,
            100,
            owner_id=0,
        )
        self.component_factory.create_unit(
            UnitType.INFANTRY,
            1,
            200,
            100,
            owner_id=1,
        )
        self.component_factory.create_unit(
            UnitType.INFANTRY,
            2,
            300,
            100,
            owner_id=2,
        )

    def create_ui_entities(self):
        """创建编辑器UI界面"""
        self.logger.info("开始创建编辑器UI实体")
        self.ui_entities = []

        screen_width, screen_height = self.engine.screen.get_size()

        # 创建侧边栏面板（用于单位类型选择）
        sidebar_panel = self.world.create_entity()
        self.world.add_component(
            sidebar_panel,
            UITransformComponent(
                x=screen_width - 150,
                y=100,
                width=140,
                height=300,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            sidebar_panel,
            PanelComponent(color=(60, 60, 90), border_width=1),
        )
        self.ui_entities.append(sidebar_panel)

        # 创建顶部工具栏面板
        toolbar_panel = self.world.create_entity()
        self.world.add_component(
            toolbar_panel,
            UITransformComponent(
                x=0,
                y=0,
                width=screen_width,
                height=50,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            toolbar_panel,
            PanelComponent(color=(60, 60, 90), border_width=1),
        )
        self.ui_entities.append(toolbar_panel)

        # 创建标题
        title_entity = self.world.create_entity()
        self.world.add_component(
            title_entity,
            UITransformComponent(x=100, y=25, visible=True, enabled=True),
        )
        self.world.add_component(
            title_entity,
            TextComponent(
                text="Editor",
                font_size=24,
                color=(255, 255, 255),
                centered=True,
            ),
        )
        self.ui_entities.append(title_entity)

        # 创建返回按钮
        back_button = self.world.create_entity()
        self.world.add_component(
            back_button,
            UITransformComponent(
                x=80,
                y=25,
                width=120,
                height=40,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            back_button,
            ButtonComponent(
                text="Back",
                callback=self._on_back_click,
            ),
        )
        self.ui_entities.append(back_button)

        # 创建重新生成地图按钮
        regen_map_button = self.world.create_entity()
        self.world.add_component(
            regen_map_button,
            UITransformComponent(
                x=220,
                y=25,
                width=120,
                height=40,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            regen_map_button,
            ButtonComponent(
                text="ReGen Map",
                callback=self._on_regen_map_click,
            ),
        )
        self.ui_entities.append(regen_map_button)

        # 创建切换战争迷雾按钮
        fog_button = self.world.create_entity()
        self.world.add_component(
            fog_button,
            UITransformComponent(
                x=360,
                y=25,
                width=120,
                height=40,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            fog_button,
            ButtonComponent(
                text="toggle fog",
                callback=self._on_toggle_fog_click,
            ),
        )
        self.ui_entities.append(fog_button)

        # 创建配置单位按钮
        unit_button = self.world.create_entity()
        self.world.add_component(
            unit_button,
            UITransformComponent(
                x=500,
                y=25,
                width=120,
                height=40,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            unit_button,
            ButtonComponent(
                text="config unit",
                callback=self._on_config_unit_click,
            ),
        )
        self.ui_entities.append(unit_button)

        # 创建配置地图按钮
        map_button = self.world.create_entity()
        self.world.add_component(
            map_button,
            UITransformComponent(
                x=640,
                y=25,
                width=120,
                height=40,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            map_button,
            ButtonComponent(
                text="config map",
                callback=self._on_config_map_click,
            ),
        )
        self.ui_entities.append(map_button)

        # 创建切换视角按钮
        view_button = self.world.create_entity()
        self.world.add_component(
            view_button,
            UITransformComponent(
                x=780,
                y=25,
                width=120,
                height=40,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            view_button,
            ButtonComponent(
                text="toggle view",
                callback=self._on_toggle_view_click,
            ),
        )
        self.ui_entities.append(view_button)

        # 创建单位类型选择按钮
        unit_types = [
            (UnitType.INFANTRY, "INFANTRY"),
            (UnitType.CAVALRY, "CAVALRY"),
            (UnitType.ARCHER, "ARCHER"),
            # (UnitType.SIEGE, "SIEGE"),
            # (UnitType.HERO, "HERO"),
        ]

        # 创建单位类型标题
        unit_type_title = self.world.create_entity()
        self.world.add_component(
            unit_type_title,
            UITransformComponent(
                x=screen_width - 80,
                y=120,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            unit_type_title,
            TextComponent(
                text="Unit Type",
                font_size=18,
                color=(255, 255, 255),
                centered=True,
            ),
        )
        self.ui_entities.append(unit_type_title)

        # 创建单位类型按钮
        for i, (unit_type, unit_name) in enumerate(unit_types):
            unit_type_button = self.world.create_entity()
            self.world.add_component(
                unit_type_button,
                UITransformComponent(
                    x=screen_width - 80,
                    y=160 + i * 50,
                    width=120,
                    height=40,
                    visible=True,
                    enabled=True,
                ),
            )
            self.world.add_component(
                unit_type_button,
                ButtonComponent(
                    text=unit_name,
                    callback=lambda ut=unit_type: self._on_unit_type_click(ut),
                ),
            )
            self.ui_entities.append(unit_type_button)

        # 创建阵营选择标题
        faction_title = self.world.create_entity()
        self.world.add_component(
            faction_title,
            UITransformComponent(
                x=screen_width - 80,
                y=400,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            faction_title,
            TextComponent(
                text="Faction",
                font_size=18,
                color=(255, 255, 255),
                centered=True,
            ),
        )
        self.ui_entities.append(faction_title)

        # 创建阵营选择按钮
        factions = [(0, "player"), (1, "enemy"), (2, "nuetral")]
        for i, (faction_id, faction_name) in enumerate(factions):
            faction_button = self.world.create_entity()
            self.world.add_component(
                faction_button,
                UITransformComponent(
                    x=screen_width - 80,
                    y=440 + i * 50,
                    width=120,
                    height=40,
                    visible=True,
                    enabled=True,
                ),
            )
            self.world.add_component(
                faction_button,
                ButtonComponent(
                    text=faction_name,
                    callback=lambda fid=faction_id: self._on_faction_click(fid),
                ),
            )
            self.ui_entities.append(faction_button)

        self.logger.info(f"创建了 {len(self.ui_entities)} 个UI实体")

    def subscribe_events(self):
        """订阅场景需要的事件"""
        self.logger.debug("订阅编辑场景事件")
        if self.engine.event_manager:
            # 订阅键盘事件
            self.engine.event_manager.subscribe(
                EventType.KEY_DOWN, self.handle_key_event
            )
            # 订阅鼠标事件
            self.engine.event_manager.subscribe(
                EventType.MOUSEBUTTON_DOWN, self.handle_mouse_event
            )
            self.logger.debug("编辑场景事件订阅成功")
        else:
            self.logger.warning("无法订阅编辑场景事件：事件管理器未设置")

    def exit(self):
        self.logger.info("退出编辑测试场景")

        # 移除所有UI实体
        self.logger.info(f"正在销毁 {len(self.ui_entities)} 个UI实体")
        for entity in self.ui_entities:
            self.world.destroy_entity(entity)
        self.ui_entities.clear()

        # 移除状态显示实体
        for entity in self.status_entities:
            self.world.destroy_entity(entity)
        self.status_entities.clear()

        # 移除所有单位实体
        if self.unit_system and hasattr(self.unit_system, "unit_entities"):
            for entity in list(self.unit_system.unit_entities):
                self.world.destroy_entity(entity)

        # 移除地图实体
        if self.map_entity:
            # 将摄像机与地图的引用解除
            if self.camera_system:
                self.camera_system.map_entity = None
                self.camera_system.map_component = None

            # 销毁地图中的所有格子实体
            if (
                hasattr(self.map_system, "map_component")
                and self.map_system.map_component
            ):
                map_component = self.map_system.map_component
                if hasattr(map_component, "tile_entities"):
                    for tile_entity in map_component.tile_entities.values():
                        self.world.destroy_entity(tile_entity)

            # 销毁地图实体
            self.world.destroy_entity(self.map_entity)
            self.map_entity = None

        # 移除所有组件
        self.logger.info("正在移除组件")
        self.world.component_manager.clear_components()
        self.logger.debug("组件移除完成")

        # 移除所有系统
        self.logger.info("正在移除系统")
        if self.ui_system:
            self.world.remove_system(self.ui_system)
        if self.unit_render_system:
            self.world.remove_system(self.unit_render_system)
        if self.unit_system:
            self.world.remove_system(self.unit_system)
        if self.movement_system:
            self.world.remove_system(self.movement_system)
        if self.fog_of_war_system:
            self.world.remove_system(self.fog_of_war_system)
        if self.map_render_system:
            self.world.remove_system(self.map_render_system)
        if self.camera_system:
            self.world.remove_system(self.camera_system)
        if self.map_system:
            self.world.remove_system(self.map_system)

        super().exit()
        self.logger.info("编辑测试场景资源清理完成")

    def update(self, delta_time):
        # 更新世界，这会调用所有系统的update方法
        super().update(delta_time)
        self.world.update(delta_time)

    def handle_key_event(self, event: EventMessage):
        """处理键盘事件"""
        if event.type == EventType.KEY_DOWN:
            key = event.data.get("key")
            if key == "m":
                self.logger.info("收到重新生成地图事件")
                self._on_regen_map_click()
            elif key == "f":
                self.logger.info("收到切换战争迷雾事件")
                self._on_toggle_fog_click()
            elif key == pygame.K_p:
                self.logger.msg("收到保存地图为图像事件")
                self._save_map_as_image()
            elif key == "escape":
                if self.edit_mode != "none":
                    self.logger.info("退出编辑模式")
                    self.edit_mode = "none"
                    self._update_status_display()
                else:
                    self.logger.info("取消选择单位")
                    if self.unit_system:
                        self.unit_system.deselect_unit()
                        self.selected_units = []

    def handle_mouse_event(self, event: EventMessage):
        """处理鼠标事件"""
        if event.type == EventType.MOUSEBUTTON_DOWN:
            button = event.data.get("button")
            pos = event.data.get("pos")

            if button == 1:  # 左键点击
                if self.edit_mode == "unit":
                    self._place_unit_at_position(pos)
                elif self.edit_mode == "map":
                    self._edit_map_at_position(pos)

    def _on_back_click(self):
        """返回按钮点击回调"""
        self.logger.info("用户点击了'返回'按钮")
        self.engine.scene_manager.load_scene("start")

    def _on_regen_map_click(self):
        """重新生成地图按钮点击回调"""
        self.logger.info("用户点击了'重新生成地图'按钮")
        # 使用组件工厂重新生成地图
        if hasattr(self, "component_factory"):
            # 清理旧地图
            if self.map_entity:
                # 销毁地图中的所有格子实体
                if (
                    hasattr(self.map_system, "map_component")
                    and self.map_system.map_component
                ):
                    map_component = self.map_system.map_component
                    if hasattr(map_component, "tile_entities"):
                        for tile_entity in map_component.tile_entities.values():
                            self.world.destroy_entity(tile_entity)
                # 销毁地图实体
                self.world.destroy_entity(self.map_entity)

            # 生成随机种子
            import random

            random_seed = random.randint(1, 999999)
            self.logger.info(f"使用随机种子生成地图: {random_seed}")

            # 修改地图生成配置中的种子
            from game.prefab.prefab_config.map_config import MAP_GENERATION_CONFIG

            MAP_GENERATION_CONFIG["default"]["seed"] = random_seed

            # 创建新地图
            self.map_entity, map_component = self.component_factory.create_map(
                "default"
            )

            # 重新创建战争迷雾
            self._create_fog_of_war()

            # 更新地图系统引用
            self.map_system.set_map_entity(self.map_entity)

    def _on_toggle_fog_click(self):
        """切换战争迷雾按钮点击回调"""
        self.logger.info("用户点击了'切换战争迷雾'按钮")
        self.fog_of_war_enabled = not self.fog_of_war_enabled
        if self.fog_of_war_system:
            self.fog_of_war_system.set_enabled(self.fog_of_war_enabled)
        self.logger.info(
            f"战争迷雾状态: {'开启' if self.fog_of_war_enabled else '关闭'}"
        )

    def _create_fog_of_war(self):
        """创建战争迷雾实体和组件"""
        if (
            not hasattr(self, "component_factory")
            or not self.map_system
            or not self.map_system.map_component
        ):
            self.logger.warning("无法创建战争迷雾：组件工厂或地图系统未初始化")
            return

        # 获取地图尺寸
        map_width = self.map_system.map_component.width
        map_height = self.map_system.map_component.height

        # 使用组件工厂创建战争迷雾
        fog_entity, fog_component = self.component_factory.create_fog_of_war(
            "default", map_width, map_height
        )

        # 设置战争迷雾系统的引用
        if self.fog_of_war_system:
            # self.fog_of_war_system.set_fog_entity(fog_entity)
            self.fog_of_war_system.set_enabled(self.fog_of_war_enabled)

        self.logger.info(f"创建了战争迷雾实体，尺寸: {map_width}x{map_height}")
        return fog_entity, fog_component

    def _on_config_unit_click(self):
        """配置单位按钮点击回调"""
        self.logger.info("用户点击了'配置单位'按钮")
        self.edit_mode = "unit" if self.edit_mode != "unit" else "none"
        self.logger.info(
            f"编辑模式: {'配置单位' if self.edit_mode == 'unit' else '无'}"
        )
        self._update_status_display()

    def _on_unit_type_click(self, unit_type):
        """单位类型按钮点击回调"""
        self.current_unit_type = unit_type
        self.logger.info(f"选择单位类型: {unit_type.name}")
        # 自动切换到单位编辑模式
        if self.edit_mode != "unit":
            self.edit_mode = "unit"
            self.logger.info("自动切换到单位编辑模式")
        self._update_status_display()

    def _on_faction_click(self, faction_id):
        """阵营选择按钮点击回调"""
        self.current_faction = faction_id
        faction_names = {0: "player", 1: "enemy", 2: "neutral"}
        self.logger.info(f"选择阵营: {faction_names.get(faction_id, str(faction_id))}")
        self._update_status_display()

    def _save_map_as_image(self):
        """将当前地图（包括单位）保存为图像文件"""
        import pygame
        import os
        import datetime

        self.logger.msg("开始保存地图为图像...")

        map_entity = self.world.context.with_all(MapComponent).first()
        map_component = self.world.context.get_component(map_entity, MapComponent)
        if not map_component:
            self.logger.error("无法保存地图：地图组件未初始化")
            return

        # 计算完整地图的尺寸
        tile_size = map_component.tile_size
        map_width_px = map_component.width * tile_size
        map_height_px = map_component.height * tile_size

        self.logger.info(f"地图尺寸: {map_width_px}x{map_height_px} 像素")

        # 创建一个足够大的surface来容纳整个地图，使用RGB模式而不是RGBA
        map_surface = pygame.Surface((map_width_px, map_height_px), pygame.SRCALPHA)
        # 填充白色背景，确保不是透明的
        map_surface.fill((255, 255, 255, 255))

        # 保存当前相机状态
        original_camera_x = None
        original_camera_y = None
        original_camera_zoom = None

        if self.camera_system and hasattr(self.camera_system, "camera_component"):
            camera_component = self.camera_system.camera_component
            original_camera_x = camera_component.x
            original_camera_y = camera_component.y
            original_camera_zoom = camera_component.zoom

            # 临时设置相机以覆盖整个地图
            camera_component.x = map_width_px / 2
            camera_component.y = map_height_px / 2
            camera_component.zoom = 1.0

        # 渲染地图到surface
        if self.map_render_system:
            # 渲染所有地形格子
            for (x, y), tile_entity in map_component.tile_entities.items():
                tile_component = self.world.get_component(tile_entity, TileComponent)
                if tile_component:
                    # 计算格子在surface上的位置
                    pos_x = x * tile_size
                    pos_y = y * tile_size

                    # 使用地图渲染系统的方法渲染格子
                    tile_surface = self.map_render_system._render_tile(
                        tile_component, tile_size
                    )
                    map_surface.blit(tile_surface, (pos_x, pos_y))

        # 渲染单位到surface
        if (
            self.unit_render_system
            and self.unit_system
            and hasattr(self.unit_system, "unit_entities")
        ):
            for unit_entity in self.unit_system.unit_entities:
                unit_component = self.world.get_component(unit_entity, UnitComponent)
                if unit_component:
                    # 计算单位在surface上的位置 - 使用格子坐标乘以格子大小
                    grid_x = int(unit_component.position_x / tile_size)
                    grid_y = int(unit_component.position_y / tile_size)
                    pos_x = grid_x * tile_size
                    pos_y = grid_y * tile_size

                    # 使用单位渲染系统的_render_unit_surface方法渲染单位
                    # 而不是_get_unit_texture，因为前者会渲染完整的单位（包括状态、血条等）
                    unit_surface = self.unit_render_system._render_unit_surface(
                        unit_component, tile_size
                    )
                    if unit_surface:
                        map_surface.blit(unit_surface, (pos_x, pos_y))

        # 恢复相机状态
        if (
            self.camera_system
            and hasattr(self.camera_system, "camera_component")
            and original_camera_x is not None
        ):
            camera_component = self.camera_system.camera_component
            camera_component.x = original_camera_x
            camera_component.y = original_camera_y
            camera_component.zoom = original_camera_zoom

        # 创建保存目录
        save_dir = os.path.join(os.getcwd(), "screenshots")
        os.makedirs(save_dir, exist_ok=True)

        # 生成文件名（使用当前时间戳）
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"map_{timestamp}.png"
        filepath = os.path.join(save_dir, filename)

        # 保存图像
        pygame.image.save(map_surface, filepath)

        self.logger.info(f"地图已保存为图像: {filepath}")

        # 显示保存成功消息
        # self._show_save_success_message(filepath)

    def _show_save_success_message(self, filepath):
        """显示保存成功的消息"""
        # 创建一个临时UI实体显示保存成功消息
        screen_width, screen_height = self.engine.screen.get_size()

        # 创建消息面板
        message_panel = self.world.create_entity()
        self.world.add_component(
            message_panel,
            UITransformComponent(
                x=screen_width // 2,
                y=100,
                width=400,
                height=80,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            message_panel,
            PanelComponent(color=(60, 100, 60), border_width=2),
        )

        # 创建消息文本
        message_text = self.world.create_entity()
        self.world.add_component(
            message_text,
            UITransformComponent(
                x=screen_width // 2,
                y=100,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            message_text,
            TextComponent(
                text=f"地图已保存为图像\n{os.path.basename(filepath)}",
                font_size=18,
                color=(255, 255, 255),
                centered=True,
            ),
        )
        self.logger.msg(f"地图已保存为图像\n{os.path.basename(filepath)}")
        # 将消息实体添加到临时列表中
        self.status_entities.append(message_panel)
        self.status_entities.append(message_text)

        # 设置定时器，3秒后移除消息
        import threading

        timer = threading.Timer(3.0, self._remove_save_message)
        timer.start()

    def _remove_save_message(self):
        """移除保存成功的消息"""
        # 移除所有状态显示实体
        for entity in self.status_entities:
            self.world.destroy_entity(entity)
        self.status_entities.clear()

    def _on_config_map_click(self):
        """配置地图按钮点击回调"""
        self.logger.info("用户点击了'配置地图'按钮")
        self.edit_mode = "map" if self.edit_mode != "map" else "none"
        self.logger.info(f"编辑模式: {'配置地图' if self.edit_mode == 'map' else '无'}")
        self._update_status_display()

    def _on_toggle_view_click(self):
        """切换视角按钮点击回调"""
        self.logger.info("用户点击了'切换视角'按钮")
        if self.camera_system:
            self.camera_system.toggle_zoom()

    def _place_unit_at_position(self, pos):
        """在指定位置放置单位"""
        if (
            not self.map_system
            or not self.unit_system
            or not hasattr(self, "component_factory")
        ):
            return

        # 将屏幕坐标转换为地图坐标
        map_x, map_y = self.camera_system.screen_to_world(pos[0], pos[1])
        tile_x, tile_y = (
            int(map_x / self.map_system.map_component.tile_size),
            int(map_y / self.map_system.map_component.tile_size),
        )

        # 检查坐标是否在地图范围内
        if not self._is_valid_map_position(tile_x, tile_y):
            return

        # 使用组件工厂创建单位
        unit_entity, unit_component = self.component_factory.create_unit(
            self.current_unit_type, self.current_faction, tile_x, tile_y, level=1
        )

        # 将单位添加到单位系统中跟踪
        if hasattr(self.unit_system, "unit_entities"):
            self.unit_system.unit_entities.add(unit_entity)

        self.logger.info(
            f"在位置 ({tile_x}, {tile_y}) 放置了 {unit_component.name} 单位，类型: {self.current_unit_type.name}, 阵营: {self.current_faction}"
        )

    def _edit_map_at_position(self, pos):
        """在指定位置编辑地图"""
        if not self.map_system:
            return

        # 将屏幕坐标转换为地图坐标
        map_x, map_y = self.camera_system.screen_to_world(pos[0], pos[1])
        tile_x, tile_y = int(map_x), int(map_y)

        # 检查坐标是否在地图范围内
        if not self._is_valid_map_position(tile_x, tile_y):
            return

        self.logger.info(f"在位置 ({tile_x}, {tile_y}) 编辑地图")

        # 获取当前格子实体和组件
        map_component = self.map_system.map_component
        tile_entity = map_component.tile_entities.get((tile_x, tile_y))
        if not tile_entity:
            self.logger.warning(f"在位置 ({tile_x}, {tile_y}) 未找到格子实体")
            return

        tile_component = self.world.get_component(tile_entity, TileComponent)
        if not tile_component:
            self.logger.warning(f"在位置 ({tile_x}, {tile_y}) 未找到格子组件")
            return

        # 修改地形类型 - 循环切换地形类型
        current_terrain = tile_component.terrain_type
        terrain_types = list(TerrainType)
        current_index = terrain_types.index(current_terrain)
        next_index = (current_index + 1) % len(terrain_types)
        new_terrain = terrain_types[next_index]

        # 更新地形类型
        tile_component.terrain_type = new_terrain

        # 根据地形类型更新移动成本和防御加成
        if new_terrain == TerrainType.PLAIN:
            tile_component.movement_cost = 1.0
            tile_component.defense_bonus = 0.0
        elif new_terrain == TerrainType.HILL:
            tile_component.movement_cost = 2.0
            tile_component.defense_bonus = 0.2
        elif new_terrain == TerrainType.MOUNTAIN:
            tile_component.movement_cost = 3.0
            tile_component.defense_bonus = 0.4
        elif new_terrain == TerrainType.FOREST:
            tile_component.movement_cost = 1.5
            tile_component.defense_bonus = 0.3
        elif new_terrain == TerrainType.RIVER:
            tile_component.movement_cost = 2.0
            tile_component.defense_bonus = -0.1
            tile_component.has_river = True
        elif new_terrain == TerrainType.ROAD:
            tile_component.movement_cost = 0.5
            tile_component.defense_bonus = 0.0
            tile_component.has_road = True
        else:
            # 默认值
            tile_component.movement_cost = 1.0
            tile_component.defense_bonus = 0.0

        self.logger.info(
            f"将位置 ({tile_x}, {tile_y}) 的地形从 {current_terrain.name} 修改为 {new_terrain.name}"
        )

        # 更新地图数据
        map_component.terrain_map[tile_y, tile_x] = new_terrain.value

    def _is_valid_map_position(self, x, y):
        """检查坐标是否在地图范围内"""
        if not self.map_system or not self.map_system.map_component:
            return False

        map_component = self.map_system.map_component
        return 0 <= x < map_component.width and 0 <= y < map_component.height

    def _create_status_display(self):
        """创建状态显示UI"""
        self.logger.info("创建状态显示UI")
        screen_width, screen_height = self.engine.screen.get_size()

        # 创建状态面板
        status_panel = self.world.create_entity()
        self.world.add_component(
            status_panel,
            UITransformComponent(
                x=10,
                y=screen_height - 40,
                width=400,
                height=30,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            status_panel,
            PanelComponent(color=(40, 40, 60), border_width=1),
        )
        self.status_entities.append(status_panel)

        # 创建状态文本
        status_text = self.world.create_entity()
        self.world.add_component(
            status_text,
            UITransformComponent(
                x=210,
                y=screen_height - 25,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            status_text,
            TextComponent(
                text="Mode: None",
                font_size=16,
                color=(255, 255, 255),
                centered=True,
            ),
        )
        self.status_entities.append(status_text)

        self._update_status_display()

    def _update_status_display(self):
        """更新状态显示"""
        if not self.status_entities or len(self.status_entities) < 2:
            return

        # 获取状态文本实体
        status_text_entity = self.status_entities[1]
        text_component = self.world.get_component(status_text_entity, TextComponent)
        if not text_component:
            return

        # 获取当前模式文本
        mode_text = "none"
        if self.edit_mode == "unit":
            unit_type_name = (
                self.current_unit_type.name if self.current_unit_type else "未选择"
            )
            faction_names = {0: "player", 1: "enemy", 2: "neutral"}
            faction_name = faction_names.get(
                self.current_faction, str(self.current_faction)
            )
            mode_text = f"config unit - type: {unit_type_name}, camp: {faction_name}"
        elif self.edit_mode == "map":
            mode_text = "config map - 点击修改地形"

        # 更新文本
        text_component.text = f"Mode: {mode_text}"

    def regenerate_map(self):
        """重新生成地图"""
        self.logger.info("开始重新生成地图")

        # 移除旧地图实体
        if self.map_entity:
            # 将摄像机与地图的引用解除
            if self.camera_system:
                self.camera_system.map_entity = None
                self.camera_system.map_component = None

            # 销毁地图中的所有格子实体
            if (
                hasattr(self.map_system, "map_component")
                and self.map_system.map_component
            ):
                map_component = self.map_system.map_component
                if hasattr(map_component, "tile_entities"):
                    for tile_entity in map_component.tile_entities.values():
                        self.world.destroy_entity(tile_entity)

            # 销毁地图实体
            self.world.destroy_entity(self.map_entity)
            self.map_entity = None

        # 生成新地图
        import random

        seed = random.randint(1, 100000)
        self.map_entity = self.map_system.generate_map(20, 20, seed=seed)

        # 重新设置相机与地图的关联
        self.camera_system.set_map(self.map_entity)
        self.logger.info("地图重新生成完成")
