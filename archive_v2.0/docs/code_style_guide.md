# 代码风格指南

为了确保代码库的一致性和可维护性，所有开发者都应遵循以下代码风格指南。

## 命名规范

### 文件命名
- 所有Python文件使用小写字母和下划线命名（snake_case）
- 配置文件使用小写字母和下划线命名
- 文档文件使用大驼峰命名（PascalCase）

### 类命名
- 使用大驼峰命名法（PascalCase）
- 例如：`MapGenerator`, `CombatSystem`, `FactionManager`

### 函数和方法命名
- 使用小写字母和下划线命名（snake_case）
- 例如：`calculate_damage()`, `get_unit_position()`, `create_entity()`

### 变量命名
- 使用小写字母和下划线命名（snake_case）
- 例如：`player_position`, `unit_stats`, `current_turn`

### 常量命名
- 使用全大写字母和下划线命名
- 例如：`MAX_UNITS`, `DEFAULT_HEALTH`, `TERRAIN_TYPES`

### 组件命名
- 组件类使用大驼峰命名并以Component结尾
- 例如：`PositionComponent`, `StatsComponent`, `MovementComponent`

### 系统命名
- 系统类使用大驼峰命名并以System结尾
- 例如：`RenderSystem`, `CombatSystem`, `AISystem`

## 代码格式

### 缩进
- 使用4个空格进行缩进，不使用制表符（Tab）

### 行长度
- 每行代码不超过88个字符
- 如果需要换行，将操作符放在行尾

### 导入顺序
- 标准库导入
- 相关第三方导入
- 本地应用/库特定导入
- 每组导入之间空一行

例如：
```python
import os
import sys
import math

import pygame
import numpy as np

from framework.core.ecs.system import System
from rotk.components import PositionComponent
```

### 空行
- 顶级函数和类定义之间空两行
- 类内方法定义之间空一行

### 注释
- 使用中文编写文档字符串和注释
- 每个模块、类和公共方法都应该有文档字符串
- 单行注释使用 `# `，确保#后有一个空格

## 代码组织

### 文件结构
- 每个文件应该有清晰的职责，避免过大的文件
- 相关功能应该分组在同一个目录下

### 类结构
- 类应该遵循单一职责原则
- 私有方法以下划线开头（例如：`_calculate_private_data`）

### 函数/方法长度
- 函数应该简短且专注于单一任务
- 如果一个函数超过50行，考虑拆分它

## ECS相关规范

### 组件设计
- 组件应该只包含数据，不包含行为
- 组件应该使用dataclass或简单的属性集合

### 系统设计
- 系统应该只关注特定功能
- 系统不应该直接修改不相关的组件

## 错误处理

### 异常
- 使用特定的异常类型
- 提供有意义的错误消息
- 在适当的抽象级别处理异常

## 测试

### 测试文件命名
- 测试文件应以`test_`开头，后跟被测试模块的名称
- 例如：`test_map_generator.py`, `test_combat_system.py`

### 测试函数命名
- 测试函数应以`test_`开头，描述测试的内容
- 例如：`test_damage_calculation()`, `test_unit_movement()` 