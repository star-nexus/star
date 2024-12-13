import pygame


class UnitController:
    def __init__(self, environment_map, unit_map, tile_size=32):
        self.environment_map = environment_map  # 不变的地形地图
        self.unit_map = unit_map  # 存储单位位置的地图，与环境分离
        self.tile_size = tile_size

        self.selected_unit_index = 0
        self.units_positions = []  # 存所有单位的位置和类型 [(y, x, type), ...]
        self._find_all_units()

    def _find_all_units(self):
        # 扫描unit_map找出所有单位
        h, w = self.unit_map.shape
        for i in range(h):
            for j in range(w):
                if self.unit_map[i][j] is not None:  # 如果这个格子有单位
                    self.units_positions.append((i, j, self.unit_map[i][j]))

    def select_unit_by_index(self, index):
        if 0 <= index < len(self.units_positions):
            self.selected_unit_index = index

    def select_unit_by_mouse(self, mouse_pos):
        # 根据鼠标点击位置选择单位
        # mouse_pos是屏幕坐标，需要转换为格子坐标
        grid_x = mouse_pos[0] // self.tile_size
        grid_y = mouse_pos[1] // self.tile_size
        # 检查点击位置是否有单位
        for idx, (uy, ux, utype) in enumerate(self.units_positions):
            if uy == grid_y and ux == grid_x:
                self.selected_unit_index = idx
                break

    @property
    def selected_unit(self):
        if self.units_positions:
            return self.units_positions[self.selected_unit_index]
        return None

    def move_unit(self, direction):
        # direction: 'up', 'down', 'left', 'right'
        if not self.units_positions:
            return

        y, x, utype = self.units_positions[self.selected_unit_index]

        new_y, new_x = y, x
        if direction == "up":
            new_y -= 1
        elif direction == "down":
            new_y += 1
        elif direction == "left":
            new_x -= 1
        elif direction == "right":
            new_x += 1

        # 检查边界
        h, w = self.environment_map.shape
        if not (0 <= new_y < h and 0 <= new_x < w):
            return  # 越界，不移动

        # 检查能否进入该地形
        terrain = self.environment_map[new_y][new_x]
        if self.can_enter(utype, terrain):
            # 更新unit_map
            self.unit_map[y][x] = None
            self.unit_map[new_y][new_x] = utype
            # 更新unit位置列表
            self.units_positions[self.selected_unit_index] = (new_y, new_x, utype)

    def can_enter(self, unit_type, terrain):
        # unit_type: R_ping, R_shui, R_shan, W_ping, W_shui, W_shan
        # 根据类型解析出 ping/shui/shan
        force, u_kind = unit_type.split("_", 1)
        # 所有单位都可进入 city, plain, forest
        if terrain in ["city", "plain", "forest"]:
            return True
        if u_kind == "shan" and terrain in ["mountain"]:
            return True
        if u_kind == "shui" and terrain in ["river"]:
            return True
        # 如果不符合规则则无法进入
        return False
