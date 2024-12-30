from collections import deque
import random
import numpy as np
from .path_planner import PathPlanner
from .unit_manager import UnitManager
from .visibility_system import VisibilitySystem
from .combat_system import CombatSystem

# 定义部队数据与战斗规则
UNIT_STATS = {
    # type: (克制谁, 被谁克制)
    # 用字符串表示克制关系：ping克shui, shui克shan, shan克ping
    # 此处简单定义一个优先级: ping>shui, shui>shan, shan>ping
    "ping": {"strong_against": "shui", "weak_against": "shan"},
    "shui": {"strong_against": "shan", "weak_against": "ping"},
    "shan": {"strong_against": "ping", "weak_against": "shui"},
}

"""
Unit Controller 设计

UnitController类负责处理单位的移动、战斗等逻辑，与地图数据分离。

1. 初始化时传入地图数据和单位数据，分别为环境地图和单位地图。
2. 调用，如选择单位、移动单位、加载执行AI指令等。
3. 查询，如获取所有单位信息、获取单位数量统计等。
4. 更新，如单位移动后更新位置、单位战斗后更新状态等。

主要数据结构：
- environment_map [][] type : 环境地图，存储地形信息
    - 类型 str[][] 矩阵
    - item type
- unit_map [][] type : 单位地图，存储单位位置信息
    - 类型 str[][] 矩阵
    - item type
- unit_all_info : 维护 所有单位ID映射,存储单位类型与位置信息
    - 类型 dict 
    - item id:(y,x,type,state)
- unit_faction_info : 维护 单位阵营信息
    - 类型 dict
    - item faction:{id:(y,x,type,state)}
- unit_all_paths {id:deque}: 存储单位的路径规划信息
    - 类型 dict
    - item id:deque
- player_mode str: 玩家模式，'human'或'ai'

主要 property:
- 
selected_unit_info: 选中单位的位置信息
- selected_unit_id: 选中单位的id
- selected_unit_pos: 选中单位的位置信息


主要接口：

GET
- get_all_unit_info() -> dict: 获取所有单位信息
- get_faction_unit_info(faction) -> dict: 获取阵营单位信息

UPDATE
- update_unit_position: 更新单位位置信息
- update_unit_state: 更新单位状态信息
- update_unit_path: 更新单位路径信息

ACTION
- move: 移动单位
- step: 沿路径前进一步
- plan_path: 规划路径
- combat: 执行战斗结算
- load_action: 装填AI传入的指令

Util
- is_enemy: 判断两个单位是否敌对
- select_unit_by_mouse: 根据鼠标点击位置选择单位
- compute_visibility: 计算视野范围
- can_enter: 判断单位是否能进入某个地形
- update_unit_position: 更新unit_id_map中单位位置信息
- reroute: 重新规划路径
- remove_unit: 移除单位信息
- find_all_units: 扫描unit_map找出所有单位
- find_path: 寻找路径
- find_closest_reachable_point: 寻找最近可到达点
- is_tile_free: 检查目标格子是否可通过

"""


class UnitController:
    def __init__(self, environment_map, unit_map, tile_size=32, player_mode="human"):
        # Initialize unit manager
        self.unit_manager = UnitManager(unit_map)
        
        # Meta
        self.player_mode = player_mode
        self.environment_map = environment_map
        self.tile_size = tile_size

        # Initialize path planner
        self.path_planner = PathPlanner(environment_map, self)

        # Initialize visibility system
        self.visibility_system = VisibilitySystem(environment_map.shape)

        # Initialize combat system
        self.combat_system = CombatSystem(UNIT_STATS)

    @property
    def selected_unit_id(self):
        return self.unit_manager.selected_unit_id

    @property
    def selected_unit_info(self):
        return self.unit_manager.selected_unit_info

    @property
    def selected_unit_pos(self):
        return self.unit_manager.selected_unit_pos

    def get_all_units_info_with_path_state(self):
        """Returns all units info with their current path/movement state"""
        info = []
        for uid, y, x, ut, _ in self.unit_manager.get_all_units_info():
            state = "idle"
            path = self.path_planner.get_path(uid)
            if path:
                dest = self.path_planner.destinations.get(uid)
                if dest:
                    ty, tx = dest["pos"]
                    state = f"moving to (x:{tx}, y:{ty})"
            info.append((uid, y, x, ut, state))
        return info

    def get_unit_info(self, id=None, pos=None):
        return self.unit_manager.get_unit_info(id, pos)

    def get_faction_unit_counts(self):
        return self.unit_manager.get_faction_unit_counts()

    def load_action(self, unit_id, action, params):
        """Load AI actions"""
        if unit_id not in self.unit_manager.unit_all_info:
            return
            
        original_selected = self.unit_manager.selected_unit_id
        try:
            self.unit_manager.selected_unit_id = unit_id
            if action == "move":
                ty, tx = params
                self.plan(ty, tx, action="move")
            elif action == "attack":
                target_uid = params
                if target_uid in self.unit_manager.unit_all_info:
                    ty, tx, _, _ = self.unit_manager.unit_all_info[target_uid]
                    self.plan(ty, tx, action="attack")
        finally:
            self.unit_manager.selected_unit_id = original_selected

    def select_unit_by_mouse(self, mouse_pos):
        grid_x = mouse_pos[0] // self.tile_size
        grid_y = mouse_pos[1] // self.tile_size
        unit = self.unit_manager.get_unit_info(pos=(grid_y, grid_x))
        if unit:
            self.unit_manager.selected_unit_id = unit[0]

    def move(self, direction):
        """
        Move the selected unit in the specified direction.

        Args:
            direction (str): One of 'up', 'down', 'left', 'right'

        Returns:
            bool: True if movement was successful, False otherwise
        """
        # Validate unit selection
        if not self.selected_unit_info:
            return False

        # Get current position and info
        y, x, utype, _ = self.selected_unit_info

        # Calculate new position
        direction_deltas = {
            "up": (-1, 0),
            "down": (1, 0),
            "left": (0, -1),
            "right": (0, 1),
        }

        if direction not in direction_deltas:
            return False

        dy, dx = direction_deltas[direction]
        new_y, new_x = y + dy, x + dx

        # Check map boundaries
        h, w = self.environment_map.shape
        if not (0 <= new_y < h and 0 <= new_x < w):
            return False

        # Check terrain and target tile
        terrain = self.environment_map[new_y][new_x]

        # Validate movement
        if not self.can_enter(utype, terrain):
            return False

        target_unit = self.unit_manager.get_unit_info(pos=(new_y, new_x))
        if target_unit:
            if self.is_enemy(utype, target_unit[3]):
                self.combat(self.selected_unit_id, (new_y, new_x))
                return True
            else:
                # Cannot move into friendly unit's space
                return False

        return self.unit_manager.update_unit_position(self.selected_unit_id, new_y, new_x)

    def can_enter(self, unit_type, terrain):
        # unit_type: R_ping, R_shui, R_shan, W_ping, W_shui, W_shan
        # 根据类型解析出 ping/shui/shan
        force, u_kind = unit_type.split("_", 1)
        # 所有单位都可进入 city, plain, forest
        if terrain in ["city", "plain", "forest", "bridge"]:
            return True
        if u_kind == "shan" and terrain in ["mountain"]:
            return True
        if u_kind == "shui" and terrain in ["river"]:
            return True
        # 如果不符合规则则无法进入
        return False

    def is_enemy(self, utype1, utype2):
        """Delegate enemy check to combat system"""
        return self.combat_system.is_enemy(utype1, utype2)

    def compute_combat(self, attacker, defender):
        # 战斗规则，根据unit类型的ping/shui/shan来决定结果
        # attacker和defender都是比如R_ping或W_shui
        att_faction, att_type = attacker.split("_", 1)
        def_faction, def_type = defender.split("_", 1)

        # 简化规则为：强克制 > 被克制 > 平手（同种类平手则随机?）
        # ping>shan, shui>ping, shan>shui
        att_data = UNIT_STATS[att_type]
        def_data = UNIT_STATS[def_type]

        if (
            att_data["strong_against"] == def_type
            and def_data["strong_against"] == att_type
        ):
            # 双方互克制？则随机
            if random.random() < 0.5:
                return attacker, defender
            else:
                return defender, attacker
        elif att_data["strong_against"] == def_type:
            return attacker, defender
        elif def_data["strong_against"] == att_type:
            return defender, attacker
        else:
            return (attacker, defender) if random.random() < 0.5 else (defender, attacker)

    def compute_visibility(self, faction, vision_range=1):
        """Compute visibility for a faction"""
        # Convert unit info to format needed by VisibilitySystem
        unit_positions = [
            ((y, x), utype)
            for _, y, x, utype, _ in self.unit_manager.get_all_units_info()
        ]
        
        return self.visibility_system.compute_visibility(
            unit_positions,
            faction,
            vision_range
        )

    def plan(self, target_y, target_x, action="move"):
        if not self.selected_unit_info:
            return
        sy, sx, utype, _ = self.selected_unit_info
        self.path_planner.plan_path(
            self.selected_unit_id,
            utype,
            (sy, sx),
            (target_y, target_x),
            action
        )

    def step(self):
        selected_id = self.selected_unit_id
        if selected_id is None:
            return

        path = self.path_planner.get_path(selected_id)
        if not path:
            return

        unit_info = self.unit_manager.get_unit_info(id=selected_id)
        if not unit_info:
            return

        _, sy, sx, utype, _ = unit_info
        ny, nx = path[0]

        if (ny, nx) == (sy, sx):
            self.path_planner.unit_paths[selected_id].popleft()
            if not self.path_planner.unit_paths[selected_id]:
                return
            ny, nx = self.path_planner.unit_paths[selected_id][0]

        target_unit = self.unit_manager.get_unit_info(pos=(ny, nx))
        target_info = self.path_planner.destinations.get(selected_id, {"action": "move"})
        current_action = target_info["action"]

        if target_unit:
            if self.is_enemy(utype, target_unit[3]):
                if current_action == "attack":
                    self.combat(selected_id, (ny, nx))
                else:
                    # move遇敌随机决定战或绕路
                    if random.random() < 0.5:
                        self.combat(selected_id, (ny, nx))
                    else:
                        self.path_planner.reroute(selected_id)
            else:
                self.path_planner.reroute(selected_id)
        else:
            # 空格子，检查可进入地形
            terrain = self.environment_map[ny, nx]
            if self.can_enter(utype, terrain):
                self.unit_manager.update_unit_position(selected_id, ny, nx)
                self.path_planner.unit_paths[selected_id].popleft()
            else:
                self.path_planner.reroute(selected_id)

    def combat(self, uid, enemy_pos):
        """Execute combat using combat system"""
        attacker = self.unit_manager.get_unit_info(id=uid)
        defender = self.unit_manager.get_unit_info(pos=enemy_pos)

        if not attacker or not defender:
            return

        _, _, _, attacker_type, _ = attacker
        defender_id, ey, ex, defender_type, _ = defender

        # Use combat system to resolve combat
        winner_id, loser_id = self.combat_system.resolve_combat(
            uid, attacker_type,
            defender_id, defender_type,
            enemy_pos
        )

        # Handle combat aftermath
        if winner_id == uid:
            self.unit_manager.remove_unit(defender_id)
            self.unit_manager.update_unit_position(uid, ey, ex)
            if self.player_mode == "ai":
                self.path_planner.unit_paths[uid].popleft()
        else:
            self.unit_manager.remove_unit(uid)
            if uid in self.path_planner.unit_paths:
                self.path_planner.unit_paths.pop(uid)
            if uid in self.path_planner.destinations:
                self.path_planner.destinations.pop(uid)

        return winner_id, loser_id
