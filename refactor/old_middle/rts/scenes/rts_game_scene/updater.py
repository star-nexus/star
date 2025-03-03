from rts.managers.game_state_manager import GameState


class RTSSceneUpdater:
    """
    RTS场景更新器：负责场景的更新逻辑
    将更新逻辑从主场景类中分离出来
    """

    def __init__(self, scene):
        """
        初始化场景更新器

        参数:
            scene: RTSGameScene实例，提供对游戏资源和系统的访问
        """
        self.scene = scene
        self.debug_mode = (
            self.scene.debug_mode if hasattr(self.scene, "debug_mode") else False
        )

    def update(self, delta_time):
        """
        更新场景状态

        参数:
            delta_time: 帧间隔时间
        """
        if not self.scene.initialized:
            return

        # 处理边缘滚动 - 移到外部以确保即使暂停也可以移动视角
        self.scene.input_handler.handle_edge_scrolling(delta_time)

        # 只有在PLAYING状态下才更新游戏逻辑
        if self.scene.game_state_manager.is_state(GameState.PLAYING):
            # 更新游戏实体和系统
            self.scene.game.world.update(delta_time)

            # 更新阵营资源显示
            self.scene.ui_manager.update_faction_ui(self.scene.faction_system)

            # 更新小地图视口信息
            self._update_minimap()

            # 处理战斗事件
            self.scene.combat_manager.process_combat_events(self.scene.combat_system)
            self.scene.combat_manager.update(delta_time)

            # 更新实体管理器
            self.scene.entity_manager.update(delta_time)

            # 更新胜利条件系统
            self.scene.victory_system.update(delta_time)

        # 始终更新游戏流程UI
        self.scene.game_flow_ui.update(delta_time)

    def _update_minimap(self):
        """更新小地图视口信息"""
        if self.scene.map_manager and self.scene.map_manager.map_renderer:
            viewport_width = self.scene.game.width
            viewport_height = self.scene.game.height
            offset_x = self.scene.map_manager.map_renderer.offset_x
            offset_y = self.scene.map_manager.map_renderer.offset_y

            self.scene.ui_manager.update_minimap(
                offset_x, offset_y, viewport_width, viewport_height
            )
