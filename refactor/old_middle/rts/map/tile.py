class TileType:
    """
    地形类型常量
    """

    PLAINS = "plains"  # 平原
    MOUNTAIN = "mountain"  # 山地
    WATER = "water"  # 水面
    FOREST = "forest"  # 森林
    SWAMP = "swamp"  # 沼泽

    # 地形颜色映射 (用于渲染)
    COLORS = {
        PLAINS: (180, 230, 150),  # 浅绿色
        MOUNTAIN: (150, 150, 150),  # 灰色
        WATER: (100, 180, 255),  # 蓝色
        FOREST: (50, 150, 50),  # 深绿色
        SWAMP: (130, 150, 90),  # 褐绿色
    }

    # 地形通行难度系数 (影响移动速度，值越大越难通行)
    MOVEMENT_COST = {
        PLAINS: 1.0,  # 基准值
        MOUNTAIN: 2.0,  # 山地通行慢
        WATER: 3.0,  # 水面通行更慢
        FOREST: 1.5,  # 森林通行较慢
        SWAMP: 2.5,  # 沼泽通行很慢
    }

    # 地形防御加成 (百分比增加防御)
    DEFENSE_BONUS = {
        PLAINS: 0.0,  # 无加成
        MOUNTAIN: 0.3,  # 30%防御加成
        WATER: -0.1,  # 水中减少防御
        FOREST: 0.2,  # 森林提供隐蔽
        SWAMP: 0.1,  # 沼泽小幅加成
    }


class Tile:
    """
    地形格子：代表地图上的一个格子单元
    """

    def __init__(self, x, y, tile_type=TileType.PLAINS):
        self.x = x  # 格子的X坐标
        self.y = y  # 格子的Y坐标
        self.type = tile_type  # 地形类型
        self.passable = True  # 是否可通行
        self.entity = None  # 占据此格子的实体
        self.resources = None  # 此格子上的资源

        # 根据地形类型设置属性
        if tile_type == TileType.WATER:
            self.passable = False  # 默认水面不可通行

    @property
    def color(self):
        """获取地形的颜色"""
        return TileType.COLORS.get(self.type, (200, 200, 200))

    @property
    def movement_cost(self):
        """获取通行难度系数"""
        return TileType.MOVEMENT_COST.get(self.type, 1.0)

    @property
    def defense_bonus(self):
        """获取防御加成"""
        return TileType.DEFENSE_BONUS.get(self.type, 0.0)
