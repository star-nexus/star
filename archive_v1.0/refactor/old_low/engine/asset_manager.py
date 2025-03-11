import pygame
import os


class AssetManager:
    """管理游戏资源（图像、音频、字体等）的加载和缓存"""

    def __init__(self):
        self.images = {}
        self.sounds = {}
        self.fonts = {}
        self.music = {}

    def load_image(self, name, path, alpha=True):
        """加载图像并存储在缓存中"""
        if name not in self.images:
            try:
                if alpha:
                    image = pygame.image.load(path).convert_alpha()
                else:
                    image = pygame.image.load(path).convert()
                self.images[name] = image
            except pygame.error as e:
                print(f"无法加载图像 {path}: {e}")
                return None
        return self.images[name]

    def load_sound(self, name, path):
        """加载音效并存储在缓存中"""
        if name not in self.sounds:
            try:
                sound = pygame.mixer.Sound(path)
                self.sounds[name] = sound
            except pygame.error as e:
                print(f"无法加载音效 {path}: {e}")
                return None
        return self.sounds[name]

    def load_font(self, name, path, size):
        """加载字体并存储在缓存中"""
        key = f"{name}_{size}"
        if key not in self.fonts:
            try:
                font = pygame.font.Font(path, size)
                self.fonts[key] = font
            except pygame.error as e:
                print(f"无法加载字体 {path}: {e}")
                return None
        return self.fonts[key]

    def load_music(self, name, path):
        """加载音乐文件路径"""
        self.music[name] = path

    def play_music(self, name, loops=-1):
        """播放背景音乐"""
        if name in self.music:
            try:
                pygame.mixer.music.load(self.music[name])
                pygame.mixer.music.play(loops)
            except pygame.error as e:
                print(f"无法播放音乐 {self.music[name]}: {e}")

    def load_sprite_sheet(self, name, path, sprite_width, sprite_height, alpha=True):
        """加载精灵表并将其分割为单独的帧

        Args:
            name: 精灵表的标识符
            path: 精灵表图像的路径
            sprite_width: 单个精灵的宽度
            sprite_height: 单个精灵的高度
            alpha: 是否使用透明通道

        Returns:
            二维列表，包含分割好的所有帧图像
        """
        sheet = self.load_image(name, path, alpha)
        if not sheet:
            return []

        frames = []
        sheet_width = sheet.get_width()
        sheet_height = sheet.get_height()

        # 计算行数和列数
        cols = sheet_width // sprite_width
        rows = sheet_height // sprite_height

        # 提取每一帧
        for row in range(rows):
            row_frames = []
            for col in range(cols):
                x = col * sprite_width
                y = row * sprite_height
                frame = pygame.Surface((sprite_width, sprite_height), pygame.SRCALPHA)
                frame.blit(sheet, (0, 0), (x, y, sprite_width, sprite_height))
                row_frames.append(frame)
            frames.append(row_frames)

        return frames

    def save_game_state(self, filename, game_state):
        """保存游戏状态到文件

        Args:
            filename: 保存文件的名称
            game_state: 要保存的游戏状态数据
        """
        import json

        try:
            with open(filename, "w") as f:
                json.dump(game_state, f)
            return True
        except Exception as e:
            print(f"保存游戏状态失败: {e}")
            return False

    def load_game_state(self, filename):
        """从文件加载游戏状态

        Args:
            filename: 要加载的游戏状态文件

        Returns:
            加载的游戏状态数据，如果加载失败则返回None
        """
        import json

        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载游戏状态失败: {e}")
            return None
