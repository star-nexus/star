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

    # Step 4.1: Add forest clusters with enhanced natural distribution
    num_forest_clusters = random.randint(4, 8)
    for cluster in range(num_forest_clusters):
        cluster_y = random.randint(0, size - 1)
        cluster_x = random.randint(0, size - 1)
        
        # Increased forest count for denser forests
        forest_count = random.randint(15, 25)
        
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
                for ny in range(max(0, y-1), min(size, y+2)):
                    for nx in range(max(0, x-1), min(size, x+2)):
                        if map_data[ny, nx] == "forest":
                            nearby_forests += 1
                
                # Higher chance to place forest if there are nearby forests
                if map_data[y, x] == "plain" and (nearby_forests > 0 or random.random() < 0.7):
                    map_data[y, x] = "forest"
                    break

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


    return map_data