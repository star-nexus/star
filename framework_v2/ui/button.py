import pygame

from framework_v2.engine.events import EventMessage,EventType

class Button:
    """
    按钮 UI 组件
    """
    def __init__(self, engine, text, x, y, width=100, height=40, 
                 color=(100, 100, 200), hover_color=(120, 120, 220), 
                 text_color=(255, 255, 255), font_size=20, callback=None):
        self.engine = engine
        self.text = text
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.font_size = font_size
        self.callback = callback
        self.hovered = False
        self.rect = pygame.Rect(x - width // 2, y - height // 2, width, height)
        self.font = pygame.font.Font(None, font_size)
        
    def update(self, dt):
        # 检查鼠标是否悬停在按钮上
        mouse_pos = pygame.mouse.get_pos()
        self.hovered = self.rect.collidepoint(mouse_pos)
        
    def render(self, surface):
        # 绘制按钮背景
        color = self.hover_color if self.hovered else self.color
        pygame.draw.rect(surface, color, self.rect)
        pygame.draw.rect(surface, (255, 255, 255), self.rect, 2)  # 边框
        
        # 绘制按钮文本
        text_surface = self.font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=(self.x, self.y))
        surface.blit(text_surface, text_rect)
        
    def handle_event(self, event:EventMessage):
        print(event)
        if event.type == EventType.MOUSEBUTTON_DOWN and event.data["button"] == 1:  # 左键点击
            if self.rect.collidepoint(event.data["pos"]) and self.callback:
                self.callback()