from framework.ecs.component import Component


class MovementComponent(Component):
    """
    移动组件：管理实体的移动能力
    控制游戏单位在不同地形上的移动速度、路径规划和特殊移动能力
    """

    def __init__(self):
        """
        初始化移动组件
        设置默认的移动参数、路径规划和特殊移动能力
        """
        super().__init__()

        # 在不同地形上的移动速度（单位：像素/秒）
        # 每种地形对不同单位有不同影响
        self.speed = {
            "plains": 100,  # 平原：基准移动速度，适合大多数单位
            "mountain": 60,  # 山地：陡峭地形，普通单位移动缓慢
            "water": 40,  # 水面：非水面单位移动极其缓慢
            "forest": 70,  # 森林：树木阻碍移动，速度下降
            "swamp": 50,  # 沼泽：泥泞地带，严重减慢速度
        }

        self.current_speed = 100  # 当前速度，受地形和单位状态影响

        # 路径规划相关属性
        self.destination = None  # 最终目标位置
        self.path = []  # 路径点列表，由寻路算法计算得出的移动路径
        self.is_moving = False  # 是否正在移动的标志

        # 特殊移动能力，允许单位适应不同地形
        self.can_traverse_water = False  # 能否穿越水面（船只、两栖单位）
        self.can_traverse_mountain = False  # 能否穿越山地（山地单位）
        self.is_flying = False  # 是否飞行单位(可以无视大部分地形限制)
