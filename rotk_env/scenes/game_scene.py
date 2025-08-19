"""
主游戏场景
"""

import pygame
import time
from typing import Dict, Any
from framework.engine.scenes import Scene, SMS
from framework import World
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
    TerritorySystem,
    UnitActionButtonSystem,
    ActionSystem,
    UIButtonSystem,
    UIRenderSystem,
)
from ..systems.map_render_system import MapRenderSystem
from ..systems.unit_render_system import UnitRenderSystem

# from ..systems.improved_ui_render_system import ImprovedUIRenderSystem
# from ..systems.improved_ui_button_system import ImprovedUIButtonSystem
from ..systems.effect_render_system import EffectRenderSystem
from ..systems.panel_render_system import PanelRenderSystem
from ..systems.statistics_system import StatisticsSystem
from ..systems.game_time_system import GameTimeSystem
from ..systems.llm_system import LLMSystem
from ..systems.resource_recovery_system import ResourceRecoverySystem
from ..systems.settlement_report_system import SettlementReportSystem
from ..components import (
    GameState,
    UIState,
    InputState,
    FogOfWar,
    GameStats,
    Player,
    AIControlled,
    Unit,
    UnitCount,
    MovementPoints,
    ActionPoints,
    AttackPoints,
    ConstructionPoints,
    SkillPoints,
    Combat,
    Vision,
    HexPosition,
    MiniMap,
    GameModeComponent,
    UnitStatus,
    UnitSkills,
    MovementAnimation,
    BattleLog,
    UnitObservation,
    UnitStatistics,
    VisibilityTracker,
    GameModeStatistics,
    UIButton,
    UIButtonCollection,
    UIPanel,
    TurnManager,
)
from ..prefabs.config import Faction, PlayerType, GameConfig, UnitType, GameMode
from performance_profiler import profiler


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
        # for wei, shu, wu: infantry, archer, cavalry
        self._initialize_units([[1, 0, 1], [1, 0, 1], [0, 0, 0]])

        # 初始化游戏统计
        self._initialize_stats()

        # 初始化小地图
        self._initialize_minimap()

    def _initialize_systems(self):
        """初始化所有游戏系统"""
        # 按优先级顺序添加系统

        systems = [
            GameTimeSystem(),  # 游戏时间系统 (优先级10) - 最早执行
            MapSystem(),  # 地图系统 (优先级100)
            VisionSystem(),  # 视野系统
            ActionSystem(),  # 行动系统
            MovementSystem(),  # 移动系统
            CombatSystem(),  # 战斗系统
            TerritorySystem(),  # 领土系统 (处理占领和工事)
            ResourceRecoverySystem(),  # 资源恢复系统
            # AISystem(),  # 仅当有AI玩家时添加AI系统 - 暂时禁用待修复
            LLMSystem(),  # LLM系统 (优先级5)
            StatisticsSystem(),  # 统计系统
            AnimationSystem(),  # 动画系统 (优先级15)
            InputHandlingSystem(),  # 输入系统 (优先级10)
            UnitActionButtonSystem(),  # 单位动作按钮系统 (优先级4)
            # 渲染系统拆分为多个独立系统（从底层到顶层）
            MapRenderSystem(),  # 地图渲染系统 (最底层)
            UnitRenderSystem(),  # 单位渲染系统 (在地图之上)
            EffectRenderSystem(),  # 效果渲染系统 (在单位之上)
            PanelRenderSystem(),  # 面板渲染系统 (在效果之上)
            UIButtonSystem(),  # 改进的UI按钮系统 (优先级2)
            UIRenderSystem(),  # 改进的UI渲染系统 (最顶层)
            MiniMapSystem(),  # 小地图系统 (优先级5)
            SettlementReportSystem(),  # 结算报告系统 (优先级200，在游戏结束后执行)
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

        # 初始化回合管理器
        turn_manager = TurnManager()
        self.world.add_singleton_component(turn_manager)

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

            # 将玩家添加到回合管理器
            turn_manager.add_player(player_entity)

    def _initialize_units(self, unit_assignments: list[list[int]]):
        """初始化单位 - 根据数量自动生成单位和位置"""

        # 定义每个阵营的起始区域中心
        faction_centers = {
            Faction.WEI: (3, 3),  # 右上区域
            Faction.SHU: (-3, -3),  # 左下区域
            Faction.WU: (3, -3),  # 右下区域
        }

        # 定义单位数量（只处理参与游戏的阵营）
        unit_counts = {}
        for faction in self.players.keys():
            if faction == Faction.WEI:
                unit_counts[faction] = unit_assignments[0]
            elif faction == Faction.SHU:
                unit_counts[faction] = unit_assignments[1]
            elif faction == Faction.WU:
                unit_counts[faction] = unit_assignments[2]

        # 🆕 记录初始单位数到GameStats（确保GameStats已存在）
        game_stats = self.world.get_singleton_component(GameStats)
        if not game_stats:
            # 如果GameStats不存在，先创建一个临时的，等_initialize_stats时会正确初始化
            print("[GameScene] ⚠️ GameStats组件不存在，等待后续初始化...")
            pass
        
        # 将初始单位数暂存，在_initialize_stats中再写入GameStats
        self._temp_initial_unit_counts = {}
        for faction, count in unit_counts.items():
            total_units = sum(count)
            self._temp_initial_unit_counts[faction] = total_units
            print(f"[GameScene] 准备记录 {faction.value} 阵营初始单位数: {total_units}")

        for faction, count in unit_counts.items():
            if sum(count) == 0:
                continue

            player_entity = self._get_player_entity(faction)
            if not player_entity:
                continue

            player = self.world.get_component(player_entity, Player)
            center_q, center_r = faction_centers[faction]

            # 生成该阵营的所有单位位置
            positions = self._generate_unit_positions(center_q, center_r, sum(count))

            # 生成多样化的单位类型
            unit_types = self._generate_unit_types(count)

            for i, ((q, r), unit_type) in enumerate(zip(positions, unit_types)):
                unit_entity = self._create_unit(
                    faction=faction,
                    unit_type=unit_type,
                    position=(q, r),
                    name=f"{faction.value}_{unit_type.value}_{i+1}",
                )
                player.units.add(unit_entity)

    def _generate_unit_positions(
        self, center_q: int, center_r: int, count: int
    ) -> list:
        """生成单位位置 - 以中心点为基础，螺旋式分布"""
        positions = []

        if count == 1:
            return [(center_q, center_r)]

        # 第一个单位放在中心
        positions.append((center_q, center_r))
        remaining = count - 1

        # 六边形的六个方向偏移量 (flat-top orientation)
        hex_directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]

        radius = 1
        while remaining > 0 and radius <= 5:  # 限制最大半径
            # 当前环的位置数量
            positions_in_ring = min(remaining, 6 * radius)

            # 在当前环上均匀分布位置
            for i in range(positions_in_ring):
                if i < 6:  # 第一层（6个方向各一个）
                    dq, dr = hex_directions[i]
                    q = center_q + dq * radius
                    r = center_r + dr * radius
                else:  # 填充边
                    # 在六边形的边上添加额外位置
                    side = (i - 6) // radius
                    pos_on_side = (i - 6) % radius

                    if side < 6:
                        dq1, dr1 = hex_directions[side]
                        dq2, dr2 = hex_directions[(side + 1) % 6]

                        # 在边上插值
                        t = (pos_on_side + 1) / (radius + 1)
                        q = center_q + int(dq1 * radius * (1 - t) + dq2 * radius * t)
                        r = center_r + int(dr1 * radius * (1 - t) + dr2 * radius * t)
                    else:
                        break

                positions.append((q, r))
                remaining -= 1

                if remaining <= 0:
                    break

            radius += 1

        return positions[:count]

    def _generate_unit_types(self, count: int | list) -> list:
        """生成多样化的单位类型组合"""

        unit_types = []

        if isinstance(count, list) and len(count) == 3:
            # count是一个3元素列表 [步兵数, 弓兵数, 骑兵数]
            infantry_count, archer_count, cavalry_count = count
            unit_types = []

            # 添加指定数量的各类型单位
            unit_types.extend([UnitType.INFANTRY] * infantry_count)
            unit_types.extend([UnitType.ARCHER] * archer_count)
            unit_types.extend([UnitType.CAVALRY] * cavalry_count)

            return unit_types

        # 基础配比：步兵40%，骑兵30%，弓兵25%，攻城5%
        base_ratios = {
            UnitType.INFANTRY: 0.50,
            UnitType.CAVALRY: 0.30,
            UnitType.ARCHER: 0.20,
        }

        # 根据数量计算各类型单位数
        for unit_type, ratio in base_ratios.items():
            type_count = max(1, int(count * ratio)) if count >= 4 else 1
            unit_types.extend([unit_type] * type_count)

        # 如果总数不够，用步兵补充
        while len(unit_types) < count:
            unit_types.append(UnitType.INFANTRY)

        # 如果超了，移除多余的（优先移除弓兵）
        while len(unit_types) > count:
            for remove_type in [UnitType.ARCHER, UnitType.CAVALRY]:
                if remove_type in unit_types:
                    unit_types.remove(remove_type)
                    break
            else:
                unit_types.pop()

        # 打乱顺序
        # random.shuffle(unit_types)
        return unit_types

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
            UnitCount(
                current_count=unit_stats.max_count, max_count=unit_stats.max_count
            ),
        )
        self.world.add_component(
            unit_entity,
            MovementPoints(
                base_mp=unit_stats.movement,
                current_mp=unit_stats.movement,
                max_mp=unit_stats.movement,
            ),
        )
        self.world.add_component(
            unit_entity,
            ActionPoints(
                current_ap=2,  # 默认行动点
                max_ap=2,
            ),
        )
        self.world.add_component(
            unit_entity,
            AttackPoints(
                normal_attacks=1,  # 默认攻击次数
                max_normal_attacks=1,
            ),
        )
        self.world.add_component(
            unit_entity,
            ConstructionPoints(
                current_cp=1,  # 默认建造点
                max_cp=1,
            ),
        )
        self.world.add_component(
            unit_entity,
            SkillPoints(
                current_sp=1,  # 默认技能点
                max_sp=1,
            ),
        )
        self.world.add_component(
            unit_entity,
            Combat(
                base_attack=unit_stats.base_attack,
                base_defense=unit_stats.base_defense,
                attack_range=unit_stats.attack_range,
            ),
        )
        self.world.add_component(unit_entity, Vision(range=unit_stats.vision_range))
        self.world.add_component(unit_entity, UnitStatus(current_status="normal"))

        # 添加行动力组件
        self.world.add_component(unit_entity, ActionPoints(current_ap=2, max_ap=2))

        # 添加技能组件
        self.world.add_component(unit_entity, UnitSkills())

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
        
        # 🆕 将之前记录的初始单位数写入GameStats
        if hasattr(self, '_temp_initial_unit_counts'):
            stats.initial_unit_counts = self._temp_initial_unit_counts.copy()
            print(f"[GameScene] ✅ 已将初始单位数写入GameStats: {stats.initial_unit_counts}")
        else:
            print("[GameScene] ⚠️ 未找到临时的初始单位数记录")
        
        self.world.add_singleton_component(stats)

        # 初始化战斗日志
        battle_log = BattleLog()
        battle_log.add_entry("游戏开始", "turn", "", (0, 255, 0))
        battle_log.add_entry("魏国回合开始", "turn", "wei", (255, 100, 100))
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
            game_mode=self.game_mode,
            game_over=False,
            winner=None,
            max_turns=GameConfig.MAX_TURNS,
        )
        self.world.add_singleton_component(game_state)

        # 初始化其他单例组件
        self.world.add_singleton_component(UIState())
        self.world.add_singleton_component(InputState())
        self.world.add_singleton_component(FogOfWar())

        # 初始化战争迷雾
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
            with profiler.time_system("world_update"):
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
        from ..components import Unit, UnitCount, GameTime, GameState

        total_units = 0
        surviving_units = 0
        faction_stats = {}

        # 统计所有单位
        for faction in [Faction.WEI, Faction.SHU, Faction.WU]:
            faction_total = 0
            faction_surviving = 0

            for entity in self.world.query().with_component(Unit).entities():
                unit = self.world.get_component(entity, Unit)
                unit_count = self.world.get_component(entity, UnitCount)

                if unit.faction == faction:
                    faction_total += 1
                    total_units += 1

                    if unit_count and unit_count.current_count > 0:
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
            total_turns = game_state.turn_number

            game_time = self.world.get_singleton_component(GameTime)
            game_duration = game_time.get_game_elapsed_seconds()

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
