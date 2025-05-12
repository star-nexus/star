import sys
import os
import logging
from rich.logging import RichHandler

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  

from framework_v2.engine.engine import Engine
from rotk_v2.scenes.simple_game_scene import SimpleGameScene

def setup_logging(level=logging.INFO, enable=True):
    """设置日志系统"""
    if not enable:
        # 禁用所有日志
        logging.disable(logging.CRITICAL)
        return
        
    # 启用日志并设置级别
    logging.disable(logging.NOTSET)
    
    # 配置根日志记录器
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True)]
    )
    
    # 为特定模块设置日志级别
    logging.getLogger('rotk_v2.systems').setLevel(logging.DEBUG)

def main():
    # 设置日志系统
    # setup_logging(level=logging.DEBUG, enable=True)
    
    print("启动简化版三国游戏...")
    
    # 创建游戏引擎
    engine = Engine(title="三国志简化版", width=1280, height=720)
    
    # 注册场景
    engine.scene_manager.add_scene("simple_game", SimpleGameScene)
    
    # 设置初始场景
    engine.scene_manager.load_scene("simple_game")
    
    # 启动游戏
    engine.start()

if __name__ == "__main__":
    main()