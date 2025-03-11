# 管理器模块

该模块包含各种全局管理器，负责处理游戏中的资源、输入和音频。

## 组件

- **resource_manager.py**: 管理游戏资源（图像、字体等）
- **input_manager.py**: 处理用户输入（键盘、鼠标）
- **audio_manager.py**: 管理游戏音效和音乐

## 管理器功能

### 资源管理器 (ResourceManager)
- 加载和缓存图像
- 管理字体
- 防止资源重复加载

### 输入管理器 (InputManager)
- 处理键盘和鼠标输入
- 提供即时输入和单次触发输入检测
- 简化输入处理的API

### 音频管理器 (AudioManager)
- 加载和播放音效
- 控制背景音乐
- 音量控制

## 使用示例

```python
# 获取游戏引擎中的管理器
input_manager = game.input
audio_manager = game.audio
resource_manager = game.resources

# 资源管理
image = resource_manager.load_image("player", "assets/player.png")
font = resource_manager.load_font("main_font", "assets/fonts/arial.ttf", 24)

# 输入处理
if input_manager.is_key_pressed(pygame.K_SPACE):
    # 空格键被按下
    player_jump()

# 音频控制
audio_manager.play_sound("jump")
audio_manager.play_music("background_music.mp3")
```
