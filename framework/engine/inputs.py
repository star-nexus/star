from sched import Event
import pygame
from typing import List
import logging
from .events import EventManager, EventType,EventMessage

class InputManager:
    """输入管理器，负责管理游戏中的输入逻辑"""
    def __init__(self, event_manager:EventManager):
        """初始化输入管理器"""
        self.event_manager = event_manager
        self.logger = logging.getLogger(__name__)

    def update(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.logger.debug("收到退出事件")
                self.event_manager.publish(EventMessage(EventType.QUIT, {}))
            
            # 鼠标/键盘
            match event.type:
                case pygame.KEYDOWN:
                    e = EventMessage(
                        type=EventType.KEY_DOWN,
                        data = {
                            "key": event.key,
                        },
                        sender=type(self).__name__,
                        timestamp=pygame.time.get_ticks()
                    )
                    self._pulisher(e)
                    self.logger.debug(f"键盘按下: {e}")
                case pygame.KEYUP:
                    e = EventMessage(
                        type=EventType.KEY_UP,
                        data = {
                            "key": event.key,
                        },
                        sender=type(self).__name__,
                        timestamp=pygame.time.get_ticks()
                    )
                    self._pulisher(e)
                    self.logger.debug(f"键盘抬起: {e}")
                case pygame.MOUSEBUTTONDOWN:
                    e = EventMessage(
                        type=EventType.MOUSEBUTTON_DOWN,
                        data = {
                            "button": event.button,
                            "pos": event.pos,
                        },
                        sender=type(self).__name__,
                        timestamp=pygame.time.get_ticks()
                    )
                    self._pulisher(e)
                    self.logger.debug(f"鼠标按下: {e}")
                case pygame.MOUSEBUTTONUP:
                    e = EventMessage(
                        type=EventType.MOUSEBUTTON_UP,
                        data = {
                            "button": event.button,
                            "pos": event.pos,
                        },
                        sender=type(self).__name__,
                        timestamp=pygame.time.get_ticks()
                    )
                    self._pulisher(e)
                    self.logger.debug(f"鼠标抬起: {e}")
                case pygame.MOUSEMOTION:
                    e = EventMessage(
                        type=EventType.MOUSE_MOTION,
                        data = {
                            "pos": event.pos,
                            "rel": event.rel,
                            "buttons": event.buttons,
                        },
                        sender=type(self).__name__,
                        timestamp=pygame.time.get_ticks()
                    )
                    self._pulisher(e)
                    self.logger.debug(f"鼠标移动: {e}")
                case pygame.MOUSEWHEEL:
                    
                    e = EventMessage(
                        type=EventType.MOUSE_WHEEL,
                        data = {
                            "x": event.x,
                            "y": event.y,
                        },
                        sender=type(self).__name__,
                        timestamp=pygame.time.get_ticks()
                    )
                    self._pulisher(e)
                    self.logger.debug(f"鼠标滚轮: {e}")
                case _:
                    self.logger.debug(f"其他事件: {event}")
                    
        
    def _pulisher(self, event:EventMessage):
        """发布输入事件"""
        self.event_manager.publish(event)
        pass


