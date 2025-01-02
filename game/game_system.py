from .planner import PathPlanner
from .agents import Unit
from .visibility import VisibilitySystem
from .combat import CombatSystem
from .movement import MovementController

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
- plan: 规划路径
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


# Game 1: Two forces encouters.
class TwoForcesEncounter:
    def __init__(self, environment_map, unit_map, tile_size=32, player_mode="human"):
        # Initialize unit manager
        self.unit_manager = Unit(unit_map)

        # Meta
        self._is_ai_mode = player_mode == "ai"
        self.environment_map = environment_map
        self.tile_size = tile_size

        # Initialize path planner
        self.path_planner = PathPlanner(environment_map, self)

        # Initialize visibility system
        self.visibility_system = VisibilitySystem(environment_map.shape)

        # Initialize combat system
        self.combat_system = CombatSystem(
            UNIT_STATS,
            self.unit_manager,
            self.path_planner,
            is_ai_mode=self._is_ai_mode,
        )

        # Initialize movement controller
        self.movement_controller = MovementController(
            environment_map, self.unit_manager, self.path_planner, self.combat_system
        )

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
        """Delegate movement to movement controller"""
        if self.selected_unit_id is None:
            return False
        return self.movement_controller.move(self.selected_unit_id, direction)

    def can_enter(self, unit_type, terrain):
        """Delegate terrain check to movement controller"""
        return self.movement_controller.can_enter(unit_type, terrain)

    def compute_visibility(self, faction, vision_range=1):
        """Compute visibility for a faction"""
        # Convert unit info to format needed by VisibilitySystem
        unit_positions = [
            ((y, x), utype)
            for _, y, x, utype, _ in self.unit_manager.get_all_units_info()
        ]

        return self.visibility_system.compute_visibility(
            unit_positions, faction, vision_range
        )

    def plan(self, target_y, target_x, action="move"):
        if not self.selected_unit_info:
            return
        sy, sx, utype, _ = self.selected_unit_info
        self.path_planner.plan_path(
            self.selected_unit_id, utype, (sy, sx), (target_y, target_x), action
        )

    def step(self):
        """Delegate path following to movement controller"""
        if self.selected_unit_id is None:
            return
        self.movement_controller.step(self.selected_unit_id)


# Game 2: Romance of the three kingdoms
class RomanceThreeKingdoms:
    pass


# Game 3: Agent use LLM for decision making. Stronger LLM defeats weaker one.
class LLMAgentArena:
    pass
