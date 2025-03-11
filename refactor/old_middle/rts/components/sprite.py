from framework.ecs.component import Component


class SpriteComponent(Component):
    """
    精灵组件：管理实体的视觉表示
    控制游戏对象在屏幕上的外观、可见性和视觉效果
    """

    def __init__(self, image_name):
        """
        初始化精灵组件

        参数:
            image_name: 图像资源名，指向资源管理器中的图像资源
        """
        super().__init__()
        self.image_name = image_name  # 图像资源名，用于从资源管理器获取对应纹理
        self.width = 32  # 宽度(像素)，控制图像在屏幕上的显示尺寸
        self.height = 32  # 高度(像素)，控制图像在屏幕上的显示尺寸
        self.is_visible = True  # 是否可见，控制实体是否被渲染
        self.layer = 0  # 渲染层级(值越大越上层)，控制绘制顺序

        # 特效相关属性
        self.is_glowing = False  # 是否发光，用于高亮显示或特殊效果
        self.glow_timer = 0  # 发光计时器，控制发光效果的持续时间
        self.original_image_name = image_name  # 原始图像资源名，用于特效结束后恢复

        # 可以直接存储纹理对象，优化渲染性能
        self.texture = None  # 直接引用纹理对象，避免每次渲染都查找

        # 可以在子类中扩展以下属性
        # self.animation_frames = []  # 动画帧列表
        # self.current_frame = 0  # 当前动画帧
        # self.frame_time = 0  # 帧切换计时器
        # self.flip_h = False  # 水平翻转
        # self.flip_v = False  # 垂直翻转
