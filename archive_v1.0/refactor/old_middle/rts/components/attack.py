from framework.ecs.component import Component


class AttackComponent(Component):
    """
    攻击组件：管理实体的攻击行为
    定义实体如何攻击其他目标，包括伤害计算、攻击范围和冷却机制
    """

    # 攻击类型常量定义
    TYPE_MELEE = "melee"  # 近战攻击：需要接近目标才能发动攻击
    TYPE_RANGED = "ranged"  # 远程攻击：可以从一定距离外发动攻击

    def __init__(self, attack_type=TYPE_MELEE):
        """
        初始化攻击组件

        参数:
            attack_type: 攻击类型，默认为近战攻击
        """
        super().__init__()
        self.attack_type = attack_type  # 攻击类型（近战或远程）

        self.damage = 10  # 基础伤害值，决定每次攻击造成的伤害
        self.range = 1  # 攻击范围(格数或游戏单位)，近战通常为1，远程>1
        self.cooldown = 1.0  # 攻击冷却时间(秒)，控制攻击频率
        self.current_cooldown = 0  # 当前冷却计时器，值为0时可以再次攻击

        self.target = None  # 当前攻击目标的引用
        self.is_attacking = False  # 标记单位是否处于攻击状态

        # 可以在子类中扩展以下属性
        # self.critical_chance = 0.05  # 暴击几率
        # self.critical_multiplier = 2.0  # 暴击伤害倍数
        # self.attack_effects = []  # 附加效果，如中毒、减速等
