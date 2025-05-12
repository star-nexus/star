class CharacterComponent:
    """
    武将组件，存储武将的基本属性
    """
    def __init__(self, name="", force="", leadership=0, war=0, intelligence=0, politics=0, charm=0, hp=100, max_hp=100):
        self.name = name  # 武将姓名
        self.force = force  # 所属势力
        self.leadership = leadership  # 统率
        self.war = war  # 武力
        self.intelligence = intelligence  # 智力
        self.politics = politics  # 政治
        self.charm = charm  # 魅力
        self.hp = hp  # 当前生命值
        self.max_hp = max_hp  # 最大生命值