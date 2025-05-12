from framework_v2.ecs.component import Component

class MovableComponent(Component):
    """
    可移动组件，用于标记可以移动的实体
    """
    def __init__(self, speed=50):
        """
        初始化可移动组件
        
        参数:
            speed: 移动速度
        """
        super().__init__()
        self.speed = speed
        self.moving = False
        self.target_x = None
        self.target_y = None
        self.path = []  # 路径点列表