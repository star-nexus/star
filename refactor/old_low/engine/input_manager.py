import pygame


class InputManager:
    """处理和管理用户输入"""

    def __init__(self, event_manager):
        self.event_manager = event_manager
        self.key_state = {}  # 键盘按键状态
        self.prev_key_state = {}  # 上一帧的键盘按键状态
        self.mouse_state = {}  # 鼠标按键状态
        self.prev_mouse_state = {}  # 上一帧的鼠标按键状态
        self.mouse_pos = (0, 0)  # 鼠标位置

    def process_event(self, event):
        """处理pygame事件"""
        if event.type == pygame.KEYDOWN:
            self.key_state[event.key] = True
            self.event_manager.dispatch("key_down", event.key)
        elif event.type == pygame.KEYUP:
            self.key_state[event.key] = False
            self.event_manager.dispatch("key_up", event.key)
        elif event.type == pygame.MOUSEMOTION:
            self.mouse_pos = event.pos
            self.event_manager.dispatch("mouse_motion", event.pos, event.rel)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self.mouse_state[event.button] = True
            self.event_manager.dispatch("mouse_down", event.button, event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            self.mouse_state[event.button] = False
            self.event_manager.dispatch("mouse_up", event.button, event.pos)

    def update(self):
        """更新输入状态"""
        self.prev_key_state = self.key_state.copy()
        self.prev_mouse_state = self.mouse_state.copy()

    def is_key_pressed(self, key):
        """检查键是否被按下"""
        return self.key_state.get(key, False)

    def is_key_just_pressed(self, key):
        """检查键是否刚刚被按下"""
        return self.key_state.get(key, False) and not self.prev_key_state.get(
            key, False
        )

    def is_key_just_released(self, key):
        """检查键是否刚刚被释放"""
        return not self.key_state.get(key, False) and self.prev_key_state.get(
            key, False
        )

    def is_mouse_button_pressed(self, button):
        """检查鼠标按钮是否被按下"""
        return self.mouse_state.get(button, False)

    def get_mouse_position(self):
        """获取鼠标位置"""
        return self.mouse_pos
