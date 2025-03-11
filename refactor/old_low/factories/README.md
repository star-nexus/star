# 实体工厂

## 概述
本目录包含封装游戏实体创建的工厂类。

## 主要组件
- `EntityFactory`: 创建具有适当组件的游戏实体

## 支持的实体
工厂目前支持创建：
- 带有移动、碰撞和动画的玩家角色
- 带有基本AI行为的敌人实体

## 组件配置
实体配置有以下组件：
- `SpriteComponent`: 视觉表示
- `MovementComponent`: 物理和运动
- `CollisionComponent`: 碰撞检测
- `AnimationComponent`: 精灵动画

## 使用示例
```python
# 在位置(400, 300)创建玩家
player = entity_factory.create_player(400, 300)

# 创建随机位置的敌人
enemy = entity_factory.create_enemy()
```

## 最佳实践
- 使用工厂模式集中实体创建逻辑
- 根据游戏进展配置实体
- 添加新实体类型时扩展工厂
