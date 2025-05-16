import numpy as np
import random

from .game_types import TerrainType


def generate_map_data(size) -> np.ndarray:
    # Initialize all cells as 'plain'
    map_data = np.full((size, size), TerrainType.PLAIN.value, dtype=object)

    # Step 2: Add water as a polyline (river)
    water_start = random.randint(0, size - 1)
    river_positions = []  # 用于记录river的坐标
    for i in range(size):
        map_data[i, water_start] = TerrainType.RIVER.value
        river_positions.append((i, water_start))
        if random.random() > 0.7:
            water_start = max(0, min(size - 1, water_start + random.choice([-1, 1])))

    # Add mountains with verified placement
    # 20% * size
    num_mountain_clusters = random.randint(int(0.2 * size), int(0.3 * size))
    for cluster in range(num_mountain_clusters):
        cluster_y = random.randint(0, size - 1)
        cluster_x = random.randint(0, size - 1)

        # Create more concentrated mountain clusters
        # 30% * size
        mountain_count = random.randint(int(1 * size), int(2 * size))
        for _ in range(mountain_count):
            spread = 2  # Reduce spread for more concentrated clusters
            y = max(0, min(size - 1, cluster_y + random.randint(-spread, spread)))
            x = max(0, min(size - 1, cluster_x + random.randint(-spread, spread)))

            # Only place mountain if location is plain
            if map_data[y, x] == TerrainType.PLAIN.value:
                map_data[y, x] = TerrainType.MOUNTAIN.value

    # Add cities (only on plains)
    # 10% * size
    num_cities = random.randint(int(0.1 * size), int(0.5 * size))
    cities_placed = 0
    max_attempts = num_cities * 3  # Prevent infinite loop
    attempts = 0

    while cities_placed < num_cities and attempts < max_attempts:
        y = random.randint(0, size - 1)
        x = random.randint(0, size - 1)
        if map_data[y, x] == TerrainType.PLAIN.value:
            map_data[y, x] = TerrainType.CITY.value
            cities_placed += 1
        attempts += 1

    # Step 4.1: Add forest clusters with enhanced natural distribution
    # 30% * size
    num_forest_clusters = random.randint(int(0.2 * size), int(0.4 * size))
    for cluster in range(num_forest_clusters):
        cluster_y = random.randint(0, size - 1)
        cluster_x = random.randint(0, size - 1)

        # Increased forest count for denser forests
        # 40% * size
        forest_count = random.randint(int(1 * size), int(2 * size))

        # Use probability distribution for more natural-looking clusters
        for _ in range(forest_count):
            for attempt in range(3):  # Multiple attempts to place each forest tile
                # Gaussian-like distribution for more natural spread
                dx = int(random.gauss(0, 2))  # Standard deviation of 2
                dy = int(random.gauss(0, 2))

                x = max(0, min(size - 1, cluster_x + dx))
                y = max(0, min(size - 1, cluster_y + dy))

                # Check for nearby forests to encourage clustering
                nearby_forests = 0
                for ny in range(max(0, y - 1), min(size, y + 2)):
                    for nx in range(max(0, x - 1), min(size, x + 2)):
                        if map_data[ny, nx] == TerrainType.FOREST.value:
                            nearby_forests += 1

                # Higher chance to place forest if there are nearby forests
                if map_data[y, x] == TerrainType.PLAIN.value and (
                    nearby_forests > 0 or random.random() < 0.7
                ):
                    map_data[y, x] = TerrainType.FOREST.value
                    break

    # Step 4.5: Add bridges on river
    # 至少一个，最多三个桥
    # 30%
    num_bridges = random.randint(int(0.15 * size), int(0.2 * size))
    if len(river_positions) > 0:
        chosen_bridges = random.sample(
            river_positions, min(num_bridges, len(river_positions))
        )
        for by, bx in chosen_bridges:
            # 将river转换为bridge
            # 前提：bridge也是一种地形类型，需要在地图渲染时支持
            map_data[by, bx] = TerrainType.BRIDGE.value
    return map_data


# 10

# 桥 1-3      30%
# 森林 4-8     20%
# 城市 1-2     10%
# 平原 10-30   50%
# 山脉 6-10    5%
# 河流 1-5     10%

# 50
