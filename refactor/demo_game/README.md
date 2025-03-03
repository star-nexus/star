# Demo Game

A simple game built on an Entity-Component-System architecture to demonstrate game development patterns and practices.

## Overview

This demo game implements a basic chase mechanic where the player (blue circle) can be chased by an enemy (red circle). The player needs to gain enough speed and collide with the enemy to win. Gray obstacles provide collision mechanics with bounce effects.

## Architecture

The game is built using an ECS (Entity-Component-System) architecture with a comprehensive engine framework. See [Arch.md](Arch.md) for a detailed architectural overview.

## How to Run

1. Ensure you have Python 3.12+ and Pygame installed
   ```
   pip install pygame
   ```

2. Run the main script
   ```
   python main.py
   ```

## Game Controls

- **Menu**: Press SPACE to start the game
- **Game**:
  - Arrow keys to control the player movement
  - Build up enough speed to defeat the enemy by colliding with it
- **Game Over**: Press R to return to the menu

## Key Components

### ECS Framework

- **Entities**: Simple identifiers (player, enemy, obstacles)
- **Components**: Data containers (Position, Velocity, Collider, etc.)
- **Systems**: Logic modules (MovementSystem, CollisionSystem, etc.)

### Manager Subsystems

- **EventManager**: Handles communication between systems
- **InputManager**: Processes player input
- **RenderManager**: Handles drawing operations
- **SceneManager**: Controls game flow and scene transitions
- **ResourceManager**: Loads and manages game assets
- **AudioManager**: Handles sound effects and music

### Game Scenes

- **MenuScene**: Title screen
- **GameScene**: Main gameplay area
- **GameOverScene**: Victory or defeat screen

## Game Logic

1. The player needs to navigate around obstacles
2. The enemy constantly follows the player
3. The player wins by colliding with the enemy while moving fast
4. Obstacles cause entities to bounce on collision
5. Collisions trigger visual glow effects

## Project Structure

```
demo_game/
├── framework/
│   ├── core/
│   │   ├── ecs/            # Entity-Component-System implementation
│   │   └── engine/         # Game engine implementation
│   └── managers/           # Game subsystem managers
│       ├── ui/             # User interface framework
│       ├── audio.py        # Audio management
│       ├── events.py       # Event system
│       ├── inputs.py       # Input handling
│       ├── renders.py      # Rendering pipeline
│       ├── resources.py    # Asset management
│       └── scenes.py       # Scene management
├── game/
│   ├── components.py       # Game-specific components
│   ├── managers.py         # Game-specific managers
│   ├── menu_scenes.py      # Menu and game over scenes
│   ├── scenes.py           # Main game scene
│   └── systems.py          # Game-specific systems
├── main.py                 # Entry point
├── README.md               # This file
└── Arch.md                 # Architecture documentation
```

## Implementation Details

1. **Physics**: Simple circular collision detection with basic bounce physics
2. **AI**: Enemy follows the player using vector normalization
3. **UI**: Basic text rendering for menus and game state
4. **Scene Transitions**: Smooth fade effects between game scenes
5. **Event System**: Publish-subscribe pattern for game events

## Extending the Game

This demo provides a foundation that can be extended in numerous ways:

1. Add more enemy types with different behaviors
2. Implement power-ups and special abilities
3. Create additional levels with different obstacle layouts
4. Add scoring and progression systems
5. Enhance visuals with particle effects and animations

## Credits

This demo game was created as an educational project to demonstrate game architecture concepts and patterns.