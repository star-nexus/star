import sys
import os
import argparse

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from framework.engine.engine import Engine
from framework.utils.logging import log_config, get_logger
from game.scenes import StartScene, GameScene, EndScene, EditorScene


def setup_argument_parser():
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(description="三国演义游戏")

    # 日志相关参数
    parser.add_argument(
        "--log-level",
        default="MSG",
        choices=["DEBUG", "INFO", "MSG", "WARNING", "ERROR", "CRITICAL"],
        help="日志级别 (默认: INFO)",
    )
    parser.add_argument(
        "--disable-log", default=False, action="store_true", help="禁用日志输出"
    )
    parser.add_argument(
        "--log-to-file", default=False, action="store_true", help="将日志输出到文件"
    )
    parser.add_argument(
        "--log-file", default="game.log", help="日志文件路径 (默认: game.log)"
    )

    return parser


def main():
    # 解析命令行参数
    parser = setup_argument_parser()
    args = parser.parse_args()

    # 配置日志
    log_config.configure(
        level=args.log_level,
        enable_output=not args.disable_log,
        log_to_file=args.log_to_file,
        log_file=args.log_file,
    )

    # 获取日志记录器
    logger = get_logger("Game")
    logger.info("游戏启动中...")
    logger.debug(f"日志级别: {args.log_level}")

    # 创建游戏引擎
    engine = Engine(title="Demo", width=1280, height=720)

    # 注册场景
    engine.scene_manager.add_scene("start", StartScene)
    engine.scene_manager.add_scene("game", GameScene)
    engine.scene_manager.add_scene("end", EndScene)
    engine.scene_manager.add_scene("editor", EditorScene)

    # 设置初始场景
    engine.scene_manager.load_scene("start")

    # 启动游戏
    engine.start()


if __name__ == "__main__":
    main()
