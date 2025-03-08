import pygame
import math


class UnitIconRenderer:
    """单位图标渲染器，根据单位类型绘制具象化的图标"""

    @staticmethod
    def render_unit_icon(
        surface, symbol, rect, main_color, accent_color=(255, 255, 255)
    ):
        """渲染单位图标

        Args:
            surface: 要渲染到的表面
            symbol: 单位标识符
            rect: 绘制区域
            main_color: 主要颜色（通常是阵营颜色）
            accent_color: 装饰颜色
        """
        # 确保使用整个渲染区域的中心点
        center_x, center_y = rect.width // 2, rect.height // 2

        # 计算适合图标的半径，略小于矩形宽度的一半
        radius = min(rect.width, rect.height) // 2 - 1

        # 填充主颜色的圆形背景
        pygame.draw.circle(surface, main_color, (center_x, center_y), radius)

        # 根据不同的symbol绘制不同的图标
        if symbol == "盾":  # 刀盾兵
            UnitIconRenderer._draw_shield_infantry(surface, rect, accent_color)
        elif symbol == "戟":  # 长戟兵
            UnitIconRenderer._draw_spear_infantry(surface, rect, accent_color)
        elif symbol == "侦":  # 斥候骑兵
            UnitIconRenderer._draw_scout_cavalry(surface, rect, accent_color)
        elif symbol == "骑":  # 骑射手
            UnitIconRenderer._draw_mounted_archer(surface, rect, accent_color)
        elif symbol == "弓":  # 弓箭手
            UnitIconRenderer._draw_archer(surface, rect, accent_color)
        elif symbol == "弩":  # 弩手
            UnitIconRenderer._draw_crossbowman(surface, rect, accent_color)
        else:
            # 未知单位类型，只绘制符号文本
            font_size = max(14, int(min(rect.width, rect.height) * 0.7))
            font = pygame.font.Font(None, font_size)
            text = font.render(symbol, True, accent_color)
            text_rect = text.get_rect(center=(center_x, center_y))
            surface.blit(text, text_rect)

    @staticmethod
    def _draw_shield_infantry(surface, rect, color):
        """绘制刀盾兵图标 - 盾牌和剑"""
        center_x, center_y = rect.width // 2, rect.height // 2
        radius = min(rect.width, rect.height) // 2 - 2

        # 绘制盾牌
        shield_width = radius * 0.7
        shield_height = radius * 1.1
        shield_rect = pygame.Rect(
            center_x - shield_width // 2,
            center_y - shield_height // 2,
            shield_width,
            shield_height,
        )

        # 盾牌底色
        pygame.draw.ellipse(surface, color, shield_rect)

        # 盾牌边框
        pygame.draw.ellipse(
            surface, (80, 80, 80), shield_rect, max(1, int(radius * 0.1))
        )

        # 盾牌中央纹章
        emblem_radius = shield_width * 0.3
        pygame.draw.circle(
            surface,
            (min(255, color[0] + 50), min(255, color[1] + 50), min(255, color[2] + 50)),
            (center_x, center_y),
            emblem_radius,
        )

        # 剑柄（从盾牌伸出）
        sword_handle_length = radius * 0.4
        pygame.draw.line(
            surface,
            (80, 60, 40),
            (center_x + shield_width // 4, center_y - shield_height // 4),
            (
                center_x + shield_width // 4 + sword_handle_length,
                center_y - shield_height // 4,
            ),
            max(2, int(radius * 0.1)),
        )

    @staticmethod
    def _draw_spear_infantry(surface, rect, color):
        """绘制长戟兵图标 - 长矛"""
        center_x, center_y = rect.width // 2, rect.height // 2
        radius = min(rect.width, rect.height) // 2 - 2

        # 绘制长矛杆
        spear_length = radius * 1.6
        spear_width = max(1, int(radius * 0.08))
        angle = -30  # 角度，使得长矛倾斜
        rad_angle = math.radians(angle)

        # 矛杆
        pygame.draw.line(
            surface,
            (80, 60, 40),  # 棕色矛杆
            (
                center_x - spear_length * 0.1 * math.cos(rad_angle),
                center_y - spear_length * 0.1 * math.sin(rad_angle),
            ),
            (
                center_x + spear_length * 0.9 * math.cos(rad_angle),
                center_y + spear_length * 0.9 * math.sin(rad_angle),
            ),
            spear_width,
        )

        # 矛头
        spear_head_length = radius * 0.4
        spear_head_width = max(2, int(radius * 0.15))

        # 计算矛头顶点
        spear_tip_x = center_x - spear_length * math.cos(rad_angle)
        spear_tip_y = center_y - spear_length * math.sin(rad_angle)

        # 计算矛头底部点
        spear_base_x = center_x - (spear_length - spear_head_length) * math.cos(
            rad_angle
        )
        spear_base_y = center_y - (spear_length - spear_head_length) * math.sin(
            rad_angle
        )

        # 计算矛头两侧点（垂直于矛杆）
        perp_angle = rad_angle + math.pi / 2  # 垂直角度
        side_distance = spear_head_width / 2

        left_x = spear_base_x + side_distance * math.cos(perp_angle)
        left_y = spear_base_y + side_distance * math.sin(perp_angle)

        right_x = spear_base_x - side_distance * math.cos(perp_angle)
        right_y = spear_base_y - side_distance * math.sin(perp_angle)

        # 绘制矛头
        pygame.draw.polygon(
            surface,
            color,  # 使用装饰颜色
            [(spear_tip_x, spear_tip_y), (left_x, left_y), (right_x, right_y)],
        )

    @staticmethod
    def _draw_scout_cavalry(surface, rect, color):
        """绘制斥候骑兵图标 - 骑马人"""
        center_x, center_y = rect.width // 2, rect.height // 2
        radius = min(rect.width, rect.height) // 2 - 2

        # 绘制马身体（椭圆）
        horse_width = radius * 1.2
        horse_height = radius * 0.8
        horse_rect = pygame.Rect(
            center_x - horse_width // 2,
            center_y - horse_height // 2 + radius * 0.2,  # 向下偏移一点
            horse_width,
            horse_height,
        )

        # 填充马身体
        pygame.draw.ellipse(surface, (80, 50, 20), horse_rect)  # 棕色马

        # 马腿（简化为几条线）
        leg_length = radius * 0.4
        leg_width = max(1, int(radius * 0.05))

        # 前腿
        leg1_top_x = center_x + radius * 0.3
        leg1_top_y = center_y + radius * 0.2
        pygame.draw.line(
            surface,
            (80, 50, 20),
            (leg1_top_x, leg1_top_y),
            (leg1_top_x - radius * 0.1, leg1_top_y + leg_length),
            leg_width,
        )

        # 后腿
        leg2_top_x = center_x - radius * 0.3
        leg2_top_y = center_y + radius * 0.2
        pygame.draw.line(
            surface,
            (80, 50, 20),
            (leg2_top_x, leg2_top_y),
            (leg2_top_x - radius * 0.1, leg2_top_y + leg_length),
            leg_width,
        )

        # 马头
        head_radius = radius * 0.25
        head_x = center_x + radius * 0.5
        head_y = center_y - radius * 0.05
        pygame.draw.circle(
            surface, (80, 50, 20), (int(head_x), int(head_y)), int(head_radius)
        )

        # 骑手（小人头）
        rider_radius = radius * 0.25
        rider_x = center_x
        rider_y = center_y - radius * 0.3
        pygame.draw.circle(
            surface, color, (int(rider_x), int(rider_y)), int(rider_radius)
        )

        # 骑手持旗（侦察兵特征）
        flag_pole_length = radius * 0.8
        pygame.draw.line(
            surface,
            (80, 80, 80),
            (rider_x, rider_y),
            (rider_x, rider_y - flag_pole_length),
            max(1, int(radius * 0.05)),
        )

        # 三角旗帜
        flag_width = radius * 0.3
        flag_height = radius * 0.2
        pygame.draw.polygon(
            surface,
            color,
            [
                (rider_x, rider_y - flag_pole_length),
                (rider_x, rider_y - flag_pole_length + flag_height),
                (rider_x + flag_width, rider_y - flag_pole_length + flag_height // 2),
            ],
        )

    @staticmethod
    def _draw_mounted_archer(surface, rect, color):
        """绘制骑射手图标 - 骑马射箭的人"""
        center_x, center_y = rect.width // 2, rect.height // 2
        radius = min(rect.width, rect.height) // 2 - 2

        # 首先绘制与斥候骑兵相似的马和骑手
        # 绘制马身体（椭圆）
        horse_width = radius * 1.2
        horse_height = radius * 0.8
        horse_rect = pygame.Rect(
            center_x - horse_width // 2,
            center_y - horse_height // 2 + radius * 0.2,
            horse_width,
            horse_height,
        )

        # 填充马身体
        pygame.draw.ellipse(surface, (80, 50, 20), horse_rect)

        # 马腿（简化为几条线）
        leg_length = radius * 0.4
        leg_width = max(1, int(radius * 0.05))

        # 前腿
        leg1_top_x = center_x + radius * 0.3
        leg1_top_y = center_y + radius * 0.2
        pygame.draw.line(
            surface,
            (80, 50, 20),
            (leg1_top_x, leg1_top_y),
            (leg1_top_x - radius * 0.1, leg1_top_y + leg_length),
            leg_width,
        )

        # 后腿
        leg2_top_x = center_x - radius * 0.3
        leg2_top_y = center_y + radius * 0.2
        pygame.draw.line(
            surface,
            (80, 50, 20),
            (leg2_top_x, leg2_top_y),
            (leg2_top_x - radius * 0.1, leg2_top_y + leg_length),
            leg_width,
        )

        # 马头
        head_radius = radius * 0.25
        head_x = center_x + radius * 0.5
        head_y = center_y - radius * 0.05
        pygame.draw.circle(
            surface, (80, 50, 20), (int(head_x), int(head_y)), int(head_radius)
        )

        # 骑手（小人头）
        rider_radius = radius * 0.25
        rider_x = center_x
        rider_y = center_y - radius * 0.3
        pygame.draw.circle(
            surface, color, (int(rider_x), int(rider_y)), int(rider_radius)
        )

        # 骑射手特有 - 弓箭
        # 弓
        bow_radius = radius * 0.4
        bow_width = max(1, int(radius * 0.05))
        bow_angle_start = math.radians(30)
        bow_angle_end = math.radians(150)

        pygame.draw.arc(
            surface,
            color,
            [
                rider_x - bow_radius,
                rider_y - bow_radius,
                bow_radius * 2,
                bow_radius * 2,
            ],
            bow_angle_start,
            bow_angle_end,
            bow_width,
        )

        # 箭
        arrow_length = radius * 0.5
        arrow_width = max(1, int(radius * 0.03))
        arrow_angle = math.radians(90)  # 水平箭

        arrow_x = rider_x
        arrow_y = rider_y

        # 箭杆
        pygame.draw.line(
            surface,
            (200, 200, 150),  # 淡黄色箭杆
            (arrow_x, arrow_y),
            (
                arrow_x + arrow_length * math.cos(arrow_angle),
                arrow_y + arrow_length * math.sin(arrow_angle),
            ),
            arrow_width,
        )

        # 箭头
        arrowhead_size = radius * 0.1
        pygame.draw.polygon(
            surface,
            (200, 200, 150),
            [
                (
                    arrow_x + arrow_length * math.cos(arrow_angle),
                    arrow_y + arrow_length * math.sin(arrow_angle),
                ),
                (
                    arrow_x
                    + (arrow_length - arrowhead_size) * math.cos(arrow_angle)
                    + arrowhead_size * math.cos(arrow_angle + math.pi / 2),
                    arrow_y
                    + (arrow_length - arrowhead_size) * math.sin(arrow_angle)
                    + arrowhead_size * math.sin(arrow_angle + math.pi / 2),
                ),
                (
                    arrow_x
                    + (arrow_length - arrowhead_size) * math.cos(arrow_angle)
                    + arrowhead_size * math.cos(arrow_angle - math.pi / 2),
                    arrow_y
                    + (arrow_length - arrowhead_size) * math.sin(arrow_angle)
                    + arrowhead_size * math.sin(arrow_angle - math.pi / 2),
                ),
            ],
        )

    @staticmethod
    def _draw_archer(surface, rect, color):
        """绘制弓箭手图标"""
        center_x, center_y = rect.width // 2, rect.height // 2
        radius = min(rect.width, rect.height) // 2 - 2

        # 绘制人体（简化为圆形）
        body_radius = radius * 0.4
        pygame.draw.circle(surface, color, (center_x, center_y), int(body_radius))

        # 弓
        bow_radius = radius * 0.7
        bow_width = max(1, int(radius * 0.07))
        bow_angle_start = math.radians(-60)
        bow_angle_end = math.radians(60)

        pygame.draw.arc(
            surface,
            (150, 120, 90),  # 棕色弓
            [
                center_x - bow_radius,
                center_y - bow_radius,
                bow_radius * 2,
                bow_radius * 2,
            ],
            bow_angle_start,
            bow_angle_end,
            bow_width,
        )

        # 弓弦
        pygame.draw.line(
            surface,
            (200, 200, 200),  # 银色弓弦
            (
                center_x + bow_radius * math.cos(bow_angle_start),
                center_y + bow_radius * math.sin(bow_angle_start),
            ),
            (
                center_x + bow_radius * math.cos(bow_angle_end),
                center_y + bow_radius * math.sin(bow_angle_end),
            ),
            max(1, int(radius * 0.02)),
        )

        # 箭
        arrow_length = radius * 0.8
        arrow_width = max(1, int(radius * 0.04))

        # 箭杆
        pygame.draw.line(
            surface,
            (200, 200, 150),  # 淡黄色箭杆
            (center_x - arrow_length * 0.3, center_y),
            (center_x + arrow_length * 0.7, center_y),
            arrow_width,
        )

        # 箭头
        arrowhead_size = radius * 0.15
        pygame.draw.polygon(
            surface,
            (150, 150, 150),  # 箭头颜色
            [
                (center_x + arrow_length * 0.7, center_y),
                (center_x + arrow_length * 0.55, center_y - arrowhead_size * 0.5),
                (center_x + arrow_length * 0.55, center_y + arrowhead_size * 0.5),
            ],
        )

        # 箭尾
        pygame.draw.line(
            surface,
            (200, 100, 100),  # 红色箭尾
            (center_x - arrow_length * 0.3, center_y - arrowhead_size * 0.4),
            (center_x - arrow_length * 0.3, center_y + arrowhead_size * 0.4),
            max(1, int(radius * 0.06)),
        )

    @staticmethod
    def _draw_crossbowman(surface, rect, color):
        """绘制弩手图标"""
        center_x, center_y = rect.width // 2, rect.height // 2
        radius = min(rect.width, rect.height) // 2 - 2

        # 绘制人体（简化为圆形）
        body_radius = radius * 0.4
        pygame.draw.circle(surface, color, (center_x, center_y), int(body_radius))

        # 弩身 - 十字形状
        crossbow_width = radius * 0.9
        crossbow_height = radius * 0.6
        crossbow_thickness = max(1, int(radius * 0.1))

        # 水平部分
        pygame.draw.line(
            surface,
            (80, 60, 40),  # 棕色弩身
            (center_x - crossbow_width // 2, center_y),
            (center_x + crossbow_width // 2, center_y),
            crossbow_thickness,
        )

        # 垂直部分
        pygame.draw.line(
            surface,
            (80, 60, 40),  # 棕色弩身
            (center_x, center_y - crossbow_height // 2),
            (center_x, center_y + crossbow_height // 2),
            crossbow_thickness,
        )

        # 弩弦
        pygame.draw.line(
            surface,
            (200, 200, 200),  # 银色弩弦
            (center_x - crossbow_width // 2, center_y),
            (center_x + crossbow_width // 2, center_y),
            max(1, int(radius * 0.03)),
        )

        # 弩箭
        arrow_length = radius * 0.6
        arrow_width = max(1, int(radius * 0.04))

        # 箭杆
        pygame.draw.line(
            surface,
            (200, 200, 150),  # 淡黄色箭杆
            (center_x, center_y - arrow_length * 0.2),
            (center_x, center_y - arrow_length),
            arrow_width,
        )

        # 箭头
        arrowhead_size = radius * 0.15
        pygame.draw.polygon(
            surface,
            (150, 150, 150),  # 箭头颜色
            [
                (center_x, center_y - arrow_length),
                (center_x - arrowhead_size * 0.5, center_y - arrow_length * 0.85),
                (center_x + arrowhead_size * 0.5, center_y - arrow_length * 0.85),
            ],
        )
