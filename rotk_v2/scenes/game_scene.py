import pygame
from framework_v2.engine.scenes import Scene
from framework_v2.ui.button import Button
from framework_v2.ui.text import Text
from framework_v2.engine.events import EventType, EventMessage

from rotk_v2.systems.render_system import RenderSystem
from rotk_v2.systems.movement_system import MovementSystem
from rotk_v2.systems.selection_system import SelectionSystem
from rotk_v2.systems.command_system import CommandSystem
from rotk_v2.systems.ai_system import AISystem
from rotk_v2.systems.map_system import MapSystem
from rotk_v2.systems.combat_system import CombatSystem
from rotk_v2.systems.camera_system import CameraSystem

from rotk_v2.components.transform_component import TransformComponent
from rotk_v2.components.render_component import RenderComponent
from rotk_v2.components.character_component import CharacterComponent
from rotk_v2.components.city_component import CityComponent
from rotk_v2.components.army_component import ArmyComponent
from rotk_v2.components.selectable_component import SelectableComponent
from rotk_v2.components.movable_component import MovableComponent
from rotk_v2.components.ai_component import AIComponent
from rotk_v2.components.camera_component import CameraComponent,MainCameraTagComponent,MiniMapCameraTagComponent
from rotk_v2.components.combat_component import CombatComponent
from rotk_v2.components.map_component import MapComponent




class GameScene(Scene):
    def __init__(self, engine):
        super().__init__(engine)
        self.ui_elements = []
        self.game_time = 0
        self.paused = False
        
    def enter(self, **kwargs):
        """场景开始时调用"""
        super().enter(**kwargs)
        
        # 创建 UI 元素
        self.create_ui_elements()
        
        # 初始化游戏状态
        self.game_time = 0
        self.paused = False

        # 创建游戏实体
        self.create_game_entities()
        
        # 注册系统
        self.register_systems()
        

        
        # 订阅事件
        self.subscribe_events()
        
    def exit(self):
        """场景结束时调用"""
        super().exit()
        
        # 取消订阅事件
        self.unsubscribe_events()
        
        # 清除 UI 元素
        self.ui_elements.clear()
        
    def register_systems(self):
        """注册系统"""
        # 创建地图系统并初始化
        map_system = MapSystem(priority=100)  # 不需要传入组件要求，MapSystem应该自己定义
        self.world.add_system(map_system)
        
        # 添加相机系统
        camera_system = CameraSystem(self.world.context)
        self.world.add_system(camera_system)
    
        # 创建渲染系统
        render_system = RenderSystem([TransformComponent, RenderComponent], priority=90)
        self.world.add_system(render_system)
        
        # # 创建移动系统
        # movement_system = MovementSystem([TransformComponent, MovableComponent], priority=50)
        # self.world.add_system(movement_system)
        
        # # 创建选择系统
        # selection_system = SelectionSystem([TransformComponent, RenderComponent, SelectableComponent], priority=30)
        # self.world.add_system(selection_system)
        
        # # 创建命令系统
        # command_system = CommandSystem([], priority=20)
        # self.world.add_system(command_system)

        # self.world.add_system(CombatSystem(
        #     required_components=[CombatComponent, ArmyComponent], 
        #     priority=50
        # ))
        
        # # 创建 AI 系统
        # ai_system = AISystem([AIComponent], priority=10)
        # self.world.add_system(ai_system)
        
    def subscribe_events(self):
        """订阅事件"""
        # 使用新的多事件类型订阅功能
        self.engine.event_manager.subscribe(
            [EventType.UNIT_SELECTED], 
            self.on_unit_selected
        )
        
        # 订阅所有单位移动相关事件
        self.engine.event_manager.subscribe(
            [EventType.UNIT_MOVE_STARTED, EventType.UNIT_MOVE_ENDED],
            self.on_unit_movement
        )

        # 订阅地图创建完成事件
        self.engine.event_manager.subscribe(
            [EventType.MAP_CREATED],
            self.on_map_created
        )

        self.engine.event_manager.subscribe(
            [EventType.MOUSEBUTTON_DOWN, EventType.KEY_DOWN],
            self.ui_event
        )
        
    def unsubscribe_events(self):
        """取消订阅事件"""
        # 取消订阅单位选择事件
        self.engine.event_manager.unsubscribe(
            [EventType.UNIT_SELECTED], 
            self.on_unit_selected
        )
        
        # 取消订阅所有单位移动相关事件
        self.engine.event_manager.unsubscribe(
            [EventType.UNIT_MOVE_STARTED, EventType.UNIT_MOVE_ENDED],
            self.on_unit_movement
        )

    def on_unit_selected(self, event):
        """单位选择事件处理"""
        # 更新 UI 显示选中单位信息
        entity = event.data.get("entity")
        if entity and self.world.entity_manager.entity_exists(entity):
            if self.world.component_manager.has_component(entity, CharacterComponent):
                character = self.world.component_manager.get_component(entity, CharacterComponent)
                # 更新 UI 显示武将信息
                
    def on_unit_movement(self, event):
        """处理所有单位移动相关事件"""
        # 根据事件类型执行不同操作
        if event.type == EventType.UNIT_MOVE_STARTED:
            # 单位开始移动的处理
            # 可以添加移动开始的音效或动画
            pass
        elif event.type == EventType.UNIT_MOVE_ENDED:
            # 单位结束移动的处理
            # 可以添加移动结束的音效或动画
            pass

        # 订阅鼠标事件
        self.engine.event_manager.subscribe(EventType.MOUSEBUTTON_DOWN, self.on_mouse_button_down)
        self.engine.event_manager.subscribe(EventType.KEY_DOWN, self.on_mouse_motion)
        
    def unsubscribe_events(self):
        """取消订阅事件"""
        # 取消订阅单位选择事件
        self.engine.event_manager.unsubscribe(EventType.UNIT_SELECTED, self.on_unit_selected)
        
        # 取消订阅单位移动事件
        self.engine.event_manager.unsubscribe(EventType.UNIT_MOVE_STARTED, self.on_unit_move_started)
        self.engine.event_manager.unsubscribe(EventType.UNIT_MOVE_ENDED, self.on_unit_move_ended)
        
    def on_unit_selected(self, event):
        """单位选择事件处理"""
        # 更新 UI 显示选中单位信息
        entity = event.data.get("entity")
        if entity and self.world.entity_manager.entity_exists(entity):
            if self.world.component_manager.has_component(entity, CharacterComponent):
                character = self.world.component_manager.get_component(entity, CharacterComponent)
                # 更新 UI 显示武将信息
                
    def on_unit_move_started(self, event):
        """单位开始移动事件处理"""
        # 可以添加移动开始的音效或动画
        pass
        
    def on_unit_move_ended(self, event):
        """单位结束移动事件处理"""
        # 可以添加移动结束的音效或动画
        pass
        
    def create_ui_elements(self):
        """创建 UI 元素"""
        # 创建暂停按钮
        self.pause_button = Button(
            self.engine,
            "Pause",
            self.engine.width - 60,
            30,
            width=100,
            height=40,
            callback=self.toggle_pause
        )
        self.ui_elements.append(self.pause_button)
        
        # 创建返回主菜单按钮
        self.menu_button = Button(
            self.engine,
            "Main Menu",
            self.engine.width - 60,
            80,
            width=100,
            height=40,
            callback=self.return_to_menu
        )
        self.ui_elements.append(self.menu_button)
        
        # 创建游戏时间显示
        self.time_text = Text(
            self.engine,
            "Time: 0:00",
            100,
            30,
            font_size=24,
            color=(255, 255, 255)
        )
        self.ui_elements.append(self.time_text)
        
        # 创建资源显示
        self.resource_text = Text(
            self.engine,
            "Source: 1000",
            100,
            60,
            font_size=24,
            color=(255, 255, 255)
        )
        self.ui_elements.append(self.resource_text)
        
    def create_game_entities(self):
        """创建游戏实体"""
        # 创建主相机实体
        self.create_camera()
        
        # 不再需要在这里创建地图，由 MapSystem 负责
        # self.create_map()
        
        # 创建城市
        self.create_cities()
        
        # 创建武将和军队
        self.create_characters_and_armies()
        
    def create_camera(self):
        """创建主相机实体"""
        # 创建主相机
        main_camera_entity = self.world.entity_manager.create_entity()
        
        # 将相机放在地图中心
        map_width_pixels = 100 * 32 // 2
        map_height_pixels = 80 * 32 // 2
        
        # 添加相机组件
        self.world.component_manager.add_component(main_camera_entity, CameraComponent(
            x=map_width_pixels,
            y=map_height_pixels,
            zoom=0.5,
            is_primary=True
        ))
        
        # 添加相机标签组件
        self.world.component_manager.add_component(main_camera_entity, MainCameraTagComponent())
        
        print(f"主相机创建在位置: ({map_width_pixels}, {map_height_pixels}), 缩放: 0.5")
        
        # 创建小地图相机
        minimap_camera_entity = self.world.entity_manager.create_entity()
        
        # 小地图相机放在地图中心，但缩放更小
        self.world.component_manager.add_component(minimap_camera_entity, CameraComponent(
            x=map_width_pixels,
            y=map_height_pixels,
            zoom=0.1,  # 更小的缩放以显示更大范围
            is_primary=False
        ))
        
        # 添加小地图相机标签
        self.world.component_manager.add_component(minimap_camera_entity, MiniMapCameraTagComponent())
        
        print(f"小地图相机创建在位置: ({map_width_pixels}, {map_height_pixels}), 缩放: 0.1")
    
    # 删除旧的 create_map 方法，由 MapSystem 负责地图创建
    # def create_map(self):
    #     """创建地图实体"""
    #     # 创建地图实体
    #     map_entity = self.world.entity_manager.create_entity()
    #     
    #     # 添加变换组件
    #     self.world.component_manager.add_component(map_entity, TransformComponent(
    #         x=self.engine.width // 2,
    #         y=self.engine.height // 2
    #     ))
    #     
    #     # 添加渲染组件
    #     self.world.component_manager.add_component(map_entity, RenderComponent(
    #         color=(0, 100, 0),
    #         width=1000,
    #         height=1000,
    #         layer=0
    #     ))
        
    def create_cities(self):
        """创建城市实体"""
        # 创建几个主要城市
        cities_data = [
            {"name": "洛阳", "force": "汉", "x": 400, "y": 300, "population": 10000, "food": 5000, "gold": 3000},
            {"name": "长安", "force": "汉", "x": 200, "y": 350, "population": 8000, "food": 4000, "gold": 2500},
            {"name": "许昌", "force": "曹操", "x": 450, "y": 400, "population": 7000, "food": 3500, "gold": 2000},
            {"name": "荆州", "force": "刘表", "x": 350, "y": 500, "population": 6000, "food": 3000, "gold": 1800},
            {"name": "成都", "force": "刘璋", "x": 150, "y": 550, "population": 5000, "food": 2500, "gold": 1500},
            {"name": "建业", "force": "孙权", "x": 550, "y": 450, "population": 6500, "food": 3200, "gold": 1900}
        ]
        
        for city_data in cities_data:
            # 创建城市实体
            city_entity = self.world.entity_manager.create_entity()
            
            # 添加变换组件
            self.world.component_manager.add_component(city_entity, TransformComponent(
                x=city_data["x"],
                y=city_data["y"]
            ))
            
            # 添加渲染组件
            color = self.get_force_color(city_data["force"])
            self.world.component_manager.add_component(city_entity, RenderComponent(
                color=color,
                width=40,
                height=40,
                layer=1
            ))
            
            # 添加城市组件
            self.world.component_manager.add_component(city_entity, CityComponent(
                name=city_data["name"],
                force=city_data["force"],
                population=city_data["population"],
                max_population=city_data["population"] * 1.5,
                food=city_data["food"],
                gold=city_data["gold"],
                defense=50
            ))
            
            # 添加可选择组件
            self.world.component_manager.add_component(city_entity, SelectableComponent())
            
    def create_characters_and_armies(self):
        """创建武将和军队实体"""
        # 创建一些著名武将和他们的军队
        # 在角色数据中添加training和morale字段
        characters_data = [
            {"name": "曹操", "force": "曹操", "x": 450, "y": 380, 
             "leadership": 95, "war": 80, "intelligence": 90, 
             "politics": 85, "charm": 75, "training": 70, "morale": 80},
            {"name": "刘备", "force": "刘备", "x": 350, "y": 480, 
             "leadership": 90, "war": 75, "intelligence": 80, 
             "politics": 80, "charm": 100, "training": 65, "morale": 85},
            {"name": "孙权", "force": "孙权", "x": 550, "y": 430, "leadership": 85, "war": 70, "intelligence": 85, "politics": 90, "charm": 80, "training": 70, "morale": 80},
            {"name": "关羽", "force": "刘备", "x": 330, "y": 490, "leadership": 90, "war": 97, "intelligence": 75, "politics": 60, "charm": 85, "training": 70, "morale": 80},
            {"name": "张飞", "force": "刘备", "x": 370, "y": 490, "leadership": 85, "war": 96, "intelligence": 50, "politics": 40, "charm": 60, "training": 70, "morale": 80},
            {"name": "赵云", "force": "刘备", "x": 350, "y": 510, "leadership": 90, "war": 95, "intelligence": 75, "politics": 65, "charm": 80, "training": 70, "morale": 80},
            {"name": "诸葛亮", "force": "刘备", "x": 350, "y": 460, "leadership": 95, "war": 50, "intelligence": 100, "politics": 90, "charm": 85, "training": 70, "morale": 80},
            {"name": "周瑜", "force": "孙权", "x": 570, "y": 450, "leadership": 90, "war": 80, "intelligence": 95, "politics": 85, "charm": 85,"training": 70, "morale": 80},
            {"name": "吕布", "force": "吕布", "x": 300, "y": 300, "leadership": 70, "war": 100, "intelligence": 40, "politics": 30, "charm": 60, "training": 50, "morale": 70}
        ]
        
        for char_data in characters_data:
            # 创建武将实体
            char_entity = self.world.entity_manager.create_entity()
            
            # 添加变换组件
            self.world.component_manager.add_component(char_entity, TransformComponent(
                x=char_data["x"],
                y=char_data["y"]
            ))
            
            # 添加渲染组件
            color = self.get_force_color(char_data["force"])
            self.world.component_manager.add_component(char_entity, RenderComponent(
                color=color,
                width=20,
                height=20,
                layer=2
            ))
            
            # 添加武将组件
            self.world.component_manager.add_component(char_entity, CharacterComponent(
                name=char_data["name"],
                force=char_data["force"],
                leadership=char_data["leadership"],
                war=char_data["war"],
                intelligence=char_data["intelligence"],
                politics=char_data["politics"],
                charm=char_data["charm"]
            ))
            
            # 添加可选择组件
            self.world.component_manager.add_component(char_entity, SelectableComponent())
            
            # 添加可移动组件
            self.world.component_manager.add_component(char_entity, MovableComponent(
                speed=50 + char_data["war"] * 0.5  # 移动速度与武力相关
            ))
            
            # 创建军队实体
            army_entity = self.world.entity_manager.create_entity()
            
            # 添加变换组件（与武将位置相同）
            self.world.component_manager.add_component(army_entity, TransformComponent(
                x=char_data["x"],
                y=char_data["y"] + 30  # 在武将下方
            ))
            
            # 添加渲染组件
            self.world.component_manager.add_component(army_entity, RenderComponent(
                color=color,
                width=30,
                height=15,
                layer=1
            ))
            
            # 添加军队组件
            troops = 1000 + char_data["leadership"] * 50  # 兵力与统率相关
            # 在原有军队创建代码中添加max_troops
            self.world.component_manager.add_component(army_entity, ArmyComponent(
                force=char_data["force"],
                troops=troops,  # 当前兵力
                max_troops=troops,  # 最大兵力初始值设为当前值
                training=char_data["training"],
                morale=char_data["morale"]
            ))
            
            # 添加可选择组件
            self.world.component_manager.add_component(army_entity, SelectableComponent())
            
            # 添加可移动组件
            self.world.component_manager.add_component(army_entity, MovableComponent(
                speed=40 + char_data["leadership"] * 0.3  # 移动速度与统率相关
            ))
            
            # 如果不是玩家势力，添加 AI 组件
            if char_data["force"] != "刘备":  # 假设玩家控制刘备势力
                self.world.component_manager.add_component(army_entity, AIComponent(
                    behavior="defensive" if char_data["force"] == "汉" else "aggressive"
                ))
    
    def get_force_color(self, force):
        """根据势力获取颜色"""
        force_colors = {
            "汉": (200, 200, 200),  # 灰色
            "曹操": (0, 0, 255),    # 蓝色
            "刘备": (0, 255, 0),    # 绿色
            "孙权": (255, 0, 0),    # 红色
            "吕布": (255, 0, 255),  # 紫色
            "刘表": (255, 255, 0),  # 黄色
            "刘璋": (0, 255, 255)   # 青色
        }
        return force_colors.get(force, (150, 150, 150))
        
    def toggle_pause(self):
        """切换游戏暂停状态"""
        self.paused = not self.paused
        self.pause_button.text = "play" if self.paused else "paused"
        
        # 发布游戏暂停/恢复事件
        event_type = EventType.GAME_PAUSED if self.paused else EventType.GAME_RESUMED
        self.engine.event_manager.publish_immediate(event_type, {"paused": self.paused})
        
    def return_to_menu(self):
        """返回主菜单"""
        self.engine.scene_manager.load_scene("start")
        
    def update(self, delta_time):
        """更新场景"""
        super().update(delta_time)
        
        # 更新 UI 元素
        for element in self.ui_elements:
            if hasattr(element, 'update'):
                element.update(delta_time)
        
        # 如果游戏暂停，不更新游戏逻辑
        if self.paused:
            return
        
        # 更新游戏时间
        self.game_time += delta_time
        minutes = int(self.game_time // 60)
        seconds = int(self.game_time % 60)
        self.time_text.set_text(f"Time: {minutes}:{seconds:02d}")
        
        # 更新世界（会自动更新所有系统）
        self.world.update(delta_time)
        
    def render(self,surface):
        """渲染场景"""
        # 绘制背景
        # surface.fill((0, 0, 0))
        
        # 渲染所有 UI 元素
        for element in self.ui_elements:
            if hasattr(element, 'render'):
                element.render(surface)
    
    def ui_event(self, event):
        """处理输入事件"""
        # 将事件传递给所有 UI 元素
        for element in self.ui_elements:
            if hasattr(element, 'handle_event'):
                element.handle_event(event)
        
        # 如果游戏暂停，不处理游戏事件
        if self.paused:
            return
        
        # 处理键盘事件
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.toggle_pause()
            elif event.key == pygame.K_w:
                self.camera_y -= 10
            elif event.key == pygame.K_s:
                self.camera_y += 10
            elif event.key == pygame.K_a:
                self.camera_x -= 10
            elif event.key == pygame.K_d:
                self.camera_x += 10
        
        # 将事件发布到事件管理器，让系统通过订阅来处理
        if event.type == pygame.MOUSEBUTTONDOWN or event.type == pygame.MOUSEBUTTONUP or event.type == pygame.MOUSEMOTION:
            # 创建自定义事件数据
            event_data = {
                "type": event.type,
                "pos": event.pos if hasattr(event, "pos") else None,
                "button": event.button if hasattr(event, "button") else None,
                "buttons": pygame.mouse.get_pressed() if event.type == pygame.MOUSEMOTION else None
            }
            
            # 发布输入事件
            self.engine.event_manager.publish_immediate(EventType.CUSTOM, event_data)
        
    def end_with_victory(self):
        """以胜利结束游戏"""
        # 收集游戏统计信息
        stats = {
            "time": f"{int(self.game_time // 60)}m{int(self.game_time % 60)}s",
            "result": "win",
            "my loss": "5",
            "peer loss": "20"
        }
        
        # 加载结束场景并传递参数
        self.engine.scene_manager.load_scene("end", {
            "result": "victory",
            "stats": stats
        })
        
    def end_with_defeat(self):
        """以失败结束游戏"""
        # 收集游戏统计信息
        stats = {
            "time": f"{int(self.game_time // 60)}m{int(self.game_time % 60)}s",
            "result": "fail",
            "my loss": "15",
            "peer loss": "8"
        }
        
        # 加载结束场景并传递参数
        self.engine.scene_manager.load_scene("end", {
            "result": "defeat",
            "stats": stats
        })

    def on_map_created(self, event):
        """地图创建完成事件处理"""
        # 获取地图实体和尺寸
        map_entity = event.data.get("map_entity")
        map_width = event.data.get("width")
        map_height = event.data.get("height")
        
        print(f"GameScene 收到地图创建事件: {map_width}x{map_height}")
        
        # 检查地图实体是否有效
        if map_entity is None:
            print("错误: 地图实体为空")
            return
            
        # 检查地图组件是否存在
        if not self.world.component_manager.has_component(map_entity, MapComponent):
            print("错误: 地图实体没有 MapComponent")
            return
            
        # 获取地图系统
        map_system = None
        for system in self.world.systems:
            if isinstance(system, MapSystem):
                map_system = system
                break
                
        if map_system is None:
            print("错误: 找不到 MapSystem")
            return
            
        print(f"地图系统状态: 地图实体 ID = {map_system.map_entity}, 地图尺寸 = {map_system.map_component.width}x{map_system.map_component.height}")
        print(f"地形块数量: {len(map_system.map_component.tile_entities)}")
        
        # 可以在这里进行地图创建后的处理
        # 例如调整相机位置、放置城市和单位等
        
        # 调整城市和武将的位置，使其适应新地图
        self.adjust_entities_to_map()
    
    def adjust_entities_to_map(self):
        """调整实体位置以适应新地图"""
        # 获取地图系统
        map_system = None
        for system in self.world.systems:
            if isinstance(system, MapSystem):
                map_system = system
                break
                
        if not map_system or not map_system.map_component:
            return
            
        # 获取地图尺寸
        map_width = map_system.map_component.width * map_system.map_component.tile_size
        map_height = map_system.map_component.height * map_system.map_component.tile_size
        
        # 调整城市位置
        cities = self.world.component_manager.get_all_entities_with_component(CityComponent)
        for city_entity in cities:
            if self.world.component_manager.has_component(city_entity, TransformComponent):
                transform = self.world.component_manager.get_component(city_entity, TransformComponent)
                # 将城市位置映射到新地图上
                transform.x = (transform.x / 1000) * map_width
                transform.y = (transform.y / 1000) * map_height
                
        # 调整武将和军队位置
        characters = self.world.component_manager.get_all_entities_with_component(CharacterComponent)
        for char_entity in characters:
            if self.world.component_manager.has_component(char_entity, TransformComponent):
                transform = self.world.component_manager.get_component(char_entity, TransformComponent)
                # 将武将位置映射到新地图上
                transform.x = (transform.x / 1000) * map_width
                transform.y = (transform.y / 1000) * map_height

