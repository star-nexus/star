from math import e
import numpy as np
import pygame
from PIL import Image
from typing import Tuple, Optional
from .game_types import TerrainType


def load_image(image_path: str) -> Image.Image:
    """
    加载图像文件

    Args:
        image_path: 图像文件路径

    Returns:
        PIL Image对象
    """
    try:
        return Image.open(image_path)
    except Exception as e:
        print(f"加载图像失败: {e}")
        raise


def image_to_ndarray(
    image_path: str, size: Optional[Tuple[int, int]] = None
) -> np.ndarray:
    """
    将图像转换为地图数组

    Args:
        image_path: 图像文件路径
        size: 可选的输出尺寸 (width, height)，如果不指定则使用原图尺寸

    Returns:
        地形图数组，每个元素是TerrainType枚举值
    """
    # 加载图像
    img = load_image(image_path)

    # 如果指定了尺寸，则调整图像大小
    if size is not None:
        img = img.resize(size, Image.LANCZOS)

    # 转换为numpy数组
    img_array = np.array(img)

    # 获取图像尺寸
    height, width = img_array.shape[:2]

    # 创建地形图数组
    terrain_map = np.full((height, width), TerrainType.PLAIN.value, dtype=object)

    # 根据颜色映射地形
    for y in range(height):
        for x in range(width):
            pixel = img_array[y, x]
            terrain_map[y, x] = color_to_terrain(pixel)

    return terrain_map


# 预定义的颜色到地形类型的映射
# 格式: (R, G, B): TerrainType.XXX.value
COLOR_TERRAIN_MAP = {
    # 蓝色系 - 水域
    (0, 0, 139): TerrainType.DEEP_WATER.value,  # 深蓝 - 深水
    (65, 105, 225): TerrainType.RIVER.value,  # 皇家蓝 - 河流
    (135, 206, 250): TerrainType.SHALLOW_WATER.value,  # 浅蓝 - 浅水
    (151, 227, 231): TerrainType.SHALLOW_WATER.value,  # 淡蓝绿 - 浅水
    # 绿色系 - 植被
    (34, 139, 34): TerrainType.FOREST.value,  # 森林绿 - 森林
    (0, 100, 0): TerrainType.FOREST.value,  # 深绿 - 森林
    (124, 252, 0): TerrainType.GRASSLAND.value,  # 草地绿 - 草地
    (128, 178, 110): TerrainType.GRASSLAND.value,  # 淡绿 - 草地
    # 棕色/灰色系 - 山地
    (120, 100, 80): TerrainType.MOUNTAIN.value,  # 灰棕 - 山地
    (160, 120, 90): TerrainType.HILL.value,  # 深棕 - 丘陵
    # 特殊地形
    (128, 128, 128): TerrainType.CITY.value,  # 灰色 - 城市
    (0, 0, 0): TerrainType.CITY.value,  # 黑色 - 城市
    (255, 255, 255): TerrainType.ROAD.value,  # 白色 - 道路
    (210, 180, 140): TerrainType.PLAIN.value,  # 棕褐色 - 平原
}

# 颜色容差值，用于颜色匹配
COLOR_TOLERANCE = 25


def analyze_image_colors(image_path: str) -> dict:
    """
    分析图像中的主要颜色，并返回颜色频率统计

    Args:
        image_path: 图像文件路径

    Returns:
        颜色及其出现频率的字典 {(r,g,b): count}
    """
    # 加载图像
    img = load_image(image_path)

    # 转换为RGB模式（确保没有alpha通道）
    if img.mode != "RGB":
        img = img.convert("RGB")

    # 获取所有像素
    pixels = list(img.getdata())

    # 统计颜色频率
    color_counts = {}
    for pixel in pixels:
        if pixel in color_counts:
            color_counts[pixel] += 1
        else:
            color_counts[pixel] = 1

    # 按频率排序
    sorted_colors = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)

    # 返回排序后的颜色字典
    return dict(sorted_colors)


def color_distance(color1, color2):
    """
    计算两个颜色之间的欧几里得距离

    Args:
        color1: 第一个颜色 (r,g,b)
        color2: 第二个颜色 (r,g,b)

    Returns:
        颜色距离值
    """
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5


def find_closest_color(pixel, color_map):
    """
    在颜色映射中找到最接近的颜色

    Args:
        pixel: 像素颜色 (r,g,b)
        color_map: 颜色映射字典 {(r,g,b): terrain_type}

    Returns:
        最接近的颜色对应的地形类型
    """
    min_distance = float("inf")
    closest_terrain = TerrainType.PLAIN.value  # 默认为平原

    for color, terrain in color_map.items():
        dist = color_distance(pixel, color)
        if dist < min_distance:
            min_distance = dist
            closest_terrain = terrain

    # 如果最小距离大于容差值，返回默认地形
    if min_distance > COLOR_TOLERANCE:
        return TerrainType.PLAIN.value

    return closest_terrain


def color_to_terrain(pixel) -> int:
    """
    根据像素颜色确定地形类型

    Args:
        pixel: 像素颜色值 (RGB或RGBA)

    Returns:
        TerrainType枚举值
    """
    # 获取RGB值
    if len(pixel) == 4:  # RGBA
        r, g, b, a = pixel
    else:  # RGB
        r, g, b = pixel

    # 精确匹配
    if (r, g, b) in COLOR_TERRAIN_MAP:
        return COLOR_TERRAIN_MAP[(r, g, b)]

    # 使用颜色距离查找最接近的颜色
    return find_closest_color((r, g, b), COLOR_TERRAIN_MAP)

    # 以下是基于规则的颜色匹配（作为备选方案）
    # 蓝色系 - 水域
    if b > 200 and r < 200 and g > 200:  # 151, 227, 231
        return TerrainType.SHALLOW_WATER.value
    # 绿色系 - 植被 # 128,178,110
    elif g < 200 and r < 100 and b < 100:
        return TerrainType.FOREST.value
    elif g > 150 and r < 150 and b > 200:
        return TerrainType.GRASSLAND.value

    # 棕色/灰色系 - 山地
    elif r > 150 and g > 100 and g < 150 and b < 100:
        return TerrainType.MOUNTAIN.value
    elif r > 120 and g > 80 and g < 120 and b < 80:
        return TerrainType.HILL.value

    # 黑色 - 城市
    elif r < 50 and g < 50 and b < 50:
        return TerrainType.CITY.value

    # 白色/浅灰色 - 道路
    elif r > 200 and g > 200 and b > 200:
        return TerrainType.ROAD.value

    # 默认为平原
    return TerrainType.PLAIN.value


def generate_map_from_image(
    image_path: str, size: Optional[int] = None
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    从图像生成地图，返回与MapGenerator.generate_map()兼容的格式

    Args:
        image_path: 图像文件路径
        size: 可选的输出尺寸，如果不指定则使用原图尺寸

    Returns:
        (海拔图, 地形图, 湿度图) 的元组
    """
    # 如果指定了尺寸，使用正方形尺寸
    output_size = (size, size) if size is not None else None

    # 生成地形图
    terrain = image_to_ndarray(image_path, output_size)
    height, width = terrain.shape

    # 创建简单的海拔图和湿度图
    # 这里只是创建空的数组，实际应用中可能需要根据地形生成相应的海拔和湿度
    elevation = np.zeros((height, width), dtype=np.int32)
    moisture = np.zeros((height, width), dtype=np.float32)

    # 根据地形设置简单的海拔值
    for y in range(height):
        for x in range(width):
            terrain_type = terrain[y, x]

            # 根据地形类型设置海拔
            if terrain_type == TerrainType.MOUNTAIN.value:
                elevation[y, x] = 80 + np.random.randint(0, 20)
            elif terrain_type == TerrainType.HILL.value:
                elevation[y, x] = 60 + np.random.randint(0, 20)
            elif terrain_type == TerrainType.PLAIN.value:
                elevation[y, x] = 30 + np.random.randint(0, 30)
            elif terrain_type == TerrainType.FOREST.value:
                elevation[y, x] = 40 + np.random.randint(0, 20)
            elif terrain_type == TerrainType.GRASSLAND.value:
                elevation[y, x] = 35 + np.random.randint(0, 15)
            elif terrain_type in [
                TerrainType.RIVER.value,
                TerrainType.SHALLOW_WATER.value,
            ]:
                elevation[y, x] = 20 + np.random.randint(0, 10)
            elif terrain_type == TerrainType.DEEP_WATER.value:
                elevation[y, x] = 10 + np.random.randint(0, 10)
            else:
                elevation[y, x] = 30 + np.random.randint(0, 10)

            # 设置湿度
            if terrain_type in [
                TerrainType.DEEP_WATER.value,
                TerrainType.RIVER.value,
                TerrainType.SHALLOW_WATER.value,
            ]:
                moisture[y, x] = 0.8 + np.random.random() * 0.2
            elif terrain_type in [TerrainType.FOREST.value]:
                moisture[y, x] = 0.6 + np.random.random() * 0.3
            elif terrain_type in [TerrainType.GRASSLAND.value]:
                moisture[y, x] = 0.4 + np.random.random() * 0.3
            elif terrain_type in [TerrainType.MOUNTAIN.value, TerrainType.HILL.value]:
                moisture[y, x] = 0.3 + np.random.random() * 0.3
            else:
                moisture[y, x] = 0.2 + np.random.random() * 0.4

    return elevation, terrain, moisture


def generate_color_mapping_from_image(image_path: str) -> dict:
    """
    从图像生成颜色到地形类型的映射

    Args:
        image_path: 图像文件路径

    Returns:
        颜色到地形类型的映射字典 {(r,g,b): terrain_type}
    """
    # 分析图像中的主要颜色
    color_counts = analyze_image_colors(image_path)

    # 获取出现频率最高的颜色（最多取前15个）
    top_colors = list(color_counts.keys())[:15]

    # 创建颜色到地形类型的映射
    custom_color_map = {}

    # 为每个主要颜色分配地形类型
    for color in top_colors:
        r, g, b = color

        # 蓝色系 - 水域
        if b > 200 and r < 150:
            if g > 200:
                custom_color_map[color] = TerrainType.SHALLOW_WATER.value
            else:
                custom_color_map[color] = TerrainType.DEEP_WATER.value

        # 绿色系 - 植被
        elif g > 150 and g > r and g > b:
            if g > 200:
                custom_color_map[color] = TerrainType.GRASSLAND.value
            else:
                custom_color_map[color] = TerrainType.FOREST.value

        # 棕色/灰色系 - 山地
        elif r > 150 and r > g and r > b:
            if g > 120:
                custom_color_map[color] = TerrainType.HILL.value
            else:
                custom_color_map[color] = TerrainType.MOUNTAIN.value

        # 黑色 - 城市
        elif r < 50 and g < 50 and b < 50:
            custom_color_map[color] = TerrainType.CITY.value

        # 白色/浅灰色 - 道路
        elif r > 200 and g > 200 and b > 200:
            custom_color_map[color] = TerrainType.ROAD.value

        # 其他颜色 - 默认为平原
        else:
            custom_color_map[color] = TerrainType.PLAIN.value

    # 合并自定义映射和预定义映射
    merged_map = {**COLOR_TERRAIN_MAP, **custom_color_map}

    print(f"分析图像颜色完成，找到 {len(top_colors)} 种主要颜色")
    for color, terrain in custom_color_map.items():
        terrain_name = next(
            name
            for name, member in TerrainType.__members__.items()
            if member.value == terrain
        )
        print(f"颜色 RGB{color} 映射为地形: {terrain_name}")

    return merged_map


def visualize_color_mapping(color_map: dict):
    """
    可视化颜色映射，显示每种颜色对应的地形类型

    Args:
        color_map: 颜色到地形类型的映射字典 {(r,g,b): terrain_type}
    """
    # 初始化pygame
    pygame.init()

    # 设置显示参数
    box_size = 30  # 每个颜色方块的大小
    padding = 5  # 方块之间的间距
    cols = 5  # 每行显示的方块数

    # 计算需要的行数
    rows = (len(color_map) + cols - 1) // cols

    # 设置窗口大小
    width = cols * (box_size + padding) + padding
    height = rows * (box_size + padding) + padding + 20  # 额外空间用于显示标题

    # 创建窗口
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("颜色映射可视化")

    # 设置字体
    try:
        font = pygame.font.SysFont("SimHei", 12)  # 使用黑体显示中文
    except e:
        font = pygame.font.Font(None, 12)  # 如果没有合适的字体，使用默认字体

    # 获取地形类型名称的映射
    terrain_names = {
        member.value: name for name, member in TerrainType.__members__.items()
    }

    # 绘制背景
    screen.fill((240, 240, 240))

    # 绘制颜色方块和标签
    items = list(color_map.items())
    for i, (color, terrain_type) in enumerate(items):
        # 计算方块位置
        row = i // cols
        col = i % cols
        x = padding + col * (box_size + padding)
        y = padding + row * (box_size + padding) + 20  # 额外空间用于标题

        # 绘制颜色方块
        pygame.draw.rect(screen, color, (x, y, box_size, box_size))

        # 绘制边框
        pygame.draw.rect(screen, (0, 0, 0), (x, y, box_size, box_size), 1)

        # 获取地形名称
        terrain_name = terrain_names.get(terrain_type, "未知")

        # 绘制地形名称标签
        text = font.render(terrain_name, True, (0, 0, 0))
        text_rect = text.get_rect(center=(x + box_size // 2, y + box_size + 5))
        screen.blit(text, text_rect)

    # 绘制标题
    title_font = pygame.font.SysFont("SimHei", 16)
    title = title_font.render("颜色到地形类型映射", True, (0, 0, 0))
    title_rect = title.get_rect(center=(width // 2, 10))
    screen.blit(title, title_rect)

    # 更新显示
    pygame.display.flip()

    # 等待用户关闭窗口
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

    # 清理
    pygame.quit()


def test_image_map(
    image_path: str,
    size: int = 100,
    analyze_colors: bool = False,
    show_color_map: bool = True,
):
    """
    测试从图像生成地图并在pygame中显示

    Args:
        image_path: 图像文件路径
        size: 地图尺寸
        analyze_colors: 是否分析图像颜色生成自定义映射
        show_color_map: 是否显示颜色映射可视化
    """
    # 如果需要分析颜色，则生成自定义颜色映射
    if analyze_colors:
        custom_map = generate_color_mapping_from_image(image_path)
        # 更新全局颜色映射
        global COLOR_TERRAIN_MAP
        COLOR_TERRAIN_MAP = custom_map

        # 显示颜色映射可视化
        if show_color_map:
            visualize_color_mapping(COLOR_TERRAIN_MAP)

    # 初始化pygame
    pygame.init()
    screen = pygame.display.set_mode((size, size))
    pygame.display.set_caption("Image Map Test")

    # 生成地图
    elevation, terrain, moisture = generate_map_from_image(image_path, size)

    # 颜色映射（用于显示）
    display_color_map = {
        TerrainType.PLAIN.value: (210, 180, 140),  # 棕褐色
        TerrainType.HILL.value: (160, 120, 90),  # 深棕色
        TerrainType.MOUNTAIN.value: (120, 100, 80),  # 灰棕色
        TerrainType.FOREST.value: (34, 139, 34),  # 森林绿
        TerrainType.GRASSLAND.value: (124, 252, 0),  # 草地绿
        TerrainType.RIVER.value: (65, 105, 225),  # 河流蓝
        TerrainType.DEEP_WATER.value: (0, 0, 139),  # 深蓝
        TerrainType.SHALLOW_WATER.value: (135, 206, 250),  # 浅蓝
        TerrainType.CITY.value: (128, 128, 128),  # 灰色
        TerrainType.ROAD.value: (255, 255, 255),  # 白色
    }

    # 绘制地图
    for y in range(size):
        for x in range(size):
            terrain_type = terrain[y, x]
            color = display_color_map.get(terrain_type, (200, 200, 200))  # 默认灰色
            pygame.draw.rect(screen, color, (x, y, 1, 1))

    pygame.display.flip()

    # 主循环
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

    pygame.quit()


if __name__ == "__main__":
    import argparse

    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description="图像到地形地图转换工具")
    parser.add_argument(
        "image_path",
        nargs="?",
        default="/Users/own/Workspace/rotk/game/utils/image.png",
        help="输入图像路径",
    )
    parser.add_argument("--size", type=int, default=800, help="输出地图尺寸")
    parser.add_argument(
        "--analyze", action="store_true", help="分析图像颜色并生成自定义映射"
    )
    parser.add_argument(
        "--no-color-map", action="store_true", help="不显示颜色映射可视化"
    )
    parser.add_argument("--tolerance", type=int, default=25, help="颜色匹配容差值")

    # 解析命令行参数
    args = parser.parse_args()

    # 设置颜色容差值
    # global COLOR_TOLERANCE
    COLOR_TOLERANCE = args.tolerance

    # 测试图像地图生成
    test_image_map(
        args.image_path,
        args.size,
        analyze_colors=args.analyze or True,  # 默认启用颜色分析
        show_color_map=not args.no_color_map,
    )
