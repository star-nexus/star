from typing import Dict, Any

# 相机组件配置
CAMERA_CONFIG = {
    "default": {
        "position_x": 0.0,
        "position_y": 0.0,
        "zoom": 1.0,
        "speed": 500.0,
        "zoom_speed": 0.5,
        "min_zoom": 0.5,
        "max_zoom": 10.0,
    },
    "overview": {
        "position_x": 0.0,
        "position_y": 0.0,
        "zoom": 0.5,
        "speed": 800.0,
        "zoom_speed": 0.2,
        "min_zoom": 0.3,
        "max_zoom": 1.5,
    },
    "close_up": {
        "position_x": 0.0,
        "position_y": 0.0,
        "zoom": 1.5,
        "speed": 300.0,
        "zoom_speed": 0.05,
        "min_zoom": 1.0,
        "max_zoom": 2.5,
    },
}


def get_camera_config(config_name: str = "default") -> Dict[str, Any]:
    """获取指定名称的相机配置"""
    return CAMERA_CONFIG.get(config_name, CAMERA_CONFIG["default"])
