import pygame


class ResourceManager:
    """
    资源管理器：加载和管理游戏资源（图像、字体等）
    """

    def __init__(self):
        self.images = {}
        self.fonts = {}

    def load_image(self, name, filepath, alpha=True):
        """加载图像"""
        try:
            if alpha:
                image = pygame.image.load(filepath).convert_alpha()
            else:
                image = pygame.image.load(filepath).convert()
            self.images[name] = image
            print(f"Loaded image: {name} from {filepath}")  # Debug print
            return image
        except Exception as e:
            print(f"无法加载图像 {filepath}: {e}")
            # 创建一个错误图像（粉色方块）
            error_image = pygame.Surface((32, 32))
            error_image.fill((255, 0, 255))
            self.images[name] = error_image
            return error_image

    def get_image(self, name):
        """获取已加载的图像"""
        return self.images.get(name)

    def load_font(self, name, filepath, size):
        """加载字体"""
        try:
            font = pygame.font.Font(filepath, size)
            self.fonts[(name, size)] = font
            return font
        except Exception as e:
            print(f"无法加载字体 {filepath}: {e}")
            # 使用系统默认字体
            font = pygame.font.SysFont("arial", size)
            self.fonts[(name, size)] = font
            return font

    def get_font(self, name, size):
        """获取已加载的字体"""
        key = (name, size)
        if key not in self.fonts:
            # 如果指定大小的字体不存在，尝试加载系统默认字体
            self.fonts[key] = pygame.font.SysFont(name, size)
        return self.fonts[key]
