"""
pygbag启动器 - 用于Web部署
使用方法: python -m pygbag pygbag_launcher.py
"""

import asyncio
from ..framework_v2.engine.async_game_engine import AsyncGameEngine


async def main():
    """pygbag主入口函数"""
    # 创建游戏引擎实例
    engine = AsyncGameEngine(
        title="Romance of the Three Kingdoms", width=1024, height=768, fps=60
    )

    # 启动游戏
    await engine.start()


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
