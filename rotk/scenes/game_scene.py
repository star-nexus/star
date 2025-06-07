"""
主游戏场景
"""

import pygame
from typing import Dict
from framework_v2.engine.scenes import Scene, SMS
from framework_v2 import World
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
    RenderSystem,
    MiniMapSystem,
)
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
        self.game_mode = "turn_based"

        # 初始化标志
        self.initialized = False

    def enter(self, **kwargs):
        """进入场景时调用"""
        super().enter(**kwargs)

        # 从kwargs获取配置
        self.players = kwargs.get(
            "players", {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI}
        )
        self.game_mode = kwargs.get("game_mode", "turn_based")

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
            TurnSystem(),  # 回合系统 (优先级90)
            RealtimeSystem(),  # 实时系统 (优先级85)
            VisionSystem(),  # 视野系统
            MovementSystem(),  # 移动系统
            CombatSystem(),  # 战斗系统
            AISystem(),  # AI系统
            AnimationSystem(),  # 动画系统 (优先级15)
            InputHandlingSystem(),  # 输入系统 (优先级10)
            MiniMapSystem(),  # 小地图系统 (优先级5)
            RenderSystem(),  # 渲染系统 (优先级1)
        ]

        for system in systems:
            self.world.add_system(system)

    def _initialize_game_mode(self):
        """初始化游戏模式组件"""
        game_mode = (
            GameMode.REAL_TIME if self.game_mode == "real_time" else GameMode.TURN_BASED
        )
        game_mode_component = GameModeComponent(mode=game_mode)
        self.world.add_singleton_component(game_mode_component)

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
        """初始化游戏统计"""

        stats = GameStats()

        # 为每个阵营初始化统计数据
        for faction in self.players.keys():
            stats.faction_stats[faction] = {
                "kills": 0,
                "losses": 0,
                "damage_dealt": 0,
                "damage_taken": 0,
                "units_remaining": len(
                    [
                        e
                        for e in self.world.query().with_component(Unit).entities()
                        if self.world.get_component(e, Unit).faction == faction
                    ]
                ),
            }

        self.world.add_singleton_component(stats)

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
                # 切换到胜利场景
                SMS.switch_to("victory", winner=game_state.winner)

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
