# 组件配置系统

## 概述

本配置系统旨在将游戏中各种组件的创建和初始化逻辑从系统代码中抽离出来，实现数据与逻辑的分离。这种设计有以下优点：

1. **提高可维护性**：组件的属性和初始值集中在配置文件中管理，便于调整和维护
2. **增强灵活性**：可以轻松创建不同类型的预设配置，无需修改代码
3. **简化系统代码**：系统只需关注逻辑处理，不需要处理组件的创建和初始化
4. **便于扩展**：添加新的组件类型或属性只需修改配置文件，无需修改多处系统代码

## 目录结构

```
game/config/
├── component_factory.py     # 组件工厂，负责根据配置创建组件
├── components/              # 各类组件的配置文件
│   ├── map_config.py        # 地图组件配置
│   ├── unit_config.py       # 单位组件配置
│   └── camera_config.py     # 相机组件配置
└── README.md               # 本文档
```

## 使用方法

### 1. 在场景中使用组件工厂

```python
# 创建组件工厂
self.component_factory = ComponentFactory(self.world)

# 创建地图
self.map_entity, map_component = self.component_factory.create_map("default")

# 创建相机
self.camera_entity, camera_component = self.component_factory.create_camera("default")

# 创建单位
unit_entity, unit_component = self.component_factory.create_unit(
    UnitType.INFANTRY,  # 单位类型
    0,                  # 阵营ID
    x, y,               # 位置坐标
    level=1             # 单位等级
)
```

### 2. 添加新的组件配置

1. 在 `components/` 目录下创建新的配置文件，例如 `building_config.py`
2. 定义配置数据结构和获取函数
3. 在 `component_factory.py` 中添加相应的创建方法

### 3. 修改现有配置

直接编辑对应的配置文件，修改属性值或添加新的预设配置。

## 配置文件说明

### 地图配置 (map_config.py)

包含地图尺寸、格子大小等基本属性，以及地形属性和地图生成参数。

### 单位配置 (unit_config.py)

定义不同类型单位的属性（生命值、攻击力、防御力等），以及阵营配置和预设单位。

### 相机配置 (camera_config.py)

定义相机的位置、缩放比例、移动速度等参数。

## 扩展建议

1. 考虑使用JSON或YAML格式存储配置，以便于非程序员编辑
2. 添加配置验证机制，确保配置数据的正确性
3. 实现配置热重载功能，支持游戏运行时更新配置