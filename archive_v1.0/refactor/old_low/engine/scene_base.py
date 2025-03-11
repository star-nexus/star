import pygame
from typing import Optional, Dict, Any, List


class BaseScene:
    """场景基类，提供场景的通用功能"""

    def __init__(self, engine):
        self.engine = engine
        self.entities = []
        self.map = None
        self.camera_x = 0
        self.camera_y = 0
        # 用于存储场景特定的数据
        self.scene_data: Dict[str, Any] = {}
        # 场景中使用的字体
        self.fonts: Dict[str, pygame.font.Font] = {}
        # 是否已初始化
        self.initialized = False

    def load_fonts(self) -> None:
        """加载场景所需的所有字体"""
        if hasattr(self.engine, "ui_manager"):
            self.fonts["default"] = self.engine.ui_manager.get_font("default")
            self.fonts["default_small"] = self.engine.ui_manager.get_font(
                "default_small"
            )
            self.fonts["default_large"] = self.engine.ui_manager.get_font(
                "default_large"
            )
            self.fonts["title"] = self.engine.ui_manager.get_font("title")
        else:
            # 兼容未使用UI管理器的情况
            self.fonts["default"] = pygame.font.SysFont("arial", 24)
            self.fonts["default_small"] = pygame.font.SysFont("arial", 16)
            self.fonts["default_large"] = pygame.font.SysFont("arial", 32)
            self.fonts["title"] = pygame.font.SysFont("arial", 64)

    def initialize(self) -> None:
        """初始化场景，子类应重写此方法"""
        if not self.initialized:
            # 加载字体
            self.load_fonts()
            # 设置已初始化标志
            self.initialized = True

    def setup_ui(self) -> None:
        """设置场景UI，子类应重写此方法"""
        pass

    def update(self, delta_time: float) -> None:
        """更新场景，子类可重写此方法"""
        # 更新所有实体
        active_entities = [entity for entity in self.entities if entity.is_active()]
        for entity in active_entities:
            entity.update(delta_time)

    def render(self, surface: pygame.Surface) -> None:
        """渲染场景，子类可重写此方法"""
        # 如果有地图，先渲染地图
        if self.map:
            self.map.render(surface, self.camera_x, self.camera_y)

        # 然后渲染实体
        for entity in self.entities:
            # 考虑相机位置来渲染实体
            original_x = entity.x
            original_y = entity.y
            entity.x -= self.camera_x
            entity.y -= self.camera_y

            entity.render(surface)

            # 还原实体位置
            entity.x = original_x
            entity.y = original_y

    def add_entity(self, entity) -> None:
        """添加实体到场景"""
        self.entities.append(entity)

    def remove_entity(self, entity) -> None:
        """从场景移除实体"""
        if entity in self.entities:
            self.entities.remove(entity)

    def set_map(self, tilemap) -> None:
        """设置场景的地图"""
        self.map = tilemap

    def move_camera(self, x: int, y: int) -> None:
        """移动相机位置"""
        self.camera_x = x
        self.camera_y = y

    def center_camera_on_entity(
        self, entity, surface_width: int, surface_height: int
    ) -> None:
        """将相机居中于某个实体"""
        # 计算以实体为中心的相机位置
        self.camera_x = entity.x - surface_width // 2
        self.camera_y = entity.y - surface_height // 2

        # 确保相机不会超出地图边界
        if self.map:
            max_camera_x = max(0, self.map.width * self.map.tile_size - surface_width)
            max_camera_y = max(0, self.map.height * self.map.tile_size - surface_height)

            self.camera_x = max(0, min(self.camera_x, max_camera_x))
            self.camera_y = max(0, min(self.camera_y, max_camera_y))

    def get_game_data(self) -> Dict[str, Any]:
        """获取游戏数据"""
        if hasattr(self.engine, "game_state_manager"):
            return self.engine.game_state_manager.get_game_data()
        return {}

    def update_game_data(self, key: str, value: Any) -> None:
        """更新游戏数据"""
        if hasattr(self.engine, "game_state_manager"):
            self.engine.game_state_manager.update_game_data(key, value)

    def on_enter(self) -> None:
        """进入场景时调用，子类可重写此方法"""
        # 如果场景尚未初始化，则初始化
        if not self.initialized:
            self.initialize()

        # 如果有UI管理器，设置UI
        if hasattr(self.engine, "ui_manager"):
            self.setup_ui()

    def on_exit(self) -> None:
        """退出场景时调用，子类应重写此方法进行资源清理"""
        pass

    def handle_event(self, event: pygame.event.Event) -> bool:
        """处理场景特定的事件，子类应重写此方法"""
        return False
