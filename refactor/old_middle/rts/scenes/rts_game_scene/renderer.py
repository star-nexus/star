import pygame
from rts.components import (
    PositionComponent,
    FactionComponent,
    SpriteComponent,
    UnitComponent,
)


class RTSGameRenderer:
    """
    RTS游戏渲染器：负责游戏场景的所有渲染工作
    将所有渲染逻辑从主游戏场景中分离出来
    """

    def __init__(self, scene):
        """
        初始化渲染器

        参数:
            scene: RTSGameScene实例，提供对游戏资源和系统的访问
        """
        self.scene = scene
        self.debug_mode = (
            self.scene.debug_mode if hasattr(self.scene, "debug_mode") else False
        )

    def render(self, screen):
        """
        执行完整的场景渲染

        参数:
            screen: pygame屏幕对象
        """
        # 清空屏幕，使用深绿色作为背景
        screen.fill((0, 50, 0))

        # 渲染地图
        self.scene.map_manager.render(screen)

        # 渲染游戏实体
        self._render_buildings_and_units(screen)

        # 渲染资源节点
        self.scene.entity_manager.render_resource_nodes(screen)

        # 渲染战斗效果
        self.scene.combat_manager.render(screen)

        # 渲染单位选择标记
        self._render_unit_selection(screen)

        # 渲染选择框
        if (
            self.scene.input_handler.is_selecting
            and self.scene.input_handler.selection_start
            and self.scene.input_handler.selection_end
        ):
            self._render_selection_box(screen)

        # 渲染游戏流程UI
        self.scene.game_flow_ui.render(screen)

    def _render_buildings_and_units(self, screen):
        """渲染建筑和单位"""
        # 收集所有需要渲染的实体
        render_entities = []
        entity_count = 0
        rendered_count = 0

        # 查找所有具有位置和精灵组件的实体（需要同时有这两个组件才能渲染）
        for entity_id, entity in self.scene.game.world.entities.items():
            entity_count += 1
            if entity.has_component(PositionComponent) and entity.has_component(
                SpriteComponent
            ):
                render_entities.append(entity)

        # 按y坐标排序以获得正确的深度渲染（y值大的在前面渲染，形成视觉上的深度）
        render_entities.sort(key=lambda e: e.get_component(PositionComponent).y)

        # 调试信息
        if self.debug_mode:
            print(f"总实体数: {entity_count}, 可渲染实体数: {len(render_entities)}")

        # 渲染每个实体
        for entity in render_entities:
            pos = entity.get_component(PositionComponent)
            sprite = entity.get_component(SpriteComponent)

            # 如果精灵被标记为不可见则跳过渲染
            if not sprite.is_visible:
                continue

            # 将世界坐标转换为屏幕坐标
            screen_x, screen_y = self.scene.map_manager.map_to_screen(pos.x, pos.y)

            # 获取图像名称
            image_name = sprite.image_name
            image = None

            # 图像查找策略，按优先级尝试不同来源：
            # 1. 优先从精灵组件自带的纹理获取（最高优先级，避免重复查找）
            if hasattr(sprite, "texture") and sprite.texture is not None:
                image = sprite.texture

            # 2. 从UnitFactory的本地纹理缓存获取
            elif (
                self.scene.unit_factory is not None
                and hasattr(self.scene.unit_factory, "local_textures")
                and image_name in self.scene.unit_factory.local_textures
            ):
                image = self.scene.unit_factory.local_textures[image_name]
                # 缓存到纹理属性中提高性能
                sprite.texture = image

            # 3. 从全局资源系统的images字典直接获取
            elif (
                hasattr(self.scene.game, "resources")
                and hasattr(self.scene.game.resources, "images")
                and image_name in self.scene.game.resources.images
            ):
                image = self.scene.game.resources.images[image_name]
                # 缓存到纹理属性中提高性能
                sprite.texture = image

            # 4. 通过资源系统的get_image方法获取
            elif hasattr(self.scene.game, "resources") and hasattr(
                self.scene.game.resources, "get_image"
            ):
                try:
                    image = self.scene.game.resources.get_image(image_name)
                    # 缓存到纹理属性中提高性能
                    if image:
                        sprite.texture = image
                except Exception as e:
                    if self.debug_mode:
                        print(f"无法加载图像 '{image_name}': {str(e)}")

            # 如果找到了图像，渲染它
            if image:
                screen.blit(image, (screen_x, screen_y))
                rendered_count += 1
            else:
                # 如果找不到图像，使用彩色矩形作为后备渲染方案
                color = (200, 100, 100)  # 默认红色

                # 如果实体有阵营组件，使用阵营颜色
                if entity.has_component(FactionComponent):
                    faction = entity.get_component(FactionComponent)
                    if hasattr(faction, "faction_color"):
                        color = faction.faction_color

                # 绘制填充矩形
                pygame.draw.rect(
                    screen,
                    color,
                    pygame.Rect(screen_x, screen_y, sprite.width, sprite.height),
                )

                # 绘制白色边框
                pygame.draw.rect(
                    screen,
                    (255, 255, 255),
                    pygame.Rect(screen_x, screen_y, sprite.width, sprite.height),
                    1,
                )

                rendered_count += 1

                # 只记录一次未找到图像的警告，避免刷屏
                if entity.has_component(UnitComponent):
                    unit_comp = entity.get_component(UnitComponent)
                    # 兼容不同版本的组件属性名
                    unit_name = (
                        unit_comp.unit_name
                        if hasattr(unit_comp, "unit_name")
                        else (
                            unit_comp.name if hasattr(unit_comp, "name") else "未知单位"
                        )
                    )
                    # 使用标记属性避免重复打印警告
                    if not hasattr(sprite, "_warned_missing_image"):
                        print(
                            f"警告: 未找到单位图像 '{image_name}' 用于单位 '{unit_name}'"
                        )
                        sprite._warned_missing_image = True

        # 打印调试信息
        if self.debug_mode:
            print(f"成功渲染实体数: {rendered_count}")

    def _render_unit_selection(self, screen):
        """渲染单位选择标记"""
        if not self.scene.unit_control_system:
            return

        # 调试信息
        if self.debug_mode:
            print(
                f"选中的单位数量: {len(self.scene.unit_control_system.selected_units)}"
            )

        for unit in self.scene.unit_control_system.selected_units:
            if unit.id in self.scene.game.world.entities:
                pos = unit.get_component(PositionComponent)
                if not pos:
                    continue

                # 将世界坐标转换为屏幕坐标
                screen_x, screen_y = self.scene.map_manager.map_to_screen(pos.x, pos.y)

                # 确保选择标记位于单位中心
                if unit.has_component(SpriteComponent):
                    sprite = unit.get_component(SpriteComponent)
                    center_x = screen_x + sprite.width // 2
                    center_y = screen_y + sprite.height // 2
                else:
                    # 默认假设32x32大小
                    center_x = screen_x + 16
                    center_y = screen_y + 16

                # 绘制选择圆圈
                selection_radius = 24  # 稍微大一点的选择圆
                pygame.draw.circle(
                    screen,
                    (0, 255, 0),  # 绿色选择标记
                    (center_x, center_y),
                    selection_radius,
                    2,  # 线宽
                )

                # 增加明显性，再绘制一个内圈
                pygame.draw.circle(
                    screen,
                    (255, 255, 0),  # 黄色内圈
                    (center_x, center_y),
                    selection_radius - 4,
                    1,  # 线宽
                )

    def _render_selection_box(self, screen):
        """渲染选择框"""
        start = self.scene.input_handler.selection_start
        end = self.scene.input_handler.selection_end

        if not start or not end:
            return

        # 计算矩形
        left = min(start[0], end[0])
        top = min(start[1], end[1])
        width = abs(end[0] - start[0])
        height = abs(end[1] - start[1])

        # 绘制半透明矩形
        selection_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        selection_surface.fill((0, 255, 0, 50))  # 绿色，半透明
        screen.blit(selection_surface, (left, top))

        # 绘制边框 - 增加可见性
        pygame.draw.rect(
            screen,
            (0, 255, 0),  # 绿色
            pygame.Rect(left, top, width, height),
            2,  # 线宽
        )
        # 添加一个内边框，增加可见性
        if width > 4 and height > 4:
            pygame.draw.rect(
                screen,
                (255, 255, 0),  # 黄色内边框
                pygame.Rect(left + 2, top + 2, width - 4, height - 4),
                1,  # 线宽
            )
