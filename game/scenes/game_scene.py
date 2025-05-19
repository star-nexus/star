import time
from typing import override
from framework.engine.scenes import Scene
from framework.utils.logging import get_logger
from framework.engine.events import EventMessage, EventType
from framework.ui import (
    UITransformComponent,
    ButtonComponent,
    PanelComponent,
    TextComponent,
)
from game.systems.unit.unit_health_system import UnitHealthSystem
from framework.ui.systems import UISystem
from game.components.map import map_component
from game.systems import MapSystem, CameraSystem, MapRenderSystem
from game.systems.unit.unit_system import UnitSystem
from game.systems.unit.unit_render_system import UnitRenderSystem
from game.systems.unit.unit_movement_system import UnitMovementSystem
from game.systems.unit.unit_attack_system import UnitAttackSystem
from game.systems import UnitControlSystem
from game.systems.unit.unit_ai_control_system import UnitAIControlSystem
from game.systems import GameStatsSystem, ViewMode
from game.systems import FogOfWarSystem
from game.systems import LLMControlSystem
from game.systems.terrain.terrain_effect_system import TerrainEffectSystem

from game.config.prefab_factory import PrefabFactory

from game.utils import UnitType
from game.components import UnitComponent


class GameScene(Scene):
    def __init__(self, engine):
        super().__init__(engine)
        # 游戏场景所需的属性
        self.logger = get_logger("GameScene")
        self.scene_start_time = None
        self.max_game_duration = 900.0  # 最大游戏时长为900秒，超时判定半歼

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
        self.terrain_effect_system = None  # 地形效果系统引用

    def enter(self, **kwargs):
        self.logger.info("进入游戏场景")
        super().enter(**kwargs)

        self.headless = kwargs.get("headless", None)

        if self.scene_start_time is None:
            self.scene_start_time = time.time()

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
        # self._create_units()
        self.prefab_factory.create_random_unit()
        # self.prefab_factory.create_benchmark_unit(2)

        # 创建UI界面
        # self.create_ui_entities()

        # 创建状态信息面板
        self._create_status_display()

        # 注册系统, 注意顺序，要最后注册
        self.register_systems()
        self.logger.info("游戏场景初始化完成")

    def _create_units(self):
        """创建单位"""
        self.logger.info("开始创建单位")
        # self.units = []

        # self.prefab_factory.create_unit(
        #     UnitType.INFANTRY,
        #     0,
        #     100,
        #     100,
        #     owner_id=0,
        # )
        # self.prefab_factory.create_unit(
        #     UnitType.INFANTRY,
        #     0,
        #     150,
        #     100,
        #     owner_id=0,
        # )
        self.prefab_factory.create_unit(
            UnitType.INFANTRY,
            1,
            20,
            10,
            owner_id=1,
        )
        self.prefab_factory.create_unit(
            UnitType.ARCHER,
            1,
            20,
            15,
            owner_id=1,
        )
        self.prefab_factory.create_unit(
            UnitType.CAVALRY,
            1,
            20,
            20,
            owner_id=1,
        )

        # self.prefab_factory.create_unit(
        #     UnitType.INFANTRY,
        #     1,
        #     220,
        #     100,
        #     owner_id=1,
        # )
        # self.prefab_factory.create_unit(
        #     UnitType.ARCHER,
        #     1,
        #     220,
        #     150,
        #     owner_id=1,
        # )
        # self.prefab_factory.create_unit(
        #     UnitType.CAVALRY,
        #     1,
        #     220,
        #     200,
        #     owner_id=1,
        # )

        # self.prefab_factory.create_unit(
        #     UnitType.INFANTRY,
        #     1,
        #     240,
        #     100,
        #     owner_id=1,
        # )

        # self.prefab_factory.create_unit(
        #     UnitType.INFANTRY,
        #     1,
        #     260,
        #     100,
        #     owner_id=1,
        # )

        self.prefab_factory.create_battle_stats(1)

        self.prefab_factory.create_unit(
            UnitType.INFANTRY,
            2,
            30,
            10,
            owner_id=2,
        )
        self.prefab_factory.create_unit(
            UnitType.ARCHER,
            2,
            30,
            15,
            owner_id=2,
        )
        self.prefab_factory.create_unit(
            UnitType.CAVALRY,
            2,
            30,
            20,
            owner_id=2,
        )
        # self.prefab_factory.create_unit(
        #     UnitType.INFANTRY,
        #     2,
        #     320,
        #     100,
        #     owner_id=2,
        # )
        # self.prefab_factory.create_unit(
        #     UnitType.ARCHER,
        #     2,
        #     320,
        #     150,
        #     owner_id=2,
        # )
        # self.prefab_factory.create_unit(
        #     UnitType.CAVALRY,
        #     2,
        #     320,
        #     200,
        #     owner_id=2,
        # )
        # self.prefab_factory.create_unit(
        #     UnitType.INFANTRY,
        #     2,
        #     280,
        #     100,
        #     owner_id=2,
        # )
        # self.prefab_factory.create_unit(
        #     UnitType.INFANTRY,
        #     2,
        #     260,
        #     100,
        #     owner_id=2,
        # )
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

        # 地形效果系统
        # 创建地形效果系统
        terrain_effect_system = TerrainEffectSystem()
        terrain_effect_system.initialize(self.world.context)
        self.world.add_system(terrain_effect_system)
        self.terrain_effect_system = terrain_effect_system

        # 单位生命值系统
        unit_health_system = (
            UnitHealthSystem()
        )  # 假设你有一个UnitHealthSystem的实现，替换为实际的实现类
        unit_health_system.initialize(self.world.context)
        self.world.add_system(unit_health_system)
        self.unit_health_system = unit_health_system

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

        # 调用LLM控制系统的cleanup方法，取消所有未完成的API请求
        if hasattr(self, "llm_controller_system") and self.llm_controller_system:
            self.logger.debug("清理LLM控制系统未完成任务")
            self.llm_controller_system.cleanup()

        # 关闭线程池
        self.world.context.executor.shutdown()

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

        end_time = time.time()
        game_duration = end_time - self.scene_start_time
        self.logger.msg(f"游戏场景运行时间: {game_duration:.2f}秒")

        # 如果游戏是由于退出而结束（而不是胜负已定）
        # 记录为提前退出的实验数据
        # 注意：这里需要添加一个标记来判断是否已经生成过实验报告，避免重复
        if (
            not hasattr(self, "_experiment_report_generated")
            or not self._experiment_report_generated
        ):
            # 获取各阵营使用的模型和策略分数
            model_info, strategy_scores, enable_thinking, response_times = self._get_model_info()
            self.generate_experiment_report(
                None,
                game_duration,
                is_tie=True,
                model_info=model_info,
                strategy_scores=strategy_scores,
                enable_thinking=enable_thinking,
                response_times=response_times
            )
            self._experiment_report_generated = True

        self.logger.debug("游戏系统移除完成")
        # 清理游戏场景资源
        super().exit()
        self.logger.debug("游戏场景资源清理完成")

    def update(self, delta_time):
        # 更新世界，这会调用所有系统的update方法
        self.world.update(delta_time)

        # 检查游戏时间是否超过最大时长
        if self.scene_start_time is not None:
            current_time = time.time()
            game_duration = current_time - self.scene_start_time

            if game_duration >= self.max_game_duration:
                self.logger.info(
                    f"游戏时间已达到{self.max_game_duration}秒上限，进行半歼结算"
                )
                self._check_half_annihilation()

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
            # self.logger.info("GameScene subscribed to UNIT_KILLED event.")

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
        # self.logger.info(f"GameScene: Unit killed event received: {event.data}")
        # 在这里可以更新游戏统计数据，例如 GameStatsSystem
        # killer_entity = event.data.get("killer")
        # killed_entity = event.data.get("target")
        # if killer_entity and killed_entity:
        #     killer_comp = self.world.get_component(killer_entity, UnitComponent)
        #     killed_comp = self.world.get_component(killed_entity, UnitComponent)

        # log_message = f"Player {killer_comp.owner_id}'s {killer_type} kill Player {killed_comp.owner_id}'s {killed_type}"
        # self._add_event_log(log_message)

        # # 检查胜负条件，确保在事件处理中调用
        self._check_win_loss_conditions()

        # 更新状态面板
        # self._update_status_display()

    def _check_win_loss_conditions(self):
        # 统计每个阵营的存活单位数量
        faction_units_alive = {}

        # 遍历所有单位，统计每个阵营的存活单位数量
        for entity, (unit_comp,) in self.world.context.with_all(
            UnitComponent
        ).iter_components(UnitComponent):
            if unit_comp.is_alive:
                owner_id = unit_comp.owner_id
                if owner_id not in faction_units_alive:
                    faction_units_alive[owner_id] = 0
                faction_units_alive[owner_id] += 1

        # 检查是否只有一个阵营有存活单位
        if len(faction_units_alive) == 1:
            # 获取胜利阵营ID
            winner_faction = list(faction_units_alive.keys())[0]

            # 在切换场景前清理LLM控制系统
            if hasattr(self, "llm_controller_system") and self.llm_controller_system:
                self.logger.debug("游戏结束，清理LLM控制系统未完成任务")
                self.llm_controller_system.cleanup()

            # 获取各阵营使用的模型和策略分数
            model_info, strategy_scores, enable_thinking, response_times = self._get_model_info()

            # 记录游戏时长和胜利阵营
            game_duration = time.time() - self.scene_start_time
            self.generate_experiment_report(
                winner_faction,
                game_duration,
                is_tie=False,
                model_info=model_info,
                strategy_scores=strategy_scores,
                enable_thinking=enable_thinking,
                response_times=response_times
            )
            self._experiment_report_generated = True

            self.logger.msg(f"阵营{winner_faction}获得胜利！其余阵营单位已全部阵亡！")
            if self.headless:
                # 切换到结束场景
                self.engine.scene_manager.load_scene("transition_end")
            else:
                self.engine.scene_manager.load_scene(
                    "end", result="victory", reason={winner_faction}
                )
        elif len(faction_units_alive) == 0:
            # 在切换场景前清理LLM控制系统
            if hasattr(self, "llm_controller_system") and self.llm_controller_system:
                self.logger.debug("游戏结束，清理LLM控制系统未完成任务")
                self.llm_controller_system.cleanup()

            # 获取各阵营使用的模型和策略分数
            model_info, strategy_scores, enable_thinking, response_times = self._get_model_info()

            # 记录平局游戏结果
            game_duration = time.time() - self.scene_start_time
            self.generate_experiment_report(
                0,
                game_duration,
                is_tie=True,
                model_info=model_info,
                strategy_scores=strategy_scores,
                enable_thinking=enable_thinking,
                response_times=response_times
            )
            self._experiment_report_generated = True

            self.logger.info("所有阵营单位均已阵亡，平局！")
            if self.headless:
                # 切换到结束场景
                self.engine.scene_manager.load_scene("transition_end")
            else:
                self.engine.scene_manager.load_scene(
                    "end", result="tie", reason="All units has died, it's a tie"
                )

    def _get_model_info(self):
        """Get various LLM-related metrics"""
        model_info = {}
        strategy_scores = {}
        enable_thinking = {}
        response_times = {}

        if hasattr(self, "llm_controller_system") and self.llm_controller_system:
            model_info = self.llm_controller_system.get_faction_models()
            strategy_scores = self.llm_controller_system.get_strategy_scores()
            enable_thinking = self.llm_controller_system.get_enable_thinking()
            response_times = self.llm_controller_system.get_response_times()
        return model_info, strategy_scores, enable_thinking, response_times

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
        for entity, (text_comp,) in self.world.context.with_all(
            TextComponent
        ).iter_components(TextComponent):
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
                        info_text += (
                            f"HP: {unit_comp.current_health}/{unit_comp.max_health}\n"
                        )
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
        # 更新状态面板
        self._update_status_display()

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
        # 更新状态面板
        self._update_status_display()

    def generate_experiment_report(
        self,
        winner_faction,
        game_duration,
        is_tie=False,
        model_info=None,
        strategy_scores=None,
        is_half_win=False,
        enable_thinking=None,
        response_times=None,
    ):
        """
        生成实验数据报告并保存到文件

        Args:
            winner_faction: 胜利的阵营ID（0表示平局）
            game_duration: 游戏持续时间（秒）
            is_tie: 是否平局
            model_info: 各阵营使用的模型信息
            strategy_scores: 各阵营的策略推理分数
            is_half_win: 是否为半歼胜利（超时后存活单位数量较多）
            enable_thinking: 是否开启思考
            response_times: 各阵营的响应次数
        """
        import os
        import json
        import datetime
        import csv

        # 创建报告目录
        report_dir = "experiment_reports"
        os.makedirs(report_dir, exist_ok=True)

        # 获取当前时间作为文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H_%M_%S")

        # 地图类型
        map_type = (
            "symmetric_5x5"
            if hasattr(self.prefab_factory, "create_symmetric_terrain")
            else "random"
        )

        # 构建实验报告数据
        report_data = {
            "experiment_id": timestamp,
            "timestamp": datetime.datetime.now().isoformat(),
            "map_type": map_type,
            "result": {
                "is_tie": is_tie,
                "winner_faction": winner_faction if not is_tie else None,
                "is_half_win": is_half_win,  # 添加半歼胜利标记
                "game_duration_seconds": game_duration,
                "game_duration_formatted": f"{game_duration:.2f}秒",
            },
            "units_info": self._get_units_info(),
            "model_info": model_info,
            "strategy_scores": strategy_scores,
            "enable_thinking": enable_thinking,
            "response_times": response_times,
        }

        # 保存为JSON文件
        report_file = os.path.join(report_dir, f"experiment_{timestamp}.json")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        # 同时保存到CSV文件便于统计分析
        csv_file = os.path.join(report_dir, "experiment_results.csv")
        csv_exists = os.path.exists(csv_file)

        with open(csv_file, "a", encoding="utf-8", newline="") as f:
            if not csv_exists:
                f.write(
                    "experiment_id,timestamp,map_type,is_tie,winner_faction,is_half_win,game_duration_seconds,faction1_model,faction2_model,faction1_strategy_score,faction2_strategy_score,faction1_response_times,faction2_response_times\n"
                )

            # 获取各阵营模型信息
            faction1_model = model_info.get(1, "unknown") if model_info else "unknown"
            faction2_model = model_info.get(2, "unknown") if model_info else "unknown"

            # 获取各阵营策略推理分数
            faction1_strategy = strategy_scores.get(1, 0) if strategy_scores else 0
            faction2_strategy = strategy_scores.get(2, 0) if strategy_scores else 0

            # 获取各阵营响应时间
            faction1_response_times = response_times.get(1, 0) if response_times else 0
            faction2_response_times = response_times.get(2, 0) if response_times else 0

            csv_row = f"{timestamp},{report_data['timestamp']},{map_type},{is_tie},{winner_faction if not is_tie else 'tie'},{is_half_win},{game_duration:.2f},{faction1_model},{faction2_model},{faction1_strategy},{faction2_strategy},{faction1_response_times},{faction2_response_times}\n"
            f.write(csv_row)

        # 输出到控制台
        self.logger.info("=" * 50)
        self.logger.info("实验报告生成成功")
        self.logger.info(f"实验ID: {timestamp}")
        if is_tie:
            self.logger.info("结果: 平局")
        else:
            victory_type = "半歼胜利" if is_half_win else "全歼胜利"
            self.logger.info(f"结果: 阵营{winner_faction}{victory_type}")
        self.logger.info(f"游戏时长: {game_duration:.2f}秒")
        if model_info:
            self.logger.info(f"阵营1使用模型: {model_info.get(1, 'unknown')}")
            self.logger.info(f"阵营2使用模型: {model_info.get(2, 'unknown')}")
        if strategy_scores:
            self.logger.info(f"阵营1策略推理分: {strategy_scores.get(1, 0)}")
            self.logger.info(f"阵营2策略推理分: {strategy_scores.get(2, 0)}")
        if response_times:
            self.logger.info(f"阵营1响应次数: {response_times.get(1, 0)}")
            self.logger.info(f"阵营2响应次数: {response_times.get(2, 0)}")
        self.logger.info(f"报告文件: {report_file}")
        self.logger.info("=" * 50)

    def _get_units_info(self):
        """收集单位信息用于实验报告"""
        units_info = {}

        for entity, (unit_comp,) in self.world.context.with_all(
            UnitComponent
        ).iter_components(UnitComponent):
            faction_id = unit_comp.owner_id
            if faction_id not in units_info:
                units_info[faction_id] = {
                    "alive": 0,
                    "dead": 0,
                    "total": 0,
                    "units": [],
                }

            # 增加相应计数
            if unit_comp.is_alive:
                units_info[faction_id]["alive"] += 1
            else:
                units_info[faction_id]["dead"] += 1
            units_info[faction_id]["total"] += 1

            # 记录详细单位信息
            units_info[faction_id]["units"].append(
                {
                    "id": entity,
                    "type": unit_comp.unit_type.name,
                    "health": unit_comp.current_health,
                    "max_health": unit_comp.max_health,
                    "is_alive": unit_comp.is_alive,
                    "position": [unit_comp.position_x, unit_comp.position_y],
                }
            )

        return units_info

    def _check_half_annihilation(self):
        """检查半歼条件，超时时根据存活单位数量判定胜负"""
        # 统计每个阵营的存活单位数量
        faction_units_alive = {}

        # 遍历所有单位，统计每个阵营的存活单位数量
        for entity, (unit_comp,) in self.world.context.with_all(
            UnitComponent
        ).iter_components(UnitComponent):
            if unit_comp.is_alive:
                owner_id = unit_comp.owner_id
                if owner_id not in faction_units_alive:
                    faction_units_alive[owner_id] = 0
                faction_units_alive[owner_id] += 1

        self.logger.info(f"半歼结算 - 各阵营存活单位数量: {faction_units_alive}")

        # 如果只有一个阵营有存活单位，就是常规胜利
        if len(faction_units_alive) <= 1:
            self._check_win_loss_conditions()
            return

        # 如果有两个或更多阵营有存活单位，比较数量
        # 首先获取阵营1和阵营2的存活单位数
        faction1_alive = faction_units_alive.get(1, 0)
        faction2_alive = faction_units_alive.get(2, 0)

        # 如果数量相同，判定为平局
        if faction1_alive == faction2_alive:
            # 在切换场景前清理LLM控制系统
            if hasattr(self, "llm_controller_system") and self.llm_controller_system:
                self.logger.debug("游戏超时平局，清理LLM控制系统未完成任务")
                self.llm_controller_system.cleanup()

            # 获取各阵营使用的模型和策略分数
            model_info, strategy_scores, enable_thinking, response_times = self._get_model_info()

            # 记录平局游戏结果
            game_duration = time.time() - self.scene_start_time
            self.generate_experiment_report(
                0,
                game_duration,
                is_tie=True,
                model_info=model_info,
                strategy_scores=strategy_scores,
                enable_thinking=enable_thinking,
                response_times=response_times
            )
            self._experiment_report_generated = True

            self.logger.info("半歼结算 - 双方存活单位数量相同，判定为平局！")
            if self.headless:
                # 切换到结束场景
                self.engine.scene_manager.load_scene("transition_end")
            else:
                self.engine.scene_manager.load_scene(
                    "end",
                    result="tie",
                    reason="Time limit reached, it's a tie with equal units",
                )
        else:
            # 数量不同，存活单位多的一方获得半歼胜利
            winner_faction = 1 if faction1_alive > faction2_alive else 2

            # 在切换场景前清理LLM控制系统
            if hasattr(self, "llm_controller_system") and self.llm_controller_system:
                self.logger.debug("游戏超时，半歼胜利，清理LLM控制系统未完成任务")
                self.llm_controller_system.cleanup()

            # 获取各阵营使用的模型和策略分数
            model_info, strategy_scores, enable_thinking, response_times = self._get_model_info()

            # 记录游戏时长和半歼胜利阵营
            game_duration = time.time() - self.scene_start_time
            # 标记为半歼胜利
            self.generate_experiment_report(
                winner_faction,
                game_duration,
                is_tie=False,
                model_info=model_info,
                strategy_scores=strategy_scores,
                is_half_win=True,
                enable_thinking=enable_thinking,
                response_times=response_times
            )
            self._experiment_report_generated = True

            self.logger.msg(
                f"半歼结算 - 阵营{winner_faction}获得半歼胜利！存活单位数量: {faction1_alive} vs {faction2_alive}"
            )
            if self.headless:
                # 切换到结束场景
                self.engine.scene_manager.load_scene("transition_end")
            else:
                self.engine.scene_manager.load_scene(
                    "end",
                    result="half_victory",
                    reason=f"Time limit reached, faction {winner_faction} wins with more units",
                )
