class CameraManager:
    """相机管理器，负责处理地图视图的平移和缩放"""

    def __init__(self, screen_width, screen_height):
        """初始化相机管理器

        Args:
            screen_width: 屏幕宽度
            screen_height: 屏幕高度
        """
        self.screen_width = screen_width
        self.screen_height = screen_height

        # 相机位置（左上角坐标）
        self.x = 0
        self.y = 0

        # 缩放级别
        self.zoom = 1.0
        self.min_zoom = 0.5
        self.max_zoom = 2.0

        # 移动速度
        self.move_speed = 10

    def move(self, dx, dy):
        """移动相机

        Args:
            dx: X轴移动量
            dy: Y轴移动量
        """
        self.x += dx * self.move_speed / self.zoom
        self.y += dy * self.move_speed / self.zoom

    def set_position(self, x, y):
        """设置相机位置

        Args:
            x: 新的X坐标
            y: 新的Y坐标
        """
        self.x = x
        self.y = y

    def zoom_in(self):
        """放大"""
        self.adjust_zoom(1.1)

    def zoom_out(self):
        """缩小"""
        self.adjust_zoom(0.9)

    def adjust_zoom(self, factor):
        """调整缩放级别

        Args:
            factor: 缩放因子，大于1表示放大，小于1表示缩小
        """
        new_zoom = self.zoom * factor
        if self.min_zoom <= new_zoom <= self.max_zoom:
            # 计算缩放前的屏幕中心点在世界坐标系中的位置
            center_world_x = self.x + self.screen_width / (2 * self.zoom)
            center_world_y = self.y + self.screen_height / (2 * self.zoom)

            self.zoom = new_zoom

            # 调整相机位置，保持屏幕中心点不变
            self.x = center_world_x - self.screen_width / (2 * self.zoom)
            self.y = center_world_y - self.screen_height / (2 * self.zoom)

    def constrain(self, map_width, map_height, cell_size):
        """限制相机不超出地图边界

        Args:
            map_width: 地图宽度（格子数）
            map_height: 地图高度（格子数）
            cell_size: 格子大小
        """
        # 计算实际地图像素尺寸
        actual_width = map_width * cell_size
        actual_height = map_height * cell_size

        # 限制最小值（不要移出地图左上方）
        self.x = max(0, self.x)
        self.y = max(0, self.y)

        # 限制最大值（不要移出地图右下方）
        max_x = max(0, actual_width - self.screen_width / self.zoom)
        max_y = max(0, actual_height - self.screen_height / self.zoom)
        self.x = min(self.x, max_x)
        self.y = min(self.y, max_y)

    def world_to_screen(self, world_x, world_y):
        """将世界坐标转换为屏幕坐标

        Args:
            world_x: 世界X坐标
            world_y: 世界Y坐标

        Returns:
            tuple: (屏幕X坐标, 屏幕Y坐标)
        """
        screen_x = (world_x - self.x) * self.zoom
        screen_y = (world_y - self.y) * self.zoom
        return int(screen_x), int(screen_y)

    def screen_to_world(self, screen_x, screen_y):
        """将屏幕坐标转换为世界坐标

        Args:
            screen_x: 屏幕X坐标
            screen_y: 屏幕Y坐标

        Returns:
            tuple: (世界X坐标, 世界Y坐标)
        """
        world_x = screen_x / self.zoom + self.x
        world_y = screen_y / self.zoom + self.y
        return world_x, world_y
