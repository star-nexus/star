import pygame

class Panel:
    """
    面板 UI 组件
    """
    def __init__(self, engine, x, y, width, height, color=(50, 50, 50, 200)):
        self.engine = engine
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.rect = pygame.Rect(x, y, width, height)
        self.surface = pygame.Surface((width, height), pygame.SRCALPHA)
        
        # 填充颜色
        if len(color) == 4:  # 带透明度
            self.surface.fill(color)
        else:  # 不带透明度
            self.surface.fill(color)
        
    def update(self, dt):
        pass
        
    def render(self, surface):
        surface.blit(self.surface, self.rect)