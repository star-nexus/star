import pygame
from framework_v2.ui.button import Button
from framework_v2.ui.text import Text
from framework_v2.ui.panel import Panel

class UIManager:
    def __init__(self, engine):
        self.engine = engine
        self.ui_elements = {}  # 名称 -> UI元素
        self.current_view_mode = "default"  # 当前视图模式
        self.selected_units = []  # 当前选中的单位
        self.selection_rect = None  # 选择框
        self.is_selecting = False  # 是否正在选择
        self.minimap_rect = None  # 小地图区域
        
    def initialize(self):
        """初始化UI元素"""
        screen_width, screen_height = self.engine.width, self.engine.height
        
        # 创建顶部面板
        top_panel = Panel(
            self.engine,
            0, 0,
            screen_width, 50,
            color=(50, 50, 50, 200)
        )
        self.ui_elements["top_panel"] = top_panel
        
        # 创建底部面板
        bottom_panel = Panel(
            self.engine,
            0, screen_height - 150,
            screen_width, 150,
            color=(50, 50, 50, 200)
        )
        self.ui_elements["bottom_panel"] = bottom_panel
        
        # 创建小地图
        minimap_size = 200
        self.minimap_rect = pygame.Rect(
            screen_width - minimap_size - 10,
            screen_height - minimap_size - 10,
            minimap_size,
            minimap_size
        )
        
        # 创建资源显示
        resources_text = Text(
            self.engine,
            "资源: 1000",
            100, 25,
            font_size=20,
            color=(255, 255, 255)
        )
        self.ui_elements["resources_text"] = resources_text
        
        # 创建单位信息显示
        unit_info_text = Text(
            self.engine,
            "未选中单位",
            screen_width // 2, screen_height - 75,
            font_size=18,
            color=(255, 255, 255)
        )
        self.ui_elements["unit_info_text"] = unit_info_text
        
        # 创建视图模式按钮
        view_modes = ["默认", "地形", "阵营", "单位"]
        button_width = 100
        button_spacing = 10
        total_width = len(view_modes) * (button_width + button_spacing) - button_spacing
        start_x = (screen_width - total_width) // 2
        
        for i, mode in enumerate(view_modes):
            button = Button(
                self.engine,
                mode,
                start_x + i * (button_width + button_spacing) + button_width // 2,
                25,
                width=button_width,
                height=30,
                callback=lambda m=mode: self.change_view_mode(m)
            )
            self.ui_elements[f"view_mode_{mode}"] = button
            
        # 创建单位操作按钮
        unit_actions = ["移动", "攻击", "防御", "巡逻"]
        button_width = 80
        button_spacing = 10
        total_width = len(unit_actions) * (button_width + button_spacing) - button_spacing
        start_x = (screen_width - total_width) // 2
        
        for i, action in enumerate(unit_actions):
            button = Button(
                self.engine,
                action,
                start_x + i * (button_width + button_spacing) + button_width // 2,
                screen_height - 30,
                width=button_width,
                height=30,
                callback=lambda a=action: self.perform_unit_action(a)
            )
            self.ui_elements[f"action_{action}"] = button
            
        # 创建暂停按钮
        pause_button = Button(
            self.engine,
            "暂停",
            screen_width - 50,
            25,
            width=80,
            height=30,
            callback=self.toggle_pause
        )
        self.ui_elements["pause_button"] = pause_button
        
        # 创建菜单按钮
        menu_button = Button(
            self.engine,
            "菜单",
            50,
            25,
            width=80,
            height=30,
            callback=self.show_menu
        )
        self.ui_elements["menu_button"] = menu_button
        
    def change_view_mode(self, mode):
        """切换视图模式"""
        mode_map = {
            "默认": "default",
            "地形": "terrain",
            "阵营": "faction",
            "单位": "unit"
        }
        self.current_view_mode = mode_map.get(mode, "default")
        
    def perform_unit_action(self, action):
        """执行单位操作"""
        if not self.selected_units:
            return
            
        scene = self.engine.scene_manager.current_scene
        unit_manager = scene.unit_manager
        task_manager = scene.task_manager
        
        if action == "移动":
            # 进入移动模式，等待玩家点击目标位置
            scene.input_mode = "move"
        elif action == "攻击":
            # 进入攻击模式，等待玩家选择目标
            scene.input_mode = "attack"
        elif action == "防御":
            # 创建防御任务
            positions = []
            for unit_id in self.selected_units:
                transform = unit_manager.get_unit_component(unit_id, "transform")
                if transform:
                    positions.append((transform.x, transform.y))
                    
            if positions:
                # 计算平均位置作为防御点
                avg_x = sum(x for x, y in positions) / len(positions)
                avg_y = sum(y for x, y in positions) / len(positions)
                
                task_id = task_manager.create_task(
                    "defend",
                    f"防御位置 ({int(avg_x)}, {int(avg_y)})",
                    target_position=(avg_x, avg_y),
                    units=self.selected_units.copy()
                )
                task_manager.start_task(task_id)
                
        elif action == "巡逻":
            # 进入巡逻模式，等待玩家设置巡逻点
            scene.input_mode = "patrol"
            
    def toggle_pause(self):
        """切换游戏暂停状态"""
        scene = self.engine.scene_manager.current_scene
        scene.paused = not scene.paused
        
        # 更新按钮文本
        pause_button = self.ui_elements.get("pause_button")
        if pause_button:
            pause_button.text = "继续" if scene.paused else "暂停"
            
    def show_menu(self):
        """显示游戏菜单"""
        # 创建菜单面板
        screen_width, screen_height = self.engine.width, self.engine.height
        
        menu_panel = Panel(
            self.engine,
            screen_width // 4,
            screen_height // 4,
            screen_width // 2,
            screen_height // 2,
            color=(30, 30, 60, 230)
        )
        self.ui_elements["menu_panel"] = menu_panel
        
        # 创建菜单标题
        menu_title = Text(
            self.engine,
            "游戏菜单",
            screen_width // 2,
            screen_height // 4 + 30,
            font_size=30,
            color=(255, 255, 255)
        )
        self.ui_elements["menu_title"] = menu_title
        
        # 创建菜单按钮
        menu_items = ["继续游戏", "保存游戏", "加载游戏", "设置", "返回主菜单", "退出游戏"]
        button_height = 40
        button_spacing = 10
        total_height = len(menu_items) * (button_height + button_spacing) - button_spacing
        start_y = (screen_height - total_height) // 2
        
        for i, item in enumerate(menu_items):
            button = Button(
                self.engine,
                item,
                screen_width // 2,
                start_y + i * (button_height + button_spacing) + button_height // 2,
                width=200,
                height=button_height,
                callback=lambda i=item: self.handle_menu_item(i)
            )
            self.ui_elements[f"menu_{item}"] = button
            
    def hide_menu(self):
        """隐藏游戏菜单"""
        # 移除菜单相关UI元素
        menu_elements = [key for key in self.ui_elements.keys() if key.startswith("menu_")]
        for key in menu_elements:
            del self.ui_elements[key]
            
    def handle_menu_item(self, item):
        """处理菜单项点击"""
        if item == "继续游戏":
            self.hide_menu()
        elif item == "保存游戏":
            # 保存游戏逻辑
            pass
        elif item == "加载游戏":
            # 加载游戏逻辑
            pass
        elif item == "设置":
            # 显示设置面板
            pass
        elif item == "返回主菜单":
            self.engine.scene_manager.load_scene("start")
        elif item == "退出游戏":
            self.engine.quit()
            
    def select_units(self, unit_ids):
        """选择单位"""
        self.selected_units = unit_ids
        self.update_unit_info()
        
    def clear_selection(self):
        """清除选择"""
        self.selected_units = []
        self.update_unit_info()
        
    def update_unit_info(self):
        """更新单位信息显示"""
        unit_info_text = self.ui_elements.get("unit_info_text")
        if not unit_info_text:
            return
            
        if not self.selected_units:
            unit_info_text.set_text("未选中单位")
            return
            
        unit_manager = self.engine.scene_manager.current_scene.unit_manager
        
        if len(self.selected_units) == 1:
            # 显示单个单位的详细信息
            unit_id = self.selected_units[0]
            stats = unit_manager.get_unit_component(unit_id, "stats")
            
            if stats:
                unit_type_names = {
                    "infantry": "步兵",
                    "cavalry": "骑兵",
                    "archer": "弓兵",
                    "mounted_archer": "弓骑兵",
                    "flying": "飞行单位"
                }
                
                unit_type = unit_type_names.get(stats.unit_type, stats.unit_type)
                health = f"{stats.current_health}/{stats.max_health}"
                attack = stats.attack
                defense = stats.defense
                
                unit_info_text.set_text(f"{unit_type} - 生命: {health} 攻击: {attack} 防御: {defense}")
        else:
            # 显示多个单位的简略信息
            unit_counts = {}
            
            for unit_id in self.selected_units:
                stats = unit_manager.get_unit_component(unit_id, "stats")
                if stats:
                    unit_type = stats.unit_type
                    unit_counts[unit_type] = unit_counts.get(unit_type, 0) + 1
                    
            unit_type_names = {
                "infantry": "步兵",
                "cavalry": "骑兵",
                "archer": "弓兵",
                "mounted_archer": "弓骑兵",
                "flying": "飞行单位"
            }
            
            info_text = "已选择: "
            for unit_type, count in unit_counts.items():
                type_name = unit_type_names.get(unit_type, unit_type)
                info_text += f"{type_name} x{count} "
                
            unit_info_text.set_text(info_text)
            
    def update_resources_display(self, resources):
        """更新资源显示"""
        resources_text = self.ui_elements.get("resources_text")
        if resources_text:
            resources_text.set_text(f"资源: {resources}")
            
    def start_selection(self, start_pos):
        """开始框选"""
        self.is_selecting = True
        self.selection_rect = pygame.Rect(start_pos[0], start_pos[1], 0, 0)
        
    def update_selection(self, current_pos):
        """更新框选区域"""
        if not self.is_selecting:
            return
            
        x, y = self.selection_rect.topleft
        width = current_pos[0] - x
        height = current_pos[1] - y
        
        self.selection_rect.width = width
        self.selection_rect.height = height
        
    def end_selection(self):
        """结束框选，选择区域内的单位"""
        if not self.is_selecting or not self.selection_rect:
            return
            
        self.is_selecting = False
        
        # 确保选择框有正确的尺寸（处理负宽度/高度）
        if self.selection_rect.width < 0:
            self.selection_rect.x += self.selection_rect.width
            self.selection_rect.width = abs(self.selection_rect.width)
            
        if self.selection_rect.height < 0:
            self.selection_rect.y += self.selection_rect.height
            self.selection_rect.height = abs(self.selection_rect.height)
            
        # 选择区域内的单位
        scene = self.engine.scene_manager.current_scene
        unit_manager = scene.unit_manager
        faction_manager = scene.faction_manager
        player_faction = faction_manager.get_player_faction()
        
        if not player_faction:
            return
            
        selected_units = []
        
        for unit_id, components in unit_manager.unit_components.items():
            faction_id = components.get("faction_id")
            transform = components.get("transform")
            
            # 只选择玩家阵营的单位
            if faction_id != player_faction.faction_id or not transform:
                continue
                
            # 计算单位在屏幕上的位置
            screen_width, screen_height = self.engine.width, self.engine.height
            camera_x, camera_y = scene.camera_x, scene.camera_y
            
            screen_x = int((transform.x - camera_x) + screen_width / 2)
            screen_y = int((transform.y - camera_y) + screen_height / 2)
            
            # 检查是否在选择框内
            if self.selection_rect.collidepoint(screen_x, screen_y):
                selected_units.append(unit_id)
                
        # 更新选中的单位
        self.select_units(selected_units)
        
        # 清除选择框
        self.selection_rect = None
        
    def render(self, surface):
        """渲染UI元素"""
        # 渲染所有UI元素
        for element in self.ui_elements.values():
            element.render(surface)
            
        # 渲染小地图
        if self.minimap_rect:
            scene = self.engine.scene_manager.current_scene
            map_manager = scene.map_manager
            
            # 绘制小地图背景
            pygame.draw.rect(surface, (0, 0, 0), self.minimap_rect)
            pygame.draw.rect(surface, (255, 255, 255), self.minimap_rect, 2)
            
            # 计算小地图比例
            map_width, map_height = map_manager.width, map_manager.height
            minimap_width, minimap_height = self.minimap_rect.width, self.minimap_rect.height
            
            scale_x = minimap_width / map_width
            scale_y = minimap_height / map_height
            
            # 绘制地形
            for row in range(map_manager.grid_rows):
                for col in range(map_manager.grid_cols):
                    terrain_type = map_manager.terrain[row, col]
                    
                    # 简化的地形颜色
                    if terrain_type == 0:  # 平原
                        color = (200, 230, 180)
                    elif terrain_type == 1:  # 丘陵
                        color = (160, 160, 120)
                    elif terrain_type == 2:  # 山地
                        color = (120, 100, 80)
                    elif terrain_type == 3:  # 森林
                        color = (50, 150, 50)
                    elif terrain_type == 4:  # 河流
                        color = (100, 150, 255)
                    elif terrain_type == 5:  # 湖泊
                        color = (50, 100, 200)
                    elif terrain_type == 6:  # 道路
                        color = (200, 200, 200)
                    else:
                        color = (128, 128, 128)
                        
                    # 计算小地图上的位置
                    mini_x = int(col * map_manager.grid_size * scale_x) + self.minimap_rect.x
                    mini_y = int(row * map_manager.grid_size * scale_y) + self.minimap_rect.y
                    mini_width = max(1, int(map_manager.grid_size * scale_x))
                    mini_height = max(1, int(map_manager.grid_size * scale_y))
                    
                    pygame.draw.rect(surface, color, (mini_x, mini_y, mini_width, mini_height))
                    
            # 绘制单位
            unit_manager = scene.unit_manager
            faction_manager = scene.faction_manager
            
            for unit_id, components in unit_manager.unit_components.items():
                transform = components.get("transform")
                faction_id = components.get("faction_id")
                
                if not transform or faction_id is None:
                    continue
                    
                # 获取阵营颜色
                faction = faction_manager.get_faction(faction_id)
                color = faction.color if faction else (255, 255, 255)
                
                # 计算小地图上的位置
                mini_x = int(transform.x * scale_x) + self.minimap_rect.x
                mini_y = int(transform.y * scale_y) + self.minimap_rect.y
                
                # 绘制单位点
                pygame.draw.circle(surface, color, (mini_x, mini_y), 2)
                
            # 绘制视口框
            viewport_x = int((scene.camera_x - self.engine.width / 2) * scale_x) + self.minimap_rect.x
            viewport_y = int((scene.camera_y - self.engine.height / 2) * scale_y) + self.minimap_rect.y
            viewport_width = int(self.engine.width * scale_x)
            viewport_height = int(self.engine.height * scale_y)
            
            pygame.draw.rect(surface, (255, 255, 255), (viewport_x, viewport_y, viewport_width, viewport_height), 1)
            
        # 渲染选择框
        if self.is_selecting and self.selection_rect:
            pygame.draw.rect(surface, (0, 255, 0), self.selection_rect, 2)