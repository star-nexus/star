# 围棋游戏

一个使用 framework_v2 ECS 架构开发的完整围棋游戏。

## 特性

- ✅ 完整的围棋规则实现（19x19 标准棋盘）
- ✅ 智能 AI 对手（三种难度等级）
- ✅ 美观的用户界面和棋盘显示
- ✅ 实时统计数据和游戏状态
- ✅ 支持本地运行和 Web 部署
- ✅ 完整的事件处理和用户交互

## 游戏功能

### 核心功能

- **标准围棋规则**: 完整实现吃子、打劫、死活判断等规则
- **AI 对手**:
  - 简单模式：随机下棋
  - 中等模式：基于规则的策略 AI
  - 困难模式：使用评估函数的高级 AI
- **游戏控制**: 支持重新开始、跳过回合、返回菜单等操作

### 用户界面

- **直观的棋盘**: 清晰的 19x19 网格，带有标准星位标记
- **实时信息**: 当前玩家、回合数、吃子统计等
- **视觉反馈**: 鼠标悬停效果、棋子放置动画
- **操作提示**: 完整的键盘快捷键说明

### 统计系统

- 游戏回合数统计
- 黑白双方吃子数记录
- 游戏时长计算
- 完整的移动历史记录

## 操作说明

### 基础操作

- **鼠标点击**: 在棋盘交叉点放置棋子
- **P 键**: 跳过当前回合（连续两次 pass 结束游戏）
- **R 键**: 重新开始当前游戏
- **ESC 键**: 返回主菜单

### 菜单导航

- **↑/↓ 方向键**: 选择菜单项
- **回车键**: 确认选择

## 运行游戏

### 方式一：直接运行本地版本

```bash
# 进入项目目录
cd /path/to/Romance-of-the-Three-Kingdoms

# 运行游戏
uv run go_game/main.py
# 或者
python go_game/main.py
```

### 方式二：使用启动器

```bash
# 运行启动器，选择运行方式
python go_game/launcher.py
```

### 方式三：Web 版本（使用 pygbag）

```bash
# 安装 pygbag
pip install pygbag

# 运行Web版本
uv run python -m pygbag go_game/pygbag_main.py
```

## 技术架构

### ECS 架构设计

游戏使用 Entity-Component-System（实体-组件-系统）架构，具有良好的可扩展性和维护性。

#### 核心组件（Components）

- `Position`: 棋盘位置
- `Stone`: 棋子属性（颜色、状态等）
- `GameBoard`: 棋盘状态管理
- `GameState`: 游戏状态（当前玩家、游戏阶段等）
- `GameStats`: 统计数据
- `AIPlayer`: AI 配置
- `UIState`: 用户界面状态
- `MouseState`: 鼠标交互状态

#### 系统（Systems）

- `InputSystem`: 处理用户输入和鼠标交互
- `BoardSystem`: 管理棋盘逻辑、棋子放置、吃子判断
- `GameLogicSystem`: 游戏规则、回合管理、胜负判定
- `AISystem`: AI 决策和自动下棋
- `RenderSystem`: 图形渲染和界面绘制
- `UISystem`: 用户界面管理

#### 场景（Scenes）

- `MenuScene`: 主菜单界面
- `GameScene`: 游戏主界面

### AI 算法

- **随机 AI**: 在可用位置随机选择
- **规则 AI**: 基于防守、攻击、战略位置的决策树
- **高级 AI**: 使用位置评估函数和简化蒙特卡洛方法

## 技术栈

- **框架**: framework_v2 ECS 架构
- **图形**: Pygame 2.6+
- **AI**: 自研决策算法
- **部署**: 支持 pygbag Web 打包
- **包管理**: UV 包管理器

## 项目结构

```
go_game/
├── __init__.py              # 包初始化
├── main.py                  # 本地运行入口
├── pygbag_launcher.py       # Web版本入口
├── launcher.py              # 启动器脚本
├── components.py            # ECS组件定义
├── systems.py               # ECS系统实现
├── scenes.py                # 游戏场景
├── ai.py                    # AI算法实现
└── README.md               # 项目说明
```

## 开发特性

- **模块化设计**: 各个系统独立，易于扩展和维护
- **事件驱动**: 基于事件总线的松耦合架构
- **跨平台**: 支持 Windows、macOS、Linux
- **Web 部署**: 一键打包为 WebAssembly 应用

## 未来扩展

- [ ] 添加更多 AI 难度等级
- [ ] 实现网络对战功能
- [ ] 添加棋谱保存和回放
- [ ] 支持不同棋盘尺寸（9x9、13x13）
- [ ] 添加音效和背景音乐
- [ ] 实现形势判断和目数计算
