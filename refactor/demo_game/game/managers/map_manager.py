import json
import random
import os
from typing import List, Tuple, Dict, Any, Optional
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message
from game.components import MapTile, Terrain, TerrainType, MapPosition, Sprite


class MapManager:
    """
    地图管理器，负责地图的生成、编辑和存储

    功能:
    1. 地图生成 - 随机生成地图或从模板生成
    2. 地图管理 - 修改地图格子、查询地图信息
    3. 地图编辑 - 提供编辑地图的功能
    4. 地图存储 - 保存/加载地图数据
    """

    def __init__(self, world: World, event_manager: EventManager):
        """
        初始化地图管理器

        Args:
            world: ECS世界实例
            event_manager: 事件管理器实例
        """
        self.world = world
        self.event_manager = event_manager
        self.map_width = 0
        self.map_height = 0
        self.tile_size = 32  # 格子大小
        self.map_entities = []  # 存储地图格子实体的ID
        self.current_map_name = ""

        # 地图默认设置
        self.default_terrain_distribution = {
            TerrainType.PLAIN: 0.6,  # 60%是平原
            TerrainType.MOUNTAIN: 0.1,  # 10%是山地
            TerrainType.RIVER: 0.1,  # 10%是河流
            TerrainType.FOREST: 0.15,  # 15%是森林
            TerrainType.LAKE: 0.05,  # 5%是湖泊
        }

        # 注册事件
        self.event_manager.subscribe("map_edit", self._handle_map_edit)

    def generate_random_map(
        self, width: int, height: int, seed: Optional[int] = None
    ) -> None:
        """
        生成随机地图

        Args:
            width: 地图宽度（格子数）
            height: 地图高度（格子数）
            seed: 随机种子，用于生成可重复的随机地图
        """
        # 如果提供了种子，设置随机种子
        if seed is not None:
            random.seed(seed)

        self.clear_map()
        self.map_width = width
        self.map_height = height

        # 使用地形分布生成地图
        terrain_types = list(TerrainType)
        weights = [self.default_terrain_distribution.get(t, 0) for t in terrain_types]

        for x in range(width):
            for y in range(height):
                # 创建地图格子实体
                tile_entity = self.world.create_entity()

                # 随机选择地形类型
                terrain_type = random.choices(terrain_types, weights=weights, k=1)[0]

                # 添加组件
                self.world.add_component(tile_entity, MapTile(x=x, y=y))
                self.world.add_component(tile_entity, Terrain(type=terrain_type))

                # 将实体ID添加到地图实体列表
                self.map_entities.append(tile_entity)

        # 发布地图生成事件
        self.event_manager.publish(
            "map_generated",
            Message(
                topic="map_generated",
                data_type="map_event",
                data={"width": width, "height": height},
            ),
        )
        print(f"随机生成了 {width}x{height} 的地图")

    def generate_template_map(self, template: List[List[TerrainType]]) -> None:
        """
        从模板生成地图

        Args:
            template: 二维数组，每个元素是TerrainType枚举值
        """
        if not template or not template[0]:
            print("错误：模板为空")
            return

        height = len(template)
        width = len(template[0])

        self.clear_map()
        self.map_width = width
        self.map_height = height

        for y in range(height):
            for x in range(width):
                # 检查坐标是否在模板范围内
                if y < len(template) and x < len(template[y]):
                    terrain_type = template[y][x]
                else:
                    terrain_type = TerrainType.PLAIN  # 默认为平原

                # 创建地图格子实体
                tile_entity = self.world.create_entity()

                # 添加组件
                self.world.add_component(tile_entity, MapTile(x=x, y=y))
                self.world.add_component(tile_entity, Terrain(type=terrain_type))

                # 将实体ID添加到地图实体列表
                self.map_entities.append(tile_entity)

        # 发布地图生成事件
        self.event_manager.publish(
            "map_generated",
            Message(
                topic="map_generated",
                data_type="map_event",
                data={"width": width, "height": height},
            ),
        )
        print(f"从模板生成了 {width}x{height} 的地图")

    def clear_map(self) -> None:
        """清除当前地图"""
        # 删除所有地图格子实体
        for entity_id in self.map_entities:
            self.world.remove_entity(entity_id)

        # 清空地图实体列表
        self.map_entities.clear()
        self.map_width = 0
        self.map_height = 0

        print("地图已清除")

    def get_tile_at(
        self, x: int, y: int
    ) -> Tuple[int, Optional[MapTile], Optional[Terrain]]:
        """
        获取指定坐标的地图格子

        Args:
            x: X坐标
            y: Y坐标

        Returns:
            元组：(实体ID, MapTile组件, Terrain组件)，如果不存在则返回(0, None, None)
        """
        # 检查坐标是否在地图范围内
        if not (0 <= x < self.map_width and 0 <= y < self.map_height):
            return 0, None, None

        # 查找指定坐标的格子
        entities = self.world.get_entities_with_components(MapTile)
        for entity in entities:
            tile = self.world.get_component(entity, MapTile)
            if tile.x == x and tile.y == y:
                terrain = self.world.get_component(entity, Terrain)
                return entity, tile, terrain

        return 0, None, None

    def set_terrain_at(self, x: int, y: int, terrain_type: TerrainType) -> bool:
        """
        设置指定坐标的地形类型

        Args:
            x: X坐标
            y: Y坐标
            terrain_type: 地形类型

        Returns:
            是否设置成功
        """
        entity, _, _ = self.get_tile_at(x, y)
        if entity == 0:
            return False

        # 更改地形类型
        terrain = self.world.get_component(entity, Terrain)
        if terrain:
            terrain.type = terrain_type
            # 更新地形属性
            terrain.__post_init__()
            return True

        return False

    def save_map(self, filename: str) -> bool:
        """
        保存地图到文件

        Args:
            filename: 文件名

        Returns:
            是否保存成功
        """
        if not self.map_entities:
            print("错误：没有地图可保存")
            return False

        try:
            # 创建地图数据
            map_data = {"width": self.map_width, "height": self.map_height, "tiles": []}

            # 收集所有格子数据
            for entity in self.map_entities:
                if self.world.entity_exists(entity):
                    tile = self.world.get_component(entity, MapTile)
                    terrain = self.world.get_component(entity, Terrain)

                    if tile and terrain:
                        # 将枚举值转换为字符串
                        terrain_str = terrain.type.name

                        tile_data = {
                            "x": tile.x,
                            "y": tile.y,
                            "terrain": terrain_str,
                            "height": tile.height,
                            "properties": tile.properties,
                        }
                        map_data["tiles"].append(tile_data)

            # 确保目录存在
            os.makedirs(os.path.dirname(filename), exist_ok=True)

            # 写入文件
            with open(filename, "w", encoding="utf-8") as file:
                json.dump(map_data, file, indent=2)

            self.current_map_name = os.path.basename(filename)
            print(f"地图已保存到：{filename}")
            return True

        except Exception as e:
            print(f"保存地图时出错：{e}")
            return False

    def load_map(self, filename: str) -> bool:
        """
        从文件加载地图

        Args:
            filename: 文件名

        Returns:
            是否加载成功
        """
        try:
            # 读取文件
            with open(filename, "r", encoding="utf-8") as file:
                map_data = json.load(file)

            # 清除当前地图
            self.clear_map()

            # 设置地图尺寸
            self.map_width = map_data.get("width", 0)
            self.map_height = map_data.get("height", 0)

            # 创建所有格子
            for tile_data in map_data.get("tiles", []):
                x = tile_data.get("x", 0)
                y = tile_data.get("y", 0)
                terrain_str = tile_data.get("terrain", "PLAIN")
                height = tile_data.get("height", 0.0)
                properties = tile_data.get("properties", {})

                # 将字符串转换为枚举值
                try:
                    terrain_type = TerrainType[terrain_str]
                except (KeyError, ValueError):
                    terrain_type = TerrainType.PLAIN

                # 创建格子实体
                tile_entity = self.world.create_entity()
                self.world.add_component(
                    tile_entity, MapTile(x=x, y=y, height=height, properties=properties)
                )
                self.world.add_component(tile_entity, Terrain(type=terrain_type))

                # 将实体ID添加到地图实体列表
                self.map_entities.append(tile_entity)

            self.current_map_name = os.path.basename(filename)

            # 发布地图加载事件
            self.event_manager.publish(
                "map_loaded",
                Message(
                    topic="map_loaded",
                    data_type="map_event",
                    data={
                        "width": self.map_width,
                        "height": self.map_height,
                        "filename": filename,
                    },
                ),
            )

            print(f"从{filename}加载了{self.map_width}x{self.map_height}的地图")
            return True

        except Exception as e:
            print(f"加载地图时出错：{e}")
            return False

    def _handle_map_edit(self, message):
        """处理地图编辑事件"""
        # 从Message对象的data属性中获取数据
        event_data = message.data if hasattr(message, "data") else message
        action = event_data.get("action")

        if action == "set_terrain":
            x = event_data.get("x", 0)
            y = event_data.get("y", 0)
            terrain_str = event_data.get("terrain", "PLAIN")

            try:
                terrain_type = TerrainType[terrain_str]
            except (KeyError, ValueError):
                terrain_type = TerrainType.PLAIN

            self.set_terrain_at(x, y, terrain_type)

        elif action == "clear_map":
            self.clear_map()

        elif action == "generate_random":
            width = event_data.get("width", 20)
            height = event_data.get("height", 15)
            seed = event_data.get("seed")
            self.generate_random_map(width, height, seed)

    def get_map_size(self) -> Tuple[int, int]:
        """获取当前地图尺寸"""
        return self.map_width, self.map_height

    def is_map_loaded(self) -> bool:
        """检查地图是否已加载"""
        return len(self.map_entities) > 0

    def get_screen_pos_from_grid(self, grid_x: int, grid_y: int) -> Tuple[int, int]:
        """
        将网格坐标转换为屏幕坐标

        Args:
            grid_x: 网格X坐标
            grid_y: 网格Y坐标

        Returns:
            屏幕坐标 (x, y)
        """
        return grid_x * self.tile_size, grid_y * self.tile_size

    def get_grid_pos_from_screen(self, screen_x: int, screen_y: int) -> Tuple[int, int]:
        """
        将屏幕坐标转换为网格坐标

        Args:
            screen_x: 屏幕X坐标
            screen_y: 屏幕Y坐标

        Returns:
            网格坐标 (x, y)
        """
        return screen_x // self.tile_size, screen_y // self.tile_size

    def cleanup(self):
        """清理资源"""
        # 取消事件订阅
        self.event_manager.unsubscribe("map_edit", self._handle_map_edit)
        # 清理地图
        self.clear_map()
