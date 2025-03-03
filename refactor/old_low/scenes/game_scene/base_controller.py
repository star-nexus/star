from typing import Optional, Any

class BaseController:
    """游戏场景控制器的基类，提供共同功能"""
    
    def __init__(self, scene):
        """初始化控制器
        
        Args:
            scene: 所属的游戏场景
        """
        self.scene = scene
        self.engine = scene.engine
        self.initialized = False
        
    def initialize(self) -> None:
        """初始化控制器，子类应重写此方法"""
        self.initialized = True
        
    def update(self, delta_time: float) -> None:
        """更新控制器状态，子类应重写此方法
        
        Args:
            delta_time: 自上一帧以来经过的时间(秒)
        """
        pass
        
    def cleanup(self) -> None:
        """清理控制器资源，子类应重写此方法"""
        pass
        
    @property
    def debug_mode(self) -> bool:
        """获取当前是否处于调试模式"""
        return getattr(self.engine, 'debug_mode', False)
