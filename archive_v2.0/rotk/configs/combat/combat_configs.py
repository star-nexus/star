from rotk.logics.components import UnitCategory, TerrainType

"""战斗系统配置"""

###################
# 攻击系统配置
###################
ATTACK_CONFIGS = {
    "BASE_HIT_CHANCE": 0.7,  # 基础命中率
    
    # 地形对命中率的影响
    "TERRAIN_HIT_MODIFIERS": {
        TerrainType.PLAIN: 0.0,  # 平原没有修正
        TerrainType.FOREST: -0.1,  # 森林降低命中
        TerrainType.HILL: -0.15,  # 丘陵降低命中
        TerrainType.MOUNTAIN: -0.2,  # 山地大幅降低命中
        TerrainType.RIVER: -0.05,  # 河流轻微降低命中
        TerrainType.DESERT: 0.05,  # 沙漠增加命中
        TerrainType.SWAMP: -0.1,  # 沼泽降低命中
        TerrainType.URBAN: -0.1,  # 城镇降低命中
    },
    
    # 粮食不足对命中率的影响
    "FOOD_SHORTAGE_HIT_PENALTY": {
        "SEVERE": 0.3,  # 粮食不足20%时降低30%命中
        "MODERATE": 0.1,  # 粮食不足50%时降低10%命中
    },
    
    # 弹药不足对命中率的影响
    "AMMO_SHORTAGE_HIT_PENALTY": {
        "SEVERE": 0.2,  # 弹药不足20%时降低20%命中
    },
    
    # 士气对命中率的影响系数
    "MORALE_HIT_FACTOR": 0.3,  # 士气每高/低于50点，命中率增/减30%
    
    # 自动攻击频率(每帧概率)
    "AUTO_ATTACK_CHANCE": 0.1,  # 平均每10帧攻击一次
}


###################
# 伤害系统配置
###################
DAMAGE_CONFIGS = {
    "MIN_DAMAGE": 5,  # 最小伤害值
    "CRITICAL_DAMAGE_MULTIPLIER": 1.5,  # 暴击伤害倍数
    "CRITICAL_HIT_CHANCE": 0.15,  # 暴击几率
    
    # 单位类型克制矩阵：[攻击方类型][防御方类型] -> 伤害倍率
    "COUNTER_MATRIX": {
        UnitCategory.INFANTRY: {
            UnitCategory.INFANTRY: 1.0,
            UnitCategory.CAVALRY: 0.8,
            UnitCategory.RANGED: 1.2,
            UnitCategory.SPECIAL: 1.5,
        },
        UnitCategory.CAVALRY: {
            UnitCategory.INFANTRY: 1.2,
            UnitCategory.CAVALRY: 1.0,
            UnitCategory.RANGED: 1.5,
            UnitCategory.SPECIAL: 1.0,
        },
        UnitCategory.RANGED: {
            UnitCategory.INFANTRY: 1.3,
            UnitCategory.CAVALRY: 1.1,
            UnitCategory.RANGED: 1.0,
            UnitCategory.SPECIAL: 0.8,
        },
        UnitCategory.SPECIAL: {
            UnitCategory.INFANTRY: 1.5,
            UnitCategory.CAVALRY: 1.0,
            UnitCategory.RANGED: 0.9,
            UnitCategory.SPECIAL: 2.0,
        },
    },
    
    # 地形防御加成
    "TERRAIN_DEFENSE_BONUS": {
        TerrainType.PLAIN: 0.0,
        TerrainType.FOREST: 0.2,
        TerrainType.HILL: 0.3,
        TerrainType.MOUNTAIN: 0.5,
        TerrainType.RIVER: -0.2,
        TerrainType.DESERT: -0.1,
        TerrainType.SWAMP: 0.1,
        TerrainType.URBAN: 0.4,
    },
    
    # 士气对伤害的影响系数
    "MORALE_DAMAGE_FACTOR": 0.2,  # 士气每高/低于50点，伤害增/减20%
    
    # 粮食不足对伤害的影响
    "FOOD_SHORTAGE_DAMAGE_PENALTY": 0.8,  # 粮食不足30%时伤害降低20%
    
    # 伤害随机波动范围
    "DAMAGE_RANDOM_FACTOR": {
        "MIN": 0.9,  # 最小随机因子(-10%)
        "MAX": 1.1,  # 最大随机因子(+10%)
    },
}


###################
# 战斗效果系统配置
###################
COMBAT_EFFECTS_CONFIGS = {
    # 士气相关常量
    "MORALE_RECOVERY_RATE": 0.5,  # 每帧士气恢复率
    "ROUTING_THRESHOLD": 20,  # 溃逃阈值，低于此值单位可能溃逃
    "ROUTING_CHECK_CHANCE": 0.2,  # 每次受伤检查溃逃的几率
    "MIN_DAMAGE_MORALE_IMPACT": 0.1,  # 最小伤害对士气的影响系数
    "CRITICAL_HIT_MORALE_PENALTY": 10,  # 暴击额外士气惩罚
    "KILL_MORALE_BONUS": 5,  # 击杀敌人的士气提升
    
    # 溃逃恢复阈值
    "ROUTING_RECOVERY_THRESHOLD": 30,  # 士气高于此值可从溃逃状态恢复
    
    # 造成伤害的士气影响
    "DAMAGE_DEALT_MORALE_FACTOR": 5.0,  # 造成伤害时的士气提升系数(相对于目标最大生命值)
    "DAMAGE_TAKEN_MORALE_FACTOR": 10.0,  # 受到伤害时的士气降低系数(相对于自身最大生命值)
    
    # 暴击额外士气影响
    "CRITICAL_HIT_ATTACKER_MORALE_BONUS": 3,  # 造成暴击的士气额外提升
    
    # 低生命值士气影响
    "LOW_HEALTH_MORALE_PENALTY": 5,  # 生命值低于30%时额外士气惩罚
    
    # 周边单位士气影响
    "ALLY_DEATH_MORALE_PENALTY": 10,  # 友军死亡造成的士气降低
    "ENEMY_DEATH_MORALE_BONUS": 5,  # 敌军死亡造成的士气提升
    "MORALE_EFFECT_RADIUS": 5.0,  # 士气影响半径
} 