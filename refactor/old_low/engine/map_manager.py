import pygame
import random
import heapq  # Added for A* pathfinding


class Tile:
    """表示地图上的一个瓦片"""

    def __init__(self, tile_type, image, passable=True):
        self.tile_type = tile_type  # 瓦片类型标识符
        self.image = image  # 瓦片图像
        self.passable = passable  # 是否可通行

    def render(self, surface, x, y, tile_size):
        """在指定位置渲染瓦片"""
        if self.image:
            # 如果原始图像大小与瓦片大小不符，进行缩放
            if (
                self.image.get_width() != tile_size
                or self.image.get_height() != tile_size
            ):
                scaled_image = pygame.transform.scale(
                    self.image, (tile_size, tile_size)
                )
                surface.blit(scaled_image, (x, y))
            else:
                surface.blit(self.image, (x, y))


class TileMap:
    """瓦片地图类，管理地图数据和渲染"""

    def __init__(self, width, height, tile_size=32):
        self.width = width  # 地图宽度（瓦片数量）
        self.height = height  # 地图高度（瓦片数量）
        self.tile_size = tile_size  # 瓦片大小（像素）
        self.tiles = [[None for _ in range(height)] for _ in range(width)]  # 地图数据
        self.tile_types = {}  # 瓦片类型字典

    def add_tile_type(self, tile_id, image, passable=True):
        """添加瓦片类型到地图中"""
        self.tile_types[tile_id] = Tile(tile_id, image, passable)

    def set_tile(self, x, y, tile_id):
        """设置指定位置的瓦片类型"""
        if 0 <= x < self.width and 0 <= y < self.height:
            if tile_id in self.tile_types:
                self.tiles[x][y] = self.tile_types[tile_id]
            else:
                print(f"瓦片类型 '{tile_id}' 不存在")
        else:
            print(f"瓦片位置 ({x}, {y}) 超出地图范围")

    def get_tile(self, x, y):
        """获取指定位置的瓦片"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[x][y]
        return None

    def is_passable(self, x, y):
        """检查指定位置是否可通行"""
        tile = self.get_tile(x, y)
        return tile is not None and tile.passable

    def render(self, surface, camera_x=0, camera_y=0):
        """渲染整个地图"""
        # 计算可见区域
        screen_width, screen_height = surface.get_size()
        start_x = max(0, int(camera_x // self.tile_size))
        start_y = max(0, int(camera_y // self.tile_size))
        end_x = min(self.width, int((camera_x + screen_width) // self.tile_size + 1))
        end_y = min(self.height, int((camera_y + screen_height) // self.tile_size + 1))

        # 只渲染可见区域内的瓦片
        for x in range(start_x, end_x):
            for y in range(start_y, end_y):
                if self.tiles[x][y]:
                    screen_x = x * self.tile_size - camera_x
                    screen_y = y * self.tile_size - camera_y
                    self.tiles[x][y].render(surface, screen_x, screen_y, self.tile_size)

    def find_path(self, start_x, start_y, end_x, end_y):
        """使用A*算法在地图上寻找路径

        Args:
            start_x, start_y: 起点坐标
            end_x, end_y: 终点坐标

        Returns:
            路径列表[(x,y), ...] 如果没有找到路径则返回空列表
        """
        if not self.is_passable(start_x, start_y) or not self.is_passable(end_x, end_y):
            return []

        # 定义启发式函数 (曼哈顿距离)
        def heuristic(x, y):
            return abs(x - end_x) + abs(y - end_y)

        # A* 算法
        open_set = []
        heapq.heappush(open_set, (0, start_x, start_y))
        came_from = {}
        g_score = {(start_x, start_y): 0}
        f_score = {(start_x, start_y): heuristic(start_x, start_y)}

        while open_set:
            _, current_x, current_y = heapq.heappop(open_set)

            if current_x == end_x and current_y == end_y:
                # 重建路径
                path = []
                x, y = end_x, end_y
                while (x, y) in came_from:
                    path.append((x, y))
                    x, y = came_from[(x, y)]
                path.append((start_x, start_y))
                return path[::-1]

            # 检查四个方向的相邻瓦片
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                neighbor_x, neighbor_y = current_x + dx, current_y + dy

                # 检查边界和可通行性
                if 0 <= neighbor_x < self.width and 0 <= neighbor_y < self.height:
                    if not self.is_passable(neighbor_x, neighbor_y):
                        continue

                    tentative_g = g_score[(current_x, current_y)] + 1

                    if (neighbor_x, neighbor_y) not in g_score or tentative_g < g_score[
                        (neighbor_x, neighbor_y)
                    ]:
                        came_from[(neighbor_x, neighbor_y)] = (current_x, current_y)
                        g_score[(neighbor_x, neighbor_y)] = tentative_g
                        f_score[(neighbor_x, neighbor_y)] = tentative_g + heuristic(
                            neighbor_x, neighbor_y
                        )
                        if not any(
                            x[1] == neighbor_x and x[2] == neighbor_y for x in open_set
                        ):
                            heapq.heappush(
                                open_set,
                                (
                                    f_score[(neighbor_x, neighbor_y)],
                                    neighbor_x,
                                    neighbor_y,
                                ),
                            )

        return []  # 没有找到路径


class MapManager:
    """地图管理器，负责创建、加载和管理地图"""

    def __init__(self, asset_manager):
        self.asset_manager = asset_manager
        self.current_map = None

    def create_empty_map(self, width, height, tile_size=32):
        """创建一个空白地图"""
        self.current_map = TileMap(width, height, tile_size)
        return self.current_map

    def load_map_from_data(self, map_data, tile_size=32):
        """从二维数组数据加载地图"""
        if not map_data:
            return None

        height = len(map_data)
        width = len(map_data[0])

        self.current_map = TileMap(width, height, tile_size)

        # 设置地图瓦片
        for y in range(height):
            for x in range(width):
                if x < width and y < height:
                    self.current_map.set_tile(x, y, map_data[y][x])

        return self.current_map

    def generate_random_map(self, width, height, tile_types, tile_size=32):
        """生成一个随机地图"""
        self.current_map = TileMap(width, height, tile_size)

        # 首先，将所有瓦片类型添加到地图中
        for tile_id, tile_data in tile_types.items():
            self.current_map.add_tile_type(
                tile_id, tile_data.get("image"), tile_data.get("passable", True)
            )

        # 随机填充地图
        tiles_list = list(tile_types.keys())
        for x in range(width):
            for y in range(height):
                tile_id = random.choice(tiles_list)
                self.current_map.set_tile(x, y, tile_id)

        return self.current_map

    def get_current_map(self):
        """获取当前地图"""
        return self.current_map
