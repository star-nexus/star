from framework_v2.engine.scenes import Scene
from framework_v2.ui.button import Button
from framework_v2.ui.text import Text
from framework_v2.ui.panel import Panel

class EndScene(Scene):
    def __init__(self, engine):
        super().__init__(engine)
        self.ui_elements = []
        self.result_text = None
        self.stats_text = None
        self.restart_button = None
        self.main_menu_button = None
        self.exit_button = None
        self.game_result = None
        self.game_stats = None
        
    def enter(self, **kwargs):
        """场景开始时调用"""
        super().enter(**kwargs)
        
        # 获取游戏结果和统计信息
        if kwargs and "result" in kwargs:
            self.game_result = kwargs["result"]
        if kwargs and "stats" in kwargs:
            self.game_stats = kwargs["stats"]
        
        # 创建结果文本
        self.result_text = Text(
            self.engine,
            "Game Over",
            self.engine.width // 2,
            100,
            font_size=48,
            color=(255, 215, 0)
        )
        self.ui_elements.append(self.result_text)
        
        # 创建统计信息标题
        self.stats_title = Text(
            self.engine,
            "Game Statistics",
            self.engine.width // 2,
            180,
            font_size=32,
            color=(255, 255, 255)
        )
        self.ui_elements.append(self.stats_title)
        
        # 为每个统计项创建单独的文本对象
        y_pos = 220
        if self.game_stats:
            for key, value in self.game_stats.items():
                stat_text = Text(
                    self.engine,
                    f"{key}: {value}",
                    self.engine.width // 2,
                    y_pos,
                    font_size=24,
                    color=(200, 200, 200)
                )
                self.ui_elements.append(stat_text)
                y_pos += 30  # 每个统计项之间的垂直间距
        
        # 创建重新开始按钮
        self.restart_button = Button(
            self.engine,
            "Restart",
            self.engine.width // 2,
            y_pos + 40,  # 根据统计项的数量动态调整按钮位置
            width=200,
            height=50,
            callback=self.restart_game
        )
        self.ui_elements.append(self.restart_button)
        
        # 创建返回主菜单按钮
        self.main_menu_button = Button(
            self.engine,
            "Main Menu",
            self.engine.width // 2,
            y_pos + 110,  # 按钮之间的间距为70
            width=200,
            height=50,
            callback=self.return_to_main_menu
        )
        self.ui_elements.append(self.main_menu_button)
        
        # 创建退出游戏按钮
        self.exit_button = Button(
            self.engine,
            "Quit",
            self.engine.width // 2,
            y_pos + 180,  # 按钮之间的间距为70
            width=200,
            height=50,
            callback=self.exit_game
        )
        self.ui_elements.append(self.exit_button)
        
        # 更新显示
        self.update_display()
        
    def update_display(self):
        """更新显示内容"""
        if self.game_result == "victory":
            self.result_text.set_text("Victory!")
            self.result_text.set_color((0, 255, 0))
        else:
            self.result_text.set_text("Defeat!")
            self.result_text.set_color((255, 0, 0))
        
    def restart_game(self):
        """重新开始游戏"""
        self.engine.scene_manager.load_scene("game")
        
    def return_to_main_menu(self):
        """返回主菜单"""
        self.engine.scene_manager.load_scene("start")
        
    def exit_game(self):
        """退出游戏"""
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
        # 绘制背景
        surface.fill((0, 0, 0))  # 修改为黑色背景
        
        # 如果有世界对象，使用ECS的渲染系统进行渲染
        if self.world:
            # 获取渲染系统并设置渲染表面
            from rotk_v2.systems.render_system import RenderSystem
            render_system = self.world.system_manager.get_system(RenderSystem)
            if render_system:
                render_system.set_surface(surface)
            
            # 使用ECS的渲染系统进行渲染
            self.world.update(0)  # 触发系统更新但不更新游戏逻辑
        
        # 渲染所有 UI 元素
        for element in self.ui_elements:
            if hasattr(element, 'render'):
                element.render(surface)
    
    def handle_event(self, event):
        """处理输入事件"""
        # 将事件传递给所有 UI 元素
        for element in self.ui_elements:
            if hasattr(element, 'handle_event'):
                element.handle_event(event)