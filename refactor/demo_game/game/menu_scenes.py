import pygame
from framework.core.ecs.world import World
from framework.managers.scenes import Scene
from framework.managers.renders import RenderManager
from game.components import Position, Renderable

class MenuScene(Scene):
    """游戏菜单场景，显示开始游戏选项"""
    
    def __init__(self, world: World):
        super().__init__(world)
        self.font = None
        self.title_text = None
        self.start_text = None
        
    def enter(self) -> None:
        # 初始化字体
        pygame.font.init()
        self.font = pygame.font.Font(None, 74)  # 使用默认字体
        
        # 创建文本
        self.title_text = self.font.render("Simple Demo Game", True, (255, 255, 255))
        self.start_text = self.font.render("Press SPACE to Start", True, (255, 255, 255))
    
    def exit(self) -> None:
        self.font = None
        self.title_text = None
        self.start_text = None
    
    def update(self, delta_time: float) -> None:
        # 检查空格键是否被按下
        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE]:
            # 切换到游戏场景
            self.engine.switch_scene("game")
    
    def render(self, render_manager: RenderManager) -> None:
        if self.title_text and self.start_text:
            # 计算文本位置
            title_rect = self.title_text.get_rect(center=(400, 200))
            start_rect = self.start_text.get_rect(center=(400, 400))
            
            # 渲染文本
            render_manager.draw(self.title_text, title_rect)
            render_manager.draw(self.start_text, start_rect)

class GameOverScene(Scene):
    """游戏结束场景，显示游戏结果"""
    
    def __init__(self, world: World, is_victory: bool = False):
        super().__init__(world)
        self.is_victory = is_victory
        self.font = None
        self.result_text = None
        self.restart_text = None
    
    def enter(self) -> None:
        # 初始化字体
        pygame.font.init()
        self.font = pygame.font.Font(None, 74)  # 使用默认字体
        
        # 创建文本
        result = "Victory!" if self.is_victory else "Defeat!"
        self.result_text = self.font.render(result, True, (255, 255, 255))
        self.restart_text = self.font.render("Press R to Restart", True, (255, 255, 255))
    
    def exit(self) -> None:
        self.font = None
        self.result_text = None
        self.restart_text = None
    
    def update(self, delta_time: float) -> None:
        # 检查空格键是否被按下
        keys = pygame.key.get_pressed()
        if keys[pygame.K_r]:
            # 切换回菜单场景
            self.engine.switch_scene("menu")
    
    def render(self, render_manager: RenderManager) -> None:
        if self.result_text and self.restart_text:
            # 计算文本位置
            result_rect = self.result_text.get_rect(center=(400, 200))
            restart_rect = self.restart_text.get_rect(center=(400, 400))
            
            # 渲染文本
            render_manager.draw(self.result_text, result_rect)
            render_manager.draw(self.restart_text, restart_rect)