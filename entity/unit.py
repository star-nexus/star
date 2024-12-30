from collections import deque
import random
import numpy as np

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

        # Meta
        self.running_id = -1  # 没有选中单位则为-1
        self.player_mode = player_mode  # 存储玩家模式(human or ai)
        # 地图
        self.environment_map = environment_map  # 不变的地形地图
        self.unit_map = unit_map  # 存储单位位置的地图，与环境分离
        self.tile_size = tile_size

        # 存储单位的位置信息
        self.unit_all_info = {}

        # 扫描unit_map找出所有单位
        h, w = self.unit_map.shape
        index = 0
        for i in range(h):
            for j in range(w):
                if self.unit_map[i][j] is not None:  # 如果这个格子有单位
                    self.unit_all_info[index] = (i, j, self.unit_map[i][j], "idle")
                    index += 1

        # 路径缓存：key是unit id，value是当前该单位的路径（队列）
        self.unit_paths = {}
        self.destination = {}  # 存储AI的目标位置

    @property
    def selected_unit_id(self):
        if self.selected_unit_info is None:
            return None
        return self.running_id

    @property
    def selected_unit_info(self):
        if self.running_id < 0:
            return None
        return self.unit_all_info[self.running_id]

    @property
    def selected_unit_pos(self):
        if self.running_id < 0:
            return None
        return self.unit_all_info[self.running_id][:2]

    #### GET ####
    def get_all_units_info(self):
        """
        返回所有单位的信息列表，以便存盘或显示。
        格式: [(unit_id, y, x, utype, 当前状态), ...]
        当前状态可以是 'idle', 'moving to (ty, tx)', 'attacking unit_id'等。
        """
        info = []
        for uid, (uy, ux, ut, _) in self.unit_all_info.items():
            state = "idle"
            if uid in self.unit_paths and self.unit_paths[uid]:
                # 有路径则说明正在移动
                if uid in self.destination:
                    ty, tx = self.destination[uid]["pos"]
                    state = f"moving to (x:{tx}, y:{ty})"
            # 攻击状态的逻辑可根据需要扩展
            info.append((uid, uy, ux, ut, state))
        return info

    def get_unit_info(self, id=None, pos=None):
        """Get unit information by either unit ID or position.

        Args:
            id: Unit ID to look up
            pos: Position tuple (y, x) to look up

        Returns:
            Tuple of (id, y, x, unit_type, state) if unit found, None otherwise

        Examples:
            >>> unit_controller.get_unit_info(id=5)  # Get unit with ID 5
            >>> unit_controller.get_unit_info(pos=(10, 15))  # Get unit at position (10,15)
        """
        # ID-based lookup (O(1))
        if id is not None and id in self.unit_all_info:
            return (id, *self.unit_all_info[id])

        # Position-based lookup (O(n))
        if pos is not None:
            try:
                current_y, current_x = pos
                for id, unit_info in self.unit_all_info.items():
                    y, x, unit_type, state = unit_info
                    if (y, x) == (current_y, current_x):
                        return (id, y, x, unit_type, state)
            except (TypeError, ValueError):
                return None

        return None

    def get_unit_path(self):
        # 返回当前选中单位的路径列表（用于渲染）
        if self.running_id in self.unit_paths:
            return list(self.unit_paths[self.running_id])
        return []

    def get_faction_unit_counts(self):
        """
        返回 R 和 W 阵营各类型单位数量统计
        格式: {
          'R': {'ping':数量, 'shui':数量, 'shan':数量},
          'W': {'ping':数量, 'shui':数量, 'shan':数量}
        }
        """
        counts = {
            "R": {"ping": 0, "shui": 0, "shan": 0},
            "W": {"ping": 0, "shui": 0, "shan": 0},
        }
        for uid, (uy, ux, ut, _) in self.unit_all_info.items():
            faction, utype = ut.split("_", 1)
            if faction in ["R", "W"] and utype in counts[faction]:
                counts[faction][utype] += 1
        return counts

    def load_action(self, unit_id, action, params):
        """
        加载AI传入的指令，例如:
        action: 'move', params: (target_y, target_x)
        action: 'attack', params: (target_unit_id)
        """
        original_index = self.running_id
        try:
            if unit_id not in self.unit_all_info:
                return
            # uy, ux, utype = self.unit_id_map[unit_id]
            if action == "move":
                ty, tx = params
                # 调用寻路接口
                self.running_id = unit_id
                self.plan(ty, tx, action="move")
            elif action == "attack":

                target_uid = params
                # 攻击逻辑可以先简化为移动到目标单位附近:
                if target_uid in self.unit_all_info:
                    ty, tx, _, _ = self.unit_all_info[target_uid]
                    self.running_id = unit_id
                    self.plan(ty, tx, action="attack")
        finally:
            self.running_id = original_index

    #### UPDATE ####
    def update_unit_position(self, uid, new_y, new_x, new_utype=None):
        """
        Updates a unit's position and synchronizes the unit map.

        Args:
            uid: Unit ID to update
            new_y: New Y coordinate
            new_x: New X coordinate
            new_utype: Optional new unit type

        Returns:
            bool: True if update successful, False otherwise
        """
        # Validate unit exists
        if uid not in self.unit_all_info:
            return False

        # Get current unit info
        old_y, old_x, old_utype, state = self.unit_all_info[uid]

        # Validate new coordinates are within map bounds
        h, w = self.unit_map.shape
        if not (0 <= new_y < h and 0 <= new_x < w):
            return False

        # Update unit_map
        self.unit_map[old_y, old_x] = None
        self.unit_map[new_y, new_x] = new_utype if new_utype else old_utype

        # Update unit info
        self.unit_all_info[uid] = (
            new_y,
            new_x,
            new_utype if new_utype else old_utype,
            state,
        )

        return True

    def select_unit_by_mouse(self, mouse_pos):
        # 根据鼠标点击位置选择单位
        # mouse_pos是屏幕坐标，需要转换为格子坐标
        grid_x = mouse_pos[0] // self.tile_size
        grid_y = mouse_pos[1] // self.tile_size
        # 检查点击位置是否有单位
        for idx, (uy, ux, _, _) in self.unit_all_info.items():
            if uy == grid_y and ux == grid_x:
                self.running_id = idx
                break

    # Human 控制移动
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

        # Handle unit interactions
        target_unit_type = self.unit_map[new_y][new_x]
        if target_unit_type is not None:
            if self.is_enemy(utype, target_unit_type):
                # Initiate combat if enemy
                print("combat target: ", (new_y, new_x))
                self.combat(self.selected_unit_id, (new_y, new_x))
                return True
            else:
                # Cannot move into friendly unit's space
                return False

        # Execute movement
        return self.update_unit_position(self.selected_unit_id, new_y, new_x)

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
        # 简单判断R_和W_前缀阵营不同即为敌人
        return (utype1.startswith("R_") and utype2.startswith("W_")) or (
            utype1.startswith("W_") and utype2.startswith("R_")
        )

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
            # 平种类，简单看成五五开
            if random.random() < 0.5:
                return attacker, defender
            else:
                return defender, attacker

    # 计算视野函数
    def compute_visibility(self, faction, vision_range=1):
        h, w = self.environment_map.shape
        visible = np.full((h, w), False, dtype=bool)
        # 使用vision_range参数决定视野范围，注意为5x5则range为2上下扩展
        for uy, ux, utype, _ in self.unit_all_info.values():
            if utype.startswith(faction + "_"):
                for dy in range(-vision_range, vision_range + 1):  # 改为5x5，即-2到2
                    for dx in range(-vision_range, vision_range + 1):
                        ny, nx = uy + dy, ux + dx
                        if 0 <= ny < h and 0 <= nx < w:
                            visible[ny][nx] = True
        return visible

    # 寻路相关函数
    def plan(self, target_y, target_x, action="move"):
        """
        为当前选中的单位规划路径。如果无法到达目标点，则寻找最近的可到达点。
        """
        sel = self.selected_unit_info
        if not sel:
            return
        sy, sx, utype, _ = sel

        path = self.find_path(utype, (sy, sx), (target_y, target_x), action)
        if not path:
            # 找不到直达路径，寻找最接近目标的点
            path = self.find_closest_reachable_point(
                utype, (sy, sx), (target_y, target_x)
            )
        self.unit_paths[self.running_id] = deque(path) if path else deque()
        # 这里确保使用字典存储信息
        self.destination[self.running_id] = {
            "pos": (target_y, target_x),
            "action": action,
        }

    def step(self):
        """
        沿规划路径前进一步。如果路径已走完或无路径，则不动。
        """
        uid = self.running_id
        if uid not in self.unit_all_info:
            return
        if uid not in self.unit_paths:
            return
        if not self.unit_paths[uid]:
            return
        ny, nx = self.unit_paths[uid][0]
        sy, sx, utype, _ = self.unit_all_info[uid]


        # 如果下个节点就是当前点，弹出后取下一个
        if (ny, nx) == (sy, sx):
            self.unit_paths[uid].popleft()
            if not self.unit_paths[uid]:
                return
            ny, nx = self.unit_paths[uid][0]
        # 检查下个格子上的单位情况
        occupant = self.unit_map[ny, nx]
        target_info = self.destination.get(uid, {"action": "move"})
        current_action = target_info["action"]

        if occupant is not None:
            # 有单位
            if self.is_enemy(utype, occupant):
                # 遇敌
                if current_action == "attack":
                    # 攻击行动下必然战斗
                    self.combat(uid, (ny, nx))
                else:
                    # move遇敌随机决定战或绕路
                    if random.random() < 0.5:
                        # 战斗
                        self.combat(uid, (ny, nx))
                    else:
                        # 尝试绕路(重新寻路)
                        self.reroute(uid)
            else:
                # 友军单位，尝试绕路
                self.reroute(uid)
        else:
            # 空格子，检查可进入地形
            terrain = self.environment_map[ny, nx]
            if self.can_enter(utype, terrain):
                self.unit_map[sy, sx] = None
                self.unit_map[ny, nx] = utype
                # self.units_positions[uid] = (ny, nx, utype)
                self.unit_paths[uid].popleft()
                # 同步更新 unit_id_map
                self.update_unit_position(uid, ny, nx)
            else:
                # 不可进入，尝试绕路
                self.reroute(uid)

    def combat(self, uid, enemy_pos):
        # 执行战斗结算
        sy, sx, sutype, _ = self.unit_all_info[uid]
        defender_uid, ey, ex, eutype, _ = self.get_unit_info(pos=enemy_pos)

        if defender_uid is None:
            # 如果地图数据不同步，无法找到防守方单位id，则不战
            print("地图数据不同步，无法找到防守方单位id")
            return
        winner, _ = self.compute_combat(sutype, eutype)
        if winner == sutype:
            # 攻击方胜利
            self.unit_map[sy, sx] = None
            self.remove_unit(defender_uid)
            self.update_unit_position(uid, ey, ex)
            self.unit_map[ey, ex] = sutype
            if self.player_mode == "ai":
                self.unit_paths[uid].popleft()
            winner_id, loser_id = uid, defender_uid
        else:
            # 攻击方失败
            self.unit_map[sy, sx] = None
            self.remove_unit(uid)  # 攻击方消失
            if uid in self.unit_paths:
                self.unit_paths.pop(uid)
            if uid in self.destination:
                self.destination.pop(uid)
            winner_id, loser_id = defender_uid, uid
        return winner_id, loser_id

    def remove_unit(self, id):
        # 从 units_positions, unit_id_map, unit_map 中移除指定类型的单位(一个)
        remove_uid = id

        if remove_uid is not None:
            uy, ux, ut, _ = self.unit_all_info[remove_uid]
            self.unit_map[uy, ux] = None

            self.unit_all_info.pop(remove_uid, None)
            # 若死的正是选中单位，需要处理running_id
            if self.running_id == remove_uid:
                self.running_id = -1

    def reroute(self, uid):
        sy, sx, utype, _ = self.unit_all_info[uid]
        tinfo = self.destination.get(uid)
        if not tinfo:
            # 没有目标就不动了
            self.unit_paths[uid].clear()
            return
        ty, tx = tinfo["pos"]
        action = tinfo["action"]
        new_path = self.find_path(utype, (sy, sx), (ty, tx))
        if not new_path:
            new_path = self.find_closest_reachable_point(utype, (sy, sx), (ty, tx))
        self.unit_paths[uid] = deque(new_path) if new_path else deque()

    def is_tile_free(self, y, x, action="move"):
        # 检查unit_map[y,x] 是否为空或是自己所在的格子
        # 不允许穿过敌人或友方单位
        # 找当前选中单位位置，如果(y,x)正是自己的位置也可通过
        sy, sx, sutype, _ = self.unit_all_info[self.running_id]
        if (y, x) == (sy, sx):
            return True
        free = self.unit_map[y, x] is None
        if free == True:
            return free
        elif action == "attack":
            if self.is_enemy(sutype, self.unit_map[y, x]):
                return True
            else:
                return False
        else:
            return False

    def find_path(self, utype, start, goal, action="move"):
        """
        使用BFS寻找从start到goal的路径。
        返回路径坐标列表(含起点和终点)，若不可达则返回None。
        """
        sy, sx = start
        gy, gx = goal
        h, w = self.environment_map.shape
        visited = np.full((h, w), False, dtype=bool)
        parent = dict()

        queue = deque()
        queue.append((sy, sx))
        visited[sy, sx] = True

        while queue:
            y, x = queue.popleft()
            if (y, x) == (gy, gx):
                # 找到目标，回溯路径
                return self.reconstruct_path(parent, start, goal)

            for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx]:
                    terrain = self.environment_map[ny, nx]
                    if self.can_enter(utype, terrain) and self.is_tile_free(
                        ny, nx, action
                    ):
                        visited[ny, nx] = True
                        parent[(ny, nx)] = (y, x)
                        queue.append((ny, nx))

        # 未找到目标
        return None

    def find_closest_reachable_point(self, utype, start, goal):
        """
        当目标不可达时，使用BFS扩张所有可达点，
        在可达点中选择与goal曼哈顿距离最近的点。
        然后返回到该点的路径。
        """
        sy, sx = start
        gy, gx = goal
        h, w = self.environment_map.shape
        visited = np.full((h, w), False, dtype=bool)
        parent = dict()

        queue = deque()
        queue.append((sy, sx))
        visited[sy, sx] = True

        reachable_points = []
        while queue:
            y, x = queue.popleft()
            reachable_points.append((y, x))
            for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx]:
                    terrain = self.environment_map[ny, nx]
                    if self.can_enter(utype, terrain) and self.is_tile_free(ny, nx):
                        visited[ny, nx] = True
                        parent[(ny, nx)] = (y, x)
                        queue.append((ny, nx))

        # 从reachable_points中选与goal距离最近的
        best_point = None
        best_dist = float("inf")
        for ry, rx in reachable_points:
            dist = abs(ry - gy) + abs(rx - gx)
            if dist < best_dist:
                best_dist = dist
                best_point = (ry, rx)
        if best_point is not None and best_point != (sy, sx):
            return self.reconstruct_path(parent, start, best_point)
        return None

    def reconstruct_path(self, parent, start, goal):
        path = []
        cur = goal
        while cur != start:
            path.append(cur)
            cur = parent[cur]
        path.append(start)
        path.reverse()
        return path
