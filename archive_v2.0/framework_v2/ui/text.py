import pygame

class Text:
    """
    文本 UI 组件
    """
    def __init__(self, engine, text, x, y, font_size=20, color=(255, 255, 255)):
        self.engine = engine
        self.text = text
        self.x = x
        self.y = y
        self.font_size = font_size
        self.color = color
        self.font = pygame.font.Font(None, font_size)
        self.surface = self.font.render(text, True, color)
        self.rect = self.surface.get_rect(center=(x, y))
        
    def set_text(self, text):
        """设置文本内容"""
        self.text = text
        self.surface = self.font.render(text, True, self.color)
        self.rect = self.surface.get_rect(center=(self.x, self.y))
        
    def set_color(self, color):
        """设置文本颜色"""
        self.color = color
        self.surface = self.font.render(self.text, True, color)
        
    def update(self, dt):
        pass
        
    def render(self, surface):
        surface.blit(self.surface, self.rect)