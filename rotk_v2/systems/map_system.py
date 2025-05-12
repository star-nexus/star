import pygame
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from framework_v2.ecs.system import System
from framework_v2.engine.events import EventType

from rotk_v2.components.transform_component import TransformComponent
from rotk_v2.components.render_component import RenderComponent
from rotk_v2.components.tile_component import TileComponent, TerrainType
from rotk_v2.components.map_component import MapComponent
from rotk_v2.components.camera_component import CameraComponent, MainCameraTagComponent
from rotk_v2.utils.map_generator import MapGenerator

class MapSystem(System):
    """地图系统，负责地图的生成、渲染和管理"""
    
    def __init__(self, required_components=None, priority=0):
        super().__init__(required_components, priority)
        self.map_entity = None
        self.map_component = None
        self.tile_size = 32
        self.show_grid = True
        self.show_elevation = False
        
        # 地形颜色映射
        self.terrain_colors = {
            TerrainType.PLAIN: (100, 200, 100),     # 浅绿色
            TerrainType.HILL: (150, 150, 100),      # 棕黄色
            TerrainType.MOUNTAIN: (120, 100, 80),   # 深棕色
            TerrainType.FOREST: (0, 150, 0),        # 深绿色
            TerrainType.WATER: (50, 100, 200),      # 蓝色
            TerrainType.DESERT: (240, 220, 160),    # 沙色
            TerrainType.SWAMP: (100, 130, 50),      # 暗绿色
            TerrainType.ROAD: (200, 180, 150),      # 浅棕色
            TerrainType.CITY: (200, 200, 200),      # 灰色
            TerrainType.PASS: (180, 120, 80)        # 棕色
        }
        
    def initialize(self):
        """初始化地图系统"""
        print("初始化地图系统...")
        
        # 创建地图实体
        self.map_entity = self.entity_manager.create_entity()
        
        # 生成地图
        map_width = 100
        map_height = 80
        self.tile_size = 32
        
        # 启用调试渲染
        self._debug_render = True
        
        # 使用地图生成器
        generator = MapGenerator(map_width, map_height)
        elevation, terrain, moisture = generator.generate_map()
        
        # 创建地图组件
        self.map_component = MapComponent(
            width=map_width,
            height=map_height,
            tile_size=self.tile_size,
            elevation_map=elevation,
            terrain_map=terrain,
            moisture_map=moisture,
            name="三国时期中国",
            description="公元200年左右的中国地图"
        )
        
        # 添加地图组件到地图实体
        self.component_manager.add_component(self.map_entity, self.map_component)
        
        # 创建所有地形块实体
        self._create_tile_entities()
        
        # 调试信息：检查创建的实体数量
        tile_count = len(self.map_component.tile_entities)
        print(f"创建了 {tile_count} 个地形块实体")
        
        # 检查几个随机地形块的组件
        import random
        for _ in range(5):
            x = random.randint(0, map_width - 1)
            y = random.randint(0, map_height - 1)
            tile_entity = self.map_component.tile_entities.get((x, y))
            if tile_entity:
                has_transform = self.component_manager.has_component(tile_entity, TransformComponent)
                has_render = self.component_manager.has_component(tile_entity, RenderComponent)
                print(f"地形块 ({x}, {y}): 实体ID={tile_entity}, 有TransformComponent={has_transform}, 有RenderComponent={has_render}")
        
        # 发布地图创建事件
        print(f"地图创建完成，发布事件: {map_width}x{map_height}")
        self.context.event_manager.publish_immediate(
            EventType.MAP_CREATED,
            {"map_entity": self.map_entity, "width": map_width, "height": map_height}
        )
        
    def _create_tile_entities(self):
        """创建所有地形块实体"""
        for y in range(self.map_component.height):
            for x in range(self.map_component.width):
                # 创建地形块实体
                tile_entity = self.entity_manager.create_entity()
                
                # 获取地形信息
                terrain_type = TerrainType(self.map_component.terrain_map[y, x])
                elevation = self.map_component.elevation_map[y, x]
                
                # 计算世界坐标
                world_x = x * self.tile_size
                world_y = y * self.tile_size
                
                # 添加变换组件
                self.component_manager.add_component(tile_entity, TransformComponent(
                    x=world_x + self.tile_size // 2,
                    y=world_y + self.tile_size // 2
                ))
                
                # 添加渲染组件
                color = self.terrain_colors.get(terrain_type, (150, 150, 150))
                self.component_manager.add_component(tile_entity, RenderComponent(
                    color=color,
                    width=self.tile_size,
                    height=self.tile_size,
                    layer=0
                ))
                
                # 添加地形块组件
                tile_component = TileComponent(
                    terrain_type=terrain_type,
                    elevation=elevation,
                    grid_x=x,
                    grid_y=y
                )
                
                # 根据地形类型设置属性
                if terrain_type == TerrainType.PLAIN:
                    tile_component.movement_cost = 1.0
                    tile_component.defense_bonus = 0.0
                elif terrain_type == TerrainType.HILL:
                    tile_component.movement_cost = 1.5
                    tile_component.defense_bonus = 0.2
                    tile_component.vision_block = 0.3
                elif terrain_type == TerrainType.MOUNTAIN:
                    tile_component.movement_cost = 3.0
                    tile_component.defense_bonus = 0.4
                    tile_component.vision_block = 0.8
                    tile_component.passable = False
                elif terrain_type == TerrainType.FOREST:
                    tile_component.movement_cost = 2.0
                    tile_component.defense_bonus = 0.3
                    tile_component.vision_block = 0.5
                    tile_component.provides_cover = True
                elif terrain_type == TerrainType.WATER:
                    tile_component.movement_cost = float('inf')
                    tile_component.passable = False
                elif terrain_type == TerrainType.DESERT:
                    tile_component.movement_cost = 1.5
                    tile_component.defense_bonus = 0.0
                elif terrain_type == TerrainType.SWAMP:
                    tile_component.movement_cost = 3.0
                    tile_component.defense_bonus = 0.1
                    tile_component.vision_block = 0.2
                elif terrain_type == TerrainType.ROAD:
                    tile_component.movement_cost = 0.5
                    tile_component.defense_bonus = -0.1
                elif terrain_type == TerrainType.CITY:
                    tile_component.movement_cost = 1.0
                    tile_component.defense_bonus = 0.5
                elif terrain_type == TerrainType.PASS:
                    tile_component.movement_cost = 2.0
                    tile_component.defense_bonus = 0.3
                    
                self.component_manager.add_component(tile_entity, tile_component)
                
                # 记录地形块实体ID
                self.map_component.tile_entities[(x, y)] = tile_entity
                
    def update(self, delta_time):
        """更新地图系统"""
        # 处理地图相关的更新逻辑
        # 添加调试渲染
        if hasattr(self, '_debug_render') and self._debug_render:
            self._debug_render_map()
            
    def _debug_render_map(self):
        """调试渲染地图"""
        # 获取主相机
        camera = None
        # 首先尝试使用标签组件查找
        camera_entities = self.context.with_all(CameraComponent, MainCameraTagComponent).result()
        if not camera_entities:
            # 如果没有找到带标签的相机，尝试获取任何相机
            camera_entities = self.context.with_all(CameraComponent).result()
            if not camera_entities:
                return
        
        # 获取相机组件
        camera = self.context.component_manager.get_component(camera_entities[0], CameraComponent)
        
        if not camera:
            return
            
        # 渲染地图中心的一小部分地形块
        center_x = int(camera.x / self.tile_size)
        center_y = int(camera.y / self.tile_size)
        
        # 渲染范围
        render_range = 5
        
        for y in range(center_y - render_range, center_y + render_range):
            for x in range(center_x - render_range, center_x + render_range):
                if not self._is_valid_position(x, y):
                    continue
                    
                # 获取地形类型
                terrain_type = self.map_component.get_terrain_at(x, y)
                if terrain_type is None:
                    continue
                    
                # 计算屏幕坐标
                screen_x = (x * self.tile_size + self.tile_size // 2) - camera.x + self.context.engine.width // 2
                screen_y = (y * self.tile_size + self.tile_size // 2) - camera.y + self.context.engine.height // 2
                
                # 应用缩放
                scaled_size = self.tile_size * camera.zoom
                
                # 创建矩形
                rect = pygame.Rect(
                    screen_x - scaled_size // 2,
                    screen_y - scaled_size // 2,
                    scaled_size,
                    scaled_size
                )
                
                # 获取颜色
                color = self.terrain_colors.get(terrain_type, (150, 150, 150))
                
                # 直接渲染
                pygame.draw.rect(self.context.engine.screen, color, rect)
                
        # 在屏幕中心绘制一个红色标记
        pygame.draw.circle(self.context.engine.screen, (255, 0, 0), 
                      (self.context.engine.width // 2, self.context.engine.height // 2), 5)
        pass
        
    def get_path(self, start_x: int, start_y: int, end_x: int, end_y: int, unit_type: str = "infantry") -> List[Tuple[int, int]]:
        """使用A*算法寻找从起点到终点的路径"""
        # 检查起点和终点是否有效
        if not self._is_valid_position(start_x, start_y) or not self._is_valid_position(end_x, end_y):
            return []
            
        # 检查缓存
        cache_key = ((start_x, start_y), (end_x, end_y))
        if cache_key in self.map_component.pathfinding_cache:
            return self.map_component.pathfinding_cache[cache_key]
            
        # A*算法实现
        open_set = [(0, 0, start_x, start_y)]  # (f, g, x, y)
        closed_set = set()
        came_from = {}
        g_score = {(start_x, start_y): 0}
        f_score = {(start_x, start_y): self._heuristic(start_x, start_y, end_x, end_y)}
        
        while open_set:
            # 获取f值最小的节点
            f, g, x, y = min(open_set)
            open_set.remove((f, g, x, y))
            
            # 如果到达终点
            if (x, y) == (end_x, end_y):
                # 重建路径
                path = self._reconstruct_path(came_from, x, y)
                # 缓存路径
                self.map_component.pathfinding_cache[cache_key] = path
                return path
                
            closed_set.add((x, y))
            
            # 检查相邻节点
            for nx, ny in self._get_neighbors(x, y):
                if (nx, ny) in closed_set:
                    continue
                    
                # 计算移动到相邻节点的成本
                movement_cost = self.map_component.get_movement_cost(nx, ny, unit_type)
                if movement_cost == float('inf'):
                    continue  # 不可通行
                    
                tentative_g = g + movement_cost
                
                # 如果这个节点不在开放集中，或者找到了更好的路径
                if not any(nx == x and ny == y for _, _, x, y in open_set) or tentative_g < g_score.get((nx, ny), float('inf')):
                    came_from[(nx, ny)] = (x, y)
                    g_score[(nx, ny)] = tentative_g
                    f_score[(nx, ny)] = tentative_g + self._heuristic(nx, ny, end_x, end_y)
                    
                    # 更新或添加到开放集
                    if not any(nx == x and ny == y for _, _, x, y in open_set):
                        open_set.append((f_score[(nx, ny)], g_score[(nx, ny)], nx, ny))
        
        # 没有找到路径
        return []
    
    def _is_valid_position(self, x: int, y: int) -> bool:
        """检查位置是否在地图范围内"""
        return 0 <= x < self.map_component.width and 0 <= y < self.map_component.height
    
    def _heuristic(self, x1: int, y1: int, x2: int, y2: int) -> float:
        """启发式函数，使用曼哈顿距离"""
        return abs(x1 - x2) + abs(y1 - y2)
    
    def _get_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        """获取相邻的格子"""
        neighbors = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]:
            nx, ny = x + dx, y + dy
            if self._is_valid_position(nx, ny):
                neighbors.append((nx, ny))
        return neighbors
    
    def _reconstruct_path(self, came_from: Dict[Tuple[int, int], Tuple[int, int]], x: int, y: int) -> List[Tuple[int, int]]:
        """重建路径"""
        path = [(x, y)]
        while (x, y) in came_from:
            x, y = came_from[(x, y)]
            path.append((x, y))
        return path[::-1]  # 反转路径，从起点到终点
    
    def get_visible_tiles(self, x: int, y: int, vision_range: int) -> List[Tuple[int, int]]:
        """获取从指定位置可见的所有格子"""
        # 检查缓存
        cache_key = (x, y)
        if cache_key in self.map_component.vision_cache:
            return self.map_component.vision_cache[cache_key]
            
        visible_tiles = []
        
        # 遍历视野范围内的所有格子
        for dy in range(-vision_range, vision_range + 1):
            for dx in range(-vision_range, vision_range + 1):
                nx, ny = x + dx, y + dy
                
                # 检查是否在地图范围内
                if not self._is_valid_position(nx, ny):
                    continue
                    
                # 计算距离
                distance = (dx**2 + dy**2)**0.5
                if distance > vision_range:
                    continue
                    
                # 使用视线追踪算法检查是否可见
                if self._has_line_of_sight(x, y, nx, ny):
                    visible_tiles.append((nx, ny))
        
        # 缓存结果
        self.map_component.vision_cache[cache_key] = visible_tiles
        return visible_tiles
    
    def _has_line_of_sight(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """检查两点之间是否有视线"""
        # 使用Bresenham算法进行视线追踪
        points = self._get_line(x1, y1, x2, y2)
        
        # 检查路径上的每个点
        for i, (x, y) in enumerate(points):
            # 跳过起点和终点
            if (x, y) == (x1, y1) or (x, y) == (x2, y2):
                continue
                
            # 获取地形块
            terrain_type = self.map_component.get_terrain_at(x, y)
            if terrain_type is None:
                continue
                
            # 获取地形块实体
            tile_entity = self.map_component.get_tile_entity_at(x, y)
            if tile_entity is None:
                continue
                
            # 检查是否有视野阻挡
            tile_component = self.component_manager.get_component(tile_entity, TileComponent)
            if tile_component and tile_component.vision_block > 0.7:  # 视野阻挡阈值
                return False
                
        return True
    
    def _get_line(self, x1: int, y1: int, x2: int, y2: int) -> List[Tuple[int, int]]:
        """使用Bresenham算法获取两点之间的线"""
        points = []
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        
        x, y = x1, y1
        while True:
            points.append((x, y))
            if x == x2 and y == y2:
                break
                
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
                
        return points
    
    def get_terrain_info(self, x: int, y: int) -> Dict[str, Any]:
        """获取指定位置的地形信息"""
        if not self._is_valid_position(x, y):
            return {}
            
        terrain_type = self.map_component.get_terrain_at(x, y)
        elevation = self.map_component.get_elevation_at(x, y)
        tile_entity = self.map_component.get_tile_entity_at(x, y)
        
        if terrain_type is None or tile_entity is None:
            return {}
            
        tile_component = self.component_manager.get_component(tile_entity, TileComponent)
        if not tile_component:
            return {}
            
        return {
            "terrain_type": terrain_type.name,
            "elevation": elevation,
            "movement_cost": tile_component.movement_cost,
            "defense_bonus": tile_component.defense_bonus,
            "vision_block": tile_component.vision_block,
            "passable": tile_component.passable,
            "provides_cover": tile_component.provides_cover
        }
    
    def modify_terrain(self, x: int, y: int, new_terrain_type: TerrainType) -> bool:
        """修改指定位置的地形类型"""
        if not self._is_valid_position(x, y):
            return False
            
        # 更新地形图
        self.map_component.terrain_map[y, x] = new_terrain_type.value
        
        # 获取地形块实体
        tile_entity = self.map_component.get_tile_entity_at(x, y)
        if tile_entity is None:
            return False
            
        # 更新渲染组件
        render_component = self.component_manager.get_component(tile_entity, RenderComponent)
        if render_component:
            render_component.color = self.terrain_colors.get(new_terrain_type, (150, 150, 150))
            
        # 更新地形块组件
        tile_component = self.component_manager.get_component(tile_entity, TileComponent)
        if tile_component:
            tile_component.terrain_type = new_terrain_type
            
            # 根据地形类型设置属性
            if new_terrain_type == TerrainType.PLAIN:
                tile_component.movement_cost = 1.0
                tile_component.defense_bonus = 0.0
                tile_component.vision_block = 0.0
                tile_component.passable = True
            elif new_terrain_type == TerrainType.HILL:
                tile_component.movement_cost = 1.5
                tile_component.defense_bonus = 0.2
                tile_component.vision_block = 0.3
                tile_component.passable = True
            elif new_terrain_type == TerrainType.MOUNTAIN:
                tile_component.movement_cost = 3.0
                tile_component.defense_bonus = 0.4
                tile_component.vision_block = 0.8
                tile_component.passable = False
            elif new_terrain_type == TerrainType.FOREST:
                tile_component.movement_cost = 2.0
                tile_component.defense_bonus = 0.3
                tile_component.vision_block = 0.5
                tile_component.passable = True
                tile_component.provides_cover = True
            elif new_terrain_type == TerrainType.WATER:
                tile_component.movement_cost = float('inf')
                tile_component.defense_bonus = 0.0
                tile_component.vision_block = 0.0
                tile_component.passable = False
            elif new_terrain_type == TerrainType.DESERT:
                tile_component.movement_cost = 1.5
                tile_component.defense_bonus = 0.0
                tile_component.vision_block = 0.1
                tile_component.passable = True
            elif new_terrain_type == TerrainType.SWAMP:
                tile_component.movement_cost = 3.0
                tile_component.defense_bonus = 0.1
                tile_component.vision_block = 0.2
                tile_component.passable = True
            elif new_terrain_type == TerrainType.ROAD:
                tile_component.movement_cost = 0.5
                tile_component.defense_bonus = -0.1
                tile_component.vision_block = 0.0
                tile_component.passable = True
            elif new_terrain_type == TerrainType.CITY:
                tile_component.movement_cost = 1.0
                tile_component.defense_bonus = 0.5
                tile_component.vision_block = 0.2
                tile_component.passable = True
            elif new_terrain_type == TerrainType.PASS:
                tile_component.movement_cost = 2.0
                tile_component.defense_bonus = 0.3
                tile_component.vision_block = 0.4
                tile_component.passable = True
                
        # 清除相关缓存
        self._clear_caches_for_position(x, y)
        
        return True
    
    def _clear_caches_for_position(self, x: int, y: int):
        """清除与指定位置相关的缓存"""
        # 清除寻路缓存
        keys_to_remove = []
        for key in self.map_component.pathfinding_cache:
            start, end = key
            if (x, y) in self.map_component.pathfinding_cache[key] or start == (x, y) or end == (x, y):
                keys_to_remove.append(key)
                
        for key in keys_to_remove:
            del self.map_component.pathfinding_cache[key]
            
        # 清除视野缓存
        vision_keys_to_remove = []
        for key in self.map_component.vision_cache:
            vx, vy = key
            # 如果缓存的视野包含修改的位置，或者视野源在修改位置的视野范围内
            if (x, y) in self.map_component.vision_cache[key] or (abs(vx - x) <= 10 and abs(vy - y) <= 10):
                vision_keys_to_remove.append(key)
                
        for key in vision_keys_to_remove:
            del self.map_component.vision_cache[key]
    
    def save_map(self, filename: str) -> bool:
        """保存地图到文件"""
        try:
            map_data = {
                "width": self.map_component.width,
                "height": self.map_component.height,
                "tile_size": self.map_component.tile_size,
                "name": self.map_component.name,
                "description": self.map_component.description,
                "elevation_map": self.map_component.elevation_map.tolist(),
                "terrain_map": self.map_component.terrain_map.tolist(),
                "moisture_map": self.map_component.moisture_map.tolist()
            }
            
            import json
            with open(filename, 'w') as f:
                json.dump(map_data, f)
                
            return True
        except Exception as e:
            print(f"保存地图失败: {e}")
            return False
    
    def load_map(self, filename: str) -> bool:
        """从文件加载地图"""
        try:
            import json
            with open(filename, 'r') as f:
                map_data = json.load(f)
                
            # 清除现有地图
            self._clear_map()
            
            # 设置新地图属性
            self.map_component.width = map_data["width"]
            self.map_component.height = map_data["height"]
            self.map_component.tile_size = map_data["tile_size"]
            self.map_component.name = map_data["name"]
            self.map_component.description = map_data["description"]
            
            # 转换数据为numpy数组
            self.map_component.elevation_map = np.array(map_data["elevation_map"], dtype=np.int32)
            self.map_component.terrain_map = np.array(map_data["terrain_map"], dtype=np.int32)
            self.map_component.moisture_map = np.array(map_data["moisture_map"], dtype=np.float32)
            
            # 重新创建地形块实体
            self._create_tile_entities()
            
            # 发布地图创建事件
            self.context.event_manager.publish_immediate(
                EventType.MAP_CREATED,
                {"map_entity": self.map_entity, "width": self.map_component.width, "height": self.map_component.height}
            )
            
            return True
        except Exception as e:
            print(f"加载地图失败: {e}")
            return False
    
    def _clear_map(self):
        """清除现有地图"""
        # 删除所有地形块实体
        for tile_entity in self.map_component.tile_entities.values():
            self.entity_manager.destroy_entity(tile_entity)
            
        # 清空地形块实体映射
        self.map_component.tile_entities.clear()
        
        # 清空缓存
        self.map_component.pathfinding_cache.clear()
        self.map_component.vision_cache.clear()
    
    def get_world_position_from_grid(self, grid_x: int, grid_y: int) -> Tuple[float, float]:
        """将网格坐标转换为世界坐标"""
        world_x = grid_x * self.tile_size + self.tile_size // 2
        world_y = grid_y * self.tile_size + self.tile_size // 2
        return world_x, world_y
    
    def get_grid_position_from_world(self, world_x: float, world_y: float) -> Tuple[int, int]:
        """将世界坐标转换为网格坐标"""
        grid_x = int(world_x // self.tile_size)
        grid_y = int(world_y // self.tile_size)
        return grid_x, grid_y
    
    def toggle_grid_display(self):
        """切换网格显示"""
        self.show_grid = not self.show_grid
    
    def toggle_elevation_display(self):
        """切换高程显示"""
        self.show_elevation = not self.show_elevation
        
        # 更新所有地形块的渲染
        if self.show_elevation:
            self._update_tiles_for_elevation_display()
        else:
            self._update_tiles_for_normal_display()
    
    def _update_tiles_for_elevation_display(self):
        """更新地形块以显示高程"""
        for y in range(self.map_component.height):
            for x in range(self.map_component.width):
                tile_entity = self.map_component.get_tile_entity_at(x, y)
                if tile_entity is None:
                    continue
                    
                # 获取高程值
                elevation = self.map_component.get_elevation_at(x, y)
                if elevation is None:
                    continue
                    
                # 根据高程计算颜色
                # 低海拔为蓝色，高海拔为白色
                blue = max(0, min(255, int(255 * (1 - elevation / 100))))
                green = max(0, min(255, int(128 + elevation / 100 * 127)))
                red = max(0, min(255, int(elevation / 100 * 255)))
                
                # 更新渲染组件
                render_component = self.component_manager.get_component(tile_entity, RenderComponent)
                if render_component:
                    render_component.color = (red, green, blue)
    
    def _update_tiles_for_normal_display(self):
        """更新地形块以显示正常地形"""
        for y in range(self.map_component.height):
            for x in range(self.map_component.width):
                tile_entity = self.map_component.get_tile_entity_at(x, y)
                if tile_entity is None:
                    continue
                    
                # 获取地形类型
                terrain_type = self.map_component.get_terrain_at(x, y)
                if terrain_type is None:
                    continue
                    
                # 更新渲染组件
                render_component = self.component_manager.get_component(tile_entity, RenderComponent)
                if render_component:
                    render_component.color = self.terrain_colors.get(terrain_type, (150, 150, 150))