import pygame
from framework.ecs.world import World
from framework.managers.input_manager import InputManager
from framework.managers.audio_manager import AudioManager
from framework.managers.resource_manager import ResourceManager
from framework.ui.ui_manager import UIManager
from framework.scene.scene_manager import SceneManager


class GameEngine:
    """
    游戏引擎：控制游戏生命周期，管理全局服务和系统
    充当游戏核心，协调各个子系统的工作，确保游戏逻辑正确执行
    """

    def __init__(self, width=800, height=600, title="Pygame Game Framework", fps=60):
        """
        初始化游戏引擎

        参数:
            width (int): 游戏窗口宽度，默认为800像素
            height (int): 游戏窗口高度，默认为600像素
            title (str): 游戏窗口标题，默认为"Pygame Game Framework"
            fps (int): 游戏目标帧率，默认为60帧/秒
        """
        # 初始化Pygame库
        pygame.init()

        # 创建游戏窗口和设置标题
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(title)

        # 存储窗口尺寸和帧率设置
        self.width = width
        self.height = height
        self.fps = fps

        # 创建时钟对象，用于控制帧率
        self.clock = pygame.time.Clock()

        # 游戏运行状态标志
        self.is_running = False

        # 创建ECS(实体-组件-系统)世界
        # 这是游戏对象和逻辑组织的核心结构
        self.world = World()

        # 初始化各种管理器
        # 输入管理器：处理键盘、鼠标和其他输入设备
        self.input = InputManager()

        # 音频管理器：处理音效和音乐
        self.audio = AudioManager()

        # 资源管理器：加载和管理图像、音频和其他资源
        self.resources = ResourceManager()

        # UI管理器：处理用户界面元素
        self.ui = UIManager(self.screen)

        # 场景管理器：管理游戏的不同场景（如主菜单、游戏场景等）
        self.scene_manager = SceneManager(self)

    def start(self):
        """
        启动游戏主循环
        设置运行标志并调用游戏循环方法
        """
        self.is_running = True
        self._run_game_loop()

    def stop(self):
        """
        停止游戏
        将运行标志设置为False，导致游戏循环终止
        """
        self.is_running = False

    def _run_game_loop(self):
        """
        游戏主循环
        处理事件、更新游戏状态、渲染画面，是游戏运行的核心
        """
        # 记录上一帧的时间，用于计算帧间时间差
        last_time = pygame.time.get_ticks() / 1000.0

        # 只要is_running为True，游戏循环就会继续运行
        while self.is_running:
            # 计算当前帧与上一帧的时间差（delta time）
            # 这个值用于基于时间的游戏逻辑更新，确保不同帧率下游戏速度一致
            current_time = pygame.time.get_ticks() / 1000.0
            delta_time = current_time - last_time
            last_time = current_time

            # 处理所有积累的pygame事件
            events = pygame.event.get()
            for event in events:
                # 检查是否点击了窗口关闭按钮
                if event.type == pygame.QUIT:
                    self.is_running = False

                # 将事件传递给各个系统处理
                self.input.process_event(event)  # 输入管理器处理输入事件
                self.ui.process_event(event)  # UI管理器处理UI相关事件
                self.scene_manager.process_event(event)  # 场景管理器处理场景相关事件

            # 清空屏幕，准备新一帧的渲染
            # 黑色背景(0, 0, 0)
            self.screen.fill((0, 0, 0))

            # 更新和渲染当前活动场景
            self.scene_manager.update(delta_time)
            self.scene_manager.render()

            # 更新UI系统
            self.ui.update(delta_time)

            # 渲染UI元素（在场景之后，确保UI始终显示在最上层）
            self.ui.render()

            # 将所有渲染内容刷新到屏幕上
            pygame.display.flip()

            # 控制游戏帧率，限制在设定的fps值
            self.clock.tick(self.fps)

            # 更新输入系统状态，准备下一帧
            self.input.update()

        # 游戏循环结束后，退出pygame
        pygame.quit()
