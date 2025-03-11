from framework.ecs.component import Component


class ResourceComponent(Component):
    """
    资源组件：管理实体拥有的资源
    控制游戏中的经济系统，包括资源收集、存储、生产和消耗
    通常附加到阵营实体或资源生产建筑上
    """

    def __init__(self):
        """
        初始化资源组件
        设置基本资源类型、产出率和存储上限
        """
        super().__init__()

        # 四种基本资源类型及其初始值
        self.gold = 0  # 金币：通用资源，用于建造建筑和招募单位
        self.weapons = 0  # 武器：用于装备和升级作战单位
        self.food = 0  # 食物：维持单位生存所需
        self.supplies = 0  # 辎重：用于远征和特殊任务

        # 资源生产/消耗率 (每秒)，正值表示生产，负值表示消耗
        self.gold_rate = 0  # 金币产出/消耗率
        self.weapons_rate = 0  # 武器产出/消耗率
        self.food_rate = 0  # 食物产出/消耗率
        self.supplies_rate = 0  # 辎重产出/消耗率

        # 最大资源存储量，限制资源积累上限
        self.max_gold = 1000  # 最大金币存储量
        self.max_weapons = 1000  # 最大武器存储量
        self.max_food = 1000  # 最大食物存储量
        self.max_supplies = 1000  # 最大辎重存储量

    def add_resource(self, resource_type, amount):
        """
        添加资源到存储中

        参数:
            resource_type: 资源类型 ("gold", "weapons", "food", "supplies")
            amount: 要添加的资源数量
        """
        if resource_type == "gold":
            self.gold = min(self.gold + amount, self.max_gold)
        elif resource_type == "weapons":
            self.weapons = min(self.weapons + amount, self.max_weapons)
        elif resource_type == "food":
            self.food = min(self.food + amount, self.max_food)
        elif resource_type == "supplies":
            self.supplies = min(self.supplies + amount, self.max_supplies)

    def consume_resource(self, resource_type, amount):
        """
        消耗资源，如果资源不足返回False

        参数:
            resource_type: 资源类型 ("gold", "weapons", "food", "supplies")
            amount: 要消耗的资源数量

        返回:
            bool: 资源消耗成功返回True，资源不足返回False
        """
        if resource_type == "gold":
            if self.gold >= amount:
                self.gold -= amount
                return True
        elif resource_type == "weapons":
            if self.weapons >= amount:
                self.weapons -= amount
                return True
        elif resource_type == "food":
            if self.food >= amount:
                self.food -= amount
                return True
        elif resource_type == "supplies":
            if self.supplies >= amount:
                self.supplies -= amount
                return True
        return False

    def update_resources(self, delta_time):
        """
        根据产出/消耗率更新资源
        在每一帧调用，实现资源的持续生产和消耗

        参数:
            delta_time: 自上一帧以来经过的时间（秒）
        """
        # 根据产出/消耗率和时间间隔更新各类资源
        self.gold += self.gold_rate * delta_time
        self.weapons += self.weapons_rate * delta_time
        self.food += self.food_rate * delta_time
        self.supplies += self.supplies_rate * delta_time

        # 确保资源数量不超过最大值或低于0
        self.gold = max(0, min(self.gold, self.max_gold))
        self.weapons = max(0, min(self.weapons, self.max_weapons))
        self.food = max(0, min(self.food, self.max_food))
        self.supplies = max(0, min(self.supplies, self.max_supplies))
