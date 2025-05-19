from framework.engine.scenes import Scene
from framework.utils.logging import get_logger
import time


class TransitionEndScene(Scene):
    def __init__(self, engine):
        super().__init__(engine)
        self.logger = get_logger("TransitionEndScene")
        self.start_time = None
        self.transition_duration = 3  # 3秒后自动关闭游戏

    def enter(self, **kwargs):
        self.logger.info("进入过渡结束场景")
        super().enter(**kwargs)
        self.start_time = time.time()
        self.logger.info(f"过渡结束场景将在{self.transition_duration}秒后自动关闭游戏")

    def update(self, dt):
        super().update(dt)
        
        # 检查是否已经过了指定的时间
        if self.start_time and time.time() - self.start_time >= self.transition_duration:
            self.logger.info(f"过渡结束场景已经运行{self.transition_duration}秒，准备关闭游戏")
            self.engine.stop()

    def exit(self):
        self.logger.info("退出过渡结束场景")
        super().exit()