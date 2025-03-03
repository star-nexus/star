from rts.components import (
    PositionComponent,
    SpriteComponent,
    FactionComponent,
)


class RTSEntityManager:
    """
    RTS Game Entity Manager: Responsible for creating, managing and rendering game entities
    """

    def __init__(self, scene):
        self.scene = scene
        self.game = scene.game
        self.resource_nodes = []
        self.entities_to_remove = []
        self.buildings = []
        self.units = []

    def update(self, delta_time):
        """Update entity manager"""
        # Process entities to remove
        for entity in self.entities_to_remove:
            if entity.id in self.game.world.entities:
                self.game.world.destroy_entity(entity.id)
        self.entities_to_remove.clear()

    def render_resource_nodes(self, screen):
        """Render resource nodes"""
        for node in self.resource_nodes:
            if node.has_component(PositionComponent) and node.has_component(
                SpriteComponent
            ):
                pos = node.get_component(PositionComponent)
                sprite = node.get_component(SpriteComponent)

                # Convert map position to screen position
                if self.scene.map_manager and self.scene.map_manager.map_renderer:
                    # Get the actual position on screen considering map view offset
                    screen_x, screen_y = self.scene.map_manager.map_to_screen(
                        pos.x, pos.y
                    )

                    # Now draw at the screen position
                    import pygame

                    color = (255, 215, 0)  # Gold color for resources
                    pygame.draw.rect(
                        screen,
                        color,
                        pygame.Rect(screen_x, screen_y, 24, 24),
                        border_radius=5,
                    )

    def render_entities(self, screen):
        """Render all entities with position and sprite components"""
        # Collect all entities to render
        render_entities = []

        # Find all entities with position and sprite components
        for entity_id, entity in self.game.world.entities.items():
            if entity.has_component(PositionComponent) and entity.has_component(
                SpriteComponent
            ):
                # Skip resource nodes as they are rendered separately
                if entity in self.resource_nodes:
                    continue
                render_entities.append(entity)

        # Sort by y-coordinate for proper depth rendering (entities lower on screen appear in front)
        render_entities.sort(key=lambda e: e.get_component(PositionComponent).y)

        # Render each entity
        for entity in render_entities:
            self._render_entity(screen, entity)

    def _render_entity(self, screen, entity):
        """Render a single entity"""
        pos = entity.get_component(PositionComponent)
        sprite = entity.get_component(SpriteComponent)

        # Skip if sprite is not visible
        if not sprite.is_visible:
            return

        # Convert world position to screen position
        screen_x, screen_y = self.scene.map_manager.map_to_screen(pos.x, pos.y)

        # Get the image
        image_name = sprite.image_name
        image = self.game.resources.get_image(image_name)

        if image:
            screen.blit(image, (screen_x, screen_y))
        else:
            # Fallback if image not found - draw colored rectangle
            import pygame

            color = (200, 100, 100)  # Default red

            # Use faction color if available
            if entity.has_component(FactionComponent):
                faction = entity.get_component(FactionComponent)
                color = faction.faction_color

            pygame.draw.rect(
                screen,
                color,
                pygame.Rect(screen_x, screen_y, sprite.width, sprite.height),
            )

            # Draw border
            pygame.draw.rect(
                screen,
                (255, 255, 255),
                pygame.Rect(screen_x, screen_y, sprite.width, sprite.height),
                1,
            )

    def mark_entity_for_removal(self, entity):
        """Mark entity for removal"""
        self.entities_to_remove.append(entity)

    def set_resource_nodes(self, nodes):
        """Set resource nodes list"""
        self.resource_nodes = nodes
