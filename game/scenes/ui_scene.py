import os
import pygame
import datetime
from framework.engine.scenes import Scene
from framework.ui import (
    UITransformComponent,
    ButtonComponent,
    PanelComponent,
    TextComponent,
)
from framework.ui.components.ui_components import ScrollableListComponent
from framework.ui.systems import UISystem
from framework.utils.logging import get_logger
from framework.engine.events import EventType, EventMessage


class UIScene(Scene):
    def __init__(self, engine):
        super().__init__(engine)
        self.logger = get_logger("UIScene")

        # UI 状态管理
        self.ui_entities = []
        self.hud_entities = []
        self.unit_panel_entities = []
        self.action_bar_entities = []
        self.menu_entities = []
        self.status_entities = []
        self.battle_log_entities = []  # 战况记录实体
        self.decision_log_entities = []  # 决策信息实体

        # 游戏状态
        self.selected_unit = None
        self.current_turn = 1
        self.current_player = "Player"
        self.resources = {
            "gold": 1000,
            "food": 500,
            "population": 100,
            "recruitment": 50,
        }

        # UI 可见性控制
        self.show_unit_panel = False
        self.show_menu = False
        self.show_tactical_overlay = False
        self.show_battle_log = True  # 默认显示战况记录
        self.show_decision_log = True  # 默认显示决策信息
        self.action_bar_extended = False  # 行动栏是否展开

        # 系统引用
        self.ui_system = None

        # 消息记录引用
        self.battle_log_component = None
        self.decision_log_component = None

    def enter(self, **kwargs):
        self.logger.info("进入战争游戏UI场景")
        super().enter(**kwargs)

        # 注册UI系统
        self.register_ui_system()

        # 创建所有UI元素
        self.create_main_hud()
        self.create_unit_info_panel()
        self.create_action_bar()
        self.create_game_menu()
        self.create_status_display()
        self.create_battle_log_panel()  # 新增战况记录面板
        self.create_decision_log_panel()  # 新增决策信息面板

        # 订阅事件
        self.subscribe_events()

        # 添加一些示例消息
        self._add_sample_messages()

        self.logger.info("战争游戏UI场景初始化完成")

    def register_ui_system(self):
        """注册UI系统"""
        self.logger.debug("注册UI系统")

        # 创建UI系统
        self.ui_system = UISystem()
        self.ui_system.initialize(self.world.context)
        self.world.add_system(self.ui_system)

        self.logger.debug("UI系统注册完成")

    def create_main_hud(self):
        """创建主要HUD界面"""
        self.logger.info("创建主要HUD界面")
        screen_width, screen_height = self.engine.screen.get_size()

        # 顶部状态栏背景
        hud_panel = self.world.create_entity()
        # 顶部状态栏背景 - UI位置
        self.world.add_component(
            hud_panel,
            UITransformComponent(
                x=0, y=0, width=screen_width, height=60, visible=True, enabled=True
            ),
        )
        # 顶部状态栏背景 - 颜色和边框
        self.world.add_component(
            hud_panel, PanelComponent(color=(40, 40, 60, 200), border_width=1)
        )
        self.hud_entities.append(hud_panel)

        # 回合信息
        turn_text = self.world.create_entity()
        # 回合信息 - UI位置
        self.world.add_component(
            turn_text, UITransformComponent(x=100, y=30, visible=True, enabled=True)
        )
        # 回合信息 - 文本组件
        self.world.add_component(
            turn_text,
            TextComponent(
                text=f"Turn {self.current_turn} - {self.current_player}",
                font_size=24,
                color=(255, 255, 255),
                centered=True,
            ),
        )
        self.hud_entities.append(turn_text)

        # 资源显示
        resource_x_start = 250
        resource_spacing = 120
        for i, (resource_name, value) in enumerate(self.resources.items()):
            resource_text = self.world.create_entity()
            self.world.add_component(
                resource_text,
                UITransformComponent(
                    x=resource_x_start + i * resource_spacing,
                    y=20,
                    visible=True,
                    enabled=True,
                ),
            )

            # 资源名称和图标
            resource_name_cn = {
                "gold": "金钱",
                "food": "粮食",
                "population": "人口",
                "recruitment": "兵力",
            }.get(resource_name, resource_name)

            self.world.add_component(
                resource_text,
                TextComponent(
                    text=f"{resource_name_cn}: {value}",
                    font_size=16,
                    color=(255, 255, 255),
                    centered=False,
                ),
            )
            self.hud_entities.append(resource_text)

        # 右侧小地图区域
        minimap_panel = self.world.create_entity()
        # 右侧小地图区域 - UI位置
        self.world.add_component(
            minimap_panel,
            UITransformComponent(
                x=screen_width - 160,
                y=70,
                width=150,
                height=150,
                visible=True,
                enabled=True,
            ),
        )
        # 右侧小地图区域 - 颜色和边框
        self.world.add_component(
            minimap_panel, PanelComponent(color=(60, 60, 90), border_width=2)
        )
        self.hud_entities.append(minimap_panel)

        # # 小地图标题
        # minimap_title = self.world.create_entity()
        # # 小地图标题 - UI位置
        # self.world.add_component(
        #     minimap_title,
        #     UITransformComponent(x=screen_width - 85, y=70, visible=True, enabled=True),
        # )
        # 小地图标题 - 文本组件
        # self.world.add_component(
        #     minimap_title,
        #     TextComponent(
        #     text="战场地图", font_size=14, color=(255, 255, 255), centered=True
        #     ),
        # )
        # self.hud_entities.append(minimap_title)

    def create_unit_info_panel(self):
        """创建单位信息面板"""
        self.logger.info("创建单位信息面板")
        screen_width, screen_height = self.engine.screen.get_size()

        # 单位信息面板背景
        unit_panel = self.world.create_entity()
        self.world.add_component(
            unit_panel,
            UITransformComponent(
                x=10,
                y=70,
                width=280,
                height=240,
                visible=self.show_unit_panel,
                enabled=True,
            ),
        )
        self.world.add_component(
            unit_panel, PanelComponent(color=(50, 50, 70, 220), border_width=2)
        )
        self.unit_panel_entities.append(unit_panel)

        # 单位名称
        unit_name = self.world.create_entity()
        self.world.add_component(
            unit_name,
            UITransformComponent(
                x=150, y=90, visible=self.show_unit_panel, enabled=True
            ),
        )
        self.world.add_component(
            unit_name,
            TextComponent(
                text="精锐步兵", font_size=20, color=(255, 255, 100), centered=True
            ),
        )
        self.unit_panel_entities.append(unit_name)

        # 单位统计信息
        stats = [
            ("等级", "3"),
            ("生命值", "85/100"),
            ("攻击力", "45"),
            ("防御力", "30"),
            ("移动力", "3/4"),
            ("士气", "高昂"),
        ]

        for i, (stat_name, value) in enumerate(stats):
            # 创建统计名称
            stat_label = self.world.create_entity()
            self.world.add_component(
                stat_label,
                UITransformComponent(
                    x=30,
                    y=120 + i * 25,
                    visible=self.show_unit_panel,
                    enabled=True,
                ),
            )
            self.world.add_component(
                stat_label,
                TextComponent(
                    text=f"{stat_name}:",
                    font_size=16,
                    color=(200, 200, 200),
                    centered=False,
                ),
            )
            self.unit_panel_entities.append(stat_label)

            # 创建统计值
            stat_value = self.world.create_entity()
            self.world.add_component(
                stat_value,
                UITransformComponent(
                    x=120,
                    y=120 + i * 25,
                    visible=self.show_unit_panel,
                    enabled=True,
                ),
            )

            # 根据统计类型选择颜色
            color = (255, 255, 255)
            if "生命值" in stat_name and "/" in value:
                current, max_hp = value.split("/")
                if int(current) < int(max_hp) * 0.3:
                    color = (255, 100, 100)  # 红色（危险）
                elif int(current) < int(max_hp) * 0.7:
                    color = (255, 255, 100)  # 黄色（警告）
                else:
                    color = (100, 255, 100)  # 绿色（健康）

            self.world.add_component(
                stat_value,
                TextComponent(text=value, font_size=16, color=color, centered=False),
            )
            self.unit_panel_entities.append(stat_value)

    def create_action_bar(self):
        """创建行动栏 - 右侧中部，两行布局，可滑动"""
        self.logger.info("创建行动栏")
        screen_width, screen_height = self.engine.screen.get_size()

        # 行动栏配置
        action_bar_width = 300
        action_bar_height = 95
        action_bar_x_hidden = screen_width - 50  # 隐藏时的位置（只显示一小部分）
        action_bar_x_shown = screen_width - action_bar_width - 10  # 展开时的位置
        action_bar_y = screen_height // 2 - action_bar_height // 2  # 垂直居中

        # 获取当前位置（根据展开状态）
        current_x = (
            action_bar_x_shown if self.action_bar_extended else action_bar_x_hidden
        )

        # 行动栏背景面板
        action_panel = self.world.create_entity()
        self.world.add_component(
            action_panel,
            UITransformComponent(
                x=current_x,
                y=action_bar_y,
                width=action_bar_width,
                height=action_bar_height,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            action_panel, PanelComponent(color=(40, 40, 60, 220), border_width=2)
        )
        self.action_bar_entities.append(action_panel)

        # 切换按钮（始终可见的部分）
        toggle_button = self.world.create_entity()
        self.world.add_component(
            toggle_button,
            UITransformComponent(
                x=current_x + 25,  # 相对于面板左侧
                y=action_bar_y + action_bar_height // 2,
                width=40,
                height=60,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            toggle_button,
            ButtonComponent(
                text="收起" if self.action_bar_extended else "打开",
                callback=self._toggle_action_bar,
                color=(60, 60, 100),
                hover_color=(80, 80, 120),
                font_size=16,
            ),
        )
        self.action_bar_entities.append(toggle_button)

        # 行动按钮（两行布局）
        actions = [
            ("移动", self._on_move_action),
            ("攻击", self._on_attack_action),
            ("防御", self._on_defend_action),
            ("技能", self._on_skill_action),
            ("等待", self._on_wait_action),
            ("撤退", self._on_retreat_action),
        ]

        button_width = 70
        button_height = 35
        button_spacing_x = 80
        button_spacing_y = 45
        start_x = current_x + 60  # 切换按钮右侧
        start_y = action_bar_y + 25

        for i, (action_name, callback) in enumerate(actions):
            # 计算按钮位置（两行三列布局）
            col = i % 3
            row = i // 3
            button_x = start_x + col * button_spacing_x
            button_y = start_y + row * button_spacing_y

            action_button = self.world.create_entity()
            self.world.add_component(
                action_button,
                UITransformComponent(
                    x=button_x,
                    y=button_y,
                    width=button_width,
                    height=button_height,
                    visible=self.action_bar_extended,
                    enabled=True,
                ),
            )
            self.world.add_component(
                action_button,
                ButtonComponent(
                    text=action_name,
                    callback=callback,
                    color=(80, 80, 120),
                    hover_color=(100, 100, 140),
                    font_size=14,
                ),
            )
            self.action_bar_entities.append(action_button)

    def create_game_menu(self):
        """创建游戏菜单"""
        self.logger.info("创建游戏菜单")
        screen_width, screen_height = self.engine.screen.get_size()

        # 菜单按钮（右上角）
        menu_button = self.world.create_entity()
        self.world.add_component(
            menu_button,
            UITransformComponent(
                x=screen_width - 80,
                y=30,
                width=60,
                height=30,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            menu_button,
            ButtonComponent(
                text="菜单",
                callback=self._toggle_menu,
                color=(100, 100, 100),
                hover_color=(120, 120, 120),
            ),
        )
        self.hud_entities.append(menu_button)

        # 菜单面板（默认隐藏）
        menu_panel = self.world.create_entity()
        self.world.add_component(
            menu_panel,
            UITransformComponent(
                x=screen_width - 200,
                y=50,
                width=180,
                height=300,
                visible=self.show_menu,
                enabled=True,
            ),
        )
        self.world.add_component(
            menu_panel, PanelComponent(color=(60, 60, 80, 240), border_width=2)
        )
        self.menu_entities.append(menu_panel)

        # 菜单选项
        menu_options = [
            ("继续游戏", self._continue_game),
            ("保存游戏", self._save_game),
            ("读取游戏", self._load_game),
            ("游戏设置", self._game_settings),
            ("战术地图", self._toggle_tactical),
            ("回到主菜单", self._return_to_main),
        ]

        for i, (option_name, callback) in enumerate(menu_options):
            menu_option = self.world.create_entity()
            self.world.add_component(
                menu_option,
                UITransformComponent(
                    x=screen_width - 110,
                    y=80 + i * 40,
                    width=140,
                    height=30,
                    visible=self.show_menu,
                    enabled=True,
                ),
            )
            self.world.add_component(
                menu_option,
                ButtonComponent(
                    text=option_name,
                    callback=callback,
                    color=(70, 70, 100),
                    hover_color=(90, 90, 120),
                    font_size=16,
                ),
            )
            self.menu_entities.append(menu_option)

    def create_status_display(self):
        """创建状态显示区域"""
        self.logger.info("创建状态显示区域")
        screen_width, screen_height = self.engine.screen.get_size()

        # 状态消息区域
        status_panel = self.world.create_entity()
        self.world.add_component(
            status_panel,
            UITransformComponent(
                x=screen_width // 2 - 200,
                y=70,
                width=400,
                height=40,
                visible=False,
                enabled=True,
            ),
        )
        self.world.add_component(
            status_panel, PanelComponent(color=(40, 80, 40, 200), border_width=1)
        )
        self.status_entities.append(status_panel)

        # 状态消息文本
        status_text = self.world.create_entity()
        self.world.add_component(
            status_text,
            UITransformComponent(
                x=screen_width // 2, y=90, visible=False, enabled=True
            ),
        )
        self.world.add_component(
            status_text,
            TextComponent(text="", font_size=18, color=(255, 255, 255), centered=True),
        )
        self.status_entities.append(status_text)

    def create_battle_log_panel(self):
        """创建战况记录面板 - 右下角"""
        self.logger.info("创建战况记录面板")
        screen_width, screen_height = self.engine.screen.get_size()

        # 战况记录面板背景
        battle_panel = self.world.create_entity()
        self.world.add_component(
            battle_panel,
            UITransformComponent(
                x=screen_width - 310,  # 右下角
                y=screen_height - 210,
                width=300,
                height=200,
                visible=self.show_battle_log,
                enabled=True,
            ),
        )
        self.world.add_component(
            battle_panel, PanelComponent(color=(60, 40, 40, 220), border_width=2)
        )
        self.battle_log_entities.append(battle_panel)

        # 战况记录标题
        battle_title = self.world.create_entity()
        self.world.add_component(
            battle_title,
            UITransformComponent(
                x=screen_width - 160,
                y=screen_height - 190,
                visible=self.show_battle_log,
                enabled=True,
            ),
        )
        self.world.add_component(
            battle_title,
            TextComponent(
                text="战况记录", font_size=18, color=(255, 200, 200), centered=True
            ),
        )
        self.battle_log_entities.append(battle_title)

        # 战况记录滚动列表
        battle_log = self.world.create_entity()
        self.world.add_component(
            battle_log,
            UITransformComponent(
                x=screen_width - 305,  # 相对于面板位置
                y=screen_height - 170,
                width=290,
                height=160,
                visible=self.show_battle_log,
                enabled=True,
            ),
        )

        self.battle_log_component = ScrollableListComponent(
            max_visible_messages=6,
            max_stored_messages=100,
            line_height=25,
            font_size=14,
            text_color=(255, 255, 255),
            background_color=(40, 30, 30, 180),
            show_timestamps=True,
            auto_scroll=True,
        )

        self.world.add_component(battle_log, self.battle_log_component)
        self.battle_log_entities.append(battle_log)

        # 切换显示按钮
        toggle_battle_button = self.world.create_entity()
        self.world.add_component(
            toggle_battle_button,
            UITransformComponent(
                x=screen_width - 40,
                y=screen_height - 190,
                width=60,
                height=20,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            toggle_battle_button,
            ButtonComponent(
                text="隐藏" if self.show_battle_log else "显示",
                callback=self._toggle_battle_log,
                color=(80, 60, 60),
                hover_color=(100, 80, 80),
                font_size=12,
            ),
        )
        self.battle_log_entities.append(toggle_battle_button)

    def create_decision_log_panel(self):
        """创建决策信息面板 - 左下角"""
        self.logger.info("创建决策信息面板")
        screen_width, screen_height = self.engine.screen.get_size()

        # 决策信息面板背景
        decision_panel = self.world.create_entity()
        self.world.add_component(
            decision_panel,
            UITransformComponent(
                x=10,  # 左下角
                y=screen_height - 210,
                width=300,
                height=200,
                visible=self.show_decision_log,
                enabled=True,
            ),
        )
        self.world.add_component(
            decision_panel, PanelComponent(color=(40, 60, 40, 220), border_width=2)
        )
        self.decision_log_entities.append(decision_panel)

        # 决策信息标题
        decision_title = self.world.create_entity()
        self.world.add_component(
            decision_title,
            UITransformComponent(
                x=160,
                y=screen_height - 190,
                visible=self.show_decision_log,
                enabled=True,
            ),
        )
        self.world.add_component(
            decision_title,
            TextComponent(
                text="决策信息", font_size=18, color=(200, 255, 200), centered=True
            ),
        )
        self.decision_log_entities.append(decision_title)

        # 决策信息滚动列表
        decision_log = self.world.create_entity()
        self.world.add_component(
            decision_log,
            UITransformComponent(
                x=15,  # 相对于面板位置
                y=screen_height - 170,
                width=290,
                height=160,
                visible=self.show_decision_log,
                enabled=True,
            ),
        )

        self.decision_log_component = ScrollableListComponent(
            max_visible_messages=6,
            max_stored_messages=100,
            line_height=25,
            font_size=14,
            text_color=(255, 255, 255),
            background_color=(30, 40, 30, 180),
            show_timestamps=True,
            auto_scroll=True,
        )

        self.world.add_component(decision_log, self.decision_log_component)
        self.decision_log_entities.append(decision_log)

        # 切换显示按钮
        toggle_decision_button = self.world.create_entity()
        self.world.add_component(
            toggle_decision_button,
            UITransformComponent(
                x=280,
                y=screen_height - 190,
                width=60,
                height=20,
                visible=True,
                enabled=True,
            ),
        )
        self.world.add_component(
            toggle_decision_button,
            ButtonComponent(
                text="隐藏" if self.show_decision_log else "显示",
                callback=self._toggle_decision_log,
                color=(60, 80, 60),
                hover_color=(80, 100, 80),
                font_size=12,
            ),
        )
        self.decision_log_entities.append(toggle_decision_button)

    def subscribe_events(self):
        """订阅游戏事件"""
        self.logger.info("订阅UI场景事件")
        if self.engine.event_manager:
            self.engine.event_manager.subscribe(
                EventType.KEY_DOWN, self.handle_key_event
            )
            self.engine.event_manager.subscribe(
                EventType.MOUSEBUTTON_DOWN, self.handle_mouse_event
            )
            self.logger.info("UI场景事件订阅成功")

    def update(self, delta_time):
        """更新场景"""
        super().update(delta_time)
        self.world.update(delta_time)

        # 更新资源显示
        self._update_resource_display()

    def handle_key_event(self, event: EventMessage):
        """处理键盘事件"""
        if event.type == EventType.KEY_DOWN:
            key = event.data.get("key")
            self.logger.info(f"按下键: {key}")
            if key == pygame.K_TAB:
                self._toggle_unit_panel()
            elif key == pygame.K_ESCAPE:
                self._toggle_menu()
            elif key == pygame.K_SPACE:
                self._end_turn()
            elif key == pygame.K_h:
                self._show_help()
            elif key == pygame.K_b:  # B键切换战况记录
                self._toggle_battle_log()
            elif key == pygame.K_d:  # D键切换决策信息
                self._toggle_decision_log()
            elif key == pygame.K_a:  # A键切换行动栏
                self._toggle_action_bar()

    def handle_mouse_event(self, event: EventMessage):
        """处理鼠标事件"""
        if event.type == EventType.MOUSEBUTTON_DOWN:
            button = event.data.get("button")
            pos = event.data.get("pos")

            if button == 3:  # 右键
                self._toggle_unit_panel()

    # 回调函数实现
    def _toggle_unit_panel(self):
        """切换单位面板显示"""
        self.show_unit_panel = not self.show_unit_panel
        self._update_panel_visibility(self.unit_panel_entities, self.show_unit_panel)
        self.logger.info(f"单位面板可见性: {self.show_unit_panel}")

    def _toggle_menu(self):
        """切换菜单显示"""
        self.show_menu = not self.show_menu
        self._update_panel_visibility(self.menu_entities, self.show_menu)
        self.logger.info(f"菜单可见性: {self.show_menu}")

    def _toggle_battle_log(self):
        """切换战况记录面板显示"""
        self.show_battle_log = not self.show_battle_log
        self._update_panel_visibility(
            self.battle_log_entities[:-1], self.show_battle_log
        )  # 除了按钮外的所有实体

        # 更新按钮文本
        if self.battle_log_entities:
            button_entity = self.battle_log_entities[-1]
            button_component = self.world.get_component(button_entity, ButtonComponent)
            if button_component:
                button_component.text = "隐藏" if self.show_battle_log else "显示"

        self.logger.info(f"战况记录面板可见性: {self.show_battle_log}")

    def _toggle_decision_log(self):
        """切换决策信息面板显示"""
        self.show_decision_log = not self.show_decision_log
        self._update_panel_visibility(
            self.decision_log_entities[:-1], self.show_decision_log
        )  # 除了按钮外的所有实体

        # 更新按钮文本
        if self.decision_log_entities:
            button_entity = self.decision_log_entities[-1]
            button_component = self.world.get_component(button_entity, ButtonComponent)
            if button_component:
                button_component.text = "隐藏" if self.show_decision_log else "显示"

        self.logger.info(f"决策信息面板可见性: {self.show_decision_log}")

    def _update_panel_visibility(self, entities, visible):
        """更新面板可见性"""
        for entity in entities:
            transform = self.world.get_component(entity, UITransformComponent)
            if transform:
                transform.visible = visible

    def _on_move_action(self):
        """移动行动"""
        self._show_status_message("选择移动目标位置")
        self.add_battle_message("单位开始移动", (200, 255, 200))
        self.add_decision_message("执行移动计划", (255, 200, 255))
        self.logger.info("执行移动行动")

    def _on_attack_action(self):
        """攻击行动"""
        self._show_status_message("选择攻击目标")
        self.add_battle_message("单位准备攻击", (255, 200, 200))
        self.add_decision_message("分析攻击目标", (255, 255, 200))
        self.logger.info("执行攻击行动")

    def _on_defend_action(self):
        """防御行动"""
        self._show_status_message("单位进入防御状态")
        self.add_battle_message("单位进入防御姿态", (200, 200, 255))
        self.add_decision_message("采用防御策略", (200, 255, 255))
        self.logger.info("执行防御行动")

    def _toggle_action_bar(self):
        """切换行动栏展开/收起状态"""
        self.action_bar_extended = not self.action_bar_extended
        screen_width, _ = self.engine.screen.get_size()

        # 计算新位置
        action_bar_width = 300
        new_x = (
            (screen_width - action_bar_width - 10)
            if self.action_bar_extended
            else (screen_width - 50)  # 隐藏时只显示一小部分
        )

        # 更新面板位置
        if len(self.action_bar_entities) > 0:
            panel_entity = self.action_bar_entities[0]
            panel_transform = self.world.get_component(
                panel_entity, UITransformComponent
            )
            if panel_transform:
                panel_transform.x = new_x

        # 更新切换按钮位置和文本
        if len(self.action_bar_entities) > 1:
            toggle_entity = self.action_bar_entities[1]
            toggle_transform = self.world.get_component(
                toggle_entity, UITransformComponent
            )
            toggle_button = self.world.get_component(toggle_entity, ButtonComponent)
            if toggle_transform and toggle_button:
                toggle_transform.x = new_x + 25
                toggle_button.text = "收起" if self.action_bar_extended else "打开"

        # 更新行动按钮位置和可见性
        for i in range(2, len(self.action_bar_entities)):  # 跳过面板和切换按钮
            button_entity = self.action_bar_entities[i]
            button_transform = self.world.get_component(
                button_entity, UITransformComponent
            )
            if button_transform:
                # 重新计算按钮位置
                button_index = i - 2
                col = button_index % 3
                row = button_index // 3
                button_spacing_x = 80
                button_spacing_y = 45
                start_x = new_x + 90
                start_y = button_transform.y  # 保持Y坐标不变

                button_transform.x = start_x + col * button_spacing_x
                button_transform.visible = self.action_bar_extended

        self.logger.info(
            f"行动栏状态: {'展开' if self.action_bar_extended else '收起'}"
        )

    def _on_skill_action(self):
        """技能行动"""
        self._show_status_message("选择要使用的技能")
        self.logger.info("执行技能行动")

    def _on_wait_action(self):
        """等待行动"""
        self._show_status_message("单位等待")
        self.logger.info("执行等待行动")

    def _on_retreat_action(self):
        """撤退行动"""
        self._show_status_message("单位撤退")
        self.logger.info("执行撤退行动")

    def _continue_game(self):
        """继续游戏"""
        self._toggle_menu()
        self.logger.info("继续游戏")

    def _save_game(self):
        """保存游戏"""
        self._show_status_message("游戏已保存")
        self.logger.info("保存游戏")

    def _load_game(self):
        """读取游戏"""
        self._show_status_message("读取游戏")
        self.logger.info("读取游戏")

    def _game_settings(self):
        """游戏设置"""
        self._show_status_message("打开游戏设置")
        self.logger.info("打开游戏设置")

    def _toggle_tactical(self):
        """切换战术视图"""
        self.show_tactical_overlay = not self.show_tactical_overlay
        self._show_status_message(
            f"战术视图: {'开启' if self.show_tactical_overlay else '关闭'}"
        )
        self.logger.info(f"战术视图: {self.show_tactical_overlay}")

    def _return_to_main(self):
        """返回主菜单"""
        self.logger.info("返回主菜单")
        self.engine.scene_manager.load_scene("start")

    def _end_turn(self):
        """结束回合"""
        self.current_turn += 1
        self._show_status_message(f"回合 {self.current_turn} 开始")
        self._update_turn_display()
        self.logger.info(f"结束回合，当前回合: {self.current_turn}")

    def _show_help(self):
        """显示帮助"""
        help_text = "快捷键: Tab-单位面板, Esc-菜单, Space-结束回合, A-行动栏, B-战况记录, D-决策信息, H-帮助"
        self._show_status_message(help_text)

    def _show_status_message(self, message):
        """显示状态消息"""
        if len(self.status_entities) >= 2:
            # 更新状态面板和文本的可见性
            panel_transform = self.world.get_component(
                self.status_entities[0], UITransformComponent
            )
            text_transform = self.world.get_component(
                self.status_entities[1], UITransformComponent
            )
            text_component = self.world.get_component(
                self.status_entities[1], TextComponent
            )

            if panel_transform and text_transform and text_component:
                panel_transform.visible = True
                text_transform.visible = True
                text_component.text = message

                # 3秒后隐藏消息
                import threading

                timer = threading.Timer(3.0, self._hide_status_message)
                timer.start()

    def _hide_status_message(self):
        """隐藏状态消息"""
        if len(self.status_entities) >= 2:
            panel_transform = self.world.get_component(
                self.status_entities[0], UITransformComponent
            )
            text_transform = self.world.get_component(
                self.status_entities[1], UITransformComponent
            )

            if panel_transform and text_transform:
                panel_transform.visible = False
                text_transform.visible = False

    def _update_resource_display(self):
        """更新资源显示"""
        # 这里可以实现资源数值的实时更新
        pass

    def _update_turn_display(self):
        """更新回合显示"""
        if self.hud_entities:
            # 更新回合文本（假设是第二个HUD实体）
            if len(self.hud_entities) > 1:
                turn_text_entity = self.hud_entities[1]
                text_component = self.world.get_component(
                    turn_text_entity, TextComponent
                )
                if text_component:
                    text_component.text = (
                        f"回合 {self.current_turn} - {self.current_player}"
                    )

    def exit(self):
        """退出场景"""
        self.logger.info("退出战争游戏UI场景")

        # 清理所有UI实体
        all_entities = (
            self.ui_entities
            + self.hud_entities
            + self.unit_panel_entities
            + self.action_bar_entities
            + self.menu_entities
            + self.status_entities
            + self.battle_log_entities
            + self.decision_log_entities
        )

        for entity in all_entities:
            self.world.destroy_entity(entity)

        # 清空列表
        self.ui_entities.clear()
        self.hud_entities.clear()
        self.unit_panel_entities.clear()
        self.action_bar_entities.clear()
        self.menu_entities.clear()
        self.status_entities.clear()
        self.battle_log_entities.clear()
        self.decision_log_entities.clear()

        # 移除UI系统
        if self.ui_system:
            self.world.remove_system(self.ui_system)

        super().exit()
        self.logger.info("战争游戏UI场景资源清理完成")

    def _add_sample_messages(self):
        """添加示例消息"""
        import time

        current_time = datetime.datetime.now()

        # 添加战况记录示例
        battle_messages = [
            {
                "text": "精锐步兵攻击敌方弓兵，造成15点伤害",
                "color": (255, 200, 200),
                "timestamp": current_time.strftime("%H:%M:%S"),
            },
            {
                "text": "敌方骑兵冲锋，我方步兵损失8点生命值",
                "color": (255, 100, 100),
                "timestamp": (current_time + datetime.timedelta(seconds=5)).strftime(
                    "%H:%M:%S"
                ),
            },
            {
                "text": "我方弓兵反击成功，击退敌方骑兵",
                "color": (200, 255, 200),
                "timestamp": (current_time + datetime.timedelta(seconds=10)).strftime(
                    "%H:%M:%S"
                ),
            },
            {
                "text": "地形加成：山地防御+20%",
                "color": (200, 200, 255),
                "timestamp": (current_time + datetime.timedelta(seconds=15)).strftime(
                    "%H:%M:%S"
                ),
            },
            {
                "text": "地形加成：山地防御+20%",
                "color": (200, 200, 255),
                "timestamp": (current_time + datetime.timedelta(seconds=15)).strftime(
                    "%H:%M:%S"
                ),
            },
            {
                "text": "地形加成：山地防御+20%",
                "color": (200, 200, 255),
                "timestamp": (current_time + datetime.timedelta(seconds=15)).strftime(
                    "%H:%M:%S"
                ),
            },
            {
                "text": "地形加成：山地防御+20%",
                "color": (200, 200, 255),
                "timestamp": (current_time + datetime.timedelta(seconds=15)).strftime(
                    "%H:%M:%S"
                ),
            },
            {
                "text": "地形加成：山地防御+20%",
                "color": (200, 200, 255),
                "timestamp": (current_time + datetime.timedelta(seconds=15)).strftime(
                    "%H:%M:%S"
                ),
            },
            {
                "text": "地形加成：山地防御+20%",
                "color": (200, 200, 255),
                "timestamp": (current_time + datetime.timedelta(seconds=15)).strftime(
                    "%H:%M:%S"
                ),
            },
        ]

        if self.battle_log_component:
            self.battle_log_component.messages.extend(battle_messages)

        # 添加决策信息示例
        decision_messages = [
            {
                "text": "AI分析：敌方弱点在左翼",
                "color": (255, 255, 200),
                "timestamp": current_time.strftime("%H:%M:%S"),
            },
            {
                "text": "建议：集中火力攻击敌方弓兵",
                "color": (200, 255, 255),
                "timestamp": (current_time + datetime.timedelta(seconds=3)).strftime(
                    "%H:%M:%S"
                ),
            },
            {
                "text": "单位规划：步兵向前推进两格",
                "color": (255, 200, 255),
                "timestamp": (current_time + datetime.timedelta(seconds=8)).strftime(
                    "%H:%M:%S"
                ),
            },
            {
                "text": "战术评估：当前优势度75%",
                "color": (200, 255, 200),
                "timestamp": (current_time + datetime.timedelta(seconds=12)).strftime(
                    "%H:%M:%S"
                ),
            },
        ]

        if self.decision_log_component:
            self.decision_log_component.messages.extend(decision_messages)

    def add_battle_message(self, message: str, color: tuple = (255, 255, 255)):
        """添加战况记录消息"""
        if self.battle_log_component:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            new_message = {"text": message, "color": color, "timestamp": timestamp}

            self.battle_log_component.messages.append(new_message)

            # 限制存储的消息数量
            if (
                len(self.battle_log_component.messages)
                > self.battle_log_component.max_stored_messages
            ):
                self.battle_log_component.messages = self.battle_log_component.messages[
                    -self.battle_log_component.max_stored_messages :
                ]

            self.logger.info(f"添加战况记录: {message}")

    def add_decision_message(self, message: str, color: tuple = (255, 255, 255)):
        """添加决策信息消息"""
        if self.decision_log_component:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            new_message = {"text": message, "color": color, "timestamp": timestamp}

            self.decision_log_component.messages.append(new_message)

            # 限制存储的消息数量
            if (
                len(self.decision_log_component.messages)
                > self.decision_log_component.max_stored_messages
            ):
                self.decision_log_component.messages = (
                    self.decision_log_component.messages[
                        -self.decision_log_component.max_stored_messages :
                    ]
                )

            self.logger.info(f"添加决策信息: {message}")
