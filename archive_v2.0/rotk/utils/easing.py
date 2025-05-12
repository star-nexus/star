"""
缓动函数工具类，用于实现平滑的动画效果
"""


class Easing:
    """
    提供各种缓动函数，用于实现平滑的动画效果
    所有函数接收参数t (0.0-1.0)并返回一个缓动后的值(0.0-1.0)
    """

    @staticmethod
    def linear(t):
        """线性缓动 - 匀速运动"""
        return t

    @staticmethod
    def ease_in_quad(t):
        """二次方缓入"""
        return t * t

    @staticmethod
    def ease_out_quad(t):
        """二次方缓出"""
        return t * (2 - t)

    @staticmethod
    def ease_in_out_quad(t):
        """二次方缓入缓出"""
        return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t

    @staticmethod
    def ease_in_cubic(t):
        """三次方缓入"""
        return t * t * t

    @staticmethod
    def ease_out_cubic(t):
        """三次方缓出"""
        t -= 1
        return t * t * t + 1

    @staticmethod
    def ease_in_out_cubic(t):
        """三次方缓入缓出"""
        return 4 * t * t * t if t < 0.5 else (t - 1) * (2 * t - 2) * (2 * t - 2) + 1

    @staticmethod
    def ease_in_back(t):
        """回弹缓入 - 稍微超出起点后开始"""
        s = 1.70158
        return t * t * ((s + 1) * t - s)

    @staticmethod
    def ease_out_back(t):
        """回弹缓出 - 稍微超出终点后结束"""
        s = 1.70158
        t -= 1
        return t * t * ((s + 1) * t + s) + 1

    @staticmethod
    def get_easing_function(name):
        """
        根据名称获取缓动函数

        Args:
            name: 缓动函数名称

        Returns:
            function: 对应的缓动函数
        """
        easing_map = {
            "linear": Easing.linear,
            "ease_in_quad": Easing.ease_in_quad,
            "ease_out_quad": Easing.ease_out_quad,
            "ease_in_out_quad": Easing.ease_in_out_quad,
            "ease_in_cubic": Easing.ease_in_cubic,
            "ease_out_cubic": Easing.ease_out_cubic,
            "ease_in_out_cubic": Easing.ease_in_out_cubic,
            "ease_in_back": Easing.ease_in_back,
            "ease_out_back": Easing.ease_out_back,
        }

        return easing_map.get(name, Easing.linear)
