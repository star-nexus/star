import uuid

class UnitManager:
    def __init__(self, engine):
        self.engine = engine
        self.units = {}  # 单位ID -> 单位实体
        self.unit_components = {}  # 单位ID -> 组件字典
        
    def create_unit(self, unit_type, faction_id, x, y):
        """创建新单位"""
        unit_id = str(uuid.uuid4())
        
        # 创建单位组件
        from rotk_v2.components.transform import Transform
        from rotk_v2.components.unit_stats import UnitStats
        from rotk_v2.components.ai import AI
        
        # 根据单位类型设置属性
        if unit_type == "infantry":
            # 步兵
            stats = UnitStats(
                unit_type="infantry",
                max_health=100,
                attack=10,
                defense=5,
                attack_range=1,
                move_speed=4,
                vision_range=200,
                attack_cooldown=1.5,
                is_ranged=False,
                is_mounted=False,
                is_flying=False
            )
        elif unit_type == "cavalry":
            # 骑兵
            stats = UnitStats(
                unit_type="cavalry",
                max_health=120,
                attack=15,
                defense=3,
                attack_range=1,
                move_speed=7,
                vision_range=250,
                attack_cooldown=2.0,
                is_ranged=False,
                is_mounted=True,
                is_flying=False
            )
        elif unit_type == "archer":
            # 弓兵
            stats = UnitStats(
                unit_type="archer",
                max_health=80,
                attack=12,
                defense=2,
                attack_range=5,
                move_speed=3.5,
                vision_range=300,
                attack_cooldown=2.5,
                is_ranged=True,
                is_mounted=False,
                is_flying=False
            )
        elif unit_type == "mounted_archer":
            # 弓骑兵
            stats = UnitStats(
                unit_type="mounted_archer",
                max_health=90,
                attack=14,
                defense=2,
                attack_range=4,
                move_speed=6,
                vision_range=350,
                attack_cooldown=3.0,
                is_ranged=True,
                is_mounted=True,
                is_flying=False
            )
        elif unit_type == "flying":
            # 飞行单位
            stats = UnitStats(
                unit_type="flying",
                max_health=70,
                attack=18,
                defense=1,
                attack_range=3,
                move_speed=10,
                vision_range=400,
                attack_cooldown=3.5,
                is_ranged=True,
                is_mounted=False,
                is_flying=True
            )
        else:
            # 默认为步兵
            stats = UnitStats(
                unit_type="infantry",
                max_health=100,
                attack=10,
                defense=5,
                attack_range=1,
                move_speed=4,
                vision_range=200,
                attack_cooldown=1.5,
                is_ranged=False,
                is_mounted=False,
                is_flying=False
            )
            
        # 创建组件
        transform = Transform(x, y)
        ai = AI()
        
        # 存储组件
        self.unit_components[unit_id] = {
            "transform": transform,
            "stats": stats,
            "ai": ai,
            "faction_id": faction_id
        }
        
        # 将单位添加到阵营
        faction_manager = self.engine.scene_manager.current_scene.faction_manager
        faction_manager.add_unit_to_faction(faction_id, unit_id)
        
        return unit_id
        
    def get_unit_component(self, unit_id, component_name):
        """获取单位的组件"""
        unit_data = self.unit_components.get(unit_id)
        if unit_data:
            return unit_data.get(component_name)
        return None
        
    def get_unit_position(self, unit_id):
        """获取单位位置"""
        transform = self.get_unit_component(unit_id, "transform")
        if transform:
            return transform.x, transform.y
        return None
        
    def get_unit_faction(self, unit_id):
        """获取单位所属阵营"""
        return self.get_unit_component(unit_id, "faction_id")
        
    def move_unit(self, unit_id, target_x, target_y):
        """移动单位到目标位置"""
        transform = self.get_unit_component(unit_id, "transform")
        stats = self.get_unit_component(unit_id, "stats")
        
        if not transform or not stats:
            return
            
        # 计算方向向量
        dx = target_x - transform.x
        dy = target_y - transform.y
        distance = (dx**2 + dy**2)**0.5
        
        if distance < 1:  # 已经非常接近目标
            return
            
        # 标准化方向向量
        dx /= distance
        dy /= distance
        
        # 计算移动距离
        move_distance = stats.move_speed  # 每秒移动的距离
        
        # 更新位置
        transform.x += dx * move_distance
        transform.y += dy * move_distance
        
        # 更新朝向
        import math
        transform.rotation = math.atan2(dy, dx)
        
    def attack_unit(self, attacker_id, target_id):
        """攻击目标单位"""
        attacker_stats = self.get_unit_component(attacker_id, "stats")
        target_stats = self.get_unit_component(target_id, "stats")
        attacker_transform = self.get_unit_component(attacker_id, "transform")
        target_transform = self.get_unit_component(target_id, "transform")
        
        if not attacker_stats or not target_stats or not attacker_transform or not target_transform:
            return False
            
        # 检查攻击冷却
        if not attacker_stats.can_attack():
            return False
            
        # 计算距离
        dx = target_transform.x - attacker_transform.x
        dy = target_transform.y - attacker_transform.y
        distance = (dx**2 + dy**2)**0.5
        
        # 检查攻击范围
        attack_range = attacker_stats.attack_range * 100  # 转换为米
        if distance > attack_range:
            return False
            
        # 执行攻击
        damage = attacker_stats.attack
        actual_damage = target_stats.take_damage(damage)
        
        # 重置攻击冷却
        attacker_stats.attack_timer = attacker_stats.attack_cooldown
        
        # 检查目标是否死亡
        if target_stats.is_dead():
            self.kill_unit(target_id)
            
        return True
        
    def kill_unit(self, unit_id):
        """杀死单位"""
        faction_id = self.get_unit_faction(unit_id)
        
        # 从阵营移除单位
        if faction_id is not None:
            faction_manager = self.engine.scene_manager.current_scene.faction_manager
            faction_manager.remove_unit_from_faction(faction_id, unit_id)
            
        # 移除单位组件
        if unit_id in self.unit_components:
            del self.unit_components[unit_id]
            
    def update_units(self, dt):
        """更新所有单位"""
        for unit_id, components in list(self.unit_components.items()):
            stats = components.get("stats")
            ai = components.get("ai")
            
            if stats:
                # 更新攻击冷却
                stats.update_cooldown(dt)
                
            if ai:
                # 更新AI行为
                self.update_unit_ai(unit_id, dt)
                
    def update_unit_ai(self, unit_id, dt):
        """更新单位AI行为"""
        ai = self.get_unit_component(unit_id, "ai")
        transform = self.get_unit_component(unit_id, "transform")
        stats = self.get_unit_component(unit_id, "stats")
        faction_id = self.get_unit_faction(unit_id)
        
        if not ai or not transform or not stats or faction_id is None:
            return
            
        # 获取当前时间
        import time
        current_time = time.time()
        
        # 检查是否可以做出决策
        if not ai.can_make_decision(current_time):
            return
            
        # 更新决策时间
        ai.update_decision_time(current_time)
        
        # 根据AI状态执行不同行为
        if ai.state == "idle":
            # 寻找附近的敌人
            nearest_enemy = self.find_nearest_enemy(unit_id)
            if nearest_enemy:
                ai.set_target(nearest_enemy)
                ai.set_state("attacking")
            else:
                # 随机移动
                import random
                target_x = transform.x + random.uniform(-500, 500)
                target_y = transform.y + random.uniform(-500, 500)
                
                # 确保目标在地图范围内
                map_manager = self.engine.scene_manager.current_scene.map_manager
                target_x = max(0, min(map_manager.width, target_x))
                target_y = max(0, min(map_manager.height, target_y))
                
                ai.set_state("moving")
                ai.set_target(None)
                ai.set_path([(target_x, target_y)])
                
        elif ai.state == "moving":
            # 检查是否有路径
            if not ai.path:
                ai.set_state("idle")
                return
                
            # 获取当前目标点
            target_x, target_y = ai.path[0]
            
            # 移动到目标点
            self.move_unit(unit_id, target_x, target_y)
            
            # 检查是否到达目标点
            dx = target_x - transform.x
            dy = target_y - transform.y
            distance = (dx**2 + dy**2)**0.5
            
            if distance < 50:  # 如果距离小于50米，认为已到达
                ai.path.pop(0)
                if not ai.path:
                    ai.set_state("idle")
                    
            # 检查是否有敌人进入视野
            nearest_enemy = self.find_nearest_enemy(unit_id)
            if nearest_enemy:
                ai.set_target(nearest_enemy)
                ai.set_state("attacking")
                
        elif ai.state == "attacking":
            # 检查目标是否存在
            target_id = ai.target_id
            if not target_id or target_id not in self.unit_components:
                ai.set_state("idle")
                return
                
            # 获取目标位置
            target_transform = self.get_unit_component(target_id, "transform")
            if not target_transform:
                ai.set_state("idle")
                return
                
            # 计算距离
            dx = target_transform.x - transform.x
            dy = target_transform.y - transform.y
            distance = (dx**2 + dy**2)**0.5
            
            # 检查是否在攻击范围内
            attack_range = stats.attack_range * 100  # 转换为米
            if distance <= attack_range:
                # 攻击目标
                self.attack_unit(unit_id, target_id)
            else:
                # 移动到目标
                self.move_unit(unit_id, target_transform.x, target_transform.y)
                
    def find_nearest_enemy(self, unit_id):
        """寻找最近的敌人"""
        transform = self.get_unit_component(unit_id, "transform")
        stats = self.get_unit_component(unit_id, "stats")
        faction_id = self.get_unit_faction(unit_id)
        
        if not transform or not stats or faction_id is None:
            return None
            
        # 获取视野范围
        vision_range = stats.vision_range
        
        nearest_enemy = None
        min_distance = float('inf')
        
        # 遍历所有单位
        for enemy_id, components in self.unit_components.items():
            enemy_faction_id = components.get("faction_id")
            enemy_transform = components.get("transform")
            
            # 跳过同一阵营的单位
            if enemy_faction_id == faction_id or not enemy_transform:
                continue
                
            # 计算距离
            dx = enemy_transform.x - transform.x
            dy = enemy_transform.y - transform.y
            distance = (dx**2 + dy**2)**0.5
            
            # 检查是否在视野范围内
            if distance <= vision_range and distance < min_distance:
                min_distance = distance
                nearest_enemy = enemy_id
                
        return nearest_enemy
        
    def render_units(self, surface, camera_x, camera_y, zoom=1.0):
        """渲染所有单位"""
        import pygame
        
        screen_width, screen_height = surface.get_size()
        
        # 单位大小（像素）
        unit_size = int(30 * zoom)
        
        # 遍历所有单位
        for unit_id, components in self.unit_components.items():
            transform = components.get("transform")
            stats = components.get("stats")
            faction_id = components.get("faction_id")
            
            if not transform or not stats or faction_id is None:
                continue
                
            # 计算单位在屏幕上的位置
            screen_x = int((transform.x - camera_x) * zoom + screen_width / 2)
            screen_y = int((transform.y - camera_y) * zoom + screen_height / 2)
            
            # 检查是否在屏幕范围内
            if (screen_x + unit_size < 0 or screen_x - unit_size > screen_width or
                screen_y + unit_size < 0 or screen_y - unit_size > screen_height):
                continue
                
            # 获取阵营颜色
            faction_manager = self.engine.scene_manager.current_scene.faction_manager
            faction = faction_manager.get_faction(faction_id)
            color = faction.color if faction else (255, 255, 255)
            
            # 绘制单位
            if stats.unit_type == "infantry":
                # 步兵 - 圆形
                pygame.draw.circle(surface, color, (screen_x, screen_y), unit_size)
                pygame.draw.circle(surface, (0, 0, 0), (screen_x, screen_y), unit_size, 2)
            elif stats.unit_type == "cavalry":
                # 骑兵 - 三角形
                points = [
                    (screen_x, screen_y - unit_size),
                    (screen_x - unit_size, screen_y + unit_size),
                    (screen_x + unit_size, screen_y + unit_size)
                ]
                pygame.draw.polygon(surface, color, points)
                pygame.draw.polygon(surface, (0, 0, 0), points, 2)
            elif stats.unit_type == "archer":
                # 弓兵 - 菱形
                points = [
                    (screen_x, screen_y - unit_size),
                    (screen_x + unit_size, screen_y),
                    (screen_x, screen_y + unit_size),
                    (screen_x - unit_size, screen_y)
                ]
                pygame.draw.polygon(surface, color, points)
                pygame.draw.polygon(surface, (0, 0, 0), points, 2)
            elif stats.unit_type == "mounted_archer":
                # 弓骑兵 - 六边形
                import math
                points = []
                for i in range(6):
                    angle = math.pi / 3 * i
                    px = screen_x + unit_size * math.cos(angle)
                    py = screen_y + unit_size * math.sin(angle)
                    points.append((px, py))
                pygame.draw.polygon(surface, color, points)
                pygame.draw.polygon(surface, (0, 0, 0), points, 2)
            elif stats.unit_type == "flying":
                # 飞行单位 - 星形
                pygame.draw.rect(surface, color, (screen_x - unit_size, screen_y - unit_size, unit_size * 2, unit_size * 2))
                pygame.draw.rect(surface, (0, 0, 0), (screen_x - unit_size, screen_y - unit_size, unit_size * 2, unit_size * 2), 2)
                
            # 绘制生命值条
            health_percent = stats.current_health / stats.max_health
            health_width = int(unit_size * 2 * health_percent)
            health_height = int(unit_size / 4)
            
            pygame.draw.rect(surface, (255, 0, 0), (screen_x - unit_size, screen_y - unit_size - health_height - 2, unit_size * 2, health_height))
            pygame.draw.rect(surface, (0, 255, 0), (screen_x - unit_size, screen_y - unit_size - health_height - 2, health_width, health_height))