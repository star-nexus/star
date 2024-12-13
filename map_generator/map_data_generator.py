import numpy as np
import random


def generate_map_data(size=50, r_units=3, w_units=3):
    # Step 1: Initialize all cells as 'plain'
    map_data = np.full((size, size), "plain", dtype=object)

    # Step 2: Add water as a polyline (river)
    water_start = random.randint(0, size - 1)
    river_positions = []  # 用于记录river的坐标
    for i in range(size):
        map_data[i, water_start] = "river"
        river_positions.append((i, water_start))
        if random.random() > 0.7:
            water_start = max(0, min(size - 1, water_start + random.choice([-1, 1])))

    # Step 3: Add mountains
    num_mountain_clusters = random.randint(6, 10)
    for cluster in range(num_mountain_clusters):
        cluster_y = random.randint(0, size - 1)
        cluster_x = random.randint(0, size - 1)
        mountain_count = random.randint(5, 15)
        for _ in range(mountain_count):
            spread = 2
            y = max(0, min(size - 1, cluster_y + random.randint(-spread, spread)))
            x = max(0, min(size - 1, cluster_x + random.randint(-spread, spread)))
            if map_data[y, x] == "plain":
                map_data[y, x] = "mountain"

    # Step 4: Add cities
    num_cities = random.randint(5, 10)
    cities_placed = 0
    max_attempts = num_cities * 3
    attempts = 0

    while cities_placed < num_cities and attempts < max_attempts:
        y = random.randint(0, size - 1)
        x = random.randint(0, size - 1)
        if map_data[y, x] == "plain":
            map_data[y, x] = "city"
            cities_placed += 1
        attempts += 1

    # Step 4.1: Add forests
    # 随机生成一定数量的森林，如随机10~30个分布
    num_forests = random.randint(10, 30)
    forest_attempts = 0
    while num_forests > 0 and forest_attempts < num_forests * 3:
        fy = random.randint(0, size - 1)
        fx = random.randint(0, size - 1)
        if map_data[fy, fx] == "plain":
            map_data[fy, fx] = "forest"
            num_forests -= 1
        forest_attempts += 1

    # Step 4.5: Add bridges on river
    # 至少一个，最多三个桥
    num_bridges = random.randint(1, 3)
    if len(river_positions) > 0:
        chosen_bridges = random.sample(
            river_positions, min(num_bridges, len(river_positions))
        )
        for by, bx in chosen_bridges:
            # 将river转换为bridge
            # 前提：bridge也是一种地形类型，需要在地图渲染时支持
            map_data[by, bx] = "bridge"

    # 此时 map_data 全为环境数据（包含plain、river、mountain、city、bridge 等）。
    # 我们将其复制为 environment_map
    environment_map = map_data.copy()

    # Step 5: Add soldier units on a separate unit_map
    unit_map = np.full((size, size), None, dtype=object)
    force_types = ["ping", "shui", "shan"]
    forces_positions = {"R": [], "W": []}

    # 定义放置单位的函数
    def place_units_for_force(force, unit_count):
        units_placed = 0
        max_unit_attempts = 50
        unit_attempts = 0

        while units_placed < unit_count and unit_attempts < max_unit_attempts:
            y = random.randint(0, size - 1)
            x = random.randint(0, size - 1)

            # 根据规则，只在plain地形上放置单位（若有其他规则，可自行扩展）
            # 并确保与已放置单位保持一定距离
            if environment_map[y, x] == "plain" and all(
                abs(pos[0] - y) + abs(pos[1] - x) > 2
                for pos in forces_positions["R"] + forces_positions["W"]
            ):
                unit_type = force_types[units_placed % len(force_types)]
                # 这里假设不要求严格顺序地分配 ping、shui、shan，
                # 但如果要求每个势力仍有 ping、shui、shan 三类单位，
                # 而且数量 > 3，需要重新定义逻辑。
                # 暂时保持最初逻辑：前3个为ping、shui、shan
                unit_map[y, x] = f"{force}_{unit_type}"
                forces_positions[force].append((y, x))
                units_placed += 1
            unit_attempts += 1

    # 按指定数量为 R 和 W 部署单位
    place_units_for_force("R", r_units)
    place_units_for_force("W", w_units)

    return environment_map, unit_map
