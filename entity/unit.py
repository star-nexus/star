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


class UnitController:
    def __init__(self, environment_map, unit_map, tile_size=32, player_mode="human"):
        self.environment_map = environment_map  # 不变的地形地图
        self.unit_map = unit_map  # 存储单位位置的地图，与环境分离
        self.tile_size = tile_size

        self.selected_unit_index = 0  # 没有选中单位则为-1
        self.units_positions = []  # 存所有单位的位置和类型 [(y, x, type), ...]
        self.player_mode = player_mode  # 存储玩家模式(human or ai)
        self._find_all_units()

        # 路径缓存：key是unit id，value是当前该单位的路径（队列）
        self.unit_paths = {}
        self.target_positions = {}  # 存储AI的目标位置

        # 分配单位ID
        # unit_id_map: unit_id -> (y, x, utype)
        # 保证每个单位一个独立ID，可在units_positions生成后分配
        self.unit_id_map = {}
        for i, (uy, ux, ut) in enumerate(self.units_positions):
            self.unit_id_map[i] = (uy, ux, ut)  # i为单位id
        self.infos_dict = self.get_all_units_info_dict()

    @property
    def selected_unit_id(self):
        if self.selected_unit is None:
            return None
        # selected_unit_index对应unit_id
        return self.selected_unit_index

    def get_all_units_info(self):
        """
        返回所有单位的信息列表，以便存盘或显示。
        格式: [(unit_id, y, x, utype, 当前状态), ...]
        当前状态可以是 'idle', 'moving to (ty, tx)', 'attacking unit_id'等。
        """
        info = []
        for uid, (uy, ux, ut) in self.unit_id_map.items():
            state = "idle"
            if uid in self.unit_paths and self.unit_paths[uid]:
                # 有路径则说明正在移动
                if uid in self.target_positions:
                    ty, tx = self.target_positions[uid]
                    state = f"moving to ({ty}, {tx})"
            # 攻击状态的逻辑可根据需要扩展
            info.append((uid, uy, ux, ut, state))
        return info

    def get_all_units_info_dict(self):
        """
        返回所有单位的信息字典，以方便查询。
        格式: [(unit_id, y, x, utype, 当前状态), ...]
        当前状态可以是 'idle', 'moving to (ty, tx)', 'attacking unit_id'等。
        """
        info = {}
        for uid, (uy, ux, ut) in self.unit_id_map.items():
            state = "idle"
            if uid in self.unit_paths and self.unit_paths[uid]:
                # 有路径则说明正在移动
                if uid in self.target_positions:
                    ty, tx = self.target_positions[uid]
                    state = f"moving to ({ty}, {tx})"
            # 攻击状态的逻辑可根据需要扩展
            info[uid] = {"y": uy, "x": ux, "utype": ut, "state": state}
        return info

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
        for uid, (uy, ux, ut) in self.unit_id_map.items():
            faction, utype = ut.split("_", 1)
            if faction in ["R", "W"] and utype in counts[faction]:
                counts[faction][utype] += 1
        return counts

    def execute_action(self, unit_id, action, params):
        """
        执行AI传入的指令，例如:
        action: 'move', params: (target_y, target_x)
        action: 'attack', params: (target_unit_id)
        """
        original_index = self.selected_unit_index
        try:
            if unit_id not in self.unit_id_map:
                return
            # uy, ux, utype = self.unit_id_map[unit_id]
            if action == "move":
                ty, tx = params
                # 调用寻路接口
                self.selected_unit_index = unit_id
                self.plan_path_to(ty, tx, action="move")
            elif action == "attack":

                target_uid = params
                # 攻击逻辑可以先简化为移动到目标单位附近:
                if target_uid in self.unit_id_map:
                    ty, tx, tutype = self.unit_id_map[target_uid]
                    # 寻路到敌人单位附近某点
                    self.selected_unit_index = unit_id
                    # 简化为寻路到目标单位位置（后续扩展为寻路到附近格子）
                    self.plan_path_to(ty, tx, action="attack")
        finally:
            self.selected_unit_index = original_index

    # 需要在单位移动或战斗后更新 self.unit_id_map 中该单位的位置和类型变化
    def _update_unit_position_in_id_map(self, uid, new_y, new_x, new_utype=None):
        # 当单位移动或变动时更新unit_id_map记录
        old_y, old_x, old_utype = self.unit_id_map[uid]
        self.unit_id_map[uid] = (new_y, new_x, new_utype if new_utype else old_utype)

    def _find_all_units(self):
        # 扫描unit_map找出所有单位
        h, w = self.unit_map.shape
        for i in range(h):
            for j in range(w):
                if self.unit_map[i][j] is not None:  # 如果这个格子有单位
                    self.units_positions.append((i, j, self.unit_map[i][j]))

    def select_unit_by_index(self, index):
        if index in self.unit_id_map:
            self.selected_unit_index = index

    def select_unit_by_mouse(self, mouse_pos):
        # 根据鼠标点击位置选择单位
        # mouse_pos是屏幕坐标，需要转换为格子坐标
        grid_x = mouse_pos[0] // self.tile_size
        grid_y = mouse_pos[1] // self.tile_size
        # 检查点击位置是否有单位
        for idx, (uy, ux, utype) in self.unit_id_map.items():
            if uy == grid_y and ux == grid_x:
                self.selected_unit_index = idx
                break

    @property
    def selected_unit(self):
        if self.selected_unit_index < 0:
            return None
        return self.unit_id_map[self.selected_unit_index]

    # [弃用]
    def move_unit(self, direction):
        # direction: 'up', 'down', 'left', 'right'
        if (
            self.selected_unit_index < 0
            or self.selected_unit_index not in self.unit_id_map
        ):
            return

        y, x, utype = self.unit_id_map[self.selected_unit_index]

        new_y, new_x = y, x
        if direction == "up":
            new_y -= 1
        elif direction == "down":
            new_y += 1
        elif direction == "left":
            new_x -= 1
        elif direction == "right":
            new_x += 1

        # 检查边界
        h, w = self.environment_map.shape
        if not (0 <= new_y < h and 0 <= new_x < w):
            return  # 越界，不移动

        # 检查能否进入该地形
        terrain = self.environment_map[new_y][new_x]
        # 检查目标点单位情况
        target_unit = self.unit_map[new_y][new_x]
        if target_unit is not None:
            # 有单位，检查阵营和战斗
            if self.is_enemy(utype, target_unit):  # 如果是敌人则战斗
                winner, loser = self.resolve_combat(utype, target_unit)
                if winner == utype:
                    # 攻击方胜利
                    self.unit_map[y][x] = None
                    self.unit_map[new_y][new_x] = utype
                    # self.units_positions[self.selected_unit_index] = (
                    #     new_y,
                    #     new_x,
                    #     utype,
                    # )
                    self._update_unit_position_in_id_map(
                        self.selected_unit_index, new_y, new_x, utype
                    )
                    # 更新units_positions中被击败单位的记录
                    # self.remove_unit_from_positions(loser)
                    self._remove_unit_by_type(loser)
                else:
                    # 攻击方失败
                    self.unit_map[y][x] = None
                    # self.remove_unit_from_positions(utype)
                    self._remove_unit_by_type(utype)
                    # 如果当前选中单位死了，需要重新选择本阵营单位，如果无则对方获胜
                    self.adjust_selection_after_death(utype)
            else:
                # 同阵营单位，不可进入
                return
        else:
            if self.can_enter(utype, terrain):
                # 更新unit_map
                self.unit_map[y][x] = None
                self.unit_map[new_y][new_x] = utype
                # 更新unit位置列表
                # self.units_positions[self.selected_unit_index] = (new_y, new_x, utype)
                self._update_unit_position_in_id_map(
                    self.selected_unit_index, new_y, new_x, utype
                )

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

    def adjust_selection_after_death(self, dead_utype):
        faction = dead_utype[0]  # 'R' or 'W'
        # 从当前列表中找到与dead_utype同阵营的其他单位
        same_faction_units = [
            (i, (uy, ux, ut))
            for i, (uy, ux, ut) in self.unit_id_map.items()
            if ut.startswith(faction + "_")
        ]

        if same_faction_units:
            # 还有本阵营单位，则选中一个（如第一个）
            self.selected_unit_index = same_faction_units[0][0]
        else:
            # 无本阵营单位则不设置selected_unit_index，但selected_unit会返回None
            # 后续由主循环判断胜负
            pass

    # [弃用]
    def remove_unit_from_positions(self, utype):
        # 移除指定类型的单位（仅移除一个，因为只会有一个该类型刚刚战死）
        for i, (uy, ux, ut) in enumerate(self.units_positions):
            if ut == utype:
                self.units_positions.pop(i)
                break

    def is_enemy(self, utype1, utype2):
        # 简单判断R_和W_前缀阵营不同即为敌人
        return (utype1.startswith("R_") and utype2.startswith("W_")) or (
            utype1.startswith("W_") and utype2.startswith("R_")
        )

    def resolve_combat(self, attacker, defender):
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
        for uy, ux, utype in self.unit_id_map.values():
            if utype.startswith(faction + "_"):
                for dy in range(-vision_range, vision_range + 1):  # 改为5x5，即-2到2
                    for dx in range(-vision_range, vision_range + 1):
                        ny, nx = uy + dy, ux + dx
                        if 0 <= ny < h and 0 <= nx < w:
                            visible[ny][nx] = True
        return visible

    # 寻路相关函数
    def plan_path_to(self, target_y, target_x, action="move"):
        """
        为当前选中的单位规划路径。如果无法到达目标点，则寻找最近的可到达点。
        """
        sel = self.selected_unit
        if not sel:
            return
        sy, sx, utype = sel

        path = self._find_path(utype, (sy, sx), (target_y, target_x), action)
        if not path:
            # 找不到直达路径，寻找最接近目标的点
            path = self._find_closest_reachable_point(
                utype, (sy, sx), (target_y, target_x)
            )
        self.unit_paths[self.selected_unit_index] = deque(path) if path else deque()
        # 这里确保使用字典存储信息
        self.target_positions[self.selected_unit_index] = {
            "pos": (target_y, target_x),
            "action": action,
        }

    def step_along_path(self):
        """
        沿规划路径前进一步。如果路径已走完或无路径，则不动。
        """
        # if self.selected_unit_index not in self.unit_paths:
        #     return
        # if not self.unit_paths[self.selected_unit_index]:
        #     return
        # # 取出下一个节点
        # ny, nx = self.unit_paths[self.selected_unit_index][0]
        # sy, sx, utype = self.units_positions[self.selected_unit_index]
        uid = self.selected_unit_index
        if uid not in self.unit_id_map:
            return
        if uid not in self.unit_paths:
            return
        if not self.unit_paths[uid]:
            return
        ny, nx = self.unit_paths[uid][0]
        sy, sx, utype = self.unit_id_map[uid]

        # # 检查能否前进到该点
        # if (ny, nx) == (sy, sx):
        #     # 如果第一个节点就是当前点，弹出后再取下一个
        #     self.unit_paths[self.selected_unit_index].popleft()
        #     if self.unit_paths[self.selected_unit_index]:
        #         ny, nx = self.unit_paths[self.selected_unit_index][0]
        #     else:
        #         return
        # 如果下个节点就是当前点，弹出后取下一个
        if (ny, nx) == (sy, sx):
            self.unit_paths[uid].popleft()
            if not self.unit_paths[uid]:
                return
            ny, nx = self.unit_paths[uid][0]
        # 检查下个格子上的单位情况
        occupant = self.unit_map[ny, nx]
        target_info = self.target_positions.get(uid, {"action": "move"})
        current_action = target_info["action"]

        if occupant is not None:
            # 有单位
            if self.is_enemy(utype, occupant):
                # 遇敌
                if current_action == "attack":
                    # 攻击行动下必然战斗
                    self._do_combat(uid, (ny, nx), utype, occupant)
                else:
                    # move遇敌随机决定战或绕路
                    if random.random() < 0.5:
                        # 战斗
                        self._do_combat(uid, (ny, nx), utype, occupant)
                    else:
                        # 尝试绕路(重新寻路)
                        self._reroute(uid)
            else:
                # 友军单位，尝试绕路
                self._reroute(uid)
        else:
            # 空格子，检查可进入地形
            terrain = self.environment_map[ny, nx]
            if self.can_enter(utype, terrain):
                self.unit_map[sy, sx] = None
                self.unit_map[ny, nx] = utype
                # self.units_positions[uid] = (ny, nx, utype)
                self.unit_paths[uid].popleft()
                # 同步更新 unit_id_map
                self._update_unit_position_in_id_map(uid, ny, nx)
            else:
                # 不可进入，尝试绕路
                self._reroute(uid)

        # # 检查动态阻挡：目标格子若有其他单位则需重新寻路
        # if not self._is_tile_free_for(utype, ny, nx):
        #     # 尝试重新寻路
        #     if self.selected_unit_index in self.target_positions:
        #         ty, tx = self.target_positions[self.selected_unit_index]
        #         new_path = self._find_path(utype, (sy, sx), (ty, tx))
        #         if not new_path:
        #             new_path = self._find_closest_reachable_point(
        #                 utype, (sy, sx), (ty, tx)
        #             )
        #         self.unit_paths[self.selected_unit_index] = (
        #             deque(new_path) if new_path else deque()
        #         )
        #     return

        # # 前进到下一节点
        # terrain = self.environment_map[ny, nx]
        # if self.can_enter(utype, terrain) and self._is_tile_free_for(utype, ny, nx):
        #     self.unit_map[sy, sx] = None
        #     self.unit_map[ny, nx] = utype
        #     self.units_positions[self.selected_unit_index] = (ny, nx, utype)
        #     self.unit_paths[self.selected_unit_index].popleft()

        # #  更新 unit_id_map
        # uid = self.selected_unit_index
        # self._update_unit_position_in_id_map(uid, ny, nx)

        # terrain = self.environment_map[ny, nx]
        # if self.can_enter(utype, terrain) and self.unit_map[ny, nx] is None:
        #     # 更新unit_map和units_positions
        #     self.unit_map[sy, sx] = None
        #     self.unit_map[ny, nx] = utype
        #     self.units_positions[self.selected_unit_index] = (ny, nx, utype)
        #     self.unit_paths[
        #         self.selected_unit_index
        #     ].popleft()  # 前进成功，移除已达到的点
        # else:
        #     # 无法前进，路径阻塞，尝试重新规划或放弃
        #     self.unit_paths[self.selected_unit_index].clear()

    def _do_combat(self, uid, enemy_pos, attacker_type, defender_type):
        # 执行战斗结算
        sy, sx, sutype = self.unit_id_map[uid]
        ey, ex = enemy_pos
        # defender_uid
        defender_uid = self.find_unit_id_by_pos(ey, ex)
        if defender_uid is None:
            # 如果地图数据不同步，无法找到防守方单位id，则不战
            print("地图数据不同步，无法找到防守方单位id")
            return
        winner, loser = self.resolve_combat(sutype, defender_type)
        if winner == sutype:
            # 攻击方胜利
            self.unit_map[sy, sx] = None
            # self.unit_map[ey, ex] = sutype
            # self.units_positions[uid] = (ey, ex, sutype)
            self._update_unit_position_in_id_map(uid, ey, ex)
            self._remove_unit_by_id(defender_uid)
            self.unit_map[ey, ex] = sutype
            self.unit_paths[uid].popleft()
        else:
            # 攻击方失败
            self.unit_map[sy, sx] = None
            self._remove_unit_by_id(uid)  # 攻击方消失
            # selected_unit_index可能失效，如果该单位死了需要调整
            if uid in self.unit_paths:
                self.unit_paths.pop(uid)
            if uid in self.target_positions:
                self.target_positions.pop(uid)

    def find_unit_id_by_pos(self, y, x):
        for uid, (uy, ux, ut) in self.unit_id_map.items():
            if (uy, ux) == (y, x):
                return uid
        return None

    def _remove_unit_by_id(self, id):
        # 从 units_positions, unit_id_map, unit_map 中移除指定类型的单位(一个)
        remove_uid = id

        if remove_uid is not None:
            uy, ux, ut = self.unit_id_map[remove_uid]
            self.unit_map[uy, ux] = None
            # 从units_positions中删除
            # for i, (py, px, put) in enumerate(self.units_positions):
            #     if (py, px, put) == (uy, ux, ut):
            #         self.units_positions.pop(i)
            #         break
            # 从unit_id_map中删除
            self.unit_id_map.pop(remove_uid, None)
            # 若死的正是选中单位，需要处理selected_unit_index
            if self.selected_unit_index == remove_uid:
                self.selected_unit_index = -1

    def _remove_unit_by_type(self, utype):
        # 从 units_positions, unit_id_map, unit_map 中移除指定类型的单位(一个)
        remove_uid = None
        for uid, (uy, ux, ut) in self.unit_id_map.items():
            if ut == utype:
                remove_uid = uid
                break
        if remove_uid is not None:
            uy, ux, ut = self.unit_id_map[remove_uid]
            self.unit_map[uy, ux] = None
            # 从units_positions中删除
            # for i, (py, px, put) in enumerate(self.units_positions):
            #     if (py, px, put) == (uy, ux, ut):
            #         self.units_positions.pop(i)
            #         break
            # 从unit_id_map中删除
            self.unit_id_map.pop(remove_uid, None)
            # 若死的正是选中单位，需要处理selected_unit_index
            if self.selected_unit_index == remove_uid:
                self.selected_unit_index = 0
                if len(self.unit_id_map) == 0:
                    self.selected_unit_index = -1

    def _reroute(self, uid):
        sy, sx, utype = self.unit_id_map[uid]
        tinfo = self.target_positions.get(uid)
        if not tinfo:
            # 没有目标就不动了
            self.unit_paths[uid].clear()
            return
        ty, tx = tinfo["pos"]
        action = tinfo["action"]
        new_path = self._find_path(utype, (sy, sx), (ty, tx))
        if not new_path:
            new_path = self._find_closest_reachable_point(utype, (sy, sx), (ty, tx))
        self.unit_paths[uid] = deque(new_path) if new_path else deque()

    def _is_tile_free_for(self, utype, y, x, action="move"):
        # 检查unit_map[y,x] 是否为空或是自己所在的格子
        # 不允许穿过敌人或友方单位
        # 找当前选中单位位置，如果(y,x)正是自己的位置也可通过
        sy, sx, sutype = self.unit_id_map[self.selected_unit_index]
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

    def _find_path(self, utype, start, goal, action="move"):
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
                return self._reconstruct_path(parent, start, goal)

            for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx]:
                    terrain = self.environment_map[ny, nx]
                    if self.can_enter(utype, terrain) and self._is_tile_free_for(
                        utype, ny, nx, action
                    ):
                        visited[ny, nx] = True
                        parent[(ny, nx)] = (y, x)
                        queue.append((ny, nx))

        # 未找到目标
        return None

    def _find_closest_reachable_point(self, utype, start, goal):
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
                    if self.can_enter(utype, terrain) and self._is_tile_free_for(
                        utype, ny, nx
                    ):
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
            return self._reconstruct_path(parent, start, best_point)
        return None

    def _reconstruct_path(self, parent, start, goal):
        path = []
        cur = goal
        while cur != start:
            path.append(cur)
            cur = parent[cur]
        path.append(start)
        path.reverse()
        return path

    def get_unit_path(self):
        # 返回当前选中单位的路径列表（用于渲染）
        if self.selected_unit_index in self.unit_paths:
            return list(self.unit_paths[self.selected_unit_index])
        return []

    # 获取当前选择单位的信息
    def get_selected_unit_info(self):
        if self.selected_unit_index < 0:
            return None
        return self.infos_dict[self.selected_unit_index]

    # 通过位置获取单位信息
    def get_unit_info_by_pos(self, y, x):
        uid = self.find_unit_id_by_pos(y, x)
        if uid is None:
            return None
        return self.infos_dict[uid]
