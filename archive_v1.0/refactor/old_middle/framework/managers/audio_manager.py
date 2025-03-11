import pygame


class AudioManager:
    """
    音频管理器：管理游戏音频（音效和音乐）
    """

    def __init__(self):
        pygame.mixer.init()
        self.sounds = {}
        self.music_volume = 1.0
        self.sound_volume = 1.0

    def load_sound(self, name, filepath):
        """加载音效"""
        try:
            sound = pygame.mixer.Sound(filepath)
            self.sounds[name] = sound
            return sound
        except Exception as e:
            print(f"无法加载音效 {filepath}: {e}")
            return None

    def play_sound(self, name, loops=0, volume=None):
        """播放已加载的音效"""
        if name in self.sounds:
            sound = self.sounds[name]
            if volume is not None:
                sound.set_volume(volume * self.sound_volume)
            else:
                sound.set_volume(self.sound_volume)
            sound.play(loops)

    def play_music(self, filepath, loops=-1, volume=None):
        """播放背景音乐"""
        try:
            pygame.mixer.music.load(filepath)
            if volume is not None:
                pygame.mixer.music.set_volume(volume * self.music_volume)
            else:
                pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(loops)
        except Exception as e:
            print(f"无法播放音乐 {filepath}: {e}")

    def stop_music(self):
        """停止背景音乐"""
        pygame.mixer.music.stop()

    def pause_music(self):
        """暂停背景音乐"""
        pygame.mixer.music.pause()

    def unpause_music(self):
        """恢复背景音乐"""
        pygame.mixer.music.unpause()

    def set_music_volume(self, volume):
        """设置背景音乐音量（0.0 - 1.0）"""
        self.music_volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(self.music_volume)

    def set_sound_volume(self, volume):
        """设置音效音量（0.0 - 1.0）"""
        self.sound_volume = max(0.0, min(1.0, volume))
