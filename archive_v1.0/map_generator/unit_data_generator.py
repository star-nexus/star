import numpy as np
import random


def generate_unit_data(map_data, r_unit_count, w_unit_count):

    size = map_data.shape[0]
    unit_data = np.full((size, size), None, dtype=object)
    force_types = ["ping", "shui", "shan"]
    forces_positions = {"R": [], "W": []}

    def place_units_for_force(force, unit_count):
        units_placed = 0
        max_unit_attempts = 50
        unit_attempts = 0

        while units_placed < unit_count and unit_attempts < max_unit_attempts:
            y = random.randint(0, size - 1)
            x = random.randint(0, size - 1)

            if map_data[y, x] == "plain" and all(
                abs(pos[0] - y) + abs(pos[1] - x) > 2
                for pos in forces_positions["R"] + forces_positions["W"]
            ):
                unit_type = force_types[units_placed % len(force_types)]
                unit_data[y, x] = f"{force}_{unit_type}"
                forces_positions[force].append((y, x))
                units_placed += 1
            unit_attempts += 1

    place_units_for_force("R", r_unit_count)
    place_units_for_force("W", w_unit_count)

    return unit_data
