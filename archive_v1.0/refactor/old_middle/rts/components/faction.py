from framework.ecs.component import Component


class FactionComponent(Component):
    """
    阵营组件：标识实体所属的阵营
    在RTS游戏中用于划分不同的游戏势力，控制单位的敌友关系和外观
    """

    def __init__(self, faction_id, faction_name="", faction_color=(255, 255, 255)):
        """
        初始化阵营组件

        参数:
            faction_id: 阵营唯一标识符
            faction_name: 阵营名称，用于显示
            faction_color: 阵营颜色，用于在游戏中区分不同势力
        """
        super().__init__()
        self.faction_id = faction_id  # 阵营ID，用于标识和区分不同势力
        self.faction_name = faction_name  # 阵营名称，用于UI显示和提示信息
        self.faction_color = faction_color  # 阵营颜色，用于UI图标和单位标识
        self.is_player = False  # 标记是否是玩家控制的阵营，影响AI行为和UI交互

        # 可以在子类中扩展以下属性
        # self.diplomacy = {}  # 与其他阵营的外交关系（盟友、敌人、中立等）
        # self.faction_tech_level = 1  # 阵营科技等级，影响可用单位和建筑
        # self.faction_bonuses = []  # 阵营特殊加成，如某种单位强化或资源产出增加
