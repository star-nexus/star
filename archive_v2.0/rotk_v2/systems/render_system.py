import pygame
from typing import List, Type
from framework_v2.ecs.system import System
from framework_v2.ecs.component import Component
from rotk_v2.components.transform_component import TransformComponent
from rotk_v2.components.render_component import RenderComponent
from rotk_v2.components.camera_component import CameraComponent,MainCameraTagComponent,MiniMapCameraTagComponent
from rotk_v2.components import CharacterComponent, ArmyComponent, SelectableComponent

class RenderSystem(System):
    """
    渲染系统，负责渲染所有具有 TransformComponent 和 RenderComponent 的实体
    """
    def __init__(self, required_components: List[Type[Component]] = None, priority: int = 0):
        if required_components is None:
            required_components = [TransformComponent, RenderComponent]
        super().__init__(required_components, priority)
        self.info_font = pygame.font.Font(None, 18)  # 预加载字体
        self._debug_counter = 0

    def update(self, delta_time: float) -> None:
        """更新系统逻辑"""
        # 更新调试计数器
        self._debug_counter += 1
            
        # 每60帧输出一次调试信息
        if self._debug_counter % 60 == 0:
            entities = self.component_manager.get_all_entities_with_components(self.required_components)
            print(f"RenderSystem: 找到 {len(entities)} 个可渲染实体")
        
        # 获取主相机
        camera = self._get_primary_camera()
        if not camera:
            print("RenderSystem: 找不到主相机")
            return
            
        if not self.context:
            return
            
        # 获取渲染管理器
        render_manager = self.context.render_manager
        if render_manager:
            # 使用渲染管理器的方式渲染
            self._render_with_manager(camera, render_manager)
        else:
            # 直接渲染到屏幕的方式
            self._render_direct(camera)
        
        # 渲染UI元素
        self.render_ui_elements()
        
        # 每60帧输出一次渲染信息
        if self._debug_counter % 60 == 0:
            print(f"相机位置: ({camera.x}, {camera.y}), 缩放: {camera.zoom}")
    
    def _render_with_manager(self, camera, render_manager):
        """使用渲染管理器渲染"""
        # 获取所有具有 TransformComponent 和 RenderComponent 的实体
        entities = self.context.with_all(*self.required_components).result()
        
        # 按照渲染层级排序
        entities.sort(key=lambda e: self.context.component_manager.get_component(e, RenderComponent).layer)
        
        # 通过渲染管理器绘制
        rendered_count = 0
        for entity in entities:
            transform = self.context.component_manager.get_component(entity, TransformComponent)
            render = self.context.component_manager.get_component(entity, RenderComponent)
            
            if not render.visible:
                continue
            
            # 创建临时表面
            surface = pygame.Surface((render.width, render.height), pygame.SRCALPHA)
            surface.fill(render.color)
            
            # 计算相对于相机的位置
            screen_x = (transform.x - camera.x) * camera.zoom + self.context.engine.width // 2
            screen_y = (transform.y - camera.y) * camera.zoom + self.context.engine.height // 2
            
            # 应用缩放
            scaled_width = render.width * camera.zoom
            scaled_height = render.height * camera.zoom
            
            # 计算绘制位置（中心点对齐）
            dest_rect = pygame.Rect(
                int(screen_x - scaled_width // 2),
                int(screen_y - scaled_height // 2),
                int(scaled_width),
                int(scaled_height)
            )
            
            # 如果实体在屏幕外，跳过渲染
            if (dest_rect.right < 0 or dest_rect.left > self.context.engine.width or
                dest_rect.bottom < 0 or dest_rect.top > self.context.engine.height):
                continue
            
            # 添加到渲染队列
            render_manager.draw(surface, dest_rect)
            rendered_count += 1
            
        if self._debug_counter % 60 == 0:
            print(f"RenderSystem: 通过管理器渲染了 {rendered_count} 个实体")
    
    def _render_direct(self, camera):
        """直接渲染到屏幕"""
        # 获取所有具有必要组件的实体
        entities = self.component_manager.get_all_entities_with_components(self.required_components)
        
        # 按层级排序实体
        sorted_entities = self._sort_entities_by_layer(entities)
        
        # 渲染所有实体
        rendered_count = 0
        for entity in sorted_entities:
            transform = self.component_manager.get_component(entity, TransformComponent)
            render = self.component_manager.get_component(entity, RenderComponent)
            
            if hasattr(render, 'visible') and not render.visible:
                continue
                
            # 计算相对于相机的位置
            screen_x = (transform.x - camera.x) * camera.zoom + self.context.engine.width // 2
            screen_y = (transform.y - camera.y) * camera.zoom + self.context.engine.height // 2
            
            # 应用缩放
            scaled_width = render.width * camera.zoom
            scaled_height = render.height * camera.zoom
            
            # 创建矩形
            rect = pygame.Rect(
                int(screen_x - scaled_width // 2),
                int(screen_y - scaled_height // 2),
                int(scaled_width),
                int(scaled_height)
            )
            
            # 如果实体在屏幕外，跳过渲染
            if (rect.right < 0 or rect.left > self.context.engine.width or
                rect.bottom < 0 or rect.top > self.context.engine.height):
                continue
            
            # 渲染实体
            pygame.draw.rect(self.context.engine.screen, render.color, rect)
            rendered_count += 1
            
        if self._debug_counter % 60 == 0:
            print(f"相机位置: ({camera.x}, {camera.y}), 缩放: {camera.zoom}")
            print(f"渲染了 {rendered_count} 个实体")
        
        if self._debug_counter % 60 == 0:
            print(f"RenderSystem: 直接渲染了 {rendered_count} 个实体")
    
    def _sort_entities_by_layer(self, entities):
        """按渲染层级排序实体"""
        return sorted(entities, key=lambda e: self.component_manager.get_component(e, RenderComponent).layer)
        
    def _get_primary_camera(self):
        """获取主相机"""
        # 首先尝试使用标签组件查找
        camera_entities = self.context.with_all(CameraComponent, MainCameraTagComponent).result()
        if not camera_entities:
            # 如果没有找到带标签的相机，尝试获取任何相机
            camera_entities = self.context.with_all(CameraComponent).result()
            if not camera_entities:
                return None
        
        # 获取相机组件
        camera_comp = self.context.component_manager.get_component(camera_entities[0], CameraComponent)
        return camera_comp

    
    
    def render_ui_elements(self):
        """通过RenderManager渲染所有UI元素"""
        camera_entities = self.context.with_all(CameraComponent).result()
        if not camera_entities:
            return
        
        camera_comp = self.context.component_manager.get_component(camera_entities[0], CameraComponent)
        entities = self.context.with_any(CharacterComponent, ArmyComponent, SelectableComponent).result()
        
        for entity in entities:
            transform = self.context.component_manager.get_component(entity, TransformComponent)
            ui_surfaces = self._generate_ui_surfaces(entity, transform, camera_comp)
            
            # 通过RenderManager绘制UI元素
            for surface, dest_rect in ui_surfaces:
                self.context.render_manager.draw(surface, dest_rect)
    
    def render_entity_info(self, entities):
        """渲染实体附加信息"""
        camera_entities = self.context.with_all(CameraComponent).result()
        if not camera_entities:
            return
            
        camera_comp = self.context.component_manager.get_component(camera_entities[0], CameraComponent)
        
        for entity in entities:
            transform = self.context.component_manager.get_component(entity, TransformComponent)
            
            # 基础信息（名称/势力）
            if self.context.component_manager.has_component(entity, CharacterComponent):
                self._render_character_info(entity, transform, camera_comp)
                
            if self.context.component_manager.has_component(entity, ArmyComponent):
                self._render_army_info(entity, transform, camera_comp)
            
            # 选中状态渲染修正
            if self.context.component_manager.has_component(entity, SelectableComponent):
                self._render_selection_indicator(transform, camera_comp)

    def _render_selection_indicator(self, transform, camera_comp):
        """绘制选中状态指示器"""
        screen_pos = self._world_to_screen(transform.x, transform.y, camera_comp)
        # 绘制选择框（示例：黄色矩形框）
        pygame.draw.rect(self.context.screen, (255,255,0), 
                        (screen_pos[0]-12, screen_pos[1]-12, 24, 24), 2)

    def _render_character_info(self, entity, transform, camera):
        """渲染角色特有信息"""
        character = self.context.component_manager.get_component(entity, CharacterComponent)
        screen_pos = self._world_to_screen(transform.x, transform.y-20, camera)
        
        # 渲染角色名称
        text_surface = self.info_font.render(character.name, True, (255,255,255))
        self.context.screen.blit(text_surface, screen_pos)

    def _render_army_info(self, entity, transform, camera):
        """渲染军队信息"""
        army = self.context.component_manager.get_component(entity, ArmyComponent)
        screen_pos = self._world_to_screen(transform.x+15, transform.y-10, camera)
        
        # 势力标识（颜色方块）
        force_color = self._get_force_color(army.force)
        pygame.draw.rect(self.context.screen, force_color, (*screen_pos, 8, 8))
        
        # 兵力状态（血条）
        bar_pos = self._world_to_screen(transform.x-20, transform.y-35, camera)
        self._draw_health_bar(bar_pos, army.troops, army.max_troops)

    def _world_to_screen(self, x, y, camera_component):
        """坐标转换：世界坐标 -> 屏幕坐标"""
        screen_width = self.context.screen.get_width()
        screen_height = self.context.screen.get_height()
        
        # 计算相对于相机中心的偏移
        offset_x = x - camera_component.x
        offset_y = y - camera_component.y
        
        # 应用缩放并转换为屏幕坐标
        screen_x = (offset_x * camera_component.zoom) + (screen_width / 2)
        screen_y = (offset_y * camera_component.zoom) + (screen_height / 2)
        
        return int(screen_x), int(screen_y)
    
    def _get_force_color(self, force):
        """势力颜色映射（示例实现）"""
        color_map = {
            "曹操": (255, 0, 0),    # 红色
            "刘备": (0, 0, 255),    # 蓝色
            "孙权": (0, 255, 0),    # 绿色
        }
        return color_map.get(force, (128, 128, 128))
        
    def _draw_health_bar(self, position, current, max_value):
        """绘制兵力状态条"""
        bar_width = 40
        bar_height = 4
        fill_width = int(bar_width * (current / max_value))
        
        # 背景框
        pygame.draw.rect(self.context.screen, (50,50,50), (position[0], position[1], bar_width, bar_height))
        # 当前兵力
        pygame.draw.rect(self.context.screen, (0,200,0), (position[0], position[1], fill_width, bar_height))

    def _generate_ui_surfaces(self, entity, transform, camera):
        """生成所有UI元素的Surface"""
        surfaces = []
        
        # 选中状态指示器
        if self.context.component_manager.has_component(entity, SelectableComponent):
            selector_surface = pygame.Surface((24, 24), pygame.SRCALPHA)
            pygame.draw.rect(selector_surface, (255,255,0), (0, 0, 24, 24), 2)
            screen_pos = self._world_to_screen(transform.x-12, transform.y-12, camera)
            surfaces.append((selector_surface, pygame.Rect(*screen_pos, 24, 24)))
        
        # 角色名称标签
        if self.context.component_manager.has_component(entity, CharacterComponent):
            character = self.context.component_manager.get_component(entity, CharacterComponent)
            name_surface = self.info_font.render(character.name, True, (255,255,255))
            screen_pos = self._world_to_screen(transform.x, transform.y-20, camera)
            surfaces.append((name_surface, pygame.Rect(*screen_pos, *name_surface.get_size())))
        
        # 军队信息
        if self.context.component_manager.has_component(entity, ArmyComponent):
            army = self.context.component_manager.get_component(entity, ArmyComponent)
            
            # 势力标识
            force_surface = pygame.Surface((8, 8))
            force_surface.fill(self._get_force_color(army.force))
            screen_pos = self._world_to_screen(transform.x+15, transform.y-10, camera)
            surfaces.append((force_surface, pygame.Rect(*screen_pos, 8, 8)))
            
            # 血条
            bar_surface = self._create_health_bar(army.troops, army.max_troops)
            screen_pos = self._world_to_screen(transform.x-20, transform.y-35, camera)
            surfaces.append((bar_surface, pygame.Rect(*screen_pos, *bar_surface.get_size())))

        return surfaces

    def _create_health_bar(self, current, max_value):
        """创建血条Surface"""
        bar_surface = pygame.Surface((40, 4), pygame.SRCALPHA)
        pygame.draw.rect(bar_surface, (50,50,50), (0, 0, 40, 4))
        fill_width = int(40 * (current / max_value))
        pygame.draw.rect(bar_surface, (0,200,0), (0, 0, fill_width, 4))
        return bar_surface
    
    def generate_ui_surfaces(self, entity, transform, camera):
        """生成UI元素的Surface和位置"""
        surfaces = []
        
        # 角色名称
        if self.context.component_manager.has_component(entity, CharacterComponent):
            char_surface, char_rect = self._create_character_ui(entity, transform, camera)
            surfaces.append((char_surface, char_rect))
        
        # 军队信息
        if self.context.component_manager.has_component(entity, ArmyComponent):
            army_surface, army_rect = self._create_army_ui(entity, transform, camera)
            surfaces.append((army_surface, army_rect))
        
        # 选中状态
        if self.context.component_manager.has_component(entity, SelectableComponent):
            selector_surface, selector_rect = self._create_selection_ui(transform, camera)
            surfaces.append((selector_surface, selector_rect))
        
        return surfaces

    def _create_character_ui(self, entity, transform, camera):
        """创建角色名称Surface"""
        character = self.context.component_manager.get_component(entity, CharacterComponent)
        screen_pos = self._world_to_screen(transform.x, transform.y-20, camera)
        
        surface = self.info_font.render(character.name, True, (255,255,255))
        rect = pygame.Rect(screen_pos[0], screen_pos[1], *surface.get_size())
        return surface, rect
    
    def _create_army_ui(self, entity, transform, camera):
        """创建军队信息Surface"""
        army = self.context.component_manager.get_component(entity, ArmyComponent)
        
        # 创建军队信息表面
        surface = pygame.Surface((40, 20), pygame.SRCALPHA)
        
        # 绘制势力标识
        force_color = self._get_force_color(army.force)
        pygame.draw.rect(surface, force_color, (0, 0, 8, 8))
        
        # 绘制兵力状态条
        pygame.draw.rect(surface, (50,50,50), (0, 12, 40, 4))
        fill_width = int(40 * (army.troops / army.max_troops))
        pygame.draw.rect(surface, (0,200,0), (0, 12, fill_width, 4))
        
        # 计算屏幕位置
        screen_pos = self._world_to_screen(transform.x-20, transform.y-35, camera)
        rect = pygame.Rect(screen_pos[0], screen_pos[1], *surface.get_size())
        
        return surface, rect
    
    def _create_selection_ui(self, transform, camera):
        """创建选中状态指示器Surface"""
        surface = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.rect(surface, (255,255,0), (0, 0, 24, 24), 2)
        
        screen_pos = self._world_to_screen(transform.x-12, transform.y-12, camera)
        rect = pygame.Rect(screen_pos[0], screen_pos[1], 24, 24)
        
        return surface, rect
                    
                    
