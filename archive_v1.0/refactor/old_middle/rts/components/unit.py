from framework.ecs.component import Component


class UnitComponent(Component):
    """
    单位组件：用于游戏中的可控制单位
    定义单位的基本属性、状态和行为能力，是RTS游戏单位系统的核心组件
    """

    # 单位类型常量定义，用于区分不同类型的单位
    TYPE_SUPPLY = "supply"  # 辎重单位：负责资源运输与采集
    TYPE_PLAINS = "plains"  # 平原单位：适合在平原地形作战的基础单位
    TYPE_MOUNTAIN = "mountain"  # 山地单位：适合在山地地形作战的专业单位
    TYPE_WATER = "water"  # 水面单位：可在水域活动的海军单位
    TYPE_RANGED = "ranged"  # 远程单位：具有远程攻击能力的单位
    TYPE_AIR = "air"  # 空中单位：可飞行的单位，无视大部分地形限制

    def __init__(self, unit_type, unit_name=""):
        """
        初始化单位组件

        参数:
            unit_type: 单位类型，决定单位的基本特性和能力
            unit_name: 单位名称，用于显示和识别
        """
        super().__init__()
        self.unit_type = unit_type  # 单位类型，如平原单位、山地单位等
        self.unit_name = unit_name  # 单位名称，显示在UI或提示信息中

        # 单位基础属性，决定单位在战斗和移动中的表现
        self.health = 100  # 当前生命值，降至0则单位死亡
        self.max_health = 100  # 最大生命值，限制恢复上限
        self.attack = 10  # 攻击力，影响单位造成的伤害
        self.defense = 5  # 防御力，减少受到的伤害
        self.attack_range = 1  # 攻击范围，决定单位可以从多远发动攻击
        self.attack_speed = 1.0  # 攻击速度(次/秒)，决定攻击频率
        self.attack_cooldown = 0  # 攻击冷却计时器，控制攻击间隔
        self.speed = 100  # 移动速度，影响单位在地图上的移动速率

        # 单位当前状态，用于控制单位行为和渲染效果
        self.is_selected = False  # 是否被玩家选中，影响界面显示
        self.is_moving = False  # 是否正在移动，影响动画和控制逻辑
        self.is_attacking = False  # 是否正在攻击，控制攻击动画和逻辑
        self.target_position = None  # 移动目标位置，用于寻路
        self.target_entity = None  # 攻击或跟随的目标实体

        # 资源消耗相关，影响玩家资源管理
        self.food_consumption = 1  # 食物消耗率(单位/秒)，维持单位所需食物
        self.weapons_consumption = 0  # 武器消耗(单位/次攻击)，发动攻击消耗的武器资源

        # 特殊能力系统，可扩展单位功能
        self.abilities = []  # 单位特殊能力列表，如治疗、隐形等高级功能
