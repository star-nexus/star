import pygame
import sys
from pathlib import Path

class Unit(pygame.sprite.Sprite):
    # Class constants
    TILE_SIZE = (32, 32)
    POWER_FONT_SIZE = 26
    POWER_MARGIN = 0
    BORDER_WIDTH = 1
    BORDER_COLOR = (0, 0, 0)
    BACKGROUND_COLOR = (255, 255, 255)
    
    def __init__(self, x: int, y: int, soldier_count: int):
        """
        Initialize a Unit sprite.
        
        Args:
            x (int): X coordinate of the unit
            y (int): Y coordinate of the unit
            soldier_count (int): Number of soldiers in the unit
        """
        super().__init__()
        self._initialize_attributes(soldier_count)
        self._load_resources()
        self._create_surface(x, y)
        self.update_text()

    def _initialize_attributes(self, soldier_count: int) -> None:
        """Initialize basic unit attributes."""
        self.soldier_count = soldier_count
        self.power = soldier_count // 1000

        self.unit_type = ""

    def _load_resources(self) -> None:
        """Load and initialize all required resources."""
        self._load_font()
        self._load_image()

    def _load_font(self) -> None:
        """Load the font for power number display."""
        try:
            self.font = pygame.font.SysFont('Microsoft_YaHei', self.POWER_FONT_SIZE)
        except pygame.error as e:
            raise Exception(f"Could not load font: {e}")

    def _load_image(self) -> None:
        """Load the mountain character image."""
        image_path = Path("map_generator/map_tiles/shui.png")
        try:
            self.mountain_image = pygame.image.load(str(image_path)).convert_alpha()
        except (pygame.error, FileNotFoundError) as e:
            raise Exception(f"Could not load mountain image at {image_path}: {e}")

    def _create_surface(self, x: int, y: int) -> None:
        """Create and initialize the unit's surface."""
        self.image = pygame.Surface(self.TILE_SIZE)
        self.rect = self.image.get_rect()
        self.rect.topleft = (x, y)

    def update_text(self) -> None:
        """Update the unit's visual representation."""
        self._clear_surface()
        self._draw_border()
        self._draw_power_number()
        self._draw_mountain_image()

    def _clear_surface(self) -> None:
        """Clear the surface with background color."""
        self.image.fill(self.BACKGROUND_COLOR)

    def _draw_border(self) -> None:
        """Draw border around the tile."""
        pygame.draw.rect(
            self.image,
            self.BORDER_COLOR,
            self.image.get_rect(),
            self.BORDER_WIDTH
        )

    def _draw_power_number(self) -> None:
        """Draw the power number in the top-right corner."""
        power_surface = self.font.render(str(self.power), True, self.BORDER_COLOR)
        power_rect = power_surface.get_rect()
        power_rect.topright = (self.TILE_SIZE[0] - self.POWER_MARGIN, self.POWER_MARGIN)
        self.image.blit(power_surface, power_rect)

    def _draw_mountain_image(self) -> None:
        """Draw the mountain image in the bottom half of the tile."""
        # Calculate dimensions for bottom half
        new_width = self.TILE_SIZE[0]
        new_height = self.TILE_SIZE[1] // 2

        # Scale the mountain image
        try:
            scaled_mountain = pygame.transform.smoothscale(
                self.mountain_image,
                (new_width, new_height)
            )
        except pygame.error:
            scaled_mountain = pygame.transform.scale(
                self.mountain_image,
                (new_width, new_height)
            )

        # Position at bottom
        mountain_rect = scaled_mountain.get_rect()
        mountain_rect.bottomleft = (0, self.TILE_SIZE[1])
        self.image.blit(scaled_mountain, mountain_rect)

    def set_soldier_count(self, new_soldier_count: int) -> None:
        """
        Update the unit's soldier count and power.
        
        Args:
            new_soldier_count (int): New number of soldiers
        """
        self.soldier_count = new_soldier_count
        self.power = self.soldier_count // 1000
        self.update_text()


def main():
    """Main game loop."""
    pygame.init()
    screen = pygame.display.set_mode((25*32, 25*32))
    clock = pygame.time.Clock()
    
    all_units = pygame.sprite.Group()
    unit_a = Unit(10*32, 10*32, 10000)
    all_units.add(unit_a)

    running = True
    while running:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                unit_a.set_soldier_count(6000)

        screen.fill((0, 128, 0))
        all_units.draw(screen)
        pygame.display.flip()
    
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()