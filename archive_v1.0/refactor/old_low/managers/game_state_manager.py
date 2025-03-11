class GameState:
    """游戏状态基类"""

    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"
    VICTORY = "victory"
    DEFEAT = "defeat"


class GameStateManager:
    """游戏状态管理器，处理游戏状态转换和数据传递"""

    def __init__(self, engine):
        """初始化游戏状态管理器

        Args:
            engine: 游戏引擎实例
        """
        self.engine = engine
        self.current_state = GameState.MENU
        # 存储场景间共享的游戏数据
        self.game_data = {
            "score": 0,
            "level": 1,
            "player_position": (400, 300),
            "defeated_enemies": 0,
            "total_enemies": 0,
        }

    def change_state(self, new_state):
        """改变游戏状态

        Args:
            new_state: 新的游戏状态
        """
        self.current_state = new_state
        self.on_state_changed(new_state)

    def on_state_changed(self, new_state):
        """处理状态变化事件

        Args:
            new_state: 新的游戏状态
        """
        # 根据新状态执行相关操作
        if new_state == GameState.MENU:
            self.engine.scene_manager.change_scene("menu")

        elif new_state == GameState.PLAYING:
            self.engine.scene_manager.change_scene("game")

        elif new_state == GameState.PAUSED:
            # 暂停状态不需要切换场景，只需更新UI显示暂停状态
            # 可以在这里添加暂停时的特定逻辑
            if hasattr(self.engine, "ui_manager"):
                # 创建暂停UI覆盖层
                self._create_pause_overlay()

        elif new_state == GameState.GAME_OVER:
            current_scene = self.engine.scene_manager.current_scene
            # 如果当前在游戏场景，则记录得分
            if hasattr(current_scene, "score"):
                self.game_data["score"] = current_scene.score
            self.engine.scene_manager.change_scene("game_over")

        elif new_state == GameState.VICTORY:
            current_scene = self.engine.scene_manager.current_scene
            # 如果当前在游戏场景，则记录得分
            if hasattr(current_scene, "score"):
                self.game_data["score"] = current_scene.score
            self.engine.scene_manager.change_scene("victory")

    def _create_pause_overlay(self):
        """创建暂停界面覆盖层"""
        if not hasattr(self.engine, "ui_manager"):
            return

        ui_manager = self.engine.ui_manager
        screen_width, screen_height = self.engine.screen.get_size()

        # 如果已存在暂停面板，先移除
        if "pause_overlay" in ui_manager.panels:
            ui_manager.remove_panel("pause_overlay")

        # 创建半透明暂停面板
        pause_panel = ui_manager.create_panel(
            "pause_overlay",
            screen_width // 4,
            screen_height // 4,
            screen_width // 2,
            screen_height // 2,
            color=(0, 0, 0),
            alpha=200,
        )

        # 添加暂停文本
        ui_manager.create_text_label(
            "pause_overlay",
            screen_width // 2,  # 居中显示
            screen_height // 4 + 30,
            "游戏已暂停",
            font_name="title",
            size=48,
            color=(255, 255, 255),
            align="center",
        )

        # 添加继续按钮
        ui_manager.create_button(
            "pause_overlay",
            screen_width // 2 - 100,
            screen_height // 2 - 20,
            200,
            40,
            "继续游戏",
            font_name="default_large",
            normal_color=(100, 100, 100),
            hover_color=(150, 150, 150),
            on_click=lambda: self.change_state("playing"),
        )

        # 添加返回主菜单按钮
        ui_manager.create_button(
            "pause_overlay",
            screen_width // 2 - 100,
            screen_height // 2 + 40,
            200,
            40,
            "返回主菜单",
            font_name="default_large",
            normal_color=(100, 100, 100),
            hover_color=(150, 150, 150),
            on_click=lambda: self.change_state("menu"),
        )

    def get_game_data(self):
        """获取当前游戏数据

        Returns:
            游戏数据字典
        """
        return self.game_data

    def update_game_data(self, key, value):
        """更新游戏数据

        Args:
            key: 数据键
            value: 数据值
        """
        self.game_data[key] = value

    def reset_game_data(self):
        """重置游戏数据为初始状态"""
        self.game_data = {
            "score": 0,
            "level": 1,
            "player_position": (400, 300),
            "defeated_enemies": 0,
            "total_enemies": 0,
        }
