import logging
from framework_v2.engine.engine import Engine
from framework_v2.engine.scenes import Scene
from framework_v2.ui.button import Button
from framework_v2.ui.text import Text
from framework_v2.ui.panel import Panel
from framework_v2.engine.events import EventType
import logging


class StartScene(Scene):
    def __init__(self, engine:Engine):
        super().__init__(engine)
        self.title = None
        self.start_button = None
        self.settings_button = None
        self.exit_button = None
        self.settings_panel = None
        self.settings_visible = False
        self.ui_elements = []  # 添加 UI 元素列表
        
    def enter(self, **kwargs):
        """场景开始时调用"""
        super().enter(**kwargs)
        # 创建标题
        self.title = Text(
            self.engine,
            "Demo - Start Scene",
            self.engine.width // 2,
            100,
            font_size=48,
            color=(255, 0, 0)
        )
        self.ui_elements.append(self.title)  # 添加到 UI 元素列表
        
        # 创建开始按钮
        self.start_button = Button(
            self.engine,
            "Start",
            self.engine.width // 2,
            250,
            width=200,
            height=50,
            callback=self.start_game
        )
        self.ui_elements.append(self.start_button)  # 添加到 UI 元素列表
        
        # 创建设置按钮
        self.settings_button = Button(
            self.engine,
            "Setting",
            self.engine.width // 2,
            320,
            width=200,
            height=50,
            callback=self.toggle_settings
        )
        self.ui_elements.append(self.settings_button)  # 添加到 UI 元素列表
        
        # 创建退出按钮
        self.exit_button = Button(
            self.engine,
            "Quit",
            self.engine.width // 2,
            390,
            width=200,
            height=50,
            callback=self.exit_game
        )
        self.ui_elements.append(self.exit_button)  # 添加到 UI 元素列表
        
        # 创建设置面板（初始隐藏）
        self.create_settings_panel()
        self.subscribe_events()

        self.logger = logging.getLogger(__name__)
    
    def exit(self):
        """场景结束时调用"""
        super().exit()
        # 取消订阅事件
        self.engine.event_manager.unsubscribe(EventType.KEY_DOWN, self.ui_event)
        self.engine.event_manager.unsubscribe(EventType.MOUSEBUTTON_DOWN, self.ui_event)
    def subscribe_events(self):
        """订阅事件"""
        self.engine.event_manager.subscribe([EventType.KEY_DOWN,EventType.MOUSEBUTTON_DOWN], self.ui_event)

    def create_settings_panel(self):
        # 这里将来实现设置面板
        pass
        
    def toggle_settings(self):
        self.settings_visible = not self.settings_visible
        # 切换设置面板可见性
        
    def start_game(self):
        print("Start Game")
        self.engine.scene_manager.load_scene("game")
        
    def exit_game(self):
        self.engine.quit()
        
    def update(self, delta_time):
        """更新场景"""
        super().update(delta_time)
        # 更新所有 UI 元素
        for element in self.ui_elements:
            if hasattr(element, 'update'):
                element.update(delta_time)
    
    def render(self, surface):
        """渲染场景"""
        
        # 渲染所有 UI 元素
        for element in self.ui_elements:
            if hasattr(element, 'render'):
                element.render(surface)
    
    def ui_event(self, event):
        """处理输入事件"""
        # 将事件传递给所有 UI 元素
        self.logger.info(f"Start Scene : {event}")
        for element in self.ui_elements:
            if hasattr(element, 'handle_event'):
                element.handle_event(event)