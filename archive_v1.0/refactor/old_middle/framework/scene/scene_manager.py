class SceneManager:
    """
    场景管理器：管理场景的加载、卸载和切换
    """

    def __init__(self, game):
        self.game = game
        self.scenes = {}
        self.current_scene = None
        self.scene_stack = []

    def register_scene(self, scene_name, scene_class):
        """注册场景"""
        self.scenes[scene_name] = scene_class

    def change_scene(self, scene_name, **params):
        """切换到指定场景，可以传递参数"""
        # 卸载当前场景
        if self.current_scene:
            self.current_scene.unload()

        # 清空场景栈
        self.scene_stack.clear()

        # 创建并加载新场景
        if scene_name in self.scenes:
            self.current_scene = self.scenes[scene_name](self.game)
            # 设置传递的参数
            for key, value in params.items():
                setattr(self.current_scene, key, value)

            self.scene_stack.append(self.current_scene)
            self.current_scene.load()
        else:
            raise ValueError(f"Scene '{scene_name}' not registered")

    def push_scene(self, scene_name):
        """将场景压入堆栈并切换到它"""
        # 暂时不卸载当前场景，只是不更新它

        # 创建并加载新场景
        if scene_name in self.scenes:
            self.current_scene = self.scenes[scene_name](self.game)
            self.scene_stack.append(self.current_scene)
            self.current_scene.load()
        else:
            raise ValueError(f"Scene '{scene_name}' not registered")

    def pop_scene(self):
        """弹出当前场景并返回到上一个场景"""
        if len(self.scene_stack) > 1:
            # 卸载当前场景
            current = self.scene_stack.pop()
            current.unload()

            # 切换到栈顶场景
            self.current_scene = self.scene_stack[-1]
        else:
            print("Warning: Attempting to pop the last scene")

    def update(self, delta_time):
        """更新当前场景"""
        if self.current_scene:
            self.current_scene.update(delta_time)

    def render(self):
        """渲染当前场景"""
        if self.current_scene:
            self.current_scene.render()

    def process_event(self, event):
        """处理输入事件"""
        if self.current_scene:
            self.current_scene.process_event(event)
