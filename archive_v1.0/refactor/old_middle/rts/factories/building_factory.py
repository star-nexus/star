import pygame
import random
from rts.components import (
    BuildingComponent,
    PositionComponent,
    FactionComponent,
    SpriteComponent,
    DefenseComponent,
    ResourceComponent,
)


class BuildingFactory:
    """
    建筑工厂：负责创建各种类型的建筑
    """

    def __init__(self, world, game=None):
        self.world = world
        self.game = game  # 存储游戏实例的引用
        # 建筑贴图名称映射
        self.building_sprites = {
            BuildingComponent.TYPE_HEADQUARTERS: "headquarters",
            BuildingComponent.TYPE_SUPPLY_DEPOT: "supply_depot",
            BuildingComponent.TYPE_FORTIFICATION: "fortification",
        }

        # 建筑默认颜色映射
        self.building_colors = {
            BuildingComponent.TYPE_HEADQUARTERS: (200, 200, 50),  # 金色
            BuildingComponent.TYPE_SUPPLY_DEPOT: (50, 150, 50),  # 绿色
            BuildingComponent.TYPE_FORTIFICATION: (120, 120, 120),  # 灰色
        }

        # 建筑尺寸（格子数）
        self.building_sizes = {
            BuildingComponent.TYPE_HEADQUARTERS: (3, 3),  # 3x3格子
            BuildingComponent.TYPE_SUPPLY_DEPOT: (2, 2),  # 2x2格子
            BuildingComponent.TYPE_FORTIFICATION: (2, 1),  # 2x1格子
        }

    def create_building(
        self, building_type, faction_id, x, y, name="", is_completed=True
    ):
        """
        创建一个基本建筑
        :param building_type: 建筑类型
        :param faction_id: 所属阵营ID
        :param x, y: 初始位置
        :param name: 建筑名称
        :param is_completed: 是否已建造完成
        :return: 创建的建筑实体
        """
        # 创建建筑实体
        building = self.world.create_entity()

        # 添加位置组件
        building.add_component(PositionComponent(x, y))

        # 添加建筑组件
        building_name = name if name else f"{building_type.capitalize()} Building"
        building_comp = BuildingComponent(building_type, building_name)
        building_comp.is_completed = is_completed

        if not is_completed:
            building_comp.construction_progress = 0

            # 设置不同类型建筑的建造时间
            if building_type == BuildingComponent.TYPE_HEADQUARTERS:
                building_comp.construction_time = 30  # 30秒
            elif building_type == BuildingComponent.TYPE_SUPPLY_DEPOT:
                building_comp.construction_time = 15  # 15秒
            elif building_type == BuildingComponent.TYPE_FORTIFICATION:
                building_comp.construction_time = 10  # 10秒

        building.add_component(building_comp)

        # 添加阵营组件
        faction_comp = FactionComponent(faction_id)
        building.add_component(faction_comp)

        # 添加防御组件
        defense = DefenseComponent()
        if building_type == BuildingComponent.TYPE_HEADQUARTERS:
            defense.max_health = 500
            defense.health = 500
            defense.armor = 15
        elif building_type == BuildingComponent.TYPE_SUPPLY_DEPOT:
            defense.max_health = 300
            defense.health = 300
            defense.armor = 8
        elif building_type == BuildingComponent.TYPE_FORTIFICATION:
            defense.max_health = 400
            defense.health = 400
            defense.armor = 20
        building.add_component(defense)

        # 添加图像组件
        sprite_name = self.building_sprites.get(building_type, "default_building")
        sprite = SpriteComponent(sprite_name)

        # 设置精灵尺寸
        size = self.building_sizes.get(building_type, (1, 1))
        tile_size = 32  # 假设一格是32像素
        sprite.width = size[0] * tile_size
        sprite.height = size[1] * tile_size

        building.add_component(sprite)

        # 创建临时可视化
        self._create_temp_building_texture(
            building, building_type, faction_id, is_completed
        )

        return building

    def create_headquarters(self, faction_id, x, y, is_completed=True):
        """创建主基地"""
        hq = self.create_building(
            BuildingComponent.TYPE_HEADQUARTERS,
            faction_id,
            x,
            y,
            "主基地",
            is_completed,
        )

        # 设置资源产出
        if is_completed:
            building_comp = hq.get_component(BuildingComponent)
            building_comp.resource_generation = {
                "gold": 5.0,
                "weapons": 1.0,
                "food": 2.0,
                "supplies": 1.0,
            }

        return hq

    def create_supply_depot(self, faction_id, x, y, is_completed=True):
        """创建补给站"""
        depot = self.create_building(
            BuildingComponent.TYPE_SUPPLY_DEPOT,
            faction_id,
            x,
            y,
            "补给站",
            is_completed,
        )

        # 设置资源产出和存储
        if is_completed:
            building_comp = depot.get_component(BuildingComponent)
            building_comp.resource_generation = {"food": 5.0}
            building_comp.resource_storage = {"food": 0, "supplies": 0}
            building_comp.max_resource_storage = {"food": 500, "supplies": 300}

        return depot

    def create_fortification(self, faction_id, x, y, is_completed=True):
        """创建防御工事"""
        fort = self.create_building(
            BuildingComponent.TYPE_FORTIFICATION,
            faction_id,
            x,
            y,
            "防御工事",
            is_completed,
        )

        # 防御工事提供额外防御力
        defense = fort.get_component(DefenseComponent)
        defense.resistance["melee"] = 0.2  # 20%近战伤害减免
        defense.resistance["ranged"] = 0.3  # 30%远程伤害减免

        return fort

    def _create_temp_building_texture(
        self, building, building_type, faction_id, is_completed
    ):
        """
        创建临时建筑贴图（用于开发阶段，后续替换为真实资源）
        """
        sprite_comp = building.get_component(SpriteComponent)
        if not sprite_comp:
            return

        # 获取建筑尺寸
        size = self.building_sizes.get(building_type, (1, 1))
        width = size[0] * 32
        height = size[1] * 32

        # 创建临时贴图
        texture = pygame.Surface((width, height))
        base_color = self.building_colors.get(building_type, (150, 150, 150))

        # 如果建筑未完成，颜色更淡
        if not is_completed:
            base_color = tuple(min(c + 50, 255) for c in base_color)

        # 查找阵营颜色
        faction_color = (255, 255, 255)  # 默认白色
        for entity in self.world.entities.values():
            if entity.has_component(FactionComponent):
                faction_comp = entity.get_component(FactionComponent)
                if faction_comp.faction_id == faction_id:
                    faction_color = faction_comp.faction_color
                    break

        # 填充建筑颜色
        texture.fill(base_color)

        # 添加阵营标识
        pygame.draw.rect(texture, faction_color, (0, 0, 16, 16))

        # 添加建筑类型特征
        if building_type == BuildingComponent.TYPE_HEADQUARTERS:
            # 主基地：大型建筑，塔楼轮廓
            pygame.draw.polygon(
                texture,
                (50, 50, 50),
                [
                    (width // 2, 10),
                    (width - 10, height // 2),
                    (width // 2, height - 10),
                    (10, height // 2),
                ],
            )
        elif building_type == BuildingComponent.TYPE_SUPPLY_DEPOT:
            # 补给站：仓库图案
            pygame.draw.rect(texture, (100, 70, 0), (8, 8, width - 16, height - 16), 2)
        elif building_type == BuildingComponent.TYPE_FORTIFICATION:
            # 防御工事：堡垒图案
            for i in range(3):
                pygame.draw.rect(
                    texture, (90, 90, 90), (width // 4, 5 + i * 10, width // 2, 5), 0
                )

        # 如果建筑未完成，添加建造中标识
        if not is_completed:
            for i in range(width):
                if i % 8 < 4:
                    pygame.draw.line(texture, (80, 80, 80), (i, 0), (i, height), 1)

        # 保存到资源字典
        sprite_name = f"{building_type}_{faction_id}"
        if not is_completed:
            sprite_name += "_construction"

        # 使用self.game而不是self.world.game
        if self.game and hasattr(self.game, "resources"):
            self.game.resources.images[sprite_name] = texture
        else:
            print(f"警告：无法访问游戏资源，纹理 {sprite_name} 未加载")

        sprite_comp.image_name = sprite_name  # 更新精灵引用
