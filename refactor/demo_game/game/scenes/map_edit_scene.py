import pygame
from framework.managers.scenes import Scene
from framework.managers.renders import RenderManager
from framework.managers.events import Message
from game.managers.map_manager import MapManager
from game.components import TerrainType


class MapEditScene(Scene):
    """地图编辑场景，用于编辑和测试地图"""

    def __init__(self, engine):
        """初始化地图编辑场景"""
        super().__init__(engine)
        self.map_manager = None
        self.current_terrain = TerrainType.PLAIN
        self.is_loaded = False
        self.terrain_buttons = []
        self.action_buttons = []
        self.info_label = None
        self.selected_terrain_label = None
        self.last_click_time = 0  # 添加点击时间记录，防止快速连续点击

    def enter(self) -> None:
        """进入场景时调用，初始化编辑器"""
        if self.is_loaded:
            return

        # 初始化地图管理器
        self.map_manager = MapManager(self.world, self.engine.event_manager)

        # 生成默认地图
        self.map_manager.generate_random_map(20, 15)

        # 设置UI界面
        self._setup_ui()

        # 订阅事件
        self._subscribe_to_events()

        self.is_loaded = True
        print("MapEditScene: Scene loaded")

    def _subscribe_to_events(self):
        """订阅场景所需事件"""
        # 订阅鼠标点击事件处理地形修改
        self.engine.event_manager.subscribe("MOUSEBUTTONDOWN", self._handle_mouse_click)

        # 订阅键盘事件处理快捷键
        self.engine.event_manager.subscribe("KEYDOWN", self._handle_key_press)

        # 订阅地图事件
        self.engine.event_manager.subscribe("map_generated", self._handle_map_update)
        self.engine.event_manager.subscribe("map_loaded", self._handle_map_update)

        # 订阅UI交互事件
        self.engine.event_manager.subscribe(
            "terrain_selected", self._handle_terrain_selection
        )
        self.engine.event_manager.subscribe("map_action", self._handle_map_action)

    def _setup_ui(self):
        """设置UI界面"""
        # 加载字体
        font = self.engine.resource_manager.load_font("default", None, 20)
        title_font = self.engine.resource_manager.load_font("default", None, 24)
        small_font = self.engine.resource_manager.load_font("default", None, 16)

        # 创建标题
        self.engine.ui_manager.create_label(
            position=(10, 10),
            size=(200, 30),
            text="Map Editor",
            font=title_font,
            text_color=(255, 255, 255),
            z_index=10,
        )

        # 创建地形选择按钮
        terrain_types = list(TerrainType)
        terrain_names = {
            TerrainType.PLAIN: "PLAIN",
            TerrainType.MOUNTAIN: "MOUNTAIN",
            TerrainType.RIVER: "RIVER",
            TerrainType.FOREST: "FOREST",
            TerrainType.LAKE: "LAKE",
        }

        button_colors = {
            TerrainType.PLAIN: (124, 252, 0),  # 浅绿色
            TerrainType.MOUNTAIN: (139, 137, 137),  # 灰色
            TerrainType.RIVER: (30, 144, 255),  # 蓝色
            TerrainType.FOREST: (34, 139, 34),  # 深绿色
            TerrainType.LAKE: (0, 191, 255),  # 浅蓝色
        }

        # 创建地形选择按钮 - 使用事件发布而不是直接调用
        for i, terrain in enumerate(terrain_types):
            terrain_type = terrain  # 创建局部变量，避免闭包问题
            button = self.engine.ui_manager.create_button(
                position=(650, 100 + i * 60),
                size=(120, 40),
                text=terrain_names.get(terrain_type, terrain_type.name),
                font=font,
                on_click=lambda t=terrain_type: self.engine.event_manager.publish(
                    "terrain_selected",
                    Message(
                        topic="terrain_selected",
                        data_type="ui_event",
                        data={"terrain_type": t},
                    ),
                ),
                z_index=10,
            )
            self.terrain_buttons.append(button)

        # 创建操作按钮
        actions = [
            ("Re Map", "regenerate"),
            ("Save Map", "save"),
            ("Load Map", "load"),
            ("Back", "back_to_menu"),
        ]

        for i, (text, action) in enumerate(actions):
            action_name = action  # 创建局部变量，避免闭包问题
            button = self.engine.ui_manager.create_button(
                position=(650, 400 + i * 50),
                size=(120, 40),
                text=text,
                font=font,
                on_click=lambda a=action_name: self.engine.event_manager.publish(
                    "map_action",
                    Message(
                        topic="map_action", data_type="ui_event", data={"action": a}
                    ),
                ),
                z_index=10,
            )
            self.action_buttons.append(button)

        # 创建当前选择的地形标签
        self.selected_terrain_label = self.engine.ui_manager.create_label(
            position=(650, 50),
            size=(120, 30),
            text=f"curr: {terrain_names.get(self.current_terrain, 'PLAIN')}",
            font=small_font,
            text_color=(255, 255, 255),
            z_index=10,
        )

        # 创建信息标签
        self.info_label = self.engine.ui_manager.create_label(
            position=(10, 560),
            size=(600, 30),
            text="Click on squares to change terrain, press M to return to menu",
            font=small_font,
            text_color=(255, 255, 255),
            z_index=10,
        )

    def _handle_terrain_selection(self, message):
        """处理地形选择事件"""
        # 从Message对象的data属性中获取数据
        event_data = message.data if hasattr(message, "data") else message
        terrain_type = event_data.get("terrain_type")

        if terrain_type:
            self.current_terrain = terrain_type
            terrain_names = {
                TerrainType.PLAIN: "PLAIN",
                TerrainType.MOUNTAIN: "MOUNTAIN",
                TerrainType.RIVER: "RIVER",
                TerrainType.FOREST: "FOREST",
                TerrainType.LAKE: "LAKE",
            }
            if self.selected_terrain_label:
                self.engine.ui_manager.set_text(
                    self.selected_terrain_label,
                    f"curr: {terrain_names.get(self.current_terrain, 'PLAIN')}",
                )

            # 输出调试信息
            print(f"Selected terrain: {self.current_terrain.name}")

    def _handle_map_action(self, message):
        """处理地图操作事件"""
        # 从Message对象的data属性中获取数据
        event_data = message.data if hasattr(message, "data") else message
        action = event_data.get("action")

        if action == "regenerate":
            self._regenerate_map()
        elif action == "save":
            self._save_map()
        elif action == "load":
            self._load_map()
        elif action == "back_to_menu":
            self._back_to_menu()

    def _handle_mouse_click(self, message):
        """处理鼠标点击事件"""
        # 从Message对象的data属性中获取数据
        event_data = message.data if hasattr(message, "data") else message

        # 确保是左键点击
        if event_data.get("button") != 1:  # 左键是1
            return

        current_time = pygame.time.get_ticks()

        # 防止快速连续点击，添加冷却时间
        if current_time - self.last_click_time > 100:  # 100毫秒冷却
            self.last_click_time = current_time

            mouse_pos = event_data.get("pos")
            if not mouse_pos:
                return

            # 确保点击在地图区域内
            if mouse_pos[0] < 640 and self.map_manager:  # 假设地图区域宽度为640
                grid_x, grid_y = self.map_manager.get_grid_pos_from_screen(
                    mouse_pos[0], mouse_pos[1]
                )

                # 确保坐标在地图范围内
                if (
                    0 <= grid_x < self.map_manager.map_width
                    and 0 <= grid_y < self.map_manager.map_height
                ):
                    success = self.map_manager.set_terrain_at(
                        grid_x, grid_y, self.current_terrain
                    )
                    if success:
                        if self.info_label:
                            self.engine.ui_manager.set_text(
                                self.info_label,
                                f"Changed terrain at ({grid_x},{grid_y}) to {self.current_terrain.name}",
                            )
                        print(
                            f"Set terrain at ({grid_x},{grid_y}) to {self.current_terrain.name}: {success}"
                        )
                    else:
                        print(f"Failed to set terrain at ({grid_x},{grid_y})")

    def _handle_key_press(self, message):
        """处理键盘按键事件"""
        # 从Message对象的data属性中获取数据
        key = message.data if hasattr(message, "data") else message

        # 处理键盘快捷键
        if key == pygame.K_m:  # 按M键返回菜单
            self._back_to_menu()

    def _handle_map_update(self, message):
        """处理地图更新事件"""
        # 从Message对象的data属性中获取数据
        event_data = message.data if hasattr(message, "data") else message

        # 更新信息标签
        if self.info_label:
            if message.topic == "map_generated":
                width = event_data.get("width", 0)
                height = event_data.get("height", 0)
                self.engine.ui_manager.set_text(
                    self.info_label, f"Generated new map ({width}x{height})"
                )
            elif message.topic == "map_loaded":
                filename = event_data.get("filename", "")
                self.engine.ui_manager.set_text(
                    self.info_label, f"Loaded map from {filename}"
                )

    def _regenerate_map(self):
        """重新生成地图"""
        if self.map_manager:
            self.map_manager.generate_random_map(20, 15)
            print("Map regenerated")

    def _save_map(self):
        """保存地图"""
        if self.map_manager:
            # 在实际应用中，这里应该弹出一个文件对话框
            # 简化处理，直接保存到预设位置
            try:
                # 确保maps目录存在
                import os

                os.makedirs("maps", exist_ok=True)

                result = self.map_manager.save_map("maps/custom_map.json")
                if self.info_label:
                    message = (
                        "Saved maps/custom_map.json" if result else "Failed to save map"
                    )
                    self.engine.ui_manager.set_text(self.info_label, message)
                print(f"Map save {result}")
            except Exception as e:
                if self.info_label:
                    self.engine.ui_manager.set_text(self.info_label, f"Error: {e}")
                print(f"Error saving map: {e}")

    def _load_map(self):
        """加载地图"""
        if self.map_manager:
            try:
                # 在实际应用中，这里应该弹出一个文件对话框
                # 简化处理，直接从预设位置加载
                success = self.map_manager.load_map("maps/custom_map.json")
                if self.info_label:
                    message = "Loaded" if success else "Load map failed"
                    self.engine.ui_manager.set_text(self.info_label, message)
                print(f"Map load {success}")
            except Exception as e:
                if self.info_label:
                    self.engine.ui_manager.set_text(self.info_label, f"Error: {e}")
                print(f"Error loading map: {e}")

    def _back_to_menu(self):
        """返回菜单"""
        self.exit()
        self.engine.switch_scene("menu")

    def update(self, delta_time: float) -> None:
        """更新编辑器"""
        # 主要的更新逻辑已经移动到事件处理函数中
        # 这里不再需要直接处理输入和UI交互
        pass

    def exit(self) -> None:
        """离开场景时调用，清理资源"""
        # 取消订阅事件
        self.engine.event_manager.unsubscribe(
            "MOUSEBUTTONDOWN", self._handle_mouse_click
        )
        self.engine.event_manager.unsubscribe("KEYDOWN", self._handle_key_press)
        self.engine.event_manager.unsubscribe("map_generated", self._handle_map_update)
        self.engine.event_manager.unsubscribe("map_loaded", self._handle_map_update)
        self.engine.event_manager.unsubscribe(
            "terrain_selected", self._handle_terrain_selection
        )
        self.engine.event_manager.unsubscribe("map_action", self._handle_map_action)

        # 清理UI元素
        for button in self.terrain_buttons:
            self.engine.ui_manager.remove_element(button)
        self.terrain_buttons.clear()

        for button in self.action_buttons:
            self.engine.ui_manager.remove_element(button)
        self.action_buttons.clear()

        if self.info_label:
            self.engine.ui_manager.remove_element(self.info_label)
            self.info_label = None

        if self.selected_terrain_label:
            self.engine.ui_manager.remove_element(self.selected_terrain_label)
            self.selected_terrain_label = None

        # 清理地图管理器
        if self.map_manager:
            self.map_manager.cleanup()
            self.map_manager = None

        self.is_loaded = False
        print("MapEditScene: Scene unloaded")

    def render(self, render_manager: RenderManager) -> None:
        """渲染编辑器"""
        # 地图由MapRenderSystem渲染，UI由UI系统自动渲染
        pass
