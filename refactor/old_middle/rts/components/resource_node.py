from framework.ecs.component import Component


class ResourceNodeComponent(Component):
    """
    资源节点组件：表示地图上的资源点
    定义地图上可被采集的资源点，包括资源类型、数量和采集机制
    """

    # 资源节点类型常量定义
    TYPE_GOLD_MINE = "gold_mine"  # 金矿：提供金币资源
    TYPE_WEAPON_CACHE = "weapon_cache"  # 武器库：提供武器资源
    TYPE_FARM = "farm"  # 农场：提供食物资源
    TYPE_SUPPLY_CACHE = "supply_cache"  # 补给仓库：提供辎重资源

    def __init__(self, node_type, resource_type, initial_amount=1000, harvest_rate=10):
        """
        初始化资源节点组件

        参数:
            node_type: 节点类型，决定资源点的外观和特性
            resource_type: 资源类型 ("gold", "weapons", "food", "supplies")
            initial_amount: 初始资源量，决定资源点可以提供多少资源
            harvest_rate: 采集速率，决定每秒可以采集多少单位资源
        """
        super().__init__()
        self.node_type = node_type  # 节点类型，影响资源点的视觉表现和属性
        self.resource_type = resource_type  # 资源类型，决定采集获得的资源种类
        self.amount = initial_amount  # 剩余资源量，随采集减少
        self.max_amount = initial_amount  # 最大资源量，用于计算资源点的"健康度"
        self.harvest_rate = harvest_rate  # 每秒采集速率，影响资源获取效率

        self.is_being_harvested = False  # 标记资源点是否正在被采集
        self.harvester_entity = None  # 当前正在采集的单位实体引用

        # 可以在子类中扩展以下属性
        # self.discovery_radius = 100  # 资源点被发现的半径
        # self.is_discovered = False   # 是否已被玩家发现
        # self.regeneration_rate = 0   # 资源再生率，某些资源可以缓慢恢复
