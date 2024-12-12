import numpy as np
import random

def generate_map_data(size=50):
    # Step 1: Initialize all cells as 'plain'
    map_data = np.full((size, size), "plain", dtype=object)
    
    # Step 2: Add water as a polyline
    water_start = random.randint(0, size - 1)
    for i in range(size):
        map_data[i, water_start] = "river"
        # Randomly meander the waterline slightly
        if random.random() > 0.7:
            water_start = max(0, min(size - 1, water_start + random.choice([-1, 1])))
    
    # Step 3: Add mountains with verified placement
    num_mountain_clusters = random.randint(6, 10)
    for cluster in range(num_mountain_clusters):
        cluster_y = random.randint(0, size - 1)
        cluster_x = random.randint(0, size - 1)
        
        # Create more concentrated mountain clusters
        mountain_count = random.randint(5, 15)
        for _ in range(mountain_count):
            spread = 2  # Reduce spread for more concentrated clusters
            y = max(0, min(size - 1, cluster_y + random.randint(-spread, spread)))
            x = max(0, min(size - 1, cluster_x + random.randint(-spread, spread)))
            
            # Only place mountain if location is plain
            if map_data[y, x] == "plain":
                map_data[y, x] = "mountain"
    
    # Step 4: Add cities (only on plains)
    num_cities = random.randint(5, 10)
    cities_placed = 0
    max_attempts = num_cities * 3  # Prevent infinite loop
    attempts = 0
    
    while cities_placed < num_cities and attempts < max_attempts:
        y = random.randint(0, size - 1)
        x = random.randint(0, size - 1)
        if map_data[y, x] == "plain":
            map_data[y, x] = "city"
            cities_placed += 1
        attempts += 1
    
    # Step 5: Add soldier units for both forces
    force_types = ['ping', 'shui', 'shan']
    forces = {
        'R': [],  # Red force positions
        'W': []   # White force positions
    }
    
    # Place units for each force
    for force in ['R', 'W']:
        units_placed = 0
        max_unit_attempts = 50  # Prevent infinite loop
        unit_attempts = 0
        
        while units_placed < 3 and unit_attempts < max_unit_attempts:
            y = random.randint(0, size - 1)
            x = random.randint(0, size - 1)
            
            # Only place units on plain terrain and away from other units
            if map_data[y, x] == "plain" and all(
                abs(pos[0] - y) + abs(pos[1] - x) > 2  # Manhattan distance > 2
                for pos in forces['R'] + forces['W']
            ):
                unit_type = force_types[units_placed]  # Each force gets one of each type
                map_data[y, x] = f"{force}_{unit_type}"  # e.g., "R_shan" or "W_shui"
                forces[force].append((y, x))
                units_placed += 1
            unit_attempts += 1
    
    # Verify the map contains all terrain types
    unique, counts = np.unique(map_data, return_counts=True)
    print("Generated map distribution:", dict(zip(unique, counts)))
    
    return map_data
