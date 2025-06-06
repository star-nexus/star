from framework.engine.scenes import Scene
from framework.ui import (
    UITransformComponent,
    ButtonComponent,
    PanelComponent,
    TextComponent,
)
from framework.ui.systems import UISystem
from framework.utils.logging_tool import get_logger


class StartScene(Scene):
    def __init__(self, engine):
        super().__init__(engine)
        self.logger = get_logger("StartScene")

    def enter(self, **kwargs):
        self.logger.info("进入开始场景")
        super().enter(**kwargs)
        # 创建UI实体
        self.create_entities()
        # 注册UI系统
        self.register_system()
        self.logger.info("开始场景初始化完成")

    def create_entities(self):
        self.logger.info("开始创建UI实体")
        self.ui_entities = []
        # 创建界面元素
        screen_width, screen_height = self.engine.screen.get_size()
        self.logger.info(f"屏幕尺寸: {screen_width}x{screen_height}")

        # 创建背景面板实体
        bg_panel_entity = self.world.create_entity()
        self.world.add_component(
            bg_panel_entity,
            UITransformComponent(
                x=0,
                y=0,
                width=screen_width,
                height=screen_height,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            bg_panel_entity,
            PanelComponent(color=(50, 50, 80), border_width=0),
        )
        self.ui_entities.append(bg_panel_entity)

        # 创建游戏标题实体
        title_entity = self.world.create_entity()
        self.world.add_component(
            title_entity,
            UITransformComponent(
                x=screen_width // 2, y=screen_height // 4, visible=True, enabled=True
            ),
        )
        self.world.add_component(
            title_entity,
            TextComponent(
                text="Demo Game",
                font_size=72,
                color=(255, 215, 0),
                centered=True,
            ),
        )
        self.ui_entities.append(title_entity)

        # 创建开始游戏按钮实体
        start_button_entity = self.world.create_entity()
        self.world.add_component(
            start_button_entity,
            UITransformComponent(
                x=screen_width // 2,
                y=screen_height // 2,
                width=200,
                height=60,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            start_button_entity,
            ButtonComponent(
                text="Start Game",
                callback=self._on_start_click,
            ),
        )
        self.ui_entities.append(start_button_entity)

        # 创建退出游戏按钮实体
        exit_button_entity = self.world.create_entity()
        self.world.add_component(
            exit_button_entity,
            UITransformComponent(
                x=screen_width // 2,
                y=screen_height // 2 + 100,
                width=200,
                height=60,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            exit_button_entity,
            ButtonComponent(
                text="Exit",
                callback=self._on_exit_click,
            ),
        )
        self.ui_entities.append(exit_button_entity)

        # 创建编辑测试场景按钮实体
        editor_button_entity = self.world.create_entity()
        self.world.add_component(
            editor_button_entity,
            UITransformComponent(
                x=screen_width // 2,
                y=screen_height // 2 + 180,
                width=200,
                height=60,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            editor_button_entity,
            ButtonComponent(
                text="Test Scene",
                callback=self._on_editor_click,
            ),
        )
        self.ui_entities.append(editor_button_entity)
        self.logger.info(f"创建了 {len(self.ui_entities)} 个UI实体")

    def register_system(self):
        self.logger.debug("正在注册UI渲染系统")
        # 添加UI渲染系统
        self.ui_system = UISystem()
        self.ui_system.initialize(self.world.context)
        self.world.add_system(self.ui_system)
        self.logger.debug("UI渲染系统注册完成")

    def exit(self):
        self.logger.info("退出开始场景")
        # 移除所有实体
        self.logger.info(f"正在销毁 {len(self.ui_entities)} 个UI实体")
        for entity in self.ui_entities:
            self.world.destroy_entity(entity)
        self.ui_entities.clear()

        # 移除所有组件
        self.logger.info("正在移除组件")
        self.world.component_manager.clear_components()
        self.logger.debug("组件移除完成")

        # 移除所有系统
        self.logger.info("正在移除UI渲染系统")
        self.world.remove_system(self.ui_system)
        super().exit()
        self.logger.info("开始场景资源清理完成")

    def update(self, delta_time):
        # 场景更新逻辑现在由ECS系统处理
        super().update(delta_time)
        self.world.update(delta_time)

    def _on_start_click(self):
        # 点击"开始游戏"按钮时的回调
        self.logger.info("用户点击了'开始游戏'按钮")
        self.engine.scene_manager.load_scene("game")

    def _on_exit_click(self):
        # 点击"退出游戏"按钮时的回调
        self.logger.info("用户点击了'退出游戏'按钮")
        self.engine.stop()

    def _on_editor_click(self):
        # 点击"编辑测试场景"按钮时的回调
        self.logger.info("用户点击了'编辑测试场景'按钮")
        self.engine.scene_manager.load_scene("editor")
