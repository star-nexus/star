import numpy as np
from PIL import Image
import os
import random
from map_data_generator import generate_map_data

class MapGenerator:
    def __init__(self, width, height, image_dir="map_tiles"):
        """Initialize map generator with dimensions and image directory"""
        self.width = width
        self.height = height
        self.image_dir = image_dir
        self.place_types = [
            "mountain", "river", "plain", "city",
            "R_ping", "R_shui", "R_shan",
            "W_ping", "W_shui", "W_shan"
        ]
        self.tile_images = self._load_tile_images()
        self.tile_size = 32  # Default tile size in pixels

    def _load_tile_images(self):
        """Load tile images from directory"""
        tile_images = {}
        for place_type in self.place_types:
            image_path = os.path.join(self.image_dir, f"{place_type}.jpg")
            try:
                img = Image.open(image_path)
                tile_images[place_type] = img
            except FileNotFoundError:
                print(f"Warning: Image for {place_type} not found at {image_path}")
        return tile_images

    def generate_map_matrix(self):
        """Generate random map matrix with place types"""
        # Initialize empty matrix
        map_matrix = np.empty((self.height, self.width), dtype='object')
        
        # Probability weights for different place types
        weights = {
            "mountain": 0.2,
            "river": 0.3,
            "plain": 0.4,
            "city": 0.1
        }
        
        # Fill matrix with random place types
        for i in range(self.height):
            for j in range(self.width):
                map_matrix[i][j] = random.choices(
                    self.place_types, 
                    weights=[weights[pt] for pt in self.place_types]
                )[0]
                
        return map_matrix

    def create_map_image(self, map_matrix):
        """Create final map image by stitching tiles together"""
        # Calculate final image dimensions
        final_width = self.width * self.tile_size
        final_height = self.height * self.tile_size
        
        # Create blank image
        final_image = Image.new('RGB', (final_width, final_height))
        
        # Paste tiles according to map matrix
        for i in range(self.height):
            for j in range(self.width):
                place_type = map_matrix[i][j]
                if place_type in self.tile_images:
                    tile = self.tile_images[place_type]
                    # Calculate position to paste tile
                    x = j * self.tile_size
                    y = i * self.tile_size
                    final_image.paste(tile, (x, y))
        
        return final_image

    def generate_map(self):
        """Main method to generate complete map"""
        # Generate random map matrix
        # map_matrix = self.generate_map_matrix()

        map_matrix = generate_map_data(self.width)
        
        # Update debug print to show all types including forces
        unique, counts = np.unique(map_matrix, return_counts=True)
        print("Map distribution:", dict(zip(unique, counts)))
        
        return self.create_map_image(map_matrix)


# Example usage:
if __name__ == "__main__":
    # Create map generator for 50x50 map
    generator = MapGenerator(25, 25)
    
    # Generate map
    map_image = generator.generate_map()
    
    # Save the generated map
    map_image.save("generated_map.png")
