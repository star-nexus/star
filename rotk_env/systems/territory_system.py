"""
领土控制系统 - 处理地块占领、工事建设和领土控制
"""

import time
from typing import Optional, Tuple
from framework import System, World
from ..components import (
    HexPosition,
    Unit,
    MapData,
    Tile,
    Terrain,
    TerritoryControl,
    CaptureAction,
    ActionPoints,
    GameState,
    GameModeComponent,
    GameTime,
)
from ..prefabs.config import GameConfig, Faction, TerrainType, ActionType, GameMode


class TerritorySystem(System):
    """领土控制系统"""

    def __init__(self):
        super().__init__(priority=250)  # 在移动和战斗之后执行

    def initialize(self, world: World) -> None:
        self.world = world
        self._initialize_territory_controls()

    def subscribe_events(self):
        """订阅事件"""
        pass

    def update(self, delta_time: float) -> None:
        """更新领土控制系统"""
        self._update_capture_actions(delta_time)
        self._check_territory_conflicts()

    def _initialize_territory_controls(self):
        """为所有地块初始化领土控制组件"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        for position, tile_entity in map_data.tiles.items():
            if not self.world.has_component(tile_entity, TerritoryControl):
                # 获取地形信息来确定占领难度
                terrain = self.world.get_component(tile_entity, Terrain)
                is_city = terrain and terrain.terrain_type == TerrainType.CITY

                # 城市需要更长时间占领
                capture_time = 10.0 if is_city else 5.0

                territory_control = TerritoryControl(
                    controlling_faction=None,
                    being_captured=False,
                    capturing_unit=None,
                    capture_progress=0.0,
                    capture_time_required=capture_time,
                    fortified=False,
                    fortification_level=0,
                    captured_time=0.0,
                    is_city=is_city,
                )

                self.world.add_component(tile_entity, territory_control)

    def _update_capture_actions(self, delta_time: float):
        """更新占领行动"""
        entities_to_remove = []

        for entity in self.world.query().with_all(CaptureAction).entities():
            capture_action = self.world.get_component(entity, CaptureAction)
            if not capture_action or capture_action.completed:
                continue

            # 检查占领单位是否还存在且在正确位置
            capturing_unit = capture_action.capturing_unit
            if not self.world.has_entity(capturing_unit):
                entities_to_remove.append(entity)
                continue

            unit_pos = self.world.get_component(capturing_unit, HexPosition)
            if (
                not unit_pos
                or (unit_pos.col, unit_pos.row) != capture_action.target_position
            ):
                # 单位离开了目标位置，取消占领
                self._cancel_capture(capture_action.target_position)
                entities_to_remove.append(entity)
                continue

            # 获取目标地块
            map_data = self.world.get_singleton_component(MapData)
            if not map_data:
                continue

            tile_entity = map_data.tiles.get(capture_action.target_position)
            if not tile_entity:
                entities_to_remove.append(entity)
                continue

            territory_control = self.world.get_component(tile_entity, TerritoryControl)
            if not territory_control:
                entities_to_remove.append(entity)
                continue

            # 检查游戏模式
            game_mode_comp = self.world.get_singleton_component(GameModeComponent)
            game_mode = game_mode_comp.mode if game_mode_comp else GameMode.TURN_BASED

            if game_mode == GameMode.TURN_BASED:
                # 回合制：立即完成占领（已消耗行动力）
                if capture_action.uses_action_points:
                    self._complete_capture(
                        capture_action.target_position, capturing_unit
                    )
                    capture_action.completed = True
                    entities_to_remove.append(entity)
            else:
                # 实时模式：需要占领时间
                game_time = self.world.get_singleton_component(GameTime)
                current_time = game_time.total_time if game_time else time.time()

                if capture_action.start_time == 0.0:
                    capture_action.start_time = current_time

                elapsed_time = current_time - capture_action.start_time
                territory_control.capture_progress = min(
                    1.0, elapsed_time / territory_control.capture_time_required
                )

                if territory_control.capture_progress >= 1.0:
                    # 占领完成
                    self._complete_capture(
                        capture_action.target_position, capturing_unit
                    )
                    capture_action.completed = True
                    entities_to_remove.append(entity)

        # 移除完成的占领行动
        for entity in entities_to_remove:
            self.world.destroy_entity(entity)

    def _check_territory_conflicts(self):
        """检查领土冲突（多个单位争夺同一地块）"""
        # 这里可以添加更复杂的冲突解决逻辑
        pass

    def start_capture(self, unit_entity: int, target_position: Tuple[int, int]) -> bool:
        """开始占领地块"""
        unit_pos = self.world.get_component(unit_entity, HexPosition)
        unit = self.world.get_component(unit_entity, Unit)
        action_points = self.world.get_component(unit_entity, ActionPoints)

        if not unit_pos or not unit:
            return False

        # 检查单位是否在目标位置
        if (unit_pos.col, unit_pos.row) != target_position:
            return False

        # 获取目标地块
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return False

        tile_entity = map_data.tiles.get(target_position)
        if not tile_entity:
            return False

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return False

        # 检查是否已经被自己的阵营控制
        if territory_control.controlling_faction == unit.faction:
            return False

        # 检查是否正在被占领
        if territory_control.being_captured:
            return False

        # 检查游戏模式和行动力
        game_mode_comp = self.world.get_singleton_component(GameModeComponent)
        game_mode = game_mode_comp.mode if game_mode_comp else GameMode.TURN_BASED

        if game_mode == GameMode.TURN_BASED:
            # 回合制模式：检查行动力
            if not action_points or not action_points.can_perform_action(
                ActionType.CAPTURE
            ):
                return False

        # 创建占领行动
        capture_entity = self.world.create_entity()

        # 计算行动力消耗（城市消耗更多）
        ap_cost = 2 if territory_control.is_city else 1

        capture_action = CaptureAction(
            capturing_unit=unit_entity,
            target_position=target_position,
            start_time=0.0,
            uses_action_points=(game_mode == GameMode.TURN_BASED),
            action_points_cost=ap_cost,
            completed=False,
        )

        self.world.add_component(capture_entity, capture_action)

        # 标记地块正在被占领
        territory_control.being_captured = True
        territory_control.capturing_unit = unit_entity
        territory_control.capture_progress = 0.0

        # 在回合制模式下消耗行动力
        if game_mode == GameMode.TURN_BASED and action_points:
            action_points.consume_ap(ActionType.CAPTURE)

        print(f"🏴 {unit.faction.value}军开始占领地块 {target_position}")
        return True

    def _complete_capture(self, position: Tuple[int, int], capturing_unit: int):
        """完成地块占领"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        unit = self.world.get_component(capturing_unit, Unit)

        if not territory_control or not unit:
            return

        # 设置控制权
        territory_control.controlling_faction = unit.faction
        territory_control.being_captured = False
        territory_control.capturing_unit = None
        territory_control.capture_progress = 1.0

        # 记录占领时间
        game_time = self.world.get_singleton_component(GameTime)
        territory_control.captured_time = (
            game_time.game_elapsed_time if game_time else time.time()
        )

        print(f"🏁 {unit.faction.value}军成功占领地块 {position}")

    def _cancel_capture(self, position: Tuple[int, int]):
        """取消地块占领"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return

        territory_control.being_captured = False
        territory_control.capturing_unit = None
        territory_control.capture_progress = 0.0

        print(f"❌ 地块 {position} 的占领被取消")

    def build_fortification(
        self, unit_entity: int, target_position: Tuple[int, int]
    ) -> bool:
        """在控制的地块上建设工事"""
        unit = self.world.get_component(unit_entity, Unit)
        action_points = self.world.get_component(unit_entity, ActionPoints)

        if not unit:
            return False

        # 获取目标地块
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return False

        tile_entity = map_data.tiles.get(target_position)
        if not tile_entity:
            return False

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return False

        # 检查是否由自己的阵营控制
        if territory_control.controlling_faction != unit.faction:
            return False

        # 检查是否已经建设了工事
        if territory_control.fortified:
            return False

        # 检查行动力
        game_mode_comp = self.world.get_singleton_component(GameModeComponent)
        game_mode = game_mode_comp.mode if game_mode_comp else GameMode.TURN_BASED

        if game_mode == GameMode.TURN_BASED:
            if not action_points or not action_points.can_perform_action(
                ActionType.FORTIFY
            ):
                return False
            action_points.consume_ap(ActionType.FORTIFY)

        # 建设工事
        territory_control.fortified = True
        territory_control.fortification_level = 1  # 基础工事等级

        print(f"🏰 {unit.faction.value}军在 {target_position} 建设了工事")
        return True

    def can_unit_enter_tile(
        self, unit_entity: int, target_position: Tuple[int, int]
    ) -> bool:
        """检查单位是否可以进入目标地块"""
        unit = self.world.get_component(unit_entity, Unit)
        if not unit:
            return True

        # 获取目标地块
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return True

        tile_entity = map_data.tiles.get(target_position)
        if not tile_entity:
            return True

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return True

        # 检查是否被敌方控制
        if (
            territory_control.controlling_faction
            and territory_control.controlling_faction != unit.faction
        ):
            return False  # 敌方控制的地块不能进入

        return True

    def get_territory_defense_bonus(
        self, position: Tuple[int, int], faction: Faction
    ) -> int:
        """获取领土防御加成"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return 0

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return 0

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return 0

        # 只有在自己控制的领土上才有防御加成
        if territory_control.controlling_faction != faction:
            return 0

        base_bonus = 1  # 基础领土防御加成

        # 工事额外加成
        if territory_control.fortified:
            base_bonus += territory_control.fortification_level * 2

        # 城市额外加成
        if territory_control.is_city:
            base_bonus += 2

        return base_bonus

    def get_territory_attack_bonus(
        self, position: Tuple[int, int], faction: Faction
    ) -> int:
        """获取领土攻击加成"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return 0

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return 0

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return 0

        # 只有在自己控制的领土上才有攻击加成
        if territory_control.controlling_faction != faction:
            return 0

        base_bonus = 0

        # 工事攻击加成
        if territory_control.fortified:
            base_bonus += territory_control.fortification_level

        # 城市攻击加成
        if territory_control.is_city:
            base_bonus += 1

        return base_bonus
