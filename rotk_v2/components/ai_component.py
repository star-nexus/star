from framework_v2.ecs.component import Component

class AIComponent(Component):
    """
    AI 组件，用于控制 NPC 实体的行为
    """
    def __init__(self, behavior="aggressive"):
        """
        初始化 AI 组件
        
        参数:
            behavior: AI 行为类型，可以是 "aggressive"（积极）或 "defensive"（防御）
        """
        super().__init__()
        self.behavior = behavior
        self.state = "idle"  # 状态：idle, patrol, attack, retreat
        self.target = None   # 目标实体
        self.patrol_timer = 0  # 巡逻计时器