"""
事件类型定义

定义系统间通信使用的标准事件类型
"""

from enum import Enum, auto


class EventType(Enum):
    """事件类型枚举"""
    
    # 系统事件
    SYSTEM_INITIALIZED = auto()
    SYSTEM_SHUTDOWN = auto()
    
    # 实体事件
    ENTITY_CREATED = auto()
    ENTITY_DESTROYED = auto()
    COMPONENT_ADDED = auto()
    COMPONENT_REMOVED = auto()
    COMPONENT_CHANGED = auto()
    
    # 游戏事件
    GAME_STARTED = auto()
    GAME_PAUSED = auto()
    GAME_RESUMED = auto()
    GAME_ENDED = auto()
    TURN_STARTED = auto()
    TURN_ENDED = auto()
    
    # 战斗事件
    COMBAT_STARTED = auto()
    COMBAT_ENDED = auto()
    COMBAT_HIT = auto()
    COMBAT_MISS = auto()
    UNIT_ATTACKED = auto()
    UNIT_DAMAGED = auto()
    UNIT_KILLED = auto()
    UNIT_ROUTED = auto()
    UNIT_RALLIED = auto()
    
    # 移动事件
    UNIT_MOVED = auto()
    UNIT_MOVE_STARTED = auto()
    UNIT_MOVE_ENDED = auto()
    UNIT_PATH_BLOCKED = auto()
    
    # 交互事件
    UNIT_SELECTED = auto()
    UNIT_DESELECTED = auto()
    TILE_SELECTED = auto()
    TILE_DESELECTED = auto()
    
    # 指令事件
    COMMAND_ISSUED = auto()
    COMMAND_COMPLETED = auto()
    COMMAND_FAILED = auto()
    
    # 资源事件
    RESOURCE_CHANGED = auto()
    SUPPLY_CHANGED = auto()
    MORALE_CHANGED = auto()
    
    # 天气和环境事件
    WEATHER_CHANGED = auto()
    TIME_OF_DAY_CHANGED = auto()
    SEASON_CHANGED = auto()
    
    # 特殊事件
    OFFICER_CAPTURED = auto()
    OFFICER_DEFECTED = auto()
    CITY_CAPTURED = auto()
    FACTION_DESTROYED = auto()
    
    # 自定义事件类型
    CUSTOM = auto()

    @classmethod
    def get_name(cls, event_type):
        """获取事件类型的名称字符串"""
        return event_type.name 