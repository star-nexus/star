from framework.managers.events import EventManager

class GameManager:
    """游戏管理器，负责处理游戏规则和状态"""
    
    def __init__(self, event_manager: EventManager):
        """初始化游戏管理器
        
        Args:
            event_manager: 事件管理器实例
        """
        self.event_manager = event_manager
        self.is_game_over = False
        self.victory = False
        
        # 订阅相关事件
        self.event_manager.subscribe("player_enemy_collision", self._handle_player_enemy_collision)
    
    def _handle_player_enemy_collision(self, event_data):
        """处理玩家与敌人碰撞事件
        
        Args:
            event_data: 包含碰撞信息的事件数据
        """
        if self.is_game_over:
            return
            
        player_speed = event_data.get("player_speed", 0)
        
        # 判断游戏胜负
        if player_speed > 180:  # 玩家速度阈值
            self.victory = True
            print("Game Over - Player Won!")
        else:
            self.victory = False
            print("Game Over - Player Lost!")
        
        self.is_game_over = True
        # 发布游戏结束事件
        self.event_manager.publish("game_over", {"victory": self.victory})
    
    def reset(self):
        """重置游戏状态"""
        self.is_game_over = False
        self.victory = False
    
    def cleanup(self):
        """清理资源"""
        # 取消事件订阅
        self.event_manager.unsubscribe("player_enemy_collision", self._handle_player_enemy_collision)