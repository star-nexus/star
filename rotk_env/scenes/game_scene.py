"""
主游戏场景
"""

import pygame
import time
from typing import Dict, Any
from framework_v2.engine.scenes import Scene, SMS
from framework_v2 import World
from ..prefabs.config import Faction
from ..systems import (
    AnimationSystem,
    MapSystem,
    TurnSystem,
    RealtimeSystem,
    MovementSystem,
    CombatSystem,
    VisionSystem,
    AISystem,
    InputHandlingSystem,
    MiniMapSystem,
)
from ..systems.map_render_system import MapRenderSystem
from ..systems.unit_render_system import UnitRenderSystem
from ..systems.ui_render_system import UIRenderSystem
from ..systems.effect_render_system import EffectRenderSystem
from ..systems.panel_render_system import PanelRenderSystem
from ..systems.statistics_system import StatisticsSystem
from ..systems.llm_system import LLMSystem
from ..components import (
    GameState,
    UIState,
    InputState,
    FogOfWar,
    GameStats,
    Player,
    AIControlled,
    Unit,
    Health,
    Movement,
    Combat,
    Vision,
    HexPosition,
    MiniMap,
    GameModeComponent,
    UnitStatus,
    MovementAnimation,
    BattleLog,
    UnitObservation,
    UnitStatistics,
    VisibilityTracker,
    GameModeStatistics,
)
from ..prefabs.config import Faction, PlayerType, GameConfig, UnitType, GameMode


class GameScene(Scene):
    """主游戏场景"""

    def __init__(self, engine):
        super().__init__(engine)
        self.name = "game"
        self.world = World()

        # 默认配置，将在enter中被覆盖
        self.players = {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI}
        self.game_mode = GameMode.TURN_BASED  # 默认游戏模式

        # 初始化标志
        self.initialized = False

    def enter(self, **kwargs):
        """进入场景时调用"""
        super().enter(**kwargs)

        # 从kwargs获取配置
        self.players = kwargs.get(
            "players", {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI}
        )

        mode = kwargs.get("mode", GameMode.TURN_BASED)
        self.game_mode = mode

        headless = kwargs.get("headless", False)
        self.headless = headless

        # 获取场景参数（可选）
        self.scenario = kwargs.get("scenario", "default")

        if not self.initialized:
            self._initialize_game()
            self.initialized = True

    def _initialize_game(self):
        """初始化游戏"""
        # 首先初始化游戏模式组件
        self._initialize_game_mode()

        # 初始化系统
        self._initialize_systems()

        # 初始化玩家
        self._initialize_players()

        # 初始化单位
        self._initialize_units()

        # 初始化游戏统计
        self._initialize_stats()

        # 初始化小地图
        self._initialize_minimap()

    def _initialize_systems(self):
        """初始化所有游戏系统"""
        # 按优先级顺序添加系统
        systems = [
            MapSystem(),  # 地图系统 (优先级100)
            VisionSystem(),  # 视野系统
            MovementSystem(),  # 移动系统
            CombatSystem(),  # 战斗系统
            # AISystem(),  # AI系统
            LLMSystem(),  # LLM系统 (优先级5)
            StatisticsSystem(),  # 统计系统
            AnimationSystem(),  # 动画系统 (优先级15)
            InputHandlingSystem(),  # 输入系统 (优先级10)
            # 渲染系统拆分为多个独立系统（从底层到顶层）
            MapRenderSystem(),  # 地图渲染系统 (最底层)
            UnitRenderSystem(),  # 单位渲染系统 (在地图之上)
            EffectRenderSystem(),  # 效果渲染系统 (在单位之上)
            PanelRenderSystem(),  # 面板渲染系统 (在效果之上)
            UIRenderSystem(),  # UI渲染系统 (最顶层)
            MiniMapSystem(),  # 小地图系统 (优先级5)
        ]
        if self.game_mode == GameMode.REAL_TIME:
            systems.append(RealtimeSystem())
        else:
            systems.append(TurnSystem())

        for system in systems:
            self.world.add_system(system)

    def _initialize_game_mode(self):
        """初始化游戏模式组件"""
        game_mode = GameModeComponent(mode=self.game_mode)
        self.world.add_singleton_component(game_mode)

    def _initialize_players(self):
        """初始化玩家"""

        for faction, player_type in self.players.items():
            # 创建玩家实体
            player_entity = self.world.create_entity()

            # 添加玩家组件
            player_comp = Player(
                faction=faction,
                player_type=player_type,
                color=GameConfig.FACTION_COLORS[faction],
                units=set(),
            )
            self.world.add_component(player_entity, player_comp)

            # 如果是AI玩家，添加AI控制组件
            if player_type == PlayerType.AI:
                self.world.add_component(player_entity, AIControlled())

    def _initialize_units(self):
        """初始化单位"""

        # 为每个玩家创建初始单位
        positions = {
            Faction.WEI: [(2, 2), (3, 2), (2, 3)],
            Faction.SHU: [(-2, -2), (-3, -2), (-2, -3)],
        }

        for faction, pos_list in positions.items():
            player_entity = self._get_player_entity(faction)
            if not player_entity:
                continue

            player = self.world.get_component(player_entity, Player)

            for i, (q, r) in enumerate(pos_list):
                unit_entity = self._create_unit(
                    faction=faction,
                    unit_type=UnitType.INFANTRY,
                    position=(q, r),
                    name=f"{faction.value}_{i+1}",
                )
                player.units.add(unit_entity)

    def _create_unit(
        self, faction: Faction, unit_type: UnitType, position: tuple, name: str = ""
    ) -> int:
        """创建单位"""

        unit_entity = self.world.create_entity()

        # 根据单位类型设置属性
        unit_stats = GameConfig.UNIT_STATS[unit_type]

        self.world.add_component(
            unit_entity, Unit(unit_type=unit_type, faction=faction, name=name)
        )

        self.world.add_component(unit_entity, HexPosition(position[0], position[1]))
        self.world.add_component(
            unit_entity,
            Health(current=unit_stats.max_hp, maximum=unit_stats.max_hp),
        )
        self.world.add_component(
            unit_entity,
            Movement(
                max_movement=unit_stats.movement,
                current_movement=unit_stats.movement,
            ),
        )
        self.world.add_component(
            unit_entity,
            Combat(
                attack=unit_stats.attack,
                defense=unit_stats.defense,
                attack_range=unit_stats.attack_range,
            ),
        )
        self.world.add_component(unit_entity, Vision(range=unit_stats.vision_range))
        self.world.add_component(unit_entity, UnitStatus(current_status="idle"))

        return unit_entity

    def _get_player_entity(self, faction: Faction) -> int:
        """获取指定阵营的玩家实体"""

        for entity in self.world.query().with_component(Player).entities():
            player = self.world.get_component(entity, Player)
            if player and player.faction == faction:
                return entity
        return None

    def _initialize_stats(self):
        """初始化游戏统计组件 - 纯数据初始化"""

        # 初始化游戏统计组件
        stats = GameStats()
        stats.game_start_time = time.time()
        self.world.add_singleton_component(stats)

        # 初始化战斗日志
        battle_log = BattleLog()
        self.world.add_singleton_component(battle_log)

        # 初始化可见性追踪器
        visibility_tracker = VisibilityTracker()
        self.world.add_singleton_component(visibility_tracker)

        # 初始化游戏模式统计
        game_mode_stats = GameModeStatistics(current_mode=self.game_mode.value)
        self.world.add_singleton_component(game_mode_stats)

        # 初始化游戏状态
        from ..prefabs.config import GameMode

        first_faction = list(self.players.keys())[0] if self.players else Faction.WEI
        game_state = GameState(
            current_player=first_faction,
            turn_number=1,
            game_mode=GameMode.TURN_BASED,
            game_over=False,
            winner=None,
            max_turns=GameConfig.MAX_TURNS,
        )
        self.world.add_singleton_component(game_state)

        # 初始化其他单例组件
        self.world.add_singleton_component(UIState())
        self.world.add_singleton_component(InputState())
        self.world.add_singleton_component(FogOfWar())

        # 初始化战况记录系统
        battle_log = BattleLog()
        battle_log.add_entry("游戏开始", "turn", "", (0, 255, 0))
        battle_log.add_entry("魏国回合开始", "turn", "wei", (255, 100, 100))
        self.world.add_singleton_component(battle_log)

    def update(self, delta_time: float) -> None:
        """更新场景"""
        if self.is_active:
            # 检查退出事件
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.engine.quit()
                    return

            # 更新世界
            self.world.update(delta_time)

            # 检查游戏结束
            game_state = self.world.get_singleton_component(GameState)
            if game_state and game_state.game_over:
                # 收集统计数据
                statistics = self._collect_game_statistics()

                # 切换到游戏结束场景，传递统计数据
                if self.headless:
                    # 在无头模式下打印统计数据
                    print(
                        f"游戏结束，胜利者：{game_state.winner}，\n统计数据：{statistics}"
                    )
                else:
                    SMS.switch_to(
                        "game_over", winner=game_state.winner, statistics=statistics
                    )

    def _collect_game_statistics(self) -> Dict[str, Any]:
        """收集游戏统计数据"""
        from ..components import Unit, Health, GameStats

        total_units = 0
        surviving_units = 0
        faction_stats = {}

        # 统计所有单位
        for faction in [Faction.WEI, Faction.SHU, Faction.WU]:
            faction_total = 0
            faction_surviving = 0

            for entity in self.world.query().with_component(Unit).entities():
                unit = self.world.get_component(entity, Unit)
                health = self.world.get_component(entity, Health)

                if unit.faction == faction:
                    faction_total += 1
                    total_units += 1

                    if health and health.current > 0:
                        faction_surviving += 1
                        surviving_units += 1

            if faction_total > 0:  # 只记录有单位的阵营
                faction_stats[faction] = {
                    "total_units": faction_total,
                    "surviving_units": faction_surviving,
                }

        # 获取游戏状态信息
        total_turns = 0
        game_duration = 0.0

        try:
            game_state = self.world.get_singleton_component(GameState)
            if game_state:
                total_turns = game_state.turn_number

            # 计算游戏时长（简单使用回合数估算）
            game_duration = total_turns * 1.0  # 假设每回合1秒

        except Exception as e:
            print(f"获取游戏状态时出错: {e}")

        return {
            "total_turns": total_turns,
            "game_duration": game_duration,
            "total_units": total_units,
            "surviving_units": surviving_units,
            "faction_stats": faction_stats,
        }

    def _initialize_minimap(self):
        """初始化小地图"""
        minimap = MiniMap(
            visible=True,
            width=200,
            height=150,
            position=(10, 10),
            scale=0.1,
            center_on_camera=True,
            show_units=True,
            show_terrain=True,
            show_fog_of_war=False,  # 小地图不显示迷雾，可以看到全局
            show_camera_viewport=True,
            clickable=True,
        )
        self.world.add_singleton_component(minimap)

    def exit(self):
        """退出场景时调用"""
        super().exit()

        # 清理世界
        self.world.reset()
