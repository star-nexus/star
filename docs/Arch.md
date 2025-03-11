# Demo Game Architecture Overview

This document provides a comprehensive overview of the architecture used in the Demo Game project. The game is built on a modular Entity-Component-System (ECS) architecture with additional supporting frameworks.

## System Architecture Diagram

```
+-------------------------------------------+
|                Game Engine                |
| +---------------+  +-------------------+  |
| | Core Systems  |  | Manager Subsystems|  |
| |               |  |                   |  |
| | +-----------+ |  | +--------------+  |  |
| | |    ECS    | |  | | SceneManager |  |  |
| | | +-------+ | |  | +--------------+  |  |
| | | |Entities| | |  | +--------------+  |  |
| | | +-------+ | |  | | EventManager  |  |  |
| | | +-------+ | |  | +--------------+  |  |
| | | |Components| |  | +--------------+  |  |
| | | +-------+ | |  | | InputManager  |  |  |
| | | +-------+ | |  | +--------------+  |  |
| | | |Systems | | |  | +--------------+  |  |
| | | +-------+ | |  | | RenderManager |  |  |
| | +-----------+ |  | +--------------+  |  |
| | +-----------+ |  | +--------------+  |  |
| | |   World   | |  | |ResourceManager|  |  |
| | +-----------+ |  | +--------------+  |  |
| +---------------+  | +--------------+  |  |
|                    | | AudioManager  |  |  |
|                    | +--------------+  |  |
|                    | +--------------+  |  |
|                    | |  UIManager   |  |  |
|                    | +--------------+  |  |
|                    +-------------------+  |
+-------------------------------------------+
            |                  |
    +---------------+  +------------------+
    | Game Scenes   |  | Game Systems     |
    | +-----------+ |  | +--------------+ |
    | | MenuScene | |  | |MovementSystem| |
    | +-----------+ |  | +--------------+ |
    | +-----------+ |  | +--------------+ |
    | | GameScene | |  | |PlayerControl | |
    | +-----------+ |  | +--------------+ |
    | +-----------+ |  | +--------------+ |
    | |GameOverScene|  | |EnemyAISystem | |
    | +-----------+ |  | +--------------+ |
    +---------------+  | +--------------+ |
                       | |CollisionSystem| |
                       | +--------------+ |
                       | +--------------+ |
                       | |  GlowSystem  | |
                       | +--------------+ |
                       | +--------------+ |
                       | | RenderSystem | |
                       | +--------------+ |
                       +------------------+
```

## Core Architecture Components

### 1. Entity-Component-System (ECS)

The game uses an ECS architecture to organize game objects and logic:

- **Entity**: Simple identifier representing a game object (player, enemy, obstacle)
- **Component**: Pure data containers that define object properties (Position, Velocity, Collider, etc.)
- **System**: Logic modules that process entities with specific combinations of components
- **World**: Central container that manages all entities, components, and systems

This approach separates data from behavior, enabling better code organization and performance optimization.

### 2. Manager Subsystems

Multiple specialized managers handle different aspects of the game:

- **EventManager**: Implements a publish-subscribe pattern for game-wide communication
- **InputManager**: Processes user input and generates appropriate events
- **RenderManager**: Handles drawing operations with layer-based rendering
- **SceneManager**: Manages scene transitions and lifecycle with smooth fade effects
- **ResourceManager**: Loads and caches game assets (images, fonts)
- **AudioManager**: Controls sound effects and background music
- **UIManager**: Manages user interface elements and their interactions

### 3. UI Framework

A hierarchical UI system built on these components:

- **UIElement**: Base class with common functionality
  - **Button**: Interactive clickable elements
  - **Panel**: Container UI elements
  - **Label**: Text display elements

UI elements support nesting, event handling, and visual customization.

### 4. Scene Management

The game flow is organized into distinct scenes:

- **MenuScene**: Title screen with game start option
- **GameScene**: Main gameplay area with entities and game logic
- **GameOverScene**: Victory or defeat screen with replay option

Each scene has its own lifecycle methods (enter, update, exit) and manages its specific entities and UI.

### 5. Game-specific Components

Game objects are composed of these components:

- **Position**: Stores x, y coordinates
- **Velocity**: Defines movement direction and speed
- **Collider**: Handles collision detection
- **Renderable**: Visual appearance properties
- **Player**: Marks an entity as controllable by the player
- **Enemy**: Defines enemy behavior properties
- **Obstacle**: Marks an entity as a static obstacle

### 6. Game-specific Systems

Game logic is implemented in these systems:

- **MovementSystem**: Updates entity positions based on velocity
- **PlayerControlSystem**: Processes player input to control movement
- **EnemyAISystem**: Controls enemy movement toward the player
- **CollisionSystem**: Detects and responds to entity collisions
- **GlowSystem**: Handles visual effects when collisions occur
- **RenderSystem**: Draws all renderable entities to the screen

## Data Flow

1. The Engine runs the main game loop, managing time and coordinating subsystems
2. Input events are captured by InputManager and converted to game events
3. EventManager distributes events to interested systems and managers
4. Active systems process entities with matching components
5. The current scene manages game state and entity lifecycle
6. RenderManager draws the final scene to the screen

## Initialization Flow

1. Engine creates subsystems and the World
2. Game-specific systems are added to the World
3. Game scenes are registered with SceneManager
4. Initial scene (MenuScene) is activated
5. Main loop begins, processing input, updating systems, and rendering

This architecture provides a flexible foundation for game development with clear separation of concerns, making the code more maintainable and extensible.
```

## Runtime Flow

The following sequence diagram illustrates the high-level flow during gameplay:

```
+--------+    +-------+    +------+    +-------+    +----------+
| Engine |    | Input |    | ECS  |    | Scene |    | Renderer |
+--------+    +-------+    +------+    +-------+    +----------+
    |             |           |           |              |
    |  Main Loop  |           |           |              |
    |------------>|           |           |              |
    |             |           |           |              |
    |       Process Events    |           |              |
    |             |---------->|           |              |
    |             |           |           |              |
    |             |  Update Systems       |              |
    |             |           |---------->|              |
    |             |           |           |              |
    |             |           | Update Scene Logic       |
    |             |           |           |------------->|
    |             |           |           |              |
    |             |           |           |  Render Scene|
    |             |           |           |              |----------->|
    |             |           |           |              |            |
    |<------------|           |           |              |            |
    |             |           |           |              |            |
```

## Key Design Patterns

1. **Entity-Component-System**: Core architectural pattern separating data from behavior
2. **Observer Pattern**: Used by EventManager for loose coupling between systems
3. **Singleton**: Used for manager classes that need global access
4. **State Pattern**: Implemented through the Scene system for game state management
5. **Command Pattern**: Used in UI interaction handlers