import sys
import os
import logging  # 添加 logging 模块导入
from rich.logging import RichHandler

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from framework_v2.engine.engine import Engine
from rotk_v2.scenes import StartScene, GameScene, EndScene

def setup_logging(level=logging.INFO, enable=True):
    """
    设置日志系统
    
    Args:
        level: 日志级别，默认为 INFO
        enable: 是否启用日志，默认为 True
    """
    if not enable:
        # 禁用所有日志
        logging.disable(logging.CRITICAL)
        return
        
    # 启用日志并设置级别
    logging.disable(logging.NOTSET)
    
    # 配置根日志记录器
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True)]
    )
    
    # 可以为特定模块设置不同的日志级别
    # logging.getLogger('framework_v2.engine').setLevel(logging.DEBUG)
    # logging.getLogger('rotk_v2.systems').setLevel(logging.WARNING)

def main():
    # 设置日志系统 - 可以根据需要调整参数
    # 日志级别可以是: DEBUG, INFO, WARNING, ERROR, CRITICAL
    setup_logging(level=logging.INFO, enable=True)
    
    # 创建游戏引擎
    engine = Engine(title="Demo", width=1280, height=720)
    
    # 注册场景
    engine.scene_manager.add_scene("start", StartScene)
    engine.scene_manager.add_scene("game", GameScene)
    engine.scene_manager.add_scene("end", EndScene)
    
    # 设置初始场景
    engine.scene_manager.load_scene("start")
    
    # 启动游戏
    engine.start()

if __name__ == "__main__":
    main()