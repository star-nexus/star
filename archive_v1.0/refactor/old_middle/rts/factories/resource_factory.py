import random
from rts.components import ResourceNodeComponent, PositionComponent, SpriteComponent


class ResourceFactory:
    """
    资源工厂：用于在地图上创建资源节点
    """

    def __init__(self, world):
        self.world = world

    def create_resource_node(self, node_type, resource_type, x, y, amount=1000):
        """创建资源节点"""
        node = self.world.create_entity()

        # 添加资源节点组件
        node_comp = ResourceNodeComponent(node_type, resource_type, amount)
        node.add_component(node_comp)

        # 添加位置组件
        node.add_component(PositionComponent(x, y))

        # 添加精灵组件
        sprite_name = self._get_sprite_name(node_type)
        node.add_component(SpriteComponent(sprite_name))

        return node

    def create_gold_mine(self, x, y, amount=1000):
        """创建金矿"""
        return self.create_resource_node(
            ResourceNodeComponent.TYPE_GOLD_MINE, "gold", x, y, amount
        )

    def create_weapon_cache(self, x, y, amount=500):
        """创建武器库"""
        return self.create_resource_node(
            ResourceNodeComponent.TYPE_WEAPON_CACHE, "weapons", x, y, amount
        )

    def create_farm(self, x, y, amount=2000):
        """创建农场"""
        return self.create_resource_node(
            ResourceNodeComponent.TYPE_FARM, "food", x, y, amount
        )

    def create_supply_cache(self, x, y, amount=800):
        """创建补给仓库"""
        return self.create_resource_node(
            ResourceNodeComponent.TYPE_SUPPLY_CACHE, "supplies", x, y, amount
        )

    def create_random_resources(self, map_data, count=10):
        """在地图上随机创建多个资源点"""
        nodes = []

        # 确保资源种类均匀分布
        resource_types = [
            ResourceNodeComponent.TYPE_GOLD_MINE,
            ResourceNodeComponent.TYPE_WEAPON_CACHE,
            ResourceNodeComponent.TYPE_FARM,
            ResourceNodeComponent.TYPE_SUPPLY_CACHE,
        ]

        # 每种资源类型创建几个
        for i in range(count):
            node_type = resource_types[i % len(resource_types)]

            # 随机选择位置
            while True:
                x = random.randint(0, map_data.width - 1)
                y = random.randint(0, map_data.height - 1)

                # 确保位置有效且不在水上
                tile = map_data.get_tile(x, y)
                if tile and tile.passable:
                    break

            # 创建对应类型的资源节点
            if node_type == ResourceNodeComponent.TYPE_GOLD_MINE:
                node = self.create_gold_mine(x * 32, y * 32)  # 假设格子大小为32像素
            elif node_type == ResourceNodeComponent.TYPE_WEAPON_CACHE:
                node = self.create_weapon_cache(x * 32, y * 32)
            elif node_type == ResourceNodeComponent.TYPE_FARM:
                node = self.create_farm(x * 32, y * 32)
            elif node_type == ResourceNodeComponent.TYPE_SUPPLY_CACHE:
                node = self.create_supply_cache(x * 32, y * 32)

            nodes.append(node)

        return nodes

    def _get_sprite_name(self, node_type):
        """获取资源节点对应的精灵名称"""
        sprite_map = {
            ResourceNodeComponent.TYPE_GOLD_MINE: "gold_mine",
            ResourceNodeComponent.TYPE_WEAPON_CACHE: "weapon_cache",
            ResourceNodeComponent.TYPE_FARM: "farm",
            ResourceNodeComponent.TYPE_SUPPLY_CACHE: "supply_cache",
        }
        return sprite_map.get(node_type, "unknown_resource")
