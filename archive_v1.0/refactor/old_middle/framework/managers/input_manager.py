import pygame


class InputManager:
    """
    输入管理器：处理键盘和鼠标输入
    """

    def __init__(self):
        self.keys_pressed = {}
        self.keys_down = set()
        self.keys_up = set()
        self.mouse_position = (0, 0)
        self.mouse_buttons = [False, False, False]
        self.mouse_down = [False, False, False]
        self.mouse_up = [False, False, False]

    def process_event(self, event):
        """处理pygame事件"""
        if event.type == pygame.KEYDOWN:
            self.keys_pressed[event.key] = True
            self.keys_down.add(event.key)
        elif event.type == pygame.KEYUP:
            self.keys_pressed[event.key] = False
            self.keys_up.add(event.key)
        elif event.type == pygame.MOUSEMOTION:
            self.mouse_position = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN:
            button_idx = event.button - 1
            if 0 <= button_idx < 3:
                self.mouse_buttons[button_idx] = True
                self.mouse_down[button_idx] = True
        elif event.type == pygame.MOUSEBUTTONUP:
            button_idx = event.button - 1
            if 0 <= button_idx < 3:
                self.mouse_buttons[button_idx] = False
                self.mouse_up[button_idx] = True

    def update(self):
        """更新输入状态，清除一次性事件"""
        self.keys_down.clear()
        self.keys_up.clear()
        self.mouse_down = [False, False, False]
        self.mouse_up = [False, False, False]

    def is_key_pressed(self, key):
        """检查键是否被按下（持续状态）"""
        return self.keys_pressed.get(key, False)

    def is_key_down(self, key):
        """检查键是否刚被按下（单次事件）"""
        return key in self.keys_down

    def is_key_up(self, key):
        """检查键是否刚被释放（单次事件）"""
        return key in self.keys_up

    def is_mouse_button_pressed(self, button):
        """检查鼠标按钮是否被按下（0=左，1=中，2=右）"""
        if 0 <= button < 3:
            return self.mouse_buttons[button]
        return False

    def is_mouse_button_down(self, button):
        """检查鼠标按钮是否刚被按下（0=左，1=中，2=右）"""
        if 0 <= button < 3:
            return self.mouse_down[button]
        return False

    def is_mouse_button_up(self, button):
        """检查鼠标按钮是否刚被释放（0=左，1=中，2=右）"""
        if 0 <= button < 3:
            return self.mouse_up[button]
        return False

    def get_mouse_position(self):
        """获取鼠标位置"""
        return self.mouse_position
