# Romance of the Three Kingdoms

基于大语言模型的多智能体三国策略游戏。这个项目创建了一个围绕三国时期战争元素的回合制策略游戏，并支持人类玩家与AI智能体交互。


## 项目特点

- **多智能体系统**：支持多个AI智能体作为游戏单位进行协同和对抗
- **基于规则的战斗系统**：山克制平，平克制水，水克制山的三角克制关系
- **动态地图生成**：随机生成包含多种地形的战场环境
- **多视角模式**：支持上帝视角、红方视角和白方视角
- **多种游戏模式**：支持人类玩家操作和AI自动对战

## 安装

1. 克隆项目仓库：

```bash
git clone https://github.com/yourusername/Romance-of-the-Three-Kingdoms.git
cd Romance-of-the-Three-Kingdoms
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

## 运行游戏

### 人类玩家模式

```bash
python run_game.py
```

### AI对战模式

单智能体调度模式：

```bash
python run_game.py --ai
python run_ai.py
```

多智能体协作模式：

```bash
python run_game.py --ai --ai_type=muti-agent
```


## 游戏规则

### 单位类型与克制关系

游戏单位遵循相互克制关系：
- 山 克制 平
- 平 克制 水
- 水 克制 山

### 游戏目标

消灭对方阵营的所有单位，或者在规定回合内拥有更多的存活单位。

## 操作方式

- **移动选中单位**：上下左右方向键
- **选择单位**：
  - 鼠标左键点击单位
  - TAB键切换选中单位
- **视角切换**：
  - 1: 上帝视角（全局可见）
  - 2: 红方视角
  - 3: 白方视角
- **路径规划**：
  - 选中单位后按G键，再点击目标位置
- **执行回合**：H键

## 项目结构

- **game/**: 游戏核心逻辑与系统
- **map_generator/**: 地图和单位生成器
- **cyber/**: AI智能体基础架构
- **mlong/**: 大语言模型集成与智能体实现
- **entity/**: 游戏实体定义
- **configs/**: 配置文件
- **run_log/**: AI运行日志与观察

## 开发环境

- Python 3.10+
- pygame
- numpy

## 许可证

[MIT License](LICENSE)