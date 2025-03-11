import pygame
import random
from rts.components import (
    UnitComponent,
    PositionComponent,
    MovementComponent,
    AttackComponent,
    DefenseComponent,
    FactionComponent,
    SpriteComponent,
)


class UnitFactory:
    """
    单位工厂：负责创建各种类型的单位
    管理单位的创建流程，配置不同类型单位的特性和属性，并生成临时贴图用于渲染
    """

    def __init__(self, world, game=None):
        """
        初始化单位工厂

        参数:
            world: 游戏世界实例，用于创建实体
            game: 游戏引擎实例，用于访问资源系统
        """
        self.world = world
        self.game = game  # 存储游戏实例的引用

        # 单位贴图名称映射：将单位类型映射到对应的贴图资源名称
        self.unit_sprites = {
            UnitComponent.TYPE_SUPPLY: "supply_unit",  # 辎重单位
            UnitComponent.TYPE_PLAINS: "plains_unit",  # 平原单位
            UnitComponent.TYPE_MOUNTAIN: "mountain_unit",  # 山地单位
            UnitComponent.TYPE_WATER: "water_unit",  # 水面单位
            UnitComponent.TYPE_RANGED: "ranged_unit",  # 远程单位
            UnitComponent.TYPE_AIR: "air_unit",  # 空中单位
        }

        # 单位默认颜色映射：为不同类型的单位定义特征颜色
        self.unit_colors = {
            UnitComponent.TYPE_SUPPLY: (220, 220, 150),  # 辎重单位：浅黄色
            UnitComponent.TYPE_PLAINS: (50, 200, 50),  # 平原单位：绿色
            UnitComponent.TYPE_MOUNTAIN: (100, 100, 150),  # 山地单位：灰蓝色
            UnitComponent.TYPE_WATER: (100, 150, 255),  # 水面单位：蓝色
            UnitComponent.TYPE_RANGED: (200, 100, 50),  # 远程单位：橙色
            UnitComponent.TYPE_AIR: (200, 200, 250),  # 空中单位：浅蓝色
        }

        # 本地纹理字典，作为资源系统的备用，存储创建的临时贴图
        self.local_textures = {}

    def create_unit(self, unit_type, faction_id, x, y, name=""):
        """
        创建一个基本单位，这是所有特定单位类型创建的基础方法

        参数:
            unit_type: 单位类型，定义了单位的基本特性
            faction_id: 所属阵营ID，决定单位的归属和颜色
            x, y: 初始位置坐标
            name: 单位名称，如果未提供则基于类型自动生成

        返回:
            Entity: 创建的单位实体
        """
        # 创建单位实体
        unit = self.world.create_entity()

        # 添加位置组件，定义单位在游戏世界中的位置
        unit.add_component(PositionComponent(x, y))

        # 添加单位组件，设置单位类型和名称
        unit_name = name if name else f"{unit_type.capitalize()} Unit"
        unit_comp = UnitComponent(unit_type, unit_name)
        unit.add_component(unit_comp)

        # 设置单位属性（根据类型），添加基本组件
        self._configure_unit_attributes(unit, unit_type)

        # 添加阵营组件，标识单位所属的势力
        faction_comp = FactionComponent(faction_id)
        unit.add_component(faction_comp)

        # 添加图像组件，用于渲染单位
        sprite_name = self.unit_sprites.get(unit_type, "default_unit")
        unit.add_component(SpriteComponent(sprite_name))
        print(f"Created unit with sprite: {sprite_name}")  # Debug print

        # 创建临时可视化（在没有实际纹理的情况下）
        self._create_temp_unit_texture(unit, unit_type, faction_id)

        return unit

    def create_supply_unit(self, faction_id, x, y):
        """
        创建辎重单位 - 用于运输和资源收集

        特性：高资源携带量，低战斗力，低速度

        参数:
            faction_id: 所属阵营ID
            x, y: 初始位置坐标

        返回:
            Entity: 创建的辎重单位
        """
        unit = self.create_unit(UnitComponent.TYPE_SUPPLY, faction_id, x, y, "辎重兵")

        # 调整单位特性：高资源携带量，低战斗力，低速度
        unit_comp = unit.get_component(UnitComponent)
        unit_comp.speed = 80  # 较低的基础速度

        movement = unit.get_component(MovementComponent)
        movement.current_speed = 80  # 设置当前移动速度

        attack = unit.get_component(AttackComponent)
        attack.damage = 5  # 较低的攻击力

        defense = unit.get_component(DefenseComponent)
        defense.max_health = 80  # 中等生命值
        defense.health = 80

        return unit

    def create_plains_unit(self, faction_id, x, y):
        """
        创建平原单位 - 基础战斗单位，适合在平原地形作战

        特性：标准属性，在平原上速度加快

        参数:
            faction_id: 所属阵营ID
            x, y: 初始位置坐标

        返回:
            Entity: 创建的平原单位
        """
        unit = self.create_unit(UnitComponent.TYPE_PLAINS, faction_id, x, y, "平原兵")

        # 平原单位特性：在平原地形上移动速度加快
        movement = unit.get_component(MovementComponent)
        movement.speed["plains"] = 150  # 平原上速度快于普通

        return unit

    def create_mountain_unit(self, faction_id, x, y):
        """
        创建山地单位 - 适合在山地地形作战的专业单位

        特性：攻击力高，在山地上速度快，可以穿越山地

        参数:
            faction_id: 所属阵营ID
            x, y: 初始位置坐标

        返回:
            Entity: 创建的山地单位
        """
        unit = self.create_unit(UnitComponent.TYPE_MOUNTAIN, faction_id, x, y, "山地兵")

        # 山地单位特性：攻击力高，在山地上速度快
        unit_comp = unit.get_component(UnitComponent)
        unit_comp.attack = 15  # 较高的攻击力

        attack = unit.get_component(AttackComponent)
        attack.damage = 15  # 较高的攻击伤害

        movement = unit.get_component(MovementComponent)
        movement.speed["mountain"] = 120  # 山地上速度快
        movement.can_traverse_mountain = True  # 可以穿越山地地形

        return unit

    def create_water_unit(self, faction_id, x, y):
        """
        创建水面单位 - 海军单位，适合在水域作战

        特性：可以在水上移动，水上速度快

        参数:
            faction_id: 所属阵营ID
            x, y: 初始位置坐标

        返回:
            Entity: 创建的水面单位
        """
        unit = self.create_unit(UnitComponent.TYPE_WATER, faction_id, x, y, "水兵")

        # 水面单位特性：可以在水上移动，水上速度快
        movement = unit.get_component(MovementComponent)
        movement.speed["water"] = 130  # 水面上速度快
        movement.can_traverse_water = True  # 可以穿越水面

        return unit

    def create_ranged_unit(self, faction_id, x, y):
        """
        创建远程单位 - 可以进行远距离攻击的单位

        特性：攻击范围远，但防御低，速度慢

        参数:
            faction_id: 所属阵营ID
            x, y: 初始位置坐标

        返回:
            Entity: 创建的远程单位
        """
        unit = self.create_unit(UnitComponent.TYPE_RANGED, faction_id, x, y, "弓箭手")

        # 远程单位特性：攻击范围远，但防御低，速度慢
        unit_comp = unit.get_component(UnitComponent)
        unit_comp.attack_range = 4  # 较远的攻击范围
        unit_comp.speed = 80  # 较低的速度

        attack = unit.get_component(AttackComponent)
        attack.range = 4  # 攻击范围
        attack.damage = 12  # 中等偏高的攻击力
        attack.attack_type = AttackComponent.TYPE_RANGED  # 设置为远程攻击类型

        defense = unit.get_component(DefenseComponent)
        defense.max_health = 70  # 较低的生命值
        defense.health = 70

        movement = unit.get_component(MovementComponent)
        movement.current_speed = 80  # 较低的移动速度

        return unit

    def create_air_unit(self, faction_id, x, y):
        """
        创建空中单位 - 可以飞行的单位，无视地形阻碍

        特性：可以飞行(忽略地形)，速度快，但相对脆弱

        参数:
            faction_id: 所属阵营ID
            x, y: 初始位置坐标

        返回:
            Entity: 创建的空中单位
        """
        unit = self.create_unit(UnitComponent.TYPE_AIR, faction_id, x, y, "飞行兵")

        # 空中单位特性：可以飞行(忽略地形)，速度快，但相对脆弱
        unit_comp = unit.get_component(UnitComponent)
        unit_comp.speed = 150  # 较高的基础速度

        movement = unit.get_component(MovementComponent)
        movement.is_flying = True  # 标记为飞行单位
        movement.current_speed = 150  # 较高的移动速度

        # 飞行单位忽略地形惩罚，在所有地形上速度一致
        for terrain in movement.speed:
            movement.speed[terrain] = 150

        defense = unit.get_component(DefenseComponent)
        defense.max_health = 60  # 较低的生命值，体现脆弱性
        defense.health = 60

        return unit

    def _configure_unit_attributes(self, unit, unit_type):
        """
        配置单位基础属性，添加所有单位共有的基础组件

        参数:
            unit: 要配置的单位实体
            unit_type: 单位类型
        """
        # 添加移动组件，控制单位的移动能力和速度
        movement = MovementComponent()
        unit.add_component(movement)

        # 添加攻击组件，定义单位的攻击能力
        attack = AttackComponent()
        unit.add_component(attack)

        # 添加防御组件，定义单位的生命值和防御能力
        defense = DefenseComponent()
        unit.add_component(defense)

    def _create_temp_unit_texture(self, unit, unit_type, faction_id):
        """
        创建临时单位贴图（用于开发阶段，后续替换为真实资源）
        为单位生成一个简单的图形表示，用于在缺少专业美术资源时进行测试

        参数:
            unit: 单位实体
            unit_type: 单位类型
            faction_id: 阵营ID，用于确定单位的颜色标识
        """
        # 获取精灵组件
        sprite_comp = unit.get_component(SpriteComponent)
        if not sprite_comp:
            return

        # 创建临时贴图，大小为32x32像素（增大尺寸，使单位更容易看到）
        texture = pygame.Surface((32, 32), pygame.SRCALPHA)  # 使用SRCALPHA支持透明度
        texture.fill((0, 0, 0, 0))  # 填充透明背景

        base_color = self.unit_colors.get(
            unit_type, (200, 200, 200)
        )  # 获取单位基础颜色

        # 查找阵营颜色
        faction_color = (255, 255, 255)  # 默认白色
        for entity in self.world.entities.values():
            if entity.has_component(FactionComponent):
                faction_comp = entity.get_component(FactionComponent)
                if faction_comp.faction_id == faction_id:
                    faction_color = faction_comp.faction_color
                    break

        # 在中央区域绘制单位的主体颜色
        pygame.draw.rect(texture, base_color, (4, 4, 24, 24))

        # 添加阵营标识（边框，更清晰地表示单位所属阵营）
        pygame.draw.rect(texture, faction_color, (4, 4, 24, 24), 2)

        # 根据单位类型添加不同的标识图案，以便区分不同类型的单位
        if unit_type == UnitComponent.TYPE_SUPPLY:
            # 辎重单位：箱子图案
            pygame.draw.rect(texture, (150, 100, 50), (10, 10, 12, 12), 2)
        elif unit_type == UnitComponent.TYPE_RANGED:
            # 远程单位：X形箭头图案
            pygame.draw.line(texture, (50, 50, 50), (10, 10), (22, 22), 2)
            pygame.draw.line(texture, (50, 50, 50), (22, 10), (10, 22), 2)
        elif unit_type == UnitComponent.TYPE_AIR:
            # 空中单位：翅膀图案
            pygame.draw.line(texture, (220, 220, 220), (8, 16), (24, 10), 2)
            pygame.draw.line(texture, (220, 220, 220), (8, 16), (24, 22), 2)
        elif unit_type == UnitComponent.TYPE_MOUNTAIN:
            # 山地单位：三角形图案（山形）
            pygame.draw.polygon(texture, (80, 80, 100), [(16, 8), (8, 24), (24, 24)], 2)
        elif unit_type == UnitComponent.TYPE_WATER:
            # 水面单位：波浪图案
            pygame.draw.arc(texture, (80, 130, 200), (8, 12, 16, 8), 0, 3.14, 2)
            pygame.draw.arc(texture, (80, 130, 200), (8, 18, 16, 8), 3.14, 6.28, 2)
        elif unit_type == UnitComponent.TYPE_PLAINS:
            # 平原单位：圆形图案
            pygame.draw.circle(texture, (40, 180, 40), (16, 16), 8, 2)

        # 更新SpriteComponent的尺寸以匹配贴图大小
        sprite_comp.width = texture.get_width()
        sprite_comp.height = texture.get_height()

        # 生成贴图资源名称 - 确保使用正确的命名格式
        # 使用unit_type作为图像名称的基础，而不是sprite_comp.image_name
        sprite_name = f"{unit_type}_{faction_id}"

        # 确保直接更新sprite_comp的image_name为我们即将存储的贴图名称
        sprite_comp.image_name = sprite_name

        # 尝试使用游戏资源系统
        try:
            if self.game and hasattr(self.game, "resources"):
                # 确保 resources 有 images 属性
                if not hasattr(self.game.resources, "images"):
                    self.game.resources.images = {}

                # 添加贴图到游戏资源系统
                self.game.resources.images[sprite_name] = texture
                print(f"Added texture '{sprite_name}' to game resources")
            else:
                # 没有游戏资源系统，使用本地纹理
                self.local_textures[sprite_name] = texture
                print(f"Added texture '{sprite_name}' to local textures")
        except Exception as e:
            print(f"Error adding texture: {e}")
            # 出错时，确保至少在本地纹理中有一个引用
            self.local_textures[sprite_name] = texture

        # 直接设置纹理到精灵组件，确保渲染系统能找到它
        sprite_comp.texture = texture
