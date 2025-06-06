from framework.engine.scenes import Scene
from framework.ui import (
    UITransformComponent,
    ButtonComponent,
    PanelComponent,
    TextComponent,
)
from framework.ui.systems import UISystem

from framework.utils.logging_tool import get_logger


class EndScene(Scene):
    def __init__(self, engine):
        super().__init__(engine)
        self.logger = get_logger("EndScene")
        self.ui_entities = []
        self.ui_system = None

    def enter(self, **kwargs):
        self.logger.info("进入结束场景")
        super().enter(**kwargs)

        result = kwargs.get("result", "游戏结束")
        reason = kwargs.get("reason", "未知原因")
        self.logger.info(f"游戏结果: {result}, 原因: {reason}")
        reason = f"faction {reason} win"
        self.create_ui_entities(result, reason)
        self.register_system()
        self.logger.info("结束场景初始化完成")

    def create_ui_entities(self, result_text_val, reason_text_val):
        self.logger.info("开始创建UI实体")
        self.ui_entities = []
        screen_width, screen_height = self.engine.screen.get_size()

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
            PanelComponent(
                color=(30, 30, 30, 200), border_width=0
            ),  # Semi-transparent dark panel
        )
        self.ui_entities.append(bg_panel_entity)

        # 创建结果标题实体
        result_title_entity = self.world.create_entity()
        self.world.add_component(
            result_title_entity,
            UITransformComponent(
                x=screen_width // 2,
                y=screen_height // 4,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            result_title_entity,
            TextComponent(
                text=result_text_val,
                font_size=48,
                color=(255, 255, 255),
                centered=True,
            ),
        )
        self.ui_entities.append(result_title_entity)

        # 创建原因文本实体
        reason_text_entity = self.world.create_entity()
        self.world.add_component(
            reason_text_entity,
            UITransformComponent(
                x=screen_width // 2,
                y=screen_height // 4 + 80,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            reason_text_entity,
            TextComponent(
                text=reason_text_val,
                font_size=24,
                color=(200, 200, 200),
                centered=True,
            ),
        )
        self.ui_entities.append(reason_text_entity)

        # 创建重新开始按钮实体
        restart_button_entity = self.world.create_entity()
        self.world.add_component(
            restart_button_entity,
            UITransformComponent(
                x=screen_width // 2,
                y=screen_height // 2 + 50,
                width=200,
                height=60,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            restart_button_entity,
            ButtonComponent(
                text="Restart",
                callback=self._on_restart_click,
            ),
        )
        self.ui_entities.append(restart_button_entity)

        # 创建退出游戏按钮实体
        exit_button_entity = self.world.create_entity()
        self.world.add_component(
            exit_button_entity,
            UITransformComponent(
                x=screen_width // 2,
                y=screen_height // 2 + 130,
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
        self.logger.info(f"创建了 {len(self.ui_entities)} 个UI实体")

    def register_system(self):
        self.logger.debug("正在注册UI渲染系统")
        self.ui_system = UISystem()
        self.ui_system.initialize(self.world.context)
        self.world.add_system(self.ui_system)
        self.logger.debug("UI渲染系统注册完成")

    def exit(self):
        self.logger.info("退出结束场景")
        # 移除所有UI实体
        self.logger.info(f"正在销毁 {len(self.ui_entities)} 个UI实体")
        for entity in self.ui_entities:
            self.world.destroy_entity(entity)
        self.ui_entities.clear()

        # 移除UI系统
        if self.ui_system:
            self.logger.info("正在移除UI渲染系统")
            self.world.remove_system(self.ui_system)
            self.ui_system = None

        # 可选：根据需要清理其他组件和系统，但通常结束场景不需要像开始场景那样彻底清理
        # self.logger.info("正在移除组件")
        # self.world.component_manager.clear_components()
        # self.logger.debug("组件移除完成")

        super().exit()
        self.logger.info("结束场景资源清理完成")

    def update(self, delta_time):
        super().update(delta_time)
        self.world.update(delta_time)

    def _on_restart_click(self):
        # 点击"重新开始"按钮时的回调
        self.engine.scene_manager.load_scene("start")

    def _on_exit_click(self):
        # 点击"退出游戏"按钮时的回调
        self.engine.stop()
