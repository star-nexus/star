import pygame
import requests
import io
import math
import os
import time
import socket
from typing import Tuple, Dict, Optional, List


class OpenStreetMapViewer:
    """使用OpenStreetMap和pygame实现的地图查看器"""

    def __init__(self, width: int = 800, height: int = 600):
        """初始化地图查看器

        Args:
            width: 窗口宽度
            height: 窗口高度
        """
        # 初始化pygame
        pygame.init()
        pygame.display.set_caption("OpenStreetMap Viewer")

        # 设置窗口大小
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        self.clock = pygame.time.Clock()

        # 地图状态
        self.zoom = 15  # 初始缩放级别 (0-19)
        self.lat = 39.9042  # 初始纬度 (北京)
        self.lon = 116.4074  # 初始经度 (北京)
        self.move_step = 0.001  # 移动步长

        # 瓦片缓存
        self.tile_cache: Dict[str, pygame.Surface] = {}
        self.max_cache_size = 500  # 最大缓存数量，防止内存溢出

        # 网络状态
        self.is_online = self.check_internet_connection()
        self.offline_mode = not self.is_online
        self.last_connection_check = time.time()
        self.connection_check_interval = 10  # 每10秒检查一次网络连接

        # 记录上次渲染的位置，用于检测变化
        self.last_render_lat = self.lat
        self.last_render_lon = self.lon
        self.last_render_zoom = self.zoom

        # 创建字体对象用于显示信息
        try:
            self.font = pygame.font.SysFont(None, 24)
        except pygame.error as e:
            print(f"字体初始化失败: {e}，使用默认字体")
            self.font = pygame.font.Font(None, 24)

        # 创建缓存目录
        self.cache_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "map_cache"
        )
        os.makedirs(self.cache_dir, exist_ok=True)

        # 预加载一个默认瓦片，用于离线模式或加载失败时
        self.default_tile = self.create_default_tile()

        print(f"网络状态: {'在线' if self.is_online else '离线'}")
        if not self.is_online:
            print("警告: 网络连接不可用，将使用离线模式")

    def check_internet_connection(self) -> bool:
        """检查网络连接状态

        Returns:
            是否有网络连接
        """
        try:
            # 尝试连接到OpenStreetMap服务器
            socket.create_connection(("tile.openstreetmap.org", 80), timeout=2)
            return True
        except (socket.timeout, socket.error):
            return False

    def create_default_tile(self) -> pygame.Surface:
        """创建默认瓦片

        Returns:
            默认瓦片Surface
        """
        tile = pygame.Surface((256, 256))
        tile.fill((200, 200, 200))  # 灰色背景

        # 添加网格线，使瓦片更容易区分
        for i in range(0, 256, 32):
            pygame.draw.line(tile, (180, 180, 180), (i, 0), (i, 255))
            pygame.draw.line(tile, (180, 180, 180), (0, i), (255, i))

        return tile

    def deg_to_tile(self, lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
        """将经纬度转换为瓦片坐标

        Args:
            lat_deg: 纬度
            lon_deg: 经度
            zoom: 缩放级别

        Returns:
            瓦片的x和y坐标
        """
        lat_rad = math.radians(lat_deg)
        n = 2.0**zoom
        xtile = int((lon_deg + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return xtile, ytile

    def tile_to_deg(self, xtile: int, ytile: int, zoom: int) -> Tuple[float, float]:
        """将瓦片坐标转换为经纬度

        Args:
            xtile: 瓦片x坐标
            ytile: 瓦片y坐标
            zoom: 缩放级别

        Returns:
            纬度和经度
        """
        n = 2.0**zoom
        lon_deg = xtile / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
        lat_deg = math.degrees(lat_rad)
        return lat_deg, lon_deg

    def get_tile_url(self, xtile: int, ytile: int, zoom: int) -> str:
        """获取瓦片的URL

        Args:
            xtile: 瓦片x坐标
            ytile: 瓦片y坐标
            zoom: 缩放级别

        Returns:
            瓦片的URL
        """
        # 使用OpenStreetMap的标准瓦片服务器
        # 注意：在实际应用中，应遵循OSM的使用政策
        return f"https://tile.openstreetmap.org/{zoom}/{xtile}/{ytile}.png"

    def manage_cache_size(self):
        """管理缓存大小，防止内存溢出"""
        if len(self.tile_cache) > self.max_cache_size:
            # 如果缓存超过最大限制，删除一半的缓存
            keys_to_remove = list(self.tile_cache.keys())[: (len(self.tile_cache) // 2)]
            for key in keys_to_remove:
                del self.tile_cache[key]
            print(
                f"缓存清理: 删除了 {len(keys_to_remove)} 个瓦片缓存，当前缓存数量: {len(self.tile_cache)}"
            )

    def get_tile(self, xtile: int, ytile: int, zoom: int) -> pygame.Surface:
        """获取地图瓦片

        Args:
            xtile: 瓦片x坐标
            ytile: 瓦片y坐标
            zoom: 缩放级别

        Returns:
            瓦片的pygame Surface对象
        """
        # 检查缓存
        cache_key = f"{zoom}_{xtile}_{ytile}"
        if cache_key in self.tile_cache:
            return self.tile_cache[cache_key]

        # 检查文件缓存
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.png")
        if os.path.exists(cache_file):
            try:
                tile_img = pygame.image.load(cache_file)
                self.tile_cache[cache_key] = tile_img
                # 管理缓存大小
                self.manage_cache_size()
                return tile_img
            except pygame.error as e:
                print(f"从缓存加载瓦片失败: {e}，将尝试重新下载")
                # 如果加载失败，删除可能损坏的缓存文件
                try:
                    os.remove(cache_file)
                except OSError:
                    pass

        # 如果是离线模式，直接返回默认瓦片
        if self.offline_mode:
            return self.default_tile

        # 定期检查网络连接状态
        current_time = time.time()
        if current_time - self.last_connection_check > self.connection_check_interval:
            self.is_online = self.check_internet_connection()
            self.offline_mode = not self.is_online
            self.last_connection_check = current_time
            if not self.is_online:
                print("网络连接不可用，切换到离线模式")
                return self.default_tile

        # 下载瓦片
        url = self.get_tile_url(xtile, ytile, zoom)
        print(url)
        # 重试机制
        try:
            # 添加User-Agent头，遵循OSM使用政策
            # headers = {
            #     "User-Agent": "PyGameMapViewer/1.0 (https://github.com/yourusername/pygamemapviewer)"
            # }
            # 添加超时设置，避免长时间等待
            response = requests.get(url)  # , headers=headers, timeout=3)
            response.raise_for_status()

            # 将图像数据转换为pygame Surface
            image_data = io.BytesIO(response.content)
            tile_img = pygame.image.load(image_data)

            # 保存到缓存
            self.tile_cache[cache_key] = tile_img
            # 管理缓存大小
            self.manage_cache_size()

            try:
                pygame.image.save(tile_img, cache_file)
            except pygame.error as e:
                print(f"保存瓦片到缓存失败: {e}")

            return tile_img
        except requests.Timeout:
            print(f"获取瓦片超时: {url}")
            # 如果连续超时，切换到离线模式
            self.offline_mode = True
            self.last_connection_check = (
                current_time - self.connection_check_interval + 5
            )  # 5秒后重试
            return self.default_tile
        except requests.RequestException as e:
            print(f"网络请求失败: {e}")
            return self.default_tile
        except pygame.error as e:
            print(f"处理瓦片图像失败: {e}")
            return self.default_tile
        except Exception as e:
            print(f"获取瓦片时发生未知错误: {e}")
            return self.default_tile

    def preload_tiles_around_current_position(self):
        """预加载当前位置周围的瓦片，提高移动时的响应速度"""
        # 获取当前中心瓦片坐标
        center_tile_x, center_tile_y = self.deg_to_tile(self.lat, self.lon, self.zoom)

        # 计算需要预加载的瓦片范围
        tiles_x = math.ceil(self.width / 256) + 2  # 水平方向的瓦片数量
        tiles_y = math.ceil(self.height / 256) + 2  # 垂直方向的瓦片数量

        # 预加载范围内的瓦片
        preloaded = 0
        for i in range(-tiles_x // 2, tiles_x // 2 + 1):
            for j in range(-tiles_y // 2, tiles_y // 2 + 1):
                # 计算瓦片坐标
                tile_x = center_tile_x + i
                tile_y = center_tile_y + j

                # 检查瓦片坐标是否有效
                if 0 <= tile_x < 2**self.zoom and 0 <= tile_y < 2**self.zoom:
                    # 异步预加载瓦片，不阻塞主线程
                    cache_key = f"{self.zoom}_{tile_x}_{tile_y}"
                    if cache_key not in self.tile_cache:
                        # 只预加载缓存中没有的瓦片
                        self.get_tile(tile_x, tile_y, self.zoom)
                        preloaded += 1

        if preloaded > 0:
            print(f"预加载了 {preloaded} 个新瓦片")

    def render_map(self):
        """渲染地图"""
        try:
            # 清空屏幕
            self.screen.fill((255, 255, 255))

            # 定期检查网络连接状态
            current_time = time.time()
            if (
                current_time - self.last_connection_check
                > self.connection_check_interval
            ):
                previous_state = self.is_online
                self.is_online = self.check_internet_connection()
                self.offline_mode = not self.is_online
                self.last_connection_check = current_time
                if previous_state != self.is_online:
                    print(f"网络状态变更: {'在线' if self.is_online else '离线'}")

            # 检查位置是否发生变化
            position_changed = (
                self.last_render_lat != self.lat
                or self.last_render_lon != self.lon
                or self.last_render_zoom != self.zoom
            )

            # 更新上次渲染位置
            self.last_render_lat = self.lat
            self.last_render_lon = self.lon
            self.last_render_zoom = self.zoom

            # 获取中心瓦片坐标
            center_tile_x, center_tile_y = self.deg_to_tile(
                self.lat, self.lon, self.zoom
            )

            # 计算屏幕中心点
            center_x = self.width // 2
            center_y = self.height // 2

            # 计算需要渲染的瓦片范围
            tiles_x = math.ceil(self.width / 256) + 2  # 水平方向的瓦片数量
            tiles_y = math.ceil(self.height / 256) + 2  # 垂直方向的瓦片数量

            # 计算中心瓦片在屏幕上的精确位置
            center_pixel_x = center_tile_x * 256
            center_pixel_y = center_tile_y * 256

            # 计算中心点的像素偏移
            lat_rad = math.radians(self.lat)
            n = 2.0**self.zoom
            x_offset = (self.lon + 180.0) / 360.0 * n * 256 - center_pixel_x
            y_offset = (
                1.0 - math.asinh(math.tan(lat_rad)) / math.pi
            ) / 2.0 * n * 256 - center_pixel_y

            # 渲染瓦片
            tiles_loaded = 0
            tiles_failed = 0
            tiles_from_cache = 0

            # 绘制网格背景，帮助用户理解地图结构
            if self.offline_mode or self.zoom < 5:
                # 在离线模式或缩放级别很低时绘制网格
                for i in range(0, self.width, 32):
                    pygame.draw.line(
                        self.screen, (230, 230, 230), (i, 0), (i, self.height)
                    )
                for j in range(0, self.height, 32):
                    pygame.draw.line(
                        self.screen, (230, 230, 230), (0, j), (self.width, j)
                    )

            for i in range(-tiles_x // 2, tiles_x // 2 + 1):
                for j in range(-tiles_y // 2, tiles_y // 2 + 1):
                    # 计算瓦片坐标
                    tile_x = center_tile_x + i
                    tile_y = center_tile_y + j

                    # 检查瓦片坐标是否有效
                    if 0 <= tile_x < 2**self.zoom and 0 <= tile_y < 2**self.zoom:
                        try:
                            # 获取瓦片前记录缓存大小
                            cache_size_before = len(self.tile_cache)

                            # 获取瓦片
                            tile = self.get_tile(tile_x, tile_y, self.zoom)

                            # 检查是否从缓存加载
                            if len(self.tile_cache) == cache_size_before + 1:
                                tiles_from_cache += 1

                            # 计算瓦片在屏幕上的位置
                            screen_x = center_x + (i * 256) - x_offset
                            screen_y = center_y + (j * 256) - y_offset

                            # 绘制瓦片
                            self.screen.blit(tile, (screen_x, screen_y))

                            # 如果是灰色瓦片（加载失败），计数
                            if tile.get_at((128, 128))[0:3] == (200, 200, 200):
                                tiles_failed += 1
                            else:
                                tiles_loaded += 1

                            # 在调试模式下显示瓦片坐标
                            if self.zoom <= 10:  # 只在缩放级别较低时显示坐标
                                coord_text = f"{tile_x},{tile_y}"
                                small_font = pygame.font.SysFont(None, 16)
                                coord_surface = small_font.render(
                                    coord_text, True, (100, 100, 100)
                                )
                                self.screen.blit(
                                    coord_surface, (screen_x + 5, screen_y + 5)
                                )

                        except Exception as e:
                            print(f"渲染瓦片时出错: {e}")
                            tiles_failed += 1

            # 显示当前位置和缩放级别
            info_text = f"longitude: {self.lon:.4f}, latitude: {self.lat:.4f}, zoom: {self.zoom}"
            info_surface = self.font.render(info_text, True, (0, 0, 0))
            self.screen.blit(info_surface, (10, 10))

            # 显示控制提示
            controls_text = "wasd key: move map, +/-: zoom, ESC: quit"
            controls_surface = self.font.render(controls_text, True, (0, 0, 0))
            self.screen.blit(controls_surface, (10, 40))

            # 显示网络状态
            network_status = "online" if self.is_online else "offline"
            network_color = (0, 128, 0) if self.is_online else (255, 0, 0)
            network_text = f"net status: {network_status} | mode: {'offline' if self.offline_mode else 'online'}"
            network_surface = self.font.render(network_text, True, network_color)
            self.screen.blit(network_surface, (10, 70))

            # 显示瓦片加载状态
            status_text = f"tile: {tiles_loaded} loaded, {tiles_failed} failed, {tiles_from_cache} from cache, total {len(self.tile_cache)} tile cache"
            status_surface = self.font.render(status_text, True, (0, 0, 0))
            self.screen.blit(status_surface, (10, 100))

            # 显示缓存目录信息
            try:
                cache_files = len(
                    [f for f in os.listdir(self.cache_dir) if f.endswith(".png")]
                )
                cache_text = f"cache files: {cache_files} ({self.cache_dir})"
                cache_surface = self.font.render(cache_text, True, (0, 0, 0))
                self.screen.blit(cache_surface, (10, 130))
            except Exception as e:
                print(f"获取缓存信息失败: {e}")

            # 显示OSM归属信息
            # attribution = "© OpenStreetMap contributors"
            # attribution_surface = self.font.render(attribution, True, (0, 0, 0))
            # self.screen.blit(
            #     attribution_surface,
            #     (self.width - attribution_surface.get_width() - 10, self.height - 30),
            # )

            # # 添加修复地图链接提示
            # fix_map_text = "发现错误? 访问 openstreetmap.org/fixthemap"
            # fix_map_surface = self.font.render(fix_map_text, True, (0, 0, 0))
            # self.screen.blit(fix_map_surface, (10, self.height - 30))

        except Exception as e:
            # 如果渲染过程中出现任何错误，显示错误信息
            self.screen.fill((255, 255, 255))
            error_text = f"渲染地图时出错: {e}"
            error_surface = self.font.render(error_text, True, (255, 0, 0))
            self.screen.blit(error_surface, (10, 10))

            # 显示详细错误信息
            import traceback

            error_details = traceback.format_exc()
            print(f"详细错误信息:\n{error_details}")

            # 尝试显示错误详情的前几行
            lines = error_details.split("\n")[:3]
            y_pos = 40
            for line in lines:
                if line.strip():
                    detail_surface = self.font.render(line[:80], True, (255, 0, 0))
                    self.screen.blit(detail_surface, (10, y_pos))
                    y_pos += 25

            help_text = "press ESC to quit"
            help_surface = self.font.render(help_text, True, (0, 0, 0))
            self.screen.blit(help_surface, (10, y_pos + 10))

    def handle_input(self):
        """处理用户输入"""
        # 记录移动前的位置，用于检测是否需要刷新地图
        old_lat = self.lat
        old_lon = self.lon
        old_zoom = self.zoom
        position_changed = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    # 放大地图
                    self.zoom = min(19, self.zoom + 1)
                    position_changed = True
                elif event.key == pygame.K_MINUS:
                    # 缩小地图
                    self.zoom = max(0, self.zoom - 1)
                    position_changed = True
                elif event.key == pygame.K_SPACE:
                    # 按空格键刷新地图
                    print("刷新地图: 清除瓦片缓存并重新获取当前位置的地图数据")
                    # 清除内存中的瓦片缓存
                    self.tile_cache.clear()
                    position_changed = True

        # 处理持续按下的键
        keys = pygame.key.get_pressed()
        move_factor = self.move_step * (
            2 ** (15 - self.zoom)
        )  # 根据缩放级别调整移动步长

        # 同时支持WASD键和方向键
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.lat += move_factor
            position_changed = True
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.lat -= move_factor
            position_changed = True
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.lon -= move_factor
            position_changed = True
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.lon += move_factor
            position_changed = True

        # 限制纬度范围
        self.lat = max(-85.0511, min(85.0511, self.lat))

        # 如果位置发生变化，记录日志并预加载新区域的瓦片
        if position_changed and (
            old_lat != self.lat or old_lon != self.lon or old_zoom != self.zoom
        ):
            # 打印位置变化信息，帮助调试
            print(
                f"位置变化: 经度 {old_lon:.6f}->{self.lon:.6f}, 纬度 {old_lat:.6f}->{self.lat:.6f}, 缩放 {old_zoom}->{self.zoom}"
            )
            # 预加载新位置周围的瓦片
            self.preload_tiles_around_current_position()

        return True

    def run(self):
        """运行地图查看器"""
        try:
            print("正在启动OpenStreetMap查看器...")
            print(
                f"初始位置: 经度={self.lon:.4f}, 纬度={self.lat:.4f}, 缩放级别={self.zoom}"
            )
            print("缓存目录: ", self.cache_dir)

            # 确保pygame正确初始化
            if not pygame.get_init():
                pygame.init()
                print("重新初始化pygame")

            # 确保显示模式正确设置
            if self.screen is None or self.screen.get_size() != (
                self.width,
                self.height,
            ):
                self.screen = pygame.display.set_mode((self.width, self.height))
                print(f"重新设置显示模式: {self.width}x{self.height}")

            # 初始化时预加载周围瓦片
            self.preload_tiles_around_current_position()
            print("初始瓦片预加载完成")

            running = True
            frame_count = 0
            start_time = pygame.time.get_ticks()

            while running:
                # 处理输入
                running = self.handle_input()

                # 渲染地图
                self.render_map()

                # 更新显示
                pygame.display.flip()

                # 限制帧率
                self.clock.tick(30)  # 限制帧率为30FPS

                # 计算实际帧率
                frame_count += 1
                if frame_count % 30 == 0:  # 每30帧显示一次帧率
                    current_time = pygame.time.get_ticks()
                    elapsed = (current_time - start_time) / 1000.0
                    fps = frame_count / elapsed if elapsed > 0 else 0
                    print(f"当前帧率: {fps:.1f} FPS")
                    frame_count = 0
                    start_time = current_time

            print("正常退出程序")
        except Exception as e:
            print(f"运行时发生错误: {e}")
        finally:
            # 确保pygame正确退出
            pygame.quit()
            print("pygame已退出")


def main():
    """主函数"""
    viewer = OpenStreetMapViewer(800, 600)
    viewer.run()


if __name__ == "__main__":
    main()
