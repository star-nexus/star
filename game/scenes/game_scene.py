from framework.engine.scenes import Scene
from framework.utils.logging import get_logger
from framework.engine.events import EventMessage, EventType
from framework.ui import (
    UITransformComponent,
    ButtonComponent,
    PanelComponent,
    TextComponent,
)
from framework.ui.systems import UISystem
from game.components.map import map_component
from game.systems import MapSystem, CameraSystem, MapRenderSystem
from game.systems import UnitSystem
from game.systems import UnitRenderSystem
from game.systems import UnitMovementSystem
from game.systems import UnitAttackSystem
from game.systems import UnitControlSystem
from game.systems import UnitAIControlSystem
from game.systems import GameStatsSystem, ViewMode
from game.systems import FogOfWarSystem
from game.systems import LLMControlSystem

from game.config.prefab_factory import PrefabFactory

from game.utils import UnitType
from game.components import UnitComponent


class GameScene(Scene):
    def __init__(self, engine):
        super().__init__(engine)
        # 游戏场景所需的属性
        self.logger = get_logger("GameScene")
        self.map_entity = None
        self.camera_entity = None
        self.units = []
        self.selected_units = []
        self.ui_entities = []  # UI实体列表
        self.status_entities = []  # 状态显示UI实体
        self.event_log = []  # 事件日志列表
        self.max_event_logs = 10  # 最大显示事件数量

        # 系统引用
        self.map_system = None
        self.camera_system = None
        self.map_render_system = None
        self.movement_system = None
        self.attack_system = None
        self.ai_controller_system = None
        self.llm_controller_system = None
        self.unit_system = None
        self.unit_render_system = None
        self.game_stats_system = None
        self.ui_system = None  # UI系统引用

    def enter(self, **kwargs):
        self.logger.info("进入游戏场景")
        super().enter(**kwargs)

        # 创建组件工厂
        self.prefab_factory = PrefabFactory(self.world)

        # 订阅事件
        self.subscribe_events()

        # 使用组件工厂创建地图
        self.prefab_factory.create_map("default")

        # 设置地图系统的地图实体引用
        # self.map_system.set_map_entity(map_entity)

        # 使用组件工厂创建相机
        self.prefab_factory.create_camera("default")

        # self.camera_system.set_camera_entity(camera_entity)

        # 创建战争迷雾
        # self._create_fog_of_war()

        # 创建单位
        self._create_units()

        # 创建UI界面
        self.create_ui_entities()

        # 创建状态信息面板
        self._create_status_display()

        # 注册系统, 注意顺序，要最后注册
        self.register_systems()
        self.logger.info("游戏场景初始化完成")

    def _create_units(self):
        """创建单位"""
        self.logger.info("开始创建单位")
        # self.units = []

        self.prefab_factory.create_unit(
            UnitType.INFANTRY,
            0,
            100,
            100,
            owner_id=0,
        )
        self.prefab_factory.create_unit(
            UnitType.INFANTRY,
            0,
            150,
            100,
            owner_id=0,
        )
        self.prefab_factory.create_unit(
            UnitType.INFANTRY,
            1,
            200,
            100,
            owner_id=1,
        )
        self.prefab_factory.create_unit(
            UnitType.ARCHER,
            1,
            200,
            150,
            owner_id=1,
        )
        self.prefab_factory.create_unit(
            UnitType.CAVALRY,
            1,
            200,
            200,
            owner_id=1,
        )

        self.prefab_factory.create_battle_stats(1)

        self.prefab_factory.create_unit(
            UnitType.INFANTRY,
            2,
            300,
            100,
            owner_id=2,
        )
        self.prefab_factory.create_unit(
            UnitType.ARCHER,
            2,
            300,
            150,
            owner_id=2,
        )
        self.prefab_factory.create_unit(
            UnitType.CAVALRY,
            2,
            300,
            200,
            owner_id=2,
        )
        self.prefab_factory.create_battle_stats(2)

    def register_systems(self):
        """注册游戏所需的系统"""
        self.logger.debug("注册游戏系统")
        # 创建地图系统
        map_system = MapSystem()
        map_system.initialize(self.world.context)
        self.world.add_system(map_system)
        self.map_system = map_system
        # 创建摄像机系统
        camera_system = CameraSystem()
        camera_system.initialize(self.world.context)
        self.world.add_system(camera_system)
        self.camera_system = camera_system
        # 创建地图渲染系统
        map_render_system = MapRenderSystem()
        map_render_system.initialize(self.world.context)
        self.world.add_system(map_render_system)
        self.map_render_system = map_render_system
        # 创建战争迷雾系统
        # fog_of_war_system = FogOfWarSystem()
        # fog_of_war_system.initialize(self.world.context)
        # self.world.add_system(fog_of_war_system)
        # self.fog_of_war_system = fog_of_war_system
        # 创建AI控制系统（必须在移动和攻击系统之前创建）
        # ai_controller_system = UnitAIControlSystem()
        # ai_controller_system.initialize(self.world.context)
        # self.world.add_system(ai_controller_system)
        # self.ai_controller_system = ai_controller_system

        # 创建LLM控制系统（必须在移动和攻击系统之前创建）
        llm_controller_system = LLMControlSystem()
        llm_controller_system.initialize(self.world.context)
        self.world.add_system(llm_controller_system)
        self.llm_controller_system = llm_controller_system

        # 创建移动系统（必须在单位系统之前创建）
        movement_system = UnitMovementSystem()
        movement_system.initialize(self.world.context)
        self.world.add_system(movement_system)
        self.movement_system = movement_system

        attack_system = UnitAttackSystem()
        attack_system.initialize(self.world.context)
        self.world.add_system(attack_system)
        self.attack_system = attack_system
        # 创建单位系统
        unit_system = UnitSystem()
        unit_system.initialize(self.world.context)
        self.world.add_system(unit_system)
        self.unit_system = unit_system
        # 创建单位渲染系统
        unit_render_system = UnitRenderSystem()
        unit_render_system.initialize(self.world.context)
        self.world.add_system(unit_render_system)
        self.unit_render_system = unit_render_system

        unit_control_system = UnitControlSystem()
        unit_control_system.initialize(self.world.context)
        self.world.add_system(unit_control_system)
        self.unit_control_system = unit_control_system

        # 创建游戏状态统计系统
        game_stats_system = GameStatsSystem()
        game_stats_system.initialize(self.world.context)
        self.world.add_system(game_stats_system)
        self.game_stats_system = game_stats_system

        # 创建UI系统
        ui_system = UISystem()
        ui_system.initialize(self.world.context)
        self.world.add_system(ui_system)
        self.ui_system = ui_system

        self.logger.debug("游戏系统注册完成")
        # 创建测试单位
        # self.create_test_units()

    def exit(self):
        self.logger.info("退出游戏场景")
        # 移除所有实体 - 使用列表复制防止迭代时修改集合
        self.logger.debug("移除游戏实体")
        self.world.entity_manager.clear_entities
        self.logger.debug("游戏实体移除完成")

        # 移除所有组件
        self.logger.debug("移除游戏组件")
        self.world.component_manager.clear_components()
        self.logger.debug("游戏组件移除完成")

        # 移除所有系统
        self.logger.debug("移除游戏系统")
        if self.unit_render_system:
            self.world.remove_system(self.unit_render_system)
        if self.unit_system:
            self.world.remove_system(self.unit_system)
        if self.movement_system:
            self.world.remove_system(self.movement_system)
        if self.attack_system:
            self.world.remove_system(self.attack_system)
        if self.ai_controller_system:
            self.world.remove_system(self.ai_controller_system)
        if self.map_render_system:
            self.world.remove_system(self.map_render_system)
        if self.camera_system:
            self.world.remove_system(self.camera_system)
        if self.map_system:
            self.world.remove_system(self.map_system)
        if self.game_stats_system:
            self.world.remove_system(self.game_stats_system)
        if self.ui_system:
            self.world.remove_system(self.ui_system)

        self.logger.debug("游戏系统移除完成")
        # 清理游戏场景资源
        super().exit()
        self.logger.debug("游戏场景资源清理完成")

    def update(self, delta_time):
        # 更新世界，这会调用所有系统的update方法
        self.world.update(delta_time)
        # 胜负条件检查已移至 _handle_unit_killed_event 和 _check_win_loss_conditions
        # self._check_win_loss_conditions() # 避免在每帧都检查，只在单位死亡时检查

    def subscribe_events(self):
        """订阅场景需要的事件"""
        self.logger.debug("订阅场景事件")
        if self.engine.event_manager:
            # 订阅键盘事件
            # self.engine.event_manager.subscribe(
            #     EventType.KEY_DOWN, self.unit_control_system.handle_key_event
            # )
            # # 订阅鼠标事件
            # self.engine.event_manager.subscribe(
            #     EventType.MOUSEBUTTON_DOWN, self.unit_control_system.handle_mouse_event
            # )
            self.engine.event_manager.subscribe(
                EventType.UNIT_KILLED, self._handle_unit_killed_event
            )
            self.logger.info("GameScene subscribed to UNIT_KILLED event.")

            # 订阅单位选择事件
            self.engine.event_manager.subscribe(
                EventType.UNIT_SELECTED, self._handle_unit_selected_event
            )
            self.logger.info("GameScene subscribed to UNIT_SELECTED event.")

            # 订阅单位移动事件
            self.engine.event_manager.subscribe(
                EventType.UNIT_MOVED, self._handle_unit_moved_event
            )
            self.logger.info("GameScene subscribed to UNIT_MOVED event.")

            # 订阅单位攻击事件
            self.engine.event_manager.subscribe(
                EventType.UNIT_ATTACKED, self._handle_unit_attacked_event
            )
            self.logger.info("GameScene subscribed to UNIT_ATTACKED event.")

            self.logger.debug("场景事件订阅成功")
        else:
            self.logger.warning("无法订阅场景事件：事件管理器未设置")

    def _handle_unit_killed_event(self, event: EventMessage):
        self.logger.info(f"GameScene: Unit killed event received: {event.data}")
        # 在这里可以更新游戏统计数据，例如 GameStatsSystem
        if self.game_stats_system:
            killer_entity = event.data.get("killer")
            killed_entity = event.data.get("target")
            if killer_entity and killed_entity:
                killer_comp = self.world.get_component(killer_entity, UnitComponent)
                killed_comp = self.world.get_component(killed_entity, UnitComponent)
                if killer_comp and killed_comp:
                    self.game_stats_system.record_kill(
                        killer_comp.owner_id, killed_comp.owner_id
                    )

                    # 添加到事件日志
                    killer_type = (
                        killer_comp.unit_type.name
                        if hasattr(killer_comp, "unit_type")
                        else "未知单位"
                    )
                    killed_type = (
                        killed_comp.unit_type.name
                        if hasattr(killed_comp, "unit_type")
                        else "未知单位"
                    )
                    log_message = f"Player {killer_comp.owner_id}'s {killer_type} kill Player {killed_comp.owner_id}'s {killed_type}"
                    self._add_event_log(log_message)

        # 检查胜负条件，确保在事件处理中调用
        self._check_win_loss_conditions()

        # 更新状态面板
        self._update_status_display()

    def _check_win_loss_conditions(self):
        # 示例：检查玩家0是否所有单位都已阵亡 (失败条件)
        # 示例：检查AI（例如玩家1）是否所有单位都已阵亡 (胜利条件)
        player_0_units_alive = 0
        ai_player_units_alive = 0  # 假设AI是玩家1

        for entity, (unit_comp,) in self.world.context.with_all(
            UnitComponent
        ).iter_components(UnitComponent):
            if unit_comp.owner_id == 0 and unit_comp.is_alive:
                player_0_units_alive += 1
            elif (
                unit_comp.owner_id != 0 and unit_comp.is_alive
            ):  # 简单假设非玩家0的都是AI
                ai_player_units_alive += 1

        # 确保场景仍在游戏中，避免重复跳转
        # if self.engine.scene_manager.current_scene_name != "game":
        #     return

        if player_0_units_alive == 0:
            self.logger.info("玩家0所有单位已阵亡，游戏失败！")
            self.engine.scene_manager.load_scene(
                "end", result="defeat", reason="All our units have been eliminated"
            )
            return

        if ai_player_units_alive == 0:
            self.logger.info("所有敌方单位已阵亡，游戏胜利！")
            self.engine.scene_manager.load_scene(
                "end", result="victory", reason="Successfully eliminate all enemy units"
            )
            return

    def handle_custom_event(self, event: EventMessage):
        """处理自定义事件"""
        if event.type == EventType.KEY_DOWN:
            if event.data.get("key") == "m":
                self.logger.info("收到重新生成地图事件")
                self.regenerate_map()
            elif event.data.get("key") == "r":
                self.logger.info("重置单位回合状态")
                if self.unit_system:
                    self.unit_system.reset_units_turn()
            elif event.data.get("key") == "escape":
                self.logger.info("取消选择单位")
                if self.unit_system:
                    self.unit_system.deselect_unit()
                    self.selected_units = []
                    # 更新状态面板
                    self._update_status_display()

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
        self.initialize_map()

        # 重新设置相机与地图的关联
        self.camera_system.set_map(self.map_entity)
        self.logger.info("地图重新生成完成")

    def create_ui_entities(self):
        """创建游戏UI界面"""
        self.logger.info("开始创建游戏UI实体")
        self.ui_entities = []

        screen_width, screen_height = self.engine.screen.get_size()

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
                text="RoTK",
                font_size=24,
                color=(255, 255, 255),
                centered=True,
            ),
        )
        self.ui_entities.append(title_entity)

    def _create_status_display(self):
        """创建状态信息面板"""
        self.logger.info("创建状态信息面板")
        self.status_entities = []

        screen_width, screen_height = self.engine.screen.get_size()

        # 创建状态面板背景
        status_panel = self.world.create_entity()
        self.world.add_component(
            status_panel,
            UITransformComponent(
                x=screen_width - 300,
                y=60,
                width=280,
                height=400,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            status_panel,
            PanelComponent(color=(40, 40, 60), border_width=1),
        )
        self.status_entities.append(status_panel)

        # 创建状态面板标题
        status_title = self.world.create_entity()
        self.world.add_component(
            status_title,
            UITransformComponent(
                x=screen_width - 150,
                y=80,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            status_title,
            TextComponent(
                text="status info",
                font_size=20,
                color=(255, 255, 255),
                centered=True,
            ),
        )
        self.status_entities.append(status_title)

        # 创建单位信息标题
        unit_info_title = self.world.create_entity()
        self.world.add_component(
            unit_info_title,
            UITransformComponent(
                x=screen_width - 150,
                y=110,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            unit_info_title,
            TextComponent(
                text="select unit info",
                font_size=16,
                color=(220, 220, 220),
                centered=True,
            ),
        )
        self.status_entities.append(unit_info_title)

        # 创建单位信息文本
        unit_info_text = self.world.create_entity()
        self.world.add_component(
            unit_info_text,
            UITransformComponent(
                x=screen_width - 280,
                y=140,
                width=260,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            unit_info_text,
            TextComponent(
                text="select nothing",
                font_size=14,
                color=(200, 200, 200),
                centered=False,
            ),
        )
        self.status_entities.append(unit_info_text)

        # 创建事件日志标题
        event_log_title = self.world.create_entity()
        self.world.add_component(
            event_log_title,
            UITransformComponent(
                x=screen_width - 150,
                y=250,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            event_log_title,
            TextComponent(
                text="event log",
                font_size=16,
                color=(220, 220, 220),
                centered=True,
            ),
        )
        self.status_entities.append(event_log_title)

        # 创建事件日志文本
        event_log_text = self.world.create_entity()
        self.world.add_component(
            event_log_text,
            UITransformComponent(
                x=screen_width - 280,
                y=280,
                width=260,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            event_log_text,
            TextComponent(
                text="game start...",
                font_size=14,
                color=(200, 200, 200),
                centered=False,
            ),
        )
        self.status_entities.append(event_log_text)

    def _add_event_log(self, message):
        """添加事件日志"""
        self.event_log.append(message)
        # 保持日志数量在限制范围内
        if len(self.event_log) > self.max_event_logs:
            self.event_log.pop(0)  # 移除最旧的日志
        self._update_status_display()

    def _update_status_display(self):
        """更新状态信息面板"""
        # 更新单位信息
        unit_info_text = None
        for entity in self.status_entities:
            text_comp = self.world.get_component(entity, TextComponent)
            if (
                text_comp
                and "select nothing" in text_comp.text
                or "unit type" in text_comp.text
            ):
                unit_info_text = text_comp
                break

        if unit_info_text:
            if self.selected_units:
                info_text = ""
                for unit_entity in self.selected_units:
                    unit_comp = self.world.get_component(unit_entity, UnitComponent)
                    if unit_comp:
                        info_text += f"unit type: {unit_comp.unit_type.name}\n"
                        info_text += f"own player: {unit_comp.owner_id}\n"
                        info_text += f"HP: {unit_comp.health}/{unit_comp.max_health}\n"
                        info_text += f"attack: {unit_comp.attack}\n"
                        info_text += f"defense: {unit_comp.defense}\n"
                        info_text += f"movement: {unit_comp.movement_points}\n"
                        info_text += f"attack_range: {unit_comp.attack_range}\n"
                        info_text += "-------------------\n"
                unit_info_text.text = info_text
            else:
                unit_info_text.text = "select nothing"

        # 更新事件日志
        event_log_text = None
        for entity in self.status_entities:
            text_comp = self.world.get_component(entity, TextComponent)
            if text_comp and (
                "game start" in text_comp.text or "Player" in text_comp.text
            ):
                event_log_text = text_comp
                break

        if event_log_text:
            if self.event_log:
                log_text = "\n".join(self.event_log)
                event_log_text.text = log_text
            else:
                event_log_text.text = "game start..."

    def _handle_unit_selected_event(self, event: EventMessage):
        """处理单位选择事件"""
        self.logger.info(f"GameScene: Unit selected event received: {event.data}")
        selected_entity = event.data.get("entity")
        if selected_entity:
            self.selected_units = [selected_entity]
            unit_comp = self.world.get_component(selected_entity, UnitComponent)
            if unit_comp:
                log_message = f"Player {unit_comp.owner_id}'s {unit_comp.unit_type.name} has been selected"
                self._add_event_log(log_message)
        self._update_status_display()

    def _handle_unit_moved_event(self, event: EventMessage):
        """处理单位移动事件"""
        self.logger.info(f"GameScene: Unit moved event received: {event.data}")
        unit_entity = event.data.get("entity")
        from_pos = event.data.get("from")
        to_pos = event.data.get("to")

        if unit_entity and from_pos and to_pos:
            unit_comp = self.world.get_component(unit_entity, UnitComponent)
            if unit_comp:
                log_message = f"Player {unit_comp.owner_id}'s {unit_comp.unit_type.name} from ({from_pos[0]},{from_pos[1]}) to ({to_pos[0]},{to_pos[1]})"
                self._add_event_log(log_message)

    def _handle_unit_attacked_event(self, event: EventMessage):
        """处理单位攻击事件"""
        self.logger.info(f"GameScene: Unit attacked event received: {event.data}")
        attacker = event.data.get("attacker")
        target = event.data.get("target")
        damage = event.data.get("damage")

        if attacker and target and damage is not None:
            attacker_comp = self.world.get_component(attacker, UnitComponent)
            target_comp = self.world.get_component(target, UnitComponent)
            if attacker_comp and target_comp:
                log_message = f"Player {attacker_comp.owner_id}'s {attacker_comp.unit_type.name} attack Player {target_comp.owner_id}'s {target_comp.unit_type.name}, take {damage} damage"
                self._add_event_log(log_message)
