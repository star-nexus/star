from rts.map.map_data import MapData
from rts.map.map_renderer import MapRenderer
from rts.map.map_generator import MapGenerator
from rts.map.pathfinder import PathFinder


class RTSMapManager:
    """
    RTS游戏地图管理器：负责地图的生成、渲染和管理
    """

    def __init__(self, scene):
        self.scene = scene
        self.map_data = None
        self.map_renderer = None
        self.map_generator = MapGenerator()
        self.pathfinder = None

    def initialize(self, map_width=50, map_height=50, complexity=0.7):
        """初始化地图系统"""
        # 创建地图生成器和地图数据
        self.map_data = self.map_generator.generate_random_map(
            map_width, map_height, complexity=complexity
        )

        # 创建地图渲染器，格子大小为32像素
        self.map_renderer = MapRenderer(tile_size=32)

        # 初始化寻路算法
        self.pathfinder = PathFinder(self.map_data)

    def render(self, screen):
        """渲染地图"""
        if self.map_data and self.map_renderer:
            self.map_renderer.render(screen, self.map_data)

    def move_view(self, dx, dy):
        """移动地图视图"""
        if self.map_renderer:
            self.map_renderer.move_view(dx, dy)

            # 确保地图不会移动到视野之外
            if self.map_data:
                # 获取地图的像素大小
                map_pixel_width = (
                    self.map_data.width
                    * self.map_renderer.tile_size
                    * self.map_renderer.zoom
                )
                map_pixel_height = (
                    self.map_data.height
                    * self.map_renderer.tile_size
                    * self.map_renderer.zoom
                )

                # 获取当前视图的边界
                max_offset_x = max(0, map_pixel_width - self.scene.game.width)
                max_offset_y = max(0, map_pixel_height - self.scene.game.height)

                # 限制地图渲染器偏移量
                self.map_renderer.offset_x = max(
                    0, min(self.map_renderer.offset_x, max_offset_x)
                )
                self.map_renderer.offset_y = max(
                    0, min(self.map_renderer.offset_y, max_offset_y)
                )

    def zoom_in(self, amount):
        """放大地图"""
        if self.map_renderer:
            current_zoom = self.map_renderer.zoom
            self.map_renderer.set_zoom(current_zoom + amount)

    def zoom_out(self, amount):
        """缩小地图"""
        if self.map_renderer:
            current_zoom = self.map_renderer.zoom
            self.map_renderer.set_zoom(current_zoom - amount)

    def screen_to_map(self, screen_x, screen_y):
        """将屏幕坐标转换为地图坐标"""
        if self.map_renderer:
            return self.map_renderer.screen_to_map(screen_x, screen_y)
        return (0, 0)

    def map_to_screen(self, map_x, map_y):
        """将地图坐标转换为屏幕坐标"""
        if self.map_renderer:
            return self.map_renderer.map_to_screen(map_x, map_y)
        return (0, 0)

    def is_valid_position(self, x, y):
        """检查坐标是否在地图范围内"""
        if self.map_data:
            return self.map_data.is_valid_position(x, y)
        return False

    def get_tile(self, x, y):
        """获取指定坐标的地图格子"""
        if self.map_data:
            return self.map_data.get_tile(x, y)
        return None

    def find_path(
        self,
        start_x,
        start_y,
        goal_x,
        goal_y,
        can_traverse_water=False,
        can_traverse_mountain=False,
    ):
        """使用寻路系统查找路径"""
        if self.pathfinder:
            return self.pathfinder.find_path(
                start_x,
                start_y,
                goal_x,
                goal_y,
                can_traverse_water,
                can_traverse_mountain,
            )
        return []

    def generate_new_map(self, complexity):
        """生成新地图"""
        if self.map_data:
            width, height = self.map_data.width, self.map_data.height
            self.map_data = self.map_generator.generate_random_map(
                width, height, complexity=complexity
            )

            # 更新寻路算法
            self.pathfinder = PathFinder(self.map_data)

            print(f"生成了新地图，复杂度: {complexity:.2f}")
            return self.map_data
        return None
