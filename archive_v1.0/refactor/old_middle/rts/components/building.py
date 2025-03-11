from framework.ecs.component import Component


class BuildingComponent(Component):
    """
    建筑组件：用于游戏中的建筑物
    定义RTS游戏中的各类建筑设施，包括生产功能、资源管理和建造过程
    """

    # 建筑类型常量定义
    TYPE_HEADQUARTERS = "headquarters"  # 主基地：核心建筑，失去则游戏结束
    TYPE_SUPPLY_DEPOT = "supply_depot"  # 补给点：提供资源存储和补给功能
    TYPE_FORTIFICATION = "fortification"  # 战斗工事：防御建筑，增强防卫能力

    def __init__(self, building_type, building_name=""):
        """
        初始化建筑组件

        参数:
            building_type: 建筑类型，决定建筑的功能和属性
            building_name: 建筑名称，用于显示和标识
        """
        super().__init__()
        self.building_type = building_type  # 建筑类型，决定基本特性和功能
        self.building_name = building_name  # 建筑名称，用于UI显示和标识

        # 建筑基础属性
        self.health = 200  # 当前生命值，建筑一般比单位有更高的生命值
        self.max_health = 200  # 最大生命值，决定建筑的耐久度
        self.defense = 10  # 防御力，减少受到的伤害

        # 建造相关信息
        self.construction_progress = 100  # 建造进度(百分比)，100表示已完成
        self.is_completed = True  # 标记建筑是否已建造完成
        self.construction_time = 0  # 建造所需的总时间(秒)

        # 生产功能
        self.production_options = []  # 可生产的选项列表，如单位或升级
        self.is_producing = False  # 标记是否正在生产中
        self.production_progress = 0  # 当前生产进度(百分比)
        self.production_target = None  # 当前生产目标，如单位类型或升级ID

        # 资源功能
        self.resource_generation = {}  # 资源产出速率，如 {"gold": 5} 表示每秒产出5金币
        self.resource_storage = {}  # 当前存储的资源量
        self.max_resource_storage = {}  # 最大资源存储容量

        # 可以在子类中扩展以下属性
        # self.radius_of_influence = 100  # 影响范围半径，用于领土控制
        # self.special_abilities = []     # 特殊能力列表，如提供视野、治疗等
        # self.upgrade_level = 0          # 升级等级，影响建筑性能
        # self.required_power = 0         # 需要的能量，部分建筑可能需要能量维持
