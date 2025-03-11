import heapq
import math


class PathFinder:
    """A* 寻路算法实现"""

    def __init__(self, map_data):
        self.map_data = map_data

    def find_path(
        self,
        start_x,
        start_y,
        goal_x,
        goal_y,
        can_traverse_water=False,
        can_traverse_mountain=False,
    ):
        """
        使用A*算法查找从起点到终点的路径
        :param start_x, start_y: 起始位置（格子坐标）
        :param goal_x, goal_y: 目标位置（格子坐标）
        :param can_traverse_water: 单位是否能穿越水面
        :param can_traverse_mountain: 单位是否能穿越山地
        :return: 路径列表[(x1,y1), (x2,y2), ...] 或空列表表示没找到路径
        """
        # 检查起止点是否有效
        if not self.map_data.is_valid_position(
            start_x, start_y
        ) or not self.map_data.is_valid_position(goal_x, goal_y):
            return []

        # 检查终点是否可到达
        goal_tile = self.map_data.get_tile(goal_x, goal_y)
        if not goal_tile.passable and not (
            can_traverse_water and goal_tile.type == "water"
        ):
            # 如果终点不可通行，找最近的可通行点
            goal_x, goal_y = self._find_nearest_passable(
                goal_x, goal_y, can_traverse_water, can_traverse_mountain
            )

            if goal_x is None:
                return []  # 找不到可通行的终点

        # A*算法
        open_set = []  # 优先队列，存储(f, (x, y))
        closed_set = set()  # 已探索的节点

        # g: 从起点到当前节点的代价
        # h: 从当前节点到目标的启发式估计
        # f: g + h
        g_score = {(start_x, start_y): 0}
        h_score = {
            (start_x, start_y): self._heuristic(start_x, start_y, goal_x, goal_y)
        }
        f_score = {(start_x, start_y): h_score[(start_x, start_y)]}

        # 用于重建路径
        came_from = {}

        # 添加起始节点
        heapq.heappush(open_set, (f_score[(start_x, start_y)], (start_x, start_y)))

        while open_set:
            _, current = heapq.heappop(open_set)
            current_x, current_y = current

            if current == (goal_x, goal_y):
                # 达到目标，重建路径
                return self._reconstruct_path(came_from, current)

            closed_set.add(current)

            # 获取相邻节点
            neighbors = self._get_neighbors(
                current_x, current_y, can_traverse_water, can_traverse_mountain
            )

            for neighbor in neighbors:
                if neighbor in closed_set:
                    continue

                # 计算从起点经过当前点到邻居的距离
                tentative_g_score = g_score[current] + self._movement_cost(
                    current, neighbor
                )

                # 如果这是一条更好的路径，或者是新发现的节点
                if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                    # 记录这条路径
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    h_score[neighbor] = self._heuristic(
                        neighbor[0], neighbor[1], goal_x, goal_y
                    )
                    f_score[neighbor] = g_score[neighbor] + h_score[neighbor]

                    # 添加到开放集
                    if neighbor not in [item[1] for item in open_set]:
                        heapq.heappush(open_set, (f_score[neighbor], neighbor))

        # 如果没有找到路径
        return []

    def _heuristic(self, x1, y1, x2, y2):
        """
        计算两点间的估计距离（曼哈顿距离）
        """
        return abs(x1 - x2) + abs(y1 - y2)

    def _get_neighbors(
        self, x, y, can_traverse_water=False, can_traverse_mountain=False
    ):
        """
        获取节点的相邻节点
        """
        neighbors = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:  # 四方向
            nx, ny = x + dx, y + dy

            if not self.map_data.is_valid_position(nx, ny):
                continue

            tile = self.map_data.get_tile(nx, ny)

            # 检查是否可通行
            if (
                tile.passable
                or (can_traverse_water and tile.type == "water")
                or (can_traverse_mountain and tile.type == "mountain")
            ):
                neighbors.append((nx, ny))

        return neighbors

    def _movement_cost(self, from_pos, to_pos):
        """
        计算从from_pos移动到to_pos的代价
        """
        # 基础代价
        cost = 1.0

        # 获取目标格子
        x, y = to_pos
        tile = self.map_data.get_tile(x, y)

        # 根据地形类型增加代价
        if tile:
            cost *= tile.movement_cost

        return cost

    def _reconstruct_path(self, came_from, current):
        """
        根据came_from重建路径
        """
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)

        # 返回反转后的路径（从起点到终点）
        return path[::-1]

    def _find_nearest_passable(
        self, x, y, can_traverse_water=False, can_traverse_mountain=False
    ):
        """
        寻找离(x,y)最近的可通行格子
        """
        # 简单的环形搜索
        for radius in range(1, 10):  # 限制搜索半径
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    # 仅检查圆环
                    if abs(dx) == radius or abs(dy) == radius:
                        nx, ny = x + dx, y + dy

                        if not self.map_data.is_valid_position(nx, ny):
                            continue

                        tile = self.map_data.get_tile(nx, ny)
                        if (
                            tile.passable
                            or (can_traverse_water and tile.type == "water")
                            or (can_traverse_mountain and tile.type == "mountain")
                        ):
                            return nx, ny

        return None, None  # 找不到可通行的格子
