"""
单位转换工具类，用于处理游戏中不同单位系统之间的转换
包括：像素、格子、实际距离(米)之间的换算
"""


class UnitConversion:
    # 基础转换常量
    CELL_SIZE_PIXELS = 32  # 一个格子包含的像素数
    CELL_SIZE_METERS = 100  # 一个格子代表的实际距离(米)
    PIXEL_TO_METER_RATIO = CELL_SIZE_METERS / CELL_SIZE_PIXELS  # 每像素代表的米数

    @classmethod
    def pixels_to_meters(cls, pixels):
        """将像素转换为米"""
        try:
            return float(pixels) * cls.PIXEL_TO_METER_RATIO
        except (ValueError, TypeError):
            print(f"警告: 无效的像素值 '{pixels}' 被转换为0")
            return 0.0

    @classmethod
    def meters_to_pixels(cls, meters):
        """将米转换为像素"""
        try:
            return float(meters) / cls.PIXEL_TO_METER_RATIO
        except (ValueError, TypeError):
            print(f"警告: 无效的米值 '{meters}' 被转换为0")
            return 0.0

    @classmethod
    def cells_to_meters(cls, cells):
        """将格子数转换为米"""
        try:
            return float(cells) * cls.CELL_SIZE_METERS
        except (ValueError, TypeError):
            print(f"警告: 无效的格子值 '{cells}' 被转换为0")
            return 0.0

    @classmethod
    def meters_to_cells(cls, meters):
        """将米转换为格子数（可能是小数）"""
        try:
            return float(meters) / cls.CELL_SIZE_METERS
        except (ValueError, TypeError):
            print(f"警告: 无效的米值 '{meters}' 被转换为0")
            return 0.0

    @classmethod
    def cells_to_pixels(cls, cells):
        """将格子数转换为像素"""
        try:
            return float(cells) * cls.CELL_SIZE_PIXELS
        except (ValueError, TypeError):
            print(f"警告: 无效的格子值 '{cells}' 被转换为0")
            return 0.0

    @classmethod
    def pixels_to_cells(cls, pixels):
        """将像素转换为格子数（可能是小数）"""
        try:
            return float(pixels) / cls.CELL_SIZE_PIXELS
        except (ValueError, TypeError):
            print(f"警告: 无效的像素值 '{pixels}' 被转换为0")
            return 0.0

    @classmethod
    def calculate_movement_distance(cls, speed_mps, delta_time_seconds):
        """
        计算给定速度和时间内应该移动的距离（米）

        Args:
            speed_mps: 速度，单位米/秒
            delta_time_seconds: 时间间隔，单位秒

        Returns:
            float: 应移动的距离，单位米
        """
        try:
            return float(speed_mps) * float(delta_time_seconds)
        except (ValueError, TypeError):
            print(f"警告: 无效的速度或时间值，计算结果为0")
            return 0.0

    @classmethod
    def calculate_pixel_movement(cls, speed_mps, delta_time_seconds):
        """
        计算给定速度和时间内应该移动的像素数

        Args:
            speed_mps: 速度，单位米/秒
            delta_time_seconds: 时间间隔，单位秒

        Returns:
            float: 应移动的像素数
        """
        meters = cls.calculate_movement_distance(speed_mps, delta_time_seconds)
        return cls.meters_to_pixels(meters)
