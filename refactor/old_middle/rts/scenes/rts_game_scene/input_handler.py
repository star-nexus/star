import pygame
import random
from rts.managers.game_state_manager import GameState


class RTSInputHandler:
    """
    RTS游戏输入处理器：处理用户输入并转换为游戏动作
    """

    def __init__(self, scene):
        self.scene = scene
        self.camera_moving = False
        self.camera_move_start = None

        # 鼠标状态
        self.mouse_state = "default"  # default, select, command, build
        self.selection_start = None
        self.selection_end = None
        self.is_selecting = False  # 是否正在框选
        self.click_threshold = 5  # 认为是点击而非拖拽的像素阈值
        self.last_click_time = 0  # 用于双击检测
        self.double_click_interval = 300  # 双击检测间隔(毫秒)

    def process_event(self, event):
        """处理输入事件"""
        # 处理鼠标事件
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # 左键
                # 记录点击位置用于判断是点击还是拖拽
                self.selection_start = event.pos
                self.is_selecting = True
                self.mouse_state = "select"
            elif event.button == 3:  # 右键
                self._handle_right_click(event.pos)
            elif event.button == 2:  # 中键
                # 开始移动地图视图
                self.camera_moving = True
                self.camera_move_start = event.pos

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self.is_selecting:  # 左键释放
                self.selection_end = event.pos

                # 如果开始和结束位置非常接近，视为点击而非框选
                if (
                    self.selection_start
                    and self.selection_end
                    and abs(self.selection_start[0] - self.selection_end[0])
                    < self.click_threshold
                    and abs(self.selection_start[1] - self.selection_end[1])
                    < self.click_threshold
                ):

                    # 处理单击选择
                    self._handle_left_click(self.selection_start)
                else:
                    # 处理框选
                    self._handle_selection()

                self.is_selecting = False
                self.mouse_state = "default"
            elif event.button == 2:  # 中键释放
                self.camera_moving = False

        elif event.type == pygame.MOUSEMOTION:
            if self.is_selecting:
                # 更新选择框终点
                self.selection_end = event.pos

            if self.camera_moving and self.camera_move_start:
                # 计算拖动距离
                dx = self.camera_move_start[0] - event.pos[0]
                dy = self.camera_move_start[1] - event.pos[1]

                # 移动地图视图
                if dx != 0 or dy != 0:
                    self.scene.map_manager.move_view(dx, dy)
                    self.camera_move_start = event.pos

        # 处理键盘事件
        elif event.type == pygame.KEYDOWN:
            self._handle_key_down(event.key)

    def _handle_left_click(self, pos):
        """处理鼠标左键点击"""
        # 检查是否点击了小地图
        map_pos = self.scene.ui_manager.handle_minimap_click(pos)
        if map_pos:
            # 如果点击了小地图，移动地图视图到该位置
            x, y = map_pos
            # 将地图位置转换为像素位置
            pixel_x = x * 32  # 假设每个格子32像素
            pixel_y = y * 32
            # 计算视口中心与点击位置的偏移
            screen_width = self.scene.game.width
            screen_height = self.scene.game.height
            offset_x = pixel_x - screen_width / 2
            offset_y = pixel_y - screen_height / 2
            # 设置地图视图位置
            if self.scene.map_manager and self.scene.map_manager.map_renderer:
                self.scene.map_manager.map_renderer.offset_x = max(0, offset_x)
                self.scene.map_manager.map_renderer.offset_y = max(0, offset_y)
            return

        # 转换屏幕坐标到地图坐标
        map_x, map_y = self.scene.map_manager.screen_to_map(pos[0], pos[1])

        # 仅在地图范围内处理点击
        if self.scene.map_manager.is_valid_position(map_x, map_y):
            # 获取点击的格子
            tile = self.scene.map_manager.get_tile(map_x, map_y)
            print(
                f"点击了格子 ({map_x}, {map_y}), 类型: {tile.type if hasattr(tile, 'type') else '未知'}"
            )

            # 实体选择逻辑
            pixel_x = map_x * 32
            pixel_y = map_y * 32
            selected_entity = None

            # 遍历所有实体，检查是否点击到
            for entity_id, entity in self.scene.game.world.entities.items():
                from rts.components import PositionComponent, SpriteComponent

                if entity.has_component(PositionComponent) and entity.has_component(
                    SpriteComponent
                ):
                    pos_comp = entity.get_component(PositionComponent)
                    sprite_comp = entity.get_component(SpriteComponent)

                    # 简单碰撞检测
                    if (
                        pixel_x >= pos_comp.x
                        and pixel_x <= pos_comp.x + sprite_comp.width
                        and pixel_y >= pos_comp.y
                        and pixel_y <= pos_comp.y + sprite_comp.height
                    ):
                        selected_entity = entity
                        break

            # 如果选中了实体，更新UI面板
            if selected_entity:
                self.scene.ui_manager.set_selected_entity(selected_entity)
                # 如果是单位实体，使用单位控制系统选择它
                from rts.components import UnitComponent

                if selected_entity.has_component(UnitComponent):
                    # 检查是否按下了Shift键（添加到当前选择）
                    add_to_selection = pygame.key.get_pressed()[pygame.K_LSHIFT]
                    self.scene.unit_control_system.select_units(
                        [selected_entity], add_to_selection
                    )

                print(f"选中了实体: {selected_entity.id}")
            else:
                # 如果没选中实体，清空选择
                self.scene.ui_manager.set_selected_entity(None)

                # 检查是否按下Shift键，如果没有则清空选择
                if not pygame.key.get_pressed()[pygame.K_LSHIFT]:
                    self.scene.unit_control_system.select_units([])

    def _handle_right_click(self, pos):
        """处理鼠标右键点击"""
        # 转换屏幕坐标到地图坐标
        map_x, map_y = self.scene.map_manager.screen_to_map(pos[0], pos[1])

        # 仅在地图范围内处理点击
        if self.scene.map_manager.is_valid_position(map_x, map_y):
            # 命令选中的单位移动到指定位置
            target_position = (map_x * 32, map_y * 32)  # 转换为像素坐标
            self.scene.unit_control_system.move_selected_units(target_position)

    def _handle_key_down(self, key):
        """处理键盘按下事件"""
        # 地图视图控制
        if key == pygame.K_w or key == pygame.K_UP:
            self.scene.map_manager.move_view(0, -30)  # 向上移动视图
        elif key == pygame.K_s or key == pygame.K_DOWN:
            self.scene.map_manager.move_view(0, 30)  # 向下移动视图
        elif key == pygame.K_a or key == pygame.K_LEFT:
            self.scene.map_manager.move_view(-30, 0)  # 向左移动视图
        elif key == pygame.K_d or key == pygame.K_RIGHT:
            self.scene.map_manager.move_view(30, 0)  # 向右移动视图
        # 缩放控制
        elif key == pygame.K_PLUS or key == pygame.K_EQUALS:
            self.scene.map_manager.zoom_in(0.1)
        elif key == pygame.K_MINUS:
            self.scene.map_manager.zoom_out(0.1)
        # 地图测试功能
        elif key == pygame.K_SPACE:
            # 生成一个新的随机地图
            complexity = random.random() * 0.5 + 0.5  # 0.5-1.0之间的复杂度
            self.scene.map_manager.generate_new_map(complexity)

        # 单位编组快捷键（Ctrl+数字）
        ctrl_pressed = (
            pygame.key.get_pressed()[pygame.K_LCTRL]
            or pygame.key.get_pressed()[pygame.K_RCTRL]
        )

        if ctrl_pressed and pygame.K_0 <= key <= pygame.K_9:
            group_number = key - pygame.K_0  # 转换为0-9的数字
            self.scene.unit_control_system.group_selected_units(group_number)
            print(f"单位编入{group_number}号编组")

        # 选择编组快捷键（数字键）
        elif pygame.K_0 <= key <= pygame.K_9 and not ctrl_pressed:
            group_number = key - pygame.K_0  # 转换为0-9的数字
            self.scene.unit_control_system.select_group(group_number)

    def handle_edge_scrolling(self, delta_time):
        """处理屏幕边缘的地图滚动"""
        # 确保游戏状态允许滚动视图
        if not self.scene.game_state_manager.is_state(GameState.PLAYING):
            return

        mouse_pos = pygame.mouse.get_pos()
        move_amount = self.scene.map_scrolling_speed * delta_time
        edge_size = 30  # 边缘区域大小，增加到30像素使其更容易触发

        # 检查鼠标是否在屏幕边缘
        if mouse_pos[0] < edge_size:  # 左边缘
            self.scene.map_manager.move_view(-move_amount, 0)
        elif mouse_pos[0] > self.scene.game.width - edge_size:  # 右边缘
            self.scene.map_manager.move_view(move_amount, 0)

        if mouse_pos[1] < edge_size:  # 上边缘
            self.scene.map_manager.move_view(0, -move_amount)
        elif mouse_pos[1] > self.scene.game.height - edge_size:  # 下边缘
            self.scene.map_manager.move_view(0, move_amount)

    def _handle_selection(self):
        """处理框选单位"""
        if not self.selection_start or not self.selection_end:
            return

        # 获取选择矩形范围
        rect = self._create_selection_rect()

        # 找出矩形内的所有单位
        selected_units = []
        for entity_id, entity in self.scene.game.world.entities.items():
            from rts.components import (
                PositionComponent,
                SpriteComponent,
                UnitComponent,
                FactionComponent,
            )

            # 需要同时有位置、精灵和单位组件
            if (
                entity.has_component(PositionComponent)
                and entity.has_component(SpriteComponent)
                and entity.has_component(UnitComponent)
            ):

                pos_comp = entity.get_component(PositionComponent)
                sprite_comp = entity.get_component(SpriteComponent)

                # 转换为屏幕坐标
                screen_x, screen_y = self.scene.map_manager.map_to_screen(
                    pos_comp.x, pos_comp.y
                )

                # 创建实体矩形
                entity_rect = pygame.Rect(
                    screen_x, screen_y, sprite_comp.width, sprite_comp.height
                )

                # 如果实体矩形与选择矩形相交，且属于玩家阵营，则选中该单位
                if rect.colliderect(entity_rect):
                    # 只选择玩家的单位
                    if entity.has_component(FactionComponent):
                        faction_comp = entity.get_component(FactionComponent)
                        # 检查是否是玩家的单位
                        if (
                            hasattr(faction_comp, "is_player")
                            and faction_comp.is_player
                        ):
                            selected_units.append(entity)
                        elif (
                            hasattr(self.scene.faction_system, "get_player_faction")
                            and self.scene.faction_system.get_player_faction()
                            is not None
                        ):
                            player_faction = (
                                self.scene.faction_system.get_player_faction()
                            )
                            player_faction_comp = player_faction.get_component(
                                FactionComponent
                            )
                            if hasattr(faction_comp, "faction_id") and hasattr(
                                player_faction_comp, "faction_id"
                            ):
                                if (
                                    faction_comp.faction_id
                                    == player_faction_comp.faction_id
                                ):
                                    selected_units.append(entity)

        # 检查是否按下了Shift键（添加到当前选择）
        add_to_selection = pygame.key.get_pressed()[pygame.K_LSHIFT]

        # 更新单位选择
        if selected_units:
            self.scene.unit_control_system.select_units(
                selected_units, add_to_selection
            )
            print(f"选中了 {len(selected_units)} 个单位")

    def _create_selection_rect(self):
        """创建选择矩形"""
        x1, y1 = self.selection_start
        x2, y2 = self.selection_end

        # 确保矩形的正确性（左上到右下）
        left = min(x1, x2)
        top = min(y1, y2)
        width = abs(x2 - x1)
        height = abs(y2 - y1)

        return pygame.Rect(left, top, width, height)
