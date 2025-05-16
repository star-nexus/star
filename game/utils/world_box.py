import pygame
import random
import math

# 初始化
pygame.init()
screen = pygame.display.set_mode((800, 600))
clock = pygame.time.Clock()

# 游戏状态
running = True
current_tool = "terrain"
simulation_speed = 1.0

# 颜色定义
COLORS = {
    "water": (30, 144, 255),
    "grass": (34, 139, 34),
    "mountain": (139, 137, 137),
    "human": (255, 215, 0),
    "animal": (139, 69, 19),
    "lava": (255, 69, 0),
}

# 地形生成
WORLD_SIZE = (40, 30)  # 网格数量
CELL_SIZE = 20  # 每个网格的像素大小

# 生成随机地形（简化版）
world_grid = []
for y in range(WORLD_SIZE[1]):
    row = []
    for x in range(WORLD_SIZE[0]):
        noise = random.random()
        if noise < 0.3:
            row.append("water")
        elif noise < 0.8:
            row.append("grass")
        else:
            row.append("mountain")
    world_grid.append(row)

# 生物系统
entities = []


class Entity:
    def __init__(self, etype, pos):
        self.type = etype
        self.pos = list(pos)
        self.health = 100
        self.speed = random.uniform(0.5, 2.0)
        self.target = None

    def update(self):
        # 简单AI：随机移动
        if self.target is None or random.random() < 0.02:
            self.target = (
                self.pos[0] + random.uniform(-5, 5),
                self.pos[1] + random.uniform(-5, 5),
            )

        dx = self.target[0] - self.pos[0]
        dy = self.target[1] - self.pos[1]
        dist = math.hypot(dx, dy)

        if dist > 0:
            self.pos[0] += dx / dist * self.speed
            self.pos[1] += dy / dist * self.speed

        # 保持在地图范围内
        self.pos[0] = max(0, min(WORLD_SIZE[0] * CELL_SIZE - 5, self.pos[0]))
        self.pos[1] = max(0, min(WORLD_SIZE[1] * CELL_SIZE - 5, self.pos[1]))


# 工具系统
def use_tool(pos):
    global world_grid, entities
    grid_x = pos[0] // CELL_SIZE
    grid_y = pos[1] // CELL_SIZE

    if 0 <= grid_x < WORLD_SIZE[0] and 0 <= grid_y < WORLD_SIZE[1]:
        if current_tool == "terrain":
            world_grid[grid_y][grid_x] = "grass"
        elif current_tool == "water":
            world_grid[grid_y][grid_x] = "water"
        elif current_tool == "mountain":
            world_grid[grid_y][grid_x] = "mountain"
        elif current_tool == "human":
            entities.append(Entity("human", pos))
        elif current_tool == "animal":
            entities.append(Entity("animal", pos))
        elif current_tool == "lava":
            world_grid[grid_y][grid_x] = "lava"


# 游戏主循环
while running:
    # 处理输入
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()
            use_tool(mouse_pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_1:
                current_tool = "terrain"
            elif event.key == pygame.K_2:
                current_tool = "water"
            elif event.key == pygame.K_3:
                current_tool = "mountain"
            elif event.key == pygame.K_4:
                current_tool = "human"
            elif event.key == pygame.K_5:
                current_tool = "animal"
            elif event.key == pygame.K_6:
                current_tool = "lava"

    # 更新游戏状态
    for _ in range(int(simulation_speed)):
        for entity in entities:
            entity.update()

    # 绘制世界
    screen.fill((0, 0, 0))

    # 绘制地形
    for y in range(WORLD_SIZE[1]):
        for x in range(WORLD_SIZE[0]):
            rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(screen, COLORS[world_grid[y][x]], rect)

    # 绘制生物
    for entity in entities:
        color = COLORS[entity.type]
        pygame.draw.circle(screen, color, (int(entity.pos[0]), int(entity.pos[1])), 5)

    # 绘制UI
    font = pygame.font.Font(None, 24)
    tools = [
        "1: Grass Tool",
        "2: Water Tool",
        "3: Mountain Tool",
        "4: Human Tool",
        "5: Animal Tool",
        "6: Lava Tool",
    ]
    for i, text in enumerate(tools):
        surf = font.render(text, True, (255, 255, 255))
        screen.blit(surf, (10, 10 + i * 20))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
