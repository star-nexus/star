from framework.ecs.component import Component


class PositionComponent(Component):
    """
    位置组件：管理实体在游戏世界中的位置
    所有可见或具有空间位置的实体都需要此组件
    提供基础的二维坐标定位功能
    """

    def __init__(self, x=0, y=0):
        """
        初始化位置组件

        参数:
            x: 实体在世界坐标系中的X坐标，默认为0
            y: 实体在世界坐标系中的Y坐标，默认为0
        """
        super().__init__()
        self.x = x  # X坐标，表示实体在水平方向上的位置
        self.y = y  # Y坐标，表示实体在垂直方向上的位置

        # 注：在RTS游戏中，通常坐标系原点(0,0)位于地图左上角
        # X轴向右为正方向，Y轴向下为正方向
        # 单位为像素或游戏单位
