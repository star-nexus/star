from typing import Dict, Any


def get_fog_of_war_config(config_name: str = "default") -> Dict[str, Any]:
    """获取战争迷雾配置

    Args:
        config_name: 配置名称

    Returns:
        战争迷雾配置字典
    """
    configs = {
        "default": {
            "fog_of_war_enabled": True,  # 战争迷雾开关
            "view_mode": "PLAYER",  # 视图模式：GLOBAL（全局）或PLAYER（玩家）
            "current_player_id": 0,  # 当前玩家ID
            # 单位视野范围（根据单位类型）
            "unit_vision_range": {
                "INFANTRY": 3,
                "CAVALRY": 4,
                "ARCHER": 5,
                "SIEGE": 2,
                "HERO": 6,
            },
        },
        "no_fog": {
            "fog_of_war_enabled": False,
            "view_mode": "GLOBAL",
            "current_player_id": 0,
            "unit_vision_range": {
                "INFANTRY": 3,
                "CAVALRY": 4,
                "ARCHER": 5,
                "SIEGE": 2,
                "HERO": 6,
            },
        },
    }

    return configs.get(config_name, configs["default"])
