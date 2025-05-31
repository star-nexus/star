import pygame
from framework.ecs.system import System
from framework.utils.logging import get_logger
from framework.engine.events import EventType, EventMessage
from game.components import CameraComponent
from game.components import MapComponent


class CameraSystem(System):
    """摄像机系统，负责处理摄像机移动和缩放"""

    def __init__(self, priority: int = 20):
        """初始化摄像机系统"""
        super().__init__(required_components=[CameraComponent], priority=priority)
        self.logger = get_logger("CameraSystem")

        # 移动状态
        self.moving_up = False
        self.moving_down = False
        self.moving_left = False
        self.moving_right = False

        # 缩放状态
        self.zooming_in = False  # 放大状态（=键）
        self.zooming_out = False  # 缩小状态（-键）

        # 平滑移动相关变量
        self.target_velocity_x = 0.0  # 目标X速度
        self.target_velocity_y = 0.0  # 目标Y速度
        self.current_velocity_x = 0.0  # 当前X速度
        self.current_velocity_y = 0.0  # 当前Y速度
        self.acceleration = 10.0  # 加速度
        self.deceleration = 15.0  # 减速度

        # 缩放相关变量
        self.zoom_acceleration = 0.5  # 缩放加速度

        # 屏幕自适应相关变量
        self.screen_width = 0
        self.screen_height = 0
        self.adaptive_min_zoom = 0.1  # 自适应最小缩放
        self.adaptive_max_zoom = 10.0  # 自适应最大缩放

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("摄像机系统初始化")

        width, height = self.context.screen.get_size()
        self.screen_width = width
        self.screen_height = height
        self.logger.debug(f"屏幕尺寸: {width}x{height}")

        self.create_camera(screen_width=width, screen_height=height)  # 创建摄像机实体
        self._update_adaptive_zoom_limits()  # 计算自适应缩放限制
        self._center_camera()
        # 订阅事件
        self.subscribe_events()

    def subscribe_events(self):
        """订阅事件"""
        self.context.event_manager.subscribe(
            [EventType.KEY_DOWN, EventType.KEY_UP, EventType.MOUSE_WHEEL],
            self.handle_event,
        )
        self.logger.debug("摄像机事件订阅成功")

    def create_camera(self, screen_width: int, screen_height: int):
        """创建摄像机实体"""
        self.logger.info(f"创建摄像机 - 视口尺寸: {screen_width}x{screen_height}")

        # 创建摄像机实体
        self.camera_entity = self.context.entity_manager.create_entity()

        # 创建摄像机组件
        camera_component = CameraComponent(
            x=0.0, y=0.0, zoom=1.0, width=screen_width, height=screen_height
        )

        # 添加组件到实体
        self.context.component_manager.add_component(
            self.camera_entity, camera_component
        )

        self.logger.info("摄像机创建完成")
        return self.camera_entity

    def _update_adaptive_zoom_limits(self):
        """更新自适应缩放限制，防止出现黑色区域"""
        map_component = self._get_map_component()
        if not map_component:
            return

        map_width_pixels = map_component.width * map_component.tile_size
        map_height_pixels = map_component.height * map_component.tile_size

        # 计算最小缩放，确保地图完全填满屏幕
        min_zoom_x = self.screen_width / map_width_pixels
        min_zoom_y = self.screen_height / map_height_pixels
        self.adaptive_min_zoom = max(min_zoom_x, min_zoom_y)

        # 确保最小缩放不会太小
        self.adaptive_min_zoom = max(self.adaptive_min_zoom, 0.1)

        # 最大缩放保持合理范围
        self.adaptive_max_zoom = max(self.adaptive_min_zoom * 10, 3.0)

        self.logger.debug(
            f"自适应缩放限制: {self.adaptive_min_zoom:.3f} - {self.adaptive_max_zoom:.3f}"
        )

    def _center_camera(self):
        """将摄像机居中到地图中央"""
        camera_component = self._get_camera_component()
        map_component = self._get_map_component()
        if not map_component:
            self.logger.warning("无法找到地图组件，无法居中摄像机")
            return

        map_component = map_component
        camera_component.x = (map_component.width * map_component.tile_size) / 2
        camera_component.y = (map_component.height * map_component.tile_size) / 2

        # 使用自适应缩放初始值
        initial_zoom = self.adaptive_min_zoom * 1.2  # 稍微放大一点以获得更好的初始视图
        camera_component.zoom = min(initial_zoom, self.adaptive_max_zoom)

        # 确保摄像机位置在有效范围内
        self._clamp_camera_position(camera_component, map_component)

        self.logger.debug(
            f"摄像机居中到位置 ({camera_component.x}, {camera_component.y}), 缩放: {camera_component.zoom:.3f}"
        )

    def _clamp_camera_position(
        self, camera_component: CameraComponent, map_component: MapComponent
    ):
        """限制摄像机位置在有效范围内"""
        if not map_component:
            return

        map_width_pixels = map_component.width * map_component.tile_size
        map_height_pixels = map_component.height * map_component.tile_size

        # 计算视口半宽和半高（考虑缩放）
        view_half_width = camera_component.width / (2 * camera_component.zoom)
        view_half_height = camera_component.height / (2 * camera_component.zoom)

        # 如果地图比屏幕小，居中显示
        if view_half_width * 2 >= map_width_pixels:
            camera_component.x = map_width_pixels / 2
        else:
            # 边界限制
            camera_component.x = max(
                view_half_width,
                min(map_width_pixels - view_half_width, camera_component.x),
            )

        if view_half_height * 2 >= map_height_pixels:
            camera_component.y = map_height_pixels / 2
        else:
            # 边界限制
            camera_component.y = max(
                view_half_height,
                min(map_height_pixels - view_half_height, camera_component.y),
            )

    def _get_camera_component(self):
        """获取摄像机组件"""
        camera_entity = self.context.with_all(CameraComponent).first()
        camera_component = self.context.get_component(camera_entity, CameraComponent)
        return camera_component

    def _get_map_component(self):
        """获取地图组件"""
        map_entity = self.context.with_all(MapComponent).first()
        map_component = self.context.get_component(map_entity, MapComponent)

        return map_component

    def toggle_zoom(self):
        """切换摄像机缩放级别"""
        camera_component = self._get_camera_component()
        if not camera_component:
            self.logger.warning("无法找到摄像机组件，无法切换缩放")
            return

        # 使用自适应缩放级别
        zoom_levels = [
            self.adaptive_min_zoom,
            self.adaptive_min_zoom * 2,
            self.adaptive_min_zoom * 4,
            self.adaptive_max_zoom,
        ]
        current_zoom = camera_component.zoom

        # 找到当前缩放级别在预设中的位置
        current_index = -1
        for i, zoom in enumerate(zoom_levels):
            if abs(current_zoom - zoom) < 0.1:  # 允许一定的误差
                current_index = i
                break

        # 切换到下一个缩放级别
        if current_index == -1 or current_index == len(zoom_levels) - 1:
            # 如果当前缩放不在预设中或已是最大缩放，则切换到最小缩放
            next_zoom = zoom_levels[0]
        else:
            # 否则切换到下一个更大的缩放级别
            next_zoom = zoom_levels[current_index + 1]

        camera_component.zoom = next_zoom
        # 调整摄像机位置以确保在有效范围内
        map_component = self._get_map_component()
        self._clamp_camera_position(camera_component, map_component)

        self.logger.info(f"摄像机缩放级别切换为: {next_zoom:.3f}")

    def handle_event(self, event: EventMessage):
        """处理输入事件"""

        camera_component = self._get_camera_component()

        # 处理键盘按下事件
        if event.type == EventType.KEY_DOWN:
            key = event.data.get("key")
            if key == pygame.K_w or key == pygame.K_UP:
                self.moving_up = True
            elif key == pygame.K_s or key == pygame.K_DOWN:
                self.moving_down = True
            elif key == pygame.K_a or key == pygame.K_LEFT:
                self.moving_left = True
            elif key == pygame.K_d or key == pygame.K_RIGHT:
                self.moving_right = True
            elif key == pygame.K_EQUALS:  # =键按下，开始放大
                self.zooming_in = True
                self.logger.debug("=键按下，开始放大")
            elif key == pygame.K_MINUS:  # -键按下，开始缩小
                self.zooming_out = True
                self.logger.debug("-键按下，开始缩小")
            elif key == pygame.K_SPACE:  # 空格键按下，将摄像机居中
                self._center_camera()
                self.logger.info("空格键按下，将摄像机居中")

        # 处理键盘松开事件
        elif event.type == EventType.KEY_UP:
            key = event.data.get("key")
            if key == pygame.K_w or key == pygame.K_UP:
                self.moving_up = False
            elif key == pygame.K_s or key == pygame.K_DOWN:
                self.moving_down = False
            elif key == pygame.K_a or key == pygame.K_LEFT:
                self.moving_left = False
            elif key == pygame.K_d or key == pygame.K_RIGHT:
                self.moving_right = False
            elif key == pygame.K_EQUALS:  # =键松开，停止放大
                self.zooming_in = False
                self.logger.debug("=键松开，停止放大")
            elif key == pygame.K_MINUS:  # -键松开，停止缩小
                self.zooming_out = False
                self.logger.debug("-键松开，停止缩小")

        # 处理鼠标滚轮事件
        elif event.type == EventType.MOUSE_WHEEL:
            # 使用鼠标滚轮缩放
            y_scroll = event.data.get("y", 0)
            if y_scroll > 0:  # 向上滚动，放大
                self._zoom_in(camera_component)
            elif y_scroll < 0:  # 向下滚动，缩小
                self._zoom_out(camera_component)

            # 记录缩放操作
            self.logger.debug(
                f"鼠标滚轮事件 - y值: {y_scroll}, 当前缩放: {camera_component.zoom:.2f}"
            )

    def _zoom_in(self, camera_component: CameraComponent):
        """放大视图"""
        if camera_component:
            # 使用自适应缩放限制
            new_zoom = min(
                camera_component.zoom * (1 + camera_component.zoom_speed),
                self.adaptive_max_zoom,
            )
            if new_zoom != camera_component.zoom:
                camera_component.zoom = new_zoom
                # 调整摄像机位置
                map_component = self._get_map_component()
                self._clamp_camera_position(camera_component, map_component)
                self.logger.debug(f"摄像机放大 - 当前缩放: {camera_component.zoom:.3f}")

    def _zoom_out(self, camera_component: CameraComponent):
        """缩小视图"""
        if camera_component:
            # 使用自适应缩放限制
            new_zoom = max(
                camera_component.zoom * (1 - camera_component.zoom_speed),
                self.adaptive_min_zoom,
            )
            if new_zoom != camera_component.zoom:
                camera_component.zoom = new_zoom
                # 调整摄像机位置
                map_component = self._get_map_component()
                self._clamp_camera_position(camera_component, map_component)
                self.logger.debug(f"摄像机缩小 - 当前缩放: {camera_component.zoom:.3f}")

    def _move_camera(
        self,
        map_component: MapComponent,
        camera_component: CameraComponent,
        delta_time: float,
    ):
        """根据当前移动状态移动摄像机，实现平滑移动"""
        if not camera_component:
            return

        # 计算移动方向
        dir_x = 0
        dir_y = 0

        if self.moving_up:
            dir_y -= 1
        if self.moving_down:
            dir_y += 1
        if self.moving_left:
            dir_x -= 1
        if self.moving_right:
            dir_x += 1

        # 计算目标速度（使用方向和基础移动速度）
        max_speed = camera_component.move_speed / camera_component.zoom

        # 如果有输入，计算目标速度
        if dir_x != 0 or dir_y != 0:
            # 归一化方向向量（对角线移动不应该更快）
            length = (dir_x * dir_x + dir_y * dir_y) ** 0.5
            if length > 0:
                dir_x /= length
                dir_y /= length

            # 设置目标速度
            self.target_velocity_x = dir_x * max_speed
            self.target_velocity_y = dir_y * max_speed
        else:
            # 没有输入，目标速度为0（停止）
            self.target_velocity_x = 0
            self.target_velocity_y = 0

        # 平滑地将当前速度过渡到目标速度
        if self.current_velocity_x < self.target_velocity_x:
            self.current_velocity_x = min(
                self.current_velocity_x + self.acceleration * delta_time,
                self.target_velocity_x,
            )
        elif self.current_velocity_x > self.target_velocity_x:
            self.current_velocity_x = max(
                self.current_velocity_x - self.deceleration * delta_time,
                self.target_velocity_x,
            )

        if self.current_velocity_y < self.target_velocity_y:
            self.current_velocity_y = min(
                self.current_velocity_y + self.acceleration * delta_time,
                self.target_velocity_y,
            )
        elif self.current_velocity_y > self.target_velocity_y:
            self.current_velocity_y = max(
                self.current_velocity_y - self.deceleration * delta_time,
                self.target_velocity_y,
            )

        # 使用当前速度更新位置
        if abs(self.current_velocity_x) > 0.01 or abs(self.current_velocity_y) > 0.01:
            # 计算新位置
            new_x = camera_component.x + self.current_velocity_x * delta_time
            new_y = camera_component.y + self.current_velocity_y * delta_time

            # 更新位置
            camera_component.x = new_x
            camera_component.y = new_y

            # 限制摄像机不要超出地图边界
            self._clamp_camera_position(camera_component, map_component)

    def _zoom_camera(self, camera_component: CameraComponent, delta_time: float):
        """处理摄像机的缩放"""
        # 处理长按键缩放
        if self.zooming_in:
            # 长按=键放大
            new_zoom = min(
                camera_component.zoom
                * (
                    1
                    + camera_component.zoom_speed * delta_time * self.zoom_acceleration
                ),
                self.adaptive_max_zoom,
            )
            if new_zoom != camera_component.zoom:
                camera_component.zoom = new_zoom
                # 调整摄像机位置
                map_component = self._get_map_component()
                self._clamp_camera_position(camera_component, map_component)
                self.logger.debug(
                    f"长按=键放大 - 当前缩放: {camera_component.zoom:.3f}"
                )

        if self.zooming_out:
            # 长按-键缩小
            new_zoom = max(
                camera_component.zoom
                * (
                    1
                    - camera_component.zoom_speed * delta_time * self.zoom_acceleration
                ),
                self.adaptive_min_zoom,
            )
            if new_zoom != camera_component.zoom:
                camera_component.zoom = new_zoom
                # 调整摄像机位置
                map_component = self._get_map_component()
                self._clamp_camera_position(camera_component, map_component)
                self.logger.debug(
                    f"长按-键缩小 - 当前缩放: {camera_component.zoom:.3f}"
                )

    def update(self, delta_time: float) -> None:
        """更新摄像机位置和缩放"""
        camera_component = self._get_camera_component()
        map_component = self._get_map_component()

        # 检查屏幕尺寸是否发生变化
        current_width, current_height = self.context.screen.get_size()
        if current_width != self.screen_width or current_height != self.screen_height:
            self.screen_width = current_width
            self.screen_height = current_height

            # 更新摄像机视口尺寸
            if camera_component:
                camera_component.width = current_width
                camera_component.height = current_height

            # 重新计算自适应缩放限制
            self._update_adaptive_zoom_limits()

            # 确保当前缩放在有效范围内
            if camera_component:
                camera_component.zoom = max(
                    self.adaptive_min_zoom,
                    min(self.adaptive_max_zoom, camera_component.zoom),
                )
                self._clamp_camera_position(camera_component, map_component)

            self.logger.info(f"屏幕尺寸变化: {current_width}x{current_height}")

        if camera_component:
            # 处理摄像机移动
            self._move_camera(map_component, camera_component, delta_time)
            self._zoom_camera(camera_component, delta_time)
