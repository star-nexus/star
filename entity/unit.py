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

        self.selected_unit_index = 0
        self.units_positions = []  # 存所有单位的位置和类型 [(y, x, type), ...]
        self.player_mode = player_mode  # 存储玩家模式(human or ai)
        self._find_all_units()

        # 路径缓存：key是unit索引，value是当前该单位的路径（队列）
        self.unit_paths = {}
        self.target_positions = {}  # 存储AI的目标位置

    def _find_all_units(self):
        # 扫描unit_map找出所有单位
        h, w = self.unit_map.shape
        for i in range(h):
            for j in range(w):
                if self.unit_map[i][j] is not None:  # 如果这个格子有单位
                    self.units_positions.append((i, j, self.unit_map[i][j]))

    def select_unit_by_index(self, index):
        if 0 <= index < len(self.units_positions):
            self.selected_unit_index = index

    def select_unit_by_mouse(self, mouse_pos):
        # 根据鼠标点击位置选择单位
        # mouse_pos是屏幕坐标，需要转换为格子坐标
        grid_x = mouse_pos[0] // self.tile_size
        grid_y = mouse_pos[1] // self.tile_size
        # 检查点击位置是否有单位
        for idx, (uy, ux, utype) in enumerate(self.units_positions):
            if uy == grid_y and ux == grid_x:
                self.selected_unit_index = idx
                break

    @property
    def selected_unit(self):
        # [MOD] 增加安全访问判断，避免IndexError
        if not self.units_positions:
            return None
        if self.selected_unit_index < 0 or self.selected_unit_index >= len(
            self.units_positions
        ):
            self.selected_unit_index = 0 if self.units_positions else 0
            if not self.units_positions:
                return None
        return self.units_positions[self.selected_unit_index]

    def move_unit(self, direction):
        # direction: 'up', 'down', 'left', 'right'
        if not self.units_positions:
            return

        y, x, utype = self.units_positions[self.selected_unit_index]

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
            if self.is_enemy(utype, target_unit):  # [MOD] 如果是敌人则战斗
                winner, loser = self.resolve_combat(utype, target_unit)
                if winner == utype:
                    # 攻击方胜利
                    self.unit_map[y][x] = None
                    self.unit_map[new_y][new_x] = utype
                    self.units_positions[self.selected_unit_index] = (
                        new_y,
                        new_x,
                        utype,
                    )
                    # 更新units_positions中被击败单位的记录
                    self.remove_unit_from_positions(loser)
                else:
                    # 攻击方失败
                    self.unit_map[y][x] = None
                    self.remove_unit_from_positions(utype)
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
                self.units_positions[self.selected_unit_index] = (new_y, new_x, utype)

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
            for i, (uy, ux, ut) in enumerate(self.units_positions)
            if ut.startswith(faction + "_")
        ]

        if same_faction_units:
            # 还有本阵营单位，则选中一个（如第一个）
            self.selected_unit_index = same_faction_units[0][0]
        else:
            # 无本阵营单位则不设置selected_unit_index，但selected_unit会返回None
            # 后续由主循环判断胜负
            pass

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
        # [MOD] 战斗规则，根据unit类型的ping/shui/shan来决定结果
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
        for uy, ux, utype in self.units_positions:
            if utype.startswith(faction + "_"):
                for dy in range(-vision_range, vision_range + 1):  # 改为5x5，即-2到2
                    for dx in range(-vision_range, vision_range + 1):
                        ny, nx = uy + dy, ux + dx
                        if 0 <= ny < h and 0 <= nx < w:
                            visible[ny][nx] = True
        return visible

    # 寻路相关函数
    def plan_path_to(self, target_y, target_x):
        """
        为当前选中的单位规划路径。如果无法到达目标点，则寻找最近的可到达点。
        """
        sel = self.selected_unit
        if not sel:
            return
        sy, sx, utype = sel
        path = self._find_path(utype, (sy, sx), (target_y, target_x))
        if not path:
            # 找不到直达路径，寻找最接近目标的点
            path = self._find_closest_reachable_point(
                utype, (sy, sx), (target_y, target_x)
            )
        self.unit_paths[self.selected_unit_index] = deque(path) if path else deque()
        self.target_positions[self.selected_unit_index] = (
            target_y,
            target_x,
        )  # 记录目标点

    def step_along_path(self):
        """
        沿规划路径前进一步。如果路径已走完或无路径，则不动。
        """
        if self.selected_unit_index not in self.unit_paths:
            return
        if not self.unit_paths[self.selected_unit_index]:
            return
        # 取出下一个节点
        ny, nx = self.unit_paths[self.selected_unit_index][0]
        sy, sx, utype = self.units_positions[self.selected_unit_index]

        # 检查能否前进到该点
        if (ny, nx) == (sy, sx):
            # 如果第一个节点就是当前点，弹出后再取下一个
            self.unit_paths[self.selected_unit_index].popleft()
            if self.unit_paths[self.selected_unit_index]:
                ny, nx = self.unit_paths[self.selected_unit_index][0]
            else:
                return

        # 检查动态阻挡：目标格子若有其他单位则需重新寻路
        if not self._is_tile_free_for(utype, ny, nx):
            # 尝试重新寻路
            if self.selected_unit_index in self.target_positions:
                ty, tx = self.target_positions[self.selected_unit_index]
                new_path = self._find_path(utype, (sy, sx), (ty, tx))
                if not new_path:
                    new_path = self._find_closest_reachable_point(
                        utype, (sy, sx), (ty, tx)
                    )
                self.unit_paths[self.selected_unit_index] = (
                    deque(new_path) if new_path else deque()
                )
            return

        # 前进到下一节点
        terrain = self.environment_map[ny, nx]
        if self.can_enter(utype, terrain) and self._is_tile_free_for(utype, ny, nx):
            self.unit_map[sy, sx] = None
            self.unit_map[ny, nx] = utype
            self.units_positions[self.selected_unit_index] = (ny, nx, utype)
            self.unit_paths[self.selected_unit_index].popleft()

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

    def _is_tile_free_for(self, utype, y, x):
        # 检查unit_map[y,x] 是否为空或是自己所在的格子
        # 不允许穿过敌人或友方单位
        # 找当前选中单位位置，如果(y,x)正是自己的位置也可通过
        sy, sx, sutype = self.units_positions[self.selected_unit_index]
        if (y, x) == (sy, sx):
            return True
        return self.unit_map[y, x] is None

    def _find_path(self, utype, start, goal):
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
                        utype, ny, nx
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
