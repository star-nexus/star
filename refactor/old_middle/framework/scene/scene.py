class Scene:
    """
    场景基类：所有场景的基础类
    """

    def __init__(self, game):
        self.game = game
        self.ui_elements = []

    def load(self):
        """场景加载时调用"""
        pass

    def unload(self):
        """场景卸载时调用"""
        # 移除所有UI元素
        for element in self.ui_elements:
            self.game.ui.remove_element(element)
        self.ui_elements.clear()

    def update(self, delta_time):
        """场景更新逻辑"""
        pass

    def render(self):
        """场景渲染逻辑"""
        pass

    def process_event(self, event):
        """处理输入事件"""
        pass

    def add_ui_element(self, element):
        """添加UI元素并跟踪它"""
        self.ui_elements.append(element)
        self.game.ui.add_element(element)
        return element
