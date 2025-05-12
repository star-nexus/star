import pygame
from typing import Dict, Optional
import os

class AudioManager:
    """音频管理器，负责管理游戏中的音频播放和控制"""
    
    def __init__(self):
        """初始化音频管理器"""
        # 确保pygame.mixer已初始化
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        
        self._sounds: Dict[str, pygame.mixer.Sound] = {}
        self._music_path: Optional[str] = None
        self._sound_volume = 1.0
        self._music_volume = 1.0
        self._sound_enabled = True
        self._music_enabled = True
    
    def load_sound(self, name: str, path: str) -> Optional[pygame.mixer.Sound]:
        """加载音效资源
        
        Args:
            name: 音效名称
            path: 音效文件路径
            
        Returns:
            加载的音效对象，加载失败则返回None
        """
        if name in self._sounds:
            return self._sounds[name]
        
        try:
            sound = pygame.mixer.Sound(path)
            self._sounds[name] = sound
            sound.set_volume(self._sound_volume)
            return sound
        except pygame.error as e:
            print(f"无法加载音效 {path}: {e}")
            return None
    
    def play_sound(self, name: str, loops: int = 0, maxtime: int = 0, fade_ms: int = 0) -> None:
        """播放音效
        
        Args:
            name: 音效名称
            loops: 循环次数，0表示播放一次，-1表示无限循环
            maxtime: 最大播放时间（毫秒），0表示不限制
            fade_ms: 淡入时间（毫秒）
        """
        if not self._sound_enabled:
            return
            
        sound = self._sounds.get(name)
        if sound:
            sound.play(loops, maxtime, fade_ms)
    
    def stop_sound(self, name: str) -> None:
        """停止指定音效
        
        Args:
            name: 音效名称
        """
        sound = self._sounds.get(name)
        if sound:
            sound.stop()
    
    def stop_all_sounds(self) -> None:
        """停止所有音效"""
        for sound in self._sounds.values():
            sound.stop()
    
    def play_music(self, path: str, loops: int = -1, start: float = 0.0, fade_ms: int = 0) -> None:
        """播放背景音乐
        
        Args:
            path: 音乐文件路径
            loops: 循环次数，-1表示无限循环
            start: 开始播放的位置（秒）
            fade_ms: 淡入时间（毫秒）
        """
        if not self._music_enabled:
            return
            
        try:
            if self._music_path != path:
                pygame.mixer.music.load(path)
                self._music_path = path
            pygame.mixer.music.set_volume(self._music_volume)
            pygame.mixer.music.play(loops, start, fade_ms)
        except pygame.error as e:
            print(f"无法播放音乐 {path}: {e}")
    
    def stop_music(self, fade_ms: int = 0) -> None:
        """停止背景音乐
        
        Args:
            fade_ms: 淡出时间（毫秒）
        """
        pygame.mixer.music.fadeout(fade_ms) if fade_ms > 0 else pygame.mixer.music.stop()
    
    def pause_music(self) -> None:
        """暂停背景音乐"""
        pygame.mixer.music.pause()
    
    def unpause_music(self) -> None:
        """恢复背景音乐"""
        pygame.mixer.music.unpause()
    
    def set_music_volume(self, volume: float) -> None:
        """设置背景音乐音量
        
        Args:
            volume: 音量值 (0.0 到 1.0)
        """
        self._music_volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(self._music_volume)
    
    def set_sound_volume(self, volume: float) -> None:
        """设置音效音量
        
        Args:
            volume: 音量值 (0.0 到 1.0)
        """
        self._sound_volume = max(0.0, min(1.0, volume))
        for sound in self._sounds.values():
            sound.set_volume(self._sound_volume)
    
    def enable_sound(self, enabled: bool) -> None:
        """启用或禁用音效
        
        Args:
            enabled: 是否启用音效
        """
        self._sound_enabled = enabled
    
    def enable_music(self, enabled: bool) -> None:
        """启用或禁用背景音乐
        
        Args:
            enabled: 是否启用背景音乐
        """
        self._music_enabled = enabled
        if not enabled and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
    
    def is_music_playing(self) -> bool:
        """检查背景音乐是否正在播放
        
        Returns:
            是否正在播放
        """
        return pygame.mixer.music.get_busy()
    
    def clear(self) -> None:
        """清理所有音频资源"""
        self.stop_all_sounds()
        self.stop_music()
        self._sounds.clear()
        self._music_path = None