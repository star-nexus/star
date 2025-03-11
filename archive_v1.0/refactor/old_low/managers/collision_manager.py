from typing import List, Tuple, Dict, Set, Optional
import pygame


class CollisionManager:
    """碰撞管理器，负责处理实体间的碰撞检测和响应"""

    def __init__(self, engine):
        """初始化碰撞管理器

        Args:
            engine: 游戏引擎实例
        """
        self.engine = engine
        # 储存碰撞组，用于控制哪些标签之间需要检测碰撞
        self.collision_groups = {}
        # 记录上一帧已发生的碰撞，避免重复触发
        self.active_collisions = set()

    def register_collision_group(self, tag1, tag2, callback=None):
        """注册需要检测碰撞的两个实体标签组

        Args:
            tag1: 第一个实体标签
            tag2: 第二个实体标签
            callback: 碰撞发生时调用的回调函数，如果为None则使用事件系统触发
        """
        group = (tag1, tag2) if tag1 < tag2 else (tag2, tag1)
        self.collision_groups[group] = callback

    def unregister_collision_group(self, tag1, tag2):
        """取消注册碰撞组

        Args:
            tag1: 第一个实体标签
            tag2: 第二个实体标签
        """
        group = (tag1, tag2) if tag1 < tag2 else (tag2, tag1)
        if group in self.collision_groups:
            del self.collision_groups[group]

    def check_entity_collisions(self, entities):
        """检查实体之间的碰撞并处理

        Args:
            entities: 需要检查碰撞的实体列表

        Returns:
            发生碰撞的实体对列表
        """
        # 只处理有碰撞组件且处于活动状态的实体
        entities_with_collision = [
            entity
            for entity in entities
            if entity.is_active() and entity.has_component("collision")
        ]

        # 按标签对实体进行分组，加速碰撞检测
        entities_by_tag = {}
        for entity in entities_with_collision:
            if entity.tag not in entities_by_tag:
                entities_by_tag[entity.tag] = []
            entities_by_tag[entity.tag].append(entity)

        # 存储本次检测到的所有碰撞
        current_collisions = set()
        collision_pairs = []

        # 检查每个注册的碰撞组,注意创建collision_groups的副本以避免迭代过程中字典大小改变
        for (
            tag1,
            tag2,
        ), callback in self.collision_groups.copy().items():
            if tag1 in entities_by_tag and tag2 in entities_by_tag:
                # 检查这两组实体之间的每一对可能的碰撞
                for entity1 in entities_by_tag[tag1]:
                    for entity2 in entities_by_tag[tag2]:
                        # 确保不是同一个实体
                        if entity1 == entity2:
                            continue

                        # 获取碰撞组件并检测碰撞
                        collision1 = entity1.get_component("collision")
                        collision2 = entity2.get_component("collision")

                        if collision1.is_colliding(collision2):
                            # 生成唯一的碰撞ID
                            collision_id = self._get_collision_id(entity1, entity2)
                            current_collisions.add(collision_id)

                            # 如果是新碰撞，触发回调或事件
                            is_new_collision = (
                                collision_id not in self.active_collisions
                            )

                            if is_new_collision:
                                collision_pairs.append((entity1, entity2))
                                # 如果有注册回调则调用，否则触发事件
                                if callback:
                                    callback(entity1, entity2)
                                else:
                                    self.engine.event_manager.dispatch(
                                        "collision", entity1, entity2
                                    )

        # 更新活动碰撞列表
        self.active_collisions = current_collisions

        return collision_pairs

    def check_map_collision(self, entity, tilemap):
        """检查实体与地图的碰撞

        Args:
            entity: 需要检查的实体
            tilemap: 地图对象

        Returns:
            碰撞信息字典，包含与哪些不可通行瓦片发生碰撞
        """
        if not entity.has_component("collision") or not entity.is_active():
            return None

        collision = entity.get_component("collision")

        # 获取实体碰撞盒的四个角坐标
        left = entity.x
        right = entity.x + collision.width
        top = entity.y
        bottom = entity.y + collision.height

        # 计算四个角所在的瓦片坐标
        tile_size = tilemap.tile_size
        tile_top_left = (int(left // tile_size), int(top // tile_size))
        tile_top_right = (int(right // tile_size), int(top // tile_size))
        tile_bottom_left = (int(left // tile_size), int(bottom // tile_size))
        tile_bottom_right = (int(right // tile_size), int(bottom // tile_size))

        # 检查这四个角是否在可通行的瓦片上
        corners = [tile_top_left, tile_top_right, tile_bottom_left, tile_bottom_right]
        collisions = []

        for i, (tile_x, tile_y) in enumerate(corners):
            if not tilemap.is_passable(tile_x, tile_y):
                collisions.append(
                    {
                        "corner": i,  # 0:左上, 1:右上, 2:左下, 3:右下
                        "tile": (tile_x, tile_y),
                        "position": corners[i],
                    }
                )

        return collisions if collisions else None

    def _get_collision_id(self, entity1, entity2):
        """生成两个实体间碰撞的唯一ID

        Args:
            entity1: 第一个实体
            entity2: 第二个实体

        Returns:
            唯一标识碰撞的字符串
        """
        # 确保ID的顺序一致性
        id1 = id(entity1)
        id2 = id(entity2)
        if id1 < id2:
            return f"{id1}_{id2}"
        else:
            return f"{id2}_{id1}"
