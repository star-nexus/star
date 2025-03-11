import pygame
import os
from typing import Dict, Any, Optional

class ResourceManager:
    """资源管理器，负责加载和管理游戏资源（图像和字体）"""
    
    def __init__(self):
        """初始化资源管理器"""
        self._images: Dict[str, pygame.Surface] = {}
        self._fonts: Dict[str, Dict[int, pygame.font.Font]] = {}
    
    def load_image(self, name: str, path: str) -> pygame.Surface:
        """加载图像资源
        
        Args:
            name: 资源名称
            path: 资源路径
            
        Returns:
            加载的图像表面
        """
        if name in self._images:
            return self._images[name]
        
        try:
            image = pygame.image.load(path).convert_alpha()
            self._images[name] = image
            return image
        except pygame.error as e:
            print(f"无法加载图像 {path}: {e}")
            # 创建一个默认的错误图像（紫色方块）
            surface = pygame.Surface((32, 32))
            surface.fill((255, 0, 255))  # 紫色
            self._images[name] = surface
            return surface
    
    def get_image(self, name: str) -> Optional[pygame.Surface]:
        """获取已加载的图像资源
        
        Args:
            name: 资源名称
            
        Returns:
            图像表面，如果不存在则返回None
        """
        return self._images.get(name)
    
    # 音频相关功能已移至AudioManager
    
    def load_font(self, name: str, path: str, size: int) -> pygame.font.Font:
        """加载字体资源
        
        Args:
            name: 字体名称
            path: 字体路径
            size: 字体大小
            
        Returns:
            加载的字体对象
        """
        if name in self._fonts and size in self._fonts[name]:
            return self._fonts[name][size]
        
        try:
            if not name in self._fonts:
                self._fonts[name] = {}
                
            font = pygame.font.Font(path, size)
            self._fonts[name][size] = font
            return font
        except pygame.error as e:
            print(f"无法加载字体 {path}: {e}")
            # 使用默认字体
            default_font = pygame.font.Font(None, size)
            if name not in self._fonts:
                self._fonts[name] = {}
            self._fonts[name][size] = default_font
            return default_font
    
    def get_font(self, name: str, size: int) -> Optional[pygame.font.Font]:
        """获取已加载的字体资源
        
        Args:
            name: 字体名称
            size: 字体大小
            
        Returns:
            字体对象，如果不存在则返回None
        """
        if name in self._fonts and size in self._fonts[name]:
            return self._fonts[name][size]
        return None
    
    # 音乐相关功能已移至AudioManager
    
    def clear(self) -> None:
        """清理所有资源"""
        self._images.clear()
        self._fonts.clear()
        
    def clear_images(self) -> None:
        """清理图像资源"""
        self._images.clear()
        
    def clear_fonts(self) -> None:
        """清理字体资源"""
        self._fonts.clear()