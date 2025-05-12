from dataclasses import dataclass

@dataclass
class ArmyComponent:
    force: str  # 所属势力
    troops: int = 1000     # 当前兵力
    max_troops: int = 1000 # 新增最大兵力属性
    training: int = 60     # 训练度
    morale: int = 80       # 士气值
    supply: int = 100      # 补给量
    equipment: dict = None # 装备信息