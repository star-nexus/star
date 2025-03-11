from framework.ecs.component import Component


class DefenseComponent(Component):
    """
    防御组件：管理实体的防御属性
    定义实体如何抵抗伤害、处理生命值和恢复机制
    是战斗系统中与攻击组件相对应的另一个核心组件
    """

    def __init__(self):
        """
        初始化防御组件
        设置实体的防御属性、生命值和恢复能力
        """
        super().__init__()
        self.armor = 5  # 护甲值，减少受到的物理伤害

        # 对不同攻击类型的抗性，以百分比形式表示伤害减免
        self.resistance = {
            "melee": 0,  # 近战抗性(百分比减伤)，对近战攻击的抵抗能力
            "ranged": 0,  # 远程抗性，对箭矢、投石等远程攻击的抵抗能力
            "magic": 0,  # 魔法抗性，对魔法和特殊攻击的抵抗能力
        }

        self.health = 100  # 当前生命值，降至0则实体死亡或被摧毁
        self.max_health = 100  # 最大生命值，限制生命恢复的上限
        self.regen_rate = 0  # 生命回复率(每秒恢复的生命值)

        # 可以在子类中扩展以下属性
        # self.shield = 0       # 护盾值，优先于生命值受到伤害的额外保护层
        # self.dodge_chance = 0  # 闪避几率，完全避免攻击的概率
        # self.is_invulnerable = False  # 无敌状态，免疫所有伤害
