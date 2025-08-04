import asyncio
import argparse
from contextvars import ContextVar
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from protocol import AgentClient

# 配置 rich 库
from rich.console import Console
from rich import print_json

from typing import Any, Dict
from menglong import Model, ChatAgent
from menglong.agents.component.tool_manager import tool
from menglong.agents.chat.tool import plan_task


console = Console()


class RemoteContext:
    client: ContextVar[AgentClient] = ContextVar("client")
    status: ContextVar[dict] = ContextVar("status")
    task_manager: ContextVar[object] = ContextVar("task_manager")
    id_map: ContextVar[dict] = ContextVar("id_map", default={})

    @staticmethod
    def set_client(client: AgentClient):
        RemoteContext.client.set(client)

    @staticmethod
    def get_client() -> AgentClient:
        return RemoteContext.client.get()

    @staticmethod
    def set_status(status: dict):
        RemoteContext.status.set(status)

    @staticmethod
    def get_status() -> dict:
        return RemoteContext.status.get()

    @staticmethod
    def set_task_manager(task_manager: object):
        RemoteContext.task_manager.set(task_manager)

    @staticmethod
    def get_task_manager() -> object:
        return RemoteContext.task_manager.get()

    @staticmethod
    def set_id_map(id_map: dict):
        RemoteContext.id_map.set(id_map)

    @staticmethod
    def get_id_map() -> dict:
        return RemoteContext.id_map.get()


class AgentDemo:
    """Agent 客户端演示类"""

    def __init__(
        self,
        server_url="ws://localhost:8000/ws/metaverse",
        env_id="env_1",
        agent_id="agent_1",
    ):
        self.server_url = server_url
        self.env_id = env_id
        self.agent_id = agent_id
        self.agent_client = None
        self.messages = []

        self.init_client()

    def init_client(self):
        # 创建客户端
        self.agent_client = AgentClient(self.server_url, self.env_id, self.agent_id)
        self.setup_hub_listeners()
        RemoteContext.set_client(self.agent_client)
        # 初始化状态
        RemoteContext.set_status({"self_status": {}, "env_status": {}})

    def setup_hub_listeners(self):
        """设置事件监听器"""

        def on_connect(data):
            message = f"✅ Agent 连接成功: {data}"
            console.print(message, style="green")
            self.messages.append(message)

        def on_message(data):
            message = f"📨 Agent 收到消息: {data}"
            print(message)
            msg_data = data.get("payload")
            msg_type = msg_data.get("type")
            if msg_type == "action":
                action = msg_data.get("action")
                params = msg_data.get("parameters")
                message += f"\n   动作: {action}, 参数: {params}"
            elif msg_type == "outcome":
                outcome_type = msg_data.get("outcome_type")
                outcome = msg_data.get("outcome")
                RemoteContext.get_id_map().update({msg_data["id"]: outcome})
                RemoteContext.set_status(
                    {"self_status": {f"任务{msg_data['id']}": outcome}}
                )
                message += f"\n   结果: {outcome}, 结果类型: {outcome_type}"
            # console.print(message, style="blue")
            self.messages.append(message)

        def on_disconnect(data):
            message = f"❌ Agent 连接断开: {data}"
            console.print(message, style="red")
            self.messages.append(message)

        def on_error(data):
            message = f"⚠️ Agent 错误: {data}"
            msg_data = data.get("payload", {})
            error = msg_data.get("error", "未知错误")
            console.print(message, style="yellow")
            # 只有当msg_data有id字段时才更新id_map
            if "id" in msg_data:
                RemoteContext.get_id_map().update({msg_data["id"]: error})
            self.messages.append(message)
            console.print("error 处理完毕", style="red")

        self.agent_client.add_hub_listener("connect", on_connect)
        self.agent_client.add_hub_listener("message", on_message)
        self.agent_client.add_hub_listener("disconnect", on_disconnect)
        self.agent_client.add_hub_listener("error", on_error)

    async def connect(self):
        """创建并连接 Agent 客户端"""
        console.print("🤖 创建 Agent 客户端", style="bold blue")
        console.print(f"📡 服务器: {self.server_url}")
        console.print(f"🌍 环境ID: {self.env_id}")
        console.print(f"🆔 Agent ID: {self.agent_id}")
        console.print("=" * 50)

        # 连接
        console.print("🔗 正在连接到服务器...", style="yellow")
        try:
            await self.agent_client.connect()
            console.print("✅ Agent 连接成功！", style="bold green")

            # 等待连接稳定
            await asyncio.sleep(1)
            return True
        except Exception as e:
            console.print(f"❌ 连接失败: {e}", style="bold red")
            return False

    async def interactive_mode(self):
        """交互模式：用户可以手动输入动作"""
        console.print("\n🎮 进入交互模式", style="bold cyan")
        console.print("=" * 20)
        console.print("可用命令:")
        console.print("  chat <prompt>")
        console.print("  message <action> <params> - 自定义动作")
        console.print("  list - 列出可用动作")
        console.print("  run - 执行预定义动作")
        console.print("  quit - 退出交互模式")
        console.print()

        # 创建异步prompt session
        session = PromptSession()

        while True:
            try:
                # 在patch_stdout外部获取用户输入，避免颜色问题
                with patch_stdout():
                    command = await session.prompt_async("🎯 请输入命令: ")
                    command = command.strip()

                if not command:
                    await asyncio.sleep(1)
                    continue

                if command.lower() == "quit":
                    console.print("👋 退出交互模式", style="bold green")
                    break

                parts = command.split()
                action = parts[0].lower()

                console.print(f"🎯 识别到命令: {action}", style="cyan")
                console.print(f"   参数: {parts[1:] if len(parts) > 1 else '无'}")

                if action in ACTION.keys():
                    # 在patch_stdout外部执行操作，确保颜色正常显示
                    await asyncio.create_task(ACTION[action](parts))
                    # await ACTION[action](parts)
                else:
                    console.print(f"❌ 未知命令: {command}", style="red")
                    console.print("输入 'quit' 退出，或查看上方的可用命令列表")

                await asyncio.sleep(0.1)  # 短暂延迟以便查看结果

            except KeyboardInterrupt:
                print("\n👋 用户中断，退出交互模式")
                break
            except Exception as e:
                print(f"❌ 命令执行错误: {e}")

    def show_summary(self):
        """显示演示总结"""
        console.print("\n📊 Agent 演示总结", style="bold cyan")
        console.print("=" * 25)
        console.print(f"📈 总消息数: {len(self.messages)}")
        console.print(f"🆔 Agent ID: {self.agent_id}")
        console.print(f"🌍 环境 ID: {self.env_id}")

        if self.messages:
            console.print("\n📝 消息历史 (最近10条):")
            for i, msg in enumerate(self.messages[-10:], 1):
                console.print(f"   {i}. {msg}")

    async def cleanup(self):
        """清理资源"""
        console.print("\n🧹 正在清理连接...", style="yellow")
        try:
            if self.agent_client:
                await self.agent_client.disconnect()
                console.print("✅ Agent 连接已断开", style="green")
        except Exception as e:
            console.print(f"⚠️ 断开连接时出错: {e}", style="yellow")

    async def run_interactive_demo(self):
        """运行交互式演示"""
        console.print("🎮 Star Client Agent 交互式演示", style="bold cyan")
        console.print("🎯 你可以手动控制 Agent 执行各种动作", style="cyan")
        console.print("=" * 50)

        try:
            # 连接
            if not await self.connect():
                return
            # 进入交互模式
            await self.interactive_mode()

            # 显示总结
            self.show_summary()

        except KeyboardInterrupt:
            print("\n⚠️ 用户中断演示")
        except Exception as e:
            print(f"\n❌ 演示过程中发生错误: {e}")
        finally:
            await self.cleanup()


async def message(parts):

    if len(parts) > 1:
        custom_action = parts[1]
        # 将参数按键值对解析成字典
        params = {}
        param_list = parts[2:] if len(parts) > 2 else []
        for i in range(0, len(param_list), 2):
            if i + 1 < len(param_list):
                params[param_list[i]] = param_list[i + 1]
            else:
                params[param_list[i]] = ""  # 如果没有值，设为空字符串
        return await perform_action(custom_action, params)
    else:
        console.print("❌ 请指定动作，如: message dance", style="red")


async def chat(parts):
    if len(parts) > 1:
        custom_action = parts[0]
        params = parts[1] if len(parts) > 1 else ""

        agent = ChatAgent()

        res = await agent.chat(task=params, tools=[available_actions, perform_action])
        print(res)
    else:
        print("❌ 请指定动作，如: chat dance")


async def raw_llm(parts):

    goal = """## 1. 游戏背景故事

### 1.1 历史背景

公元220年，东汉末年，天下大乱。黄巾起义的余波未散，各地军阀割据一方，民不聊生。在这个英雄辈出的乱世中，三位雄主逐渐崭露头角：

- **曹操**，挟天子以令诸侯，建立魏国，雄踞北方
- **刘备**，汉室宗亲，仁德著称，在蜀地建立汉政权
- **孙权**，承父兄之业，据守江东，建立吴国

### 1.2 故事设定

游戏设定在三国鼎立的关键时期，三方势力在一片战略要地上展开激烈争夺。这里地形复杂多样，既有利于骑兵冲锋的平原，也有适合步兵防守的山地，还有考验指挥官智慧的城池要塞。

在这场群雄逐鹿的战争中，每一步棋都关乎国运，每一次战斗都可能改变历史走向。作为三国名将，你需要运用兵法智谋，合理配置兵力，在这个充满机遇与挑战的战场上为你的君主夺取最终胜利。

### 1.3 游戏主题

- **战略决策**: 在有限资源下做出最优选择
- **兵法运用**: 体现古代军事思想的博弈
- **英雄传说**: 重现三国英雄的传奇故事
- **智慧较量**: 智能体与人类的策略对抗

---

## 2. 游戏概述

### 2.1 游戏目标

玩家扮演三国时期的军事统帅，指挥自己的军队在战场上与其他阵营争夺控制权。通过合理的兵力部署、巧妙的战术安排和明智的战略决策，最终实现统一天下或完成特定的胜利目标。

### 2.2 核心玩法

#### 2.2.1 回合制模式
- 玩家轮流进行回合，每回合可执行多个动作
- 每个单位有限定的行动点数和移动力
- 深思熟虑的策略规划是获胜关键

#### 2.2.2 实时制模式
- 所有玩家同时进行操作
- 动作有冷却时间，考验反应速度
- 更加紧张刺激的游戏体验

### 2.3 游戏特色

- **六边形格子地图**: 提供更丰富的移动选择和战术可能
- **多样化单位**: 步兵、骑兵、弓兵各有特色
- **地形影响**: 不同地形对战斗和移动产生重要影响
- **技能系统**: 单位可使用特殊技能改变战局
- **战争迷雾**: 增加信息不完全带来的策略深度
- **AI智能体**: 支持先进的LLM智能体对战

---

## 3. 基础规则

### 3.1 游戏设置

#### 3.1.1 地图初始化
- 地图大小：通常为20x20到50x50六边形格子
- 地形生成：随机生成或预设地图
- 起始位置：各阵营在地图边缘获得起始区域

#### 3.1.2 单位部署
- 每个阵营开始时拥有8-15个单位
- 单位随机分配或按预设配置生成
- 初始单位包含步兵、骑兵、弓兵的组合

#### 3.1.3 资源分配
- 每个单位有独立的行动点数和移动力
- 初始状态下所有单位满血满状态
- 技能点数根据单位类型和等级确定

### 3.2 回合结构（回合制模式）

#### 3.2.1 回合顺序
1. **魏国回合** → **蜀国回合** → **吴国回合** → 重复
2. 回合顺序在游戏开始时随机确定
3. 可通过特殊事件或技能改变回合顺序

#### 3.2.2 回合阶段
每个玩家的回合包含以下阶段：

1. **回合开始阶段**
   - 恢复所有单位的行动点和移动力
   - 结算持续效果（buff/debuff）
   - 检查胜利条件

2. **行动阶段**
   - 可以任意顺序操作所有己方单位
   - 每个单位可进行移动、攻击、使用技能等动作
   - 可以多次在不同单位间切换操作

3. **回合结束阶段**
   - 结算回合结束效果
   - 清除临时状态
   - 传递回合给下一位玩家

### 3.3 行动规则

#### 3.3.1 行动点系统
- **行动点(AP)**: 用于执行各种动作的基础资源
- **移动力(MP)**: 专门用于移动的资源
- **技能点(SP)**: 用于使用特殊技能的资源

| 动作类型 | 消耗 | 说明 |
|----------|------|------|
| 基础移动 | 1 MP/格 | 移动到相邻格子 |
| 普通攻击 | 1 AP | 攻击相邻敌方单位 |
| 远程攻击 | 1 AP | 弓兵的远程攻击 |
| 使用技能 | 1-3 SP | 根据技能复杂度 |
| 待命恢复 | 1 AP | 恢复状态和士气 |
| 建设工事 | 2 AP | 建造防御设施 |

#### 3.3.2 移动规则
- 单位只能移动到空旷或己方控制的格子
- 不能穿越敌方单位或障碍物
- 不同地形有不同的移动消耗
- 可以在移动前后进行其他动作

#### 3.3.3 攻击规则
- 只能攻击相邻的敌方单位（近战）
- 弓兵可以进行2-3格的远程攻击
- 攻击后通常无法继续移动
- 反击机制：被攻击时有概率进行反击

---

## 4. 游戏机制

### 4.1 视野与战争迷雾

#### 4.1.1 视野机制
- 每个单位有固定的视野范围（通常为2-3格）
- 只能看到视野范围内的敌方单位和地形
- 高地和特殊位置可以提供视野加成
- 某些单位（如斥候）拥有更大的视野范围

#### 4.1.2 战争迷雾
- 未被己方单位探索的区域保持迷雾状态
- 离开视野的敌方单位会再次隐藏
- 迷雾中可能隐藏敌方单位或重要资源
- 情报收集成为重要的战略要素

### 4.2 地形效果

#### 4.2.1 移动影响
- **平原**: 移动消耗正常，无特殊效果
- **森林**: 移动消耗+1，提供隐蔽和防御加成
- **山地**: 移动消耗+2，提供高度和防御优势
- **丘陵**: 移动消耗+1，提供中等防御加成
- **水域**: 大部分单位无法进入
- **城池**: 提供强大防御，可作为补给点

#### 4.2.2 战斗影响
- **高地优势**: 攻击低地目标时伤害+20%
- **森林掩护**: 受到远程攻击时伤害-30%
- **城墙防护**: 防御+50%，但移动受限
- **河流阻碍**: 跨河攻击伤害-20%

### 4.3 单位属性系统

#### 4.3.1 基础属性
- **生命值(HP)**: 单位的生存能力，降为0时单位死亡
- **攻击力(ATK)**: 造成伤害的基础数值
- **防御力(DEF)**: 减少受到伤害的能力
- **移动力(MOV)**: 每回合可移动的最大距离
- **士气(MORALE)**: 影响战斗表现和特殊能力

#### 4.3.2 次要属性
- **攻击范围**: 可以攻击的距离
- **命中率**: 攻击成功的概率
- **暴击率**: 造成额外伤害的概率
- **闪避率**: 完全避免伤害的概率
- **视野范围**: 可以观察的距离

### 4.4 状态效果系统

#### 4.4.1 正面状态
- **士气高昂**: 攻击力+20%，持续3回合
- **防御姿态**: 防御力+50%，移动力-50%
- **急行军**: 移动力+2，攻击力-10%
- **隐蔽**: 不易被发现，首次攻击伤害+30%

#### 4.4.2 负面状态
- **混乱**: 无法使用技能，移动随机
- **疲劳**: 所有数值-20%，持续2回合
- **恐惧**: 无法主动攻击，防御力-30%
- **中毒**: 每回合损失5点生命值

---

## 5. 胜利条件

### 5.1 标准胜利条件

#### 5.1.1 完全消灭（Total Elimination）
- **条件**: 消灭所有敌方单位
- **难度**: ★★★★☆
- **策略**: 积极进攻，快速决战
- **适用**: 小地图，短时间游戏

#### 5.1.2 控制胜利（Territory Control）
- **条件**: 控制地图上70%以上的关键区域
- **计分方式**: 
  - 城池：5分/个
  - 要塞：3分/个
  - 资源点：2分/个
  - 普通格子：1分/个
- **难度**: ★★★☆☆
- **策略**: 平衡扩张与防守
- **适用**: 大地图，中长时间游戏

#### 5.1.3 时间限制胜利（Turn Limit Victory）
- **条件**: 规定回合数结束时分数最高
- **最大回合**: 通常为50-100回合
- **计分标准**:
  - 存活单位：每个10分
  - 控制领土：按类型计分
  - 击杀敌军：每个5分
  - 特殊成就：额外奖励分
- **难度**: ★★★☆☆
- **策略**: 平衡发展，把握时机

### 5.2 特殊胜利条件

#### 5.2.1 统治胜利（Domination Victory）
- **条件**: 同时满足以下要求
  - 控制至少5座城池
  - 己方单位数量是敌方总和的1.5倍以上
  - 连续5回合保持领先地位
- **难度**: ★★★★★
- **奖励**: 额外成就和分数奖励

#### 5.2.2 经济胜利（Economic Victory）
- **条件**: 积累足够的资源和基础设施
  - 建造10个防御工事
  - 控制所有资源丰富区域
  - 维持30回合无单位死亡
- **难度**: ★★★☆☆
- **策略**: 重防守，轻进攻

#### 5.2.3 快速胜利（Blitz Victory）
- **条件**: 在20回合内达成任一标准胜利条件
- **奖励**: 双倍分数奖励
- **难度**: ★★★★★
- **策略**: 激进进攻，高风险高回报

### 5.3 特殊情况

#### 5.3.1 平局判定
当满足以下条件时判定为平局：
- 达到最大回合数，多方分数相等
- 所有阵营同时满足胜利条件
- 游戏进入无法打破的僵持状态

平局时的排名规则：
1. 存活单位数量
2. 控制的领土总价值
3. 击杀敌军数量
4. 特殊成就数量

#### 5.3.2 提前认输
- 玩家可以在任何时候选择认输
- 认输后该玩家的所有单位立即消失
- 认输不影响其他玩家继续游戏
- AI智能体有自动认输机制（当胜率低于5%时）

---

## 6. 阵营介绍

### 6.1 魏国 (Wei) - 曹操势力

#### 6.1.1 阵营特色
- **政治特点**: 挟天子以令诸侯，正统性强
- **军事特点**: 兵强马壮，训练有素
- **战略优势**: 综合实力均衡，适应性强
- **历史背景**: 占据中原要地，人才荟萃

#### 6.1.2 阵营能力
- **精锐训练**: 所有单位初始等级+1
- **统一指挥**: 批量操作时效率+20%
- **中原优势**: 在平原地形战斗力+15%
- **人才荟萃**: 技能冷却时间-1回合

#### 6.1.3 特色单位
- **虎豹骑**: 精锐骑兵，高攻击高机动
- **青州兵**: 精锐步兵，防御力强
- **连弩手**: 远程单位，可连续射击

#### 6.1.4 代表武将
- **曹操**: 奸雄，全能型指挥官
- **许褚**: 虎卫，近战无敌
- **张辽**: 名将，突击专家

### 6.2 蜀国 (Shu) - 刘备势力

#### 6.2.1 阵营特色
- **政治特点**: 汉室宗亲，仁德治国
- **军事特点**: 士气高昂，忠诚度强
- **战略优势**: 防守反击，后发制人
- **历史背景**: 占据巴蜀险要，民心所向

#### 6.2.2 阵营能力
- **仁德之师**: 单位死亡时周围友军士气+1
- **巴蜀险阻**: 在山地丘陵地形防御+25%
- **民心所向**: 占领敌方领土时有额外奖励
- **桃园结义**: 相邻友军之间有战斗加成

#### 6.2.3 特色单位
- **白毦兵**: 精锐步兵，士气永不下降
- **蜀地弓手**: 山地作战专家
- **锦马超骑**: 西凉铁骑，冲锋无敌

#### 6.2.4 代表武将
- **刘备**: 仁主，鼓舞士气专家
- **关羽**: 武圣，无双猛将
- **诸葛亮**: 智绝，策略大师

### 6.3 吴国 (Wu) - 孙权势力

#### 6.3.1 阵营特色
- **政治特点**: 世代经营，根基深厚
- **军事特点**: 水战无敌，机动灵活
- **战略优势**: 游击战术，声东击西
- **历史背景**: 占据江东水乡，善用地利

#### 6.3.2 阵营能力
- **江东猛虎**: 首次攻击必定暴击
- **水战无敌**: 在水域附近战斗力+30%
- **机动作战**: 所有单位移动力+1
- **世代经营**: 建造设施耗时减半

#### 6.3.3 特色单位
- **丹阳兵**: 精锐步兵，擅长山地作战
- **江东水师**: 水上作战单位
- **陷阵营**: 突击专家，破阵能力强

#### 6.3.4 代表武将
- **孙权**: 明主，平衡发展专家
- **周瑜**: 美周郎，水战之神
- **甘宁**: 锦帆贼，奇袭专家

---

## 7. 单位系统

### 7.1 单位分类

#### 7.1.1 步兵 (Infantry)
**基础属性**:
- 生命值: 100
- 攻击力: 20-25
- 防御力: 15-20
- 移动力: 2-3
- 攻击范围: 1

**特殊能力**:
- **盾墙**: 提高防御力，降低移动速度
- **密集阵型**: 相邻友军提供防御加成
- **坚守**: 在原地不动时防御力大幅提升

**优势**:
- 高生命值和防御力
- 建造和占领效率高
- 多种战术技能

**劣势**:
- 移动速度慢
- 缺乏远程攻击能力
- 容易被骑兵冲击

#### 7.1.2 骑兵 (Cavalry)
**基础属性**:
- 生命值: 80
- 攻击力: 25-35
- 防御力: 10-15
- 移动力: 4-5
- 攻击范围: 1

**特殊能力**:
- **冲锋**: 移动后攻击伤害翻倍
- **追击**: 击杀敌人后可继续行动
- **快速机动**: 不受大部分地形移动限制

**优势**:
- 高移动力和攻击力
- 优秀的机动性
- 强大的冲锋能力

**劣势**:
- 防御力相对较低
- 在复杂地形受限
- 容易被弓兵克制

#### 7.1.3 弓兵 (Archer)
**基础属性**:
- 生命值: 70
- 攻击力: 15-20
- 防御力: 8-12
- 移动力: 2-3
- 攻击范围: 2-3

**特殊能力**:
- **远程射击**: 可攻击2-3格内的目标
- **箭雨**: 攻击一个区域内的所有敌人
- **精准射击**: 提高命中率和暴击率

**优势**:
- 远程攻击能力
- 可以越过友军攻击
- 对骑兵有克制效果

**劣势**:
- 生命值和防御力最低
- 近战能力弱
- 需要友军保护

### 7.2 单位等级系统

#### 7.2.1 经验获得
- **击杀敌军**: +20-30经验
- **攻击敌军**: +5-10经验  
- **占领领土**: +10-15经验
- **完成特殊任务**: +15-25经验
- **存活回合**: +2-5经验

#### 7.2.2 等级效果
| 等级 | 经验需求 | 属性提升 | 特殊能力 |
|------|----------|----------|----------|
| 1级 | 0 | 基础属性 | 基础技能 |
| 2级 | 100 | 全属性+10% | 解锁1个新技能 |
| 3级 | 250 | 全属性+20% | 技能威力+25% |
| 4级 | 450 | 全属性+35% | 解锁1个高级技能 |
| 5级 | 700 | 全属性+50% | 所有技能威力+50% |

#### 7.2.3 晋升奖励
- **等级2**: 获得一个随机装备
- **等级3**: 生命值上限+20
- **等级4**: 获得称号和特殊外观
- **等级5**: 成为精英单位，获得独特能力

### 7.3 装备系统

#### 7.3.1 武器类型
- **铁剑**: 攻击力+5，命中率+10%
- **长枪**: 攻击力+3，可攻击2格距离
- **战戟**: 攻击力+8，可同时攻击相邻2个敌人
- **强弓**: 射程+1，攻击力+4
- **连弩**: 可连续射击2次

#### 7.3.2 防具类型
- **皮甲**: 防御力+3，移动力不减
- **锁甲**: 防御力+6，移动力-1
- **板甲**: 防御力+10，移动力-2
- **盾牌**: 防御力+4，反击伤害+50%

#### 7.3.3 特殊装备
- **战马**: 移动力+2，冲锋伤害+100%
- **药品**: 每回合恢复10点生命值
- **军旗**: 周围友军士气+1
- **号角**: 可以召唤援军

---

## 8. 地形系统

### 8.1 地形类型详解

#### 8.1.1 平原 (Plain)
- **移动消耗**: 1点移动力
- **战斗修正**: 无
- **特殊效果**: 适合大规模会战
- **战术意义**: 骑兵的天堂，步兵的战场
- **出现频率**: 40-50%

#### 8.1.2 森林 (Forest)
- **移动消耗**: 2点移动力
- **战斗修正**: 防御+20%，远程攻击-30%
- **特殊效果**: 提供隐蔽，视野受限
- **战术意义**: 伏击和防守的好地方
- **出现频率**: 20-25%

#### 8.1.3 山地 (Mountain)
- **移动消耗**: 3点移动力（骑兵4点）
- **战斗修正**: 防御+40%，高地优势+20%
- **特殊效果**: 视野+1，骑兵受限
- **战术意义**: 易守难攻的要塞
- **出现频率**: 15-20%

#### 8.1.4 丘陵 (Hill)
- **移动消耗**: 2点移动力
- **战斗修正**: 防御+15%，高地优势+10%
- **特殊效果**: 轻微视野加成
- **战术意义**: 制高点的争夺
- **出现频率**: 15-20%

#### 8.1.5 水域 (Water)
- **移动消耗**: 无法通过（大部分单位）
- **战斗修正**: 水战单位+50%
- **特殊效果**: 自然屏障
- **战术意义**: 分割战场，限制机动
- **出现频率**: 5-10%

#### 8.1.6 城池 (City)
- **移动消耗**: 1点移动力（己方控制时）
- **战斗修正**: 防御+60%，补给+全恢复
- **特殊效果**: 胜利点+5，可建造设施
- **战术意义**: 战略要点，必争之地
- **出现频率**: 3-5个/地图

### 8.2 地形组合效果

#### 8.2.1 河流 (River)
- 跨越河流攻击伤害-20%
- 在河边防守获得额外加成
- 某些位置可能有桥梁或浅滩

#### 8.2.2 城墙 (Wall)
- 只有攻城器械可以破坏
- 提供极高的防御加成
- 限制大型单位通过

#### 8.2.3 道路 (Road)
- 移动消耗-1（最少消耗1点）
- 提高移动速度，便于机动
- 连接重要地点

### 8.3 动态地形

#### 8.3.1 季节变化
- **春季**: 所有单位恢复能力+20%
- **夏季**: 行动力消耗+10%，视野+1
- **秋季**: 资源收集效率+30%
- **冬季**: 移动消耗+1，生命恢复-50%

#### 8.3.2 天气效果
- **晴天**: 无特殊效果
- **雨天**: 视野-1，火攻无效
- **雾天**: 视野-2，伏击成功率+50%
- **雪天**: 移动消耗+1，追击距离-1

---

## 9. 战斗机制

### 9.1 战斗流程

#### 9.1.1 战斗发起
1. 选择攻击方单位
2. 选择目标（在攻击范围内）
3. 确认攻击类型（普通/技能/特殊）
4. 系统计算伤害
5. 应用战斗结果

#### 9.1.2 伤害计算
```
基础伤害 = 攻击力 × (1 + 随机因子[-0.2, +0.2])
实际伤害 = 基础伤害 × 地形修正 × 兵种克制 × 状态修正 - 目标防御力
最终伤害 = max(实际伤害, 1)  // 至少造成1点伤害
```

#### 9.1.3 命中判定
```
基础命中率 = 80%
最终命中率 = 基础命中率 + 攻击方命中加成 - 防守方闪避加成 + 地形修正
暴击判定 = 独立10%概率（可被装备和技能影响）
```

### 9.2 兵种相克

#### 9.2.1 相克关系
```
步兵 → 弓兵 → 骑兵 → 步兵
(克制)   (克制)   (克制)
```

#### 9.2.2 相克效果
| 攻击方 | 防守方 | 伤害修正 | 命中修正 |
|--------|--------|----------|----------|
| 步兵 | 弓兵 | +30% | +20% |
| 弓兵 | 骑兵 | +25% | +15% |
| 骑兵 | 步兵 | +35% | +10% |
| 相同兵种 | 相同兵种 | 0% | 0% |

### 9.3 特殊战斗情况

#### 9.3.1 包围攻击
- 当目标被3个或以上敌方单位包围时
- 目标防御力-30%，无法反击
- 包围方每个单位伤害+10%

#### 9.3.2 夹击攻击
- 两个友军从相对方向攻击同一目标
- 伤害+20%，命中率+15%
- 目标有概率陷入混乱状态

#### 9.3.3 背后偷袭
- 从目标背后（或侧后）发起攻击
- 伤害+50%，必定命中
- 有高概率造成暴击

#### 9.3.4 高地攻击
- 从高地攻击低地目标
- 伤害+20%，射程+1（远程单位）
- 命中率+10%

### 9.4 反击机制

#### 9.4.1 反击条件
- 受到近战攻击时
- 自身具备反击能力
- 没有处于特殊状态（如混乱）
- 攻击方在反击范围内

#### 9.4.2 反击计算
- 反击伤害为正常攻击的70%
- 不触发特殊效果和技能
- 不消耗行动点或移动力
- 可以被装备和技能强化

---

## 10. 策略要素

### 10.1 资源管理

#### 10.1.1 行动点规划
- 每个单位每回合的行动点有限
- 需要在移动、攻击、技能之间做出选择
- 合理分配资源是获胜关键

#### 10.1.2 技能冷却管理
- 强力技能通常有较长冷却时间
- 需要提前规划技能使用时机
- 考虑技能组合的协同效果

### 10.2 阵型战术

#### 10.2.1 经典阵型
- **一字长龙**: 适合防守，火力集中
- **鹤翼阵**: 适合包围，双翼合击
- **锥形攻击**: 适合突破，集中火力
- **方圆大阵**: 适合防守，相互支援

#### 10.2.2 组合战术
- **步弓配合**: 步兵在前保护，弓兵在后输出
- **骑兵突击**: 集中骑兵快速突破敌阵
- **分进合击**: 多路并进，同时发起攻击
- **声东击西**: 佯攻吸引注意，主力从侧翼突破

### 10.3 地图控制

#### 10.3.1 关键地点
- **制高点**: 控制视野和火力优势
- **隘口**: 控制通道，限制敌军机动
- **城池**: 重要的战略资源和胜利点
- **资源点**: 提供持续的战略优势

#### 10.3.2 控制策略
- **快速占领**: 游戏初期抢占关键位置
- **据点防守**: 建立防线，步步为营
- **机动控制**: 利用速度优势控制多个地点
- **深度防御**: 层层设防，消耗敌军

### 10.4 信息战

#### 10.4.1 侦察重要性
- 了解敌军分布和动向
- 发现敌军弱点和机会
- 预测敌军战略意图

#### 10.4.2 反侦察
- 隐藏自己的真实意图
- 制造虚假信息误导敌军
- 保护关键单位和计划

### 10.5 时机把握

#### 10.5.1 攻击时机
- **敌军分散**: 集中优势兵力各个击破
- **敌军疲劳**: 利用敌军状态不佳发起攻击
- **地形优势**: 在有利地形发起决战
- **兵种优势**: 利用兵种相克关系

#### 10.5.2 防守时机
- **兵力劣势**: 避免决战，积蓄实力
- **地形不利**: 选择有利地形进行防守
- **等待援军**: 拖延时间等待援军到达
- **消耗敌军**: 利用防御优势消耗敌军

---

## 11. 游戏模式

### 11.1 单人模式

#### 11.1.1 教学模式
- **目标**: 学习游戏基础操作和规则
- **特点**: 步骤引导，难度渐进
- **内容**: 移动、攻击、技能、战术
- **时长**: 15-30分钟

#### 11.1.2 挑战模式
- **关卡1**: 初出茅庐 - 学习基础操作
- **关卡2**: 小试牛刀 - 简单AI对战
- **关卡3**: 崭露头角 - 兵种配合
- **关卡4**: 运筹帷幄 - 复杂地形战
- **关卡5**: 纵横捭阖 - 多方混战

#### 11.1.3 自由模式
- 可自定义游戏参数
- 选择地图大小和复杂度
- 调整AI难度等级
- 设置特殊规则和胜利条件

### 11.2 多人模式

#### 11.2.1 本地对战
- 2-3人在同一设备上轮流操作
- 适合面对面的策略对战
- 即时反馈和讨论

#### 11.2.2 网络对战
- 支持在线匹配和好友对战
- 排名系统和季度赛事
- 回放系统和战术分析

#### 11.2.3 AI混战模式
- 人类玩家与AI智能体混合对战
- 可观察和学习AI的策略
- 测试和验证AI能力

### 11.3 AI智能体模式

#### 11.3.1 规则基础AI
- 基于预设规则和启发式算法
- 反应迅速，逻辑清晰
- 适合作为基准和训练对手

#### 11.3.2 机器学习AI
- 基于强化学习训练的AI
- 能够学习和适应不同策略
- 提供挑战性的对战体验

#### 11.3.3 大语言模型AI
- 基于LLM的智能体
- 能够理解自然语言指令
- 支持解释决策过程和策略分析

### 11.4 实验模式

#### 11.4.1 AI训练场
- 专门用于AI训练和测试
- 可加速游戏进程
- 大量并行对战

#### 11.4.2 策略实验室
- 测试特定战术和策略
- 可设置特殊情况和条件
- 用于研究和分析

#### 11.4.3 平衡测试
- 测试游戏平衡性
- 收集数据进行调优
- 验证规则修改效果

---

## 12. 高级规则

### 12.1 特殊能力

#### 12.1.1 武将技能
- **曹操 - 奸雄**: 击杀敌军后可立即行动
- **刘备 - 仁德**: 周围友军防御力+20%
- **孙权 - 制衡**: 可重新分配行动点

#### 12.1.2 阵营特性
- **魏国 - 王者之师**: 军团作战时有额外加成
- **蜀国 - 义勇军**: 为友军复仇时伤害翻倍
- **吴国 - 江东猛虎**: 主动攻击必定先手

### 12.2 环境事件

#### 12.2.1 随机事件
- **暴雨**: 全地图视野-1，持续3回合
- **瘟疫**: 随机单位生命值-20
- **援军**: 随机阵营获得1个援军单位
- **谍报**: 随机暴露一个敌方单位的位置

#### 12.2.2 季节效应
- 每10回合变换一次季节
- 不同季节对所有单位产生影响
- 需要调整战术适应环境变化

### 12.3 高级战术

#### 12.3.1 连环计
- 利用地形和位置制造连锁反应
- 一个攻击触发多个后续效果
- 需要精密的计算和规划

#### 12.3.2 空城计
- 故意暴露弱点吸引敌军
- 在敌军进攻时实施反击
- 心理战和信息战的运用

#### 12.3.3 围魏救赵
- 攻击敌军重要目标迫使其回援
- 缓解己方其他战线的压力
- 战略层面的调动和牵制

### 12.4 专家规则

#### 12.4.1 限时决策
- 每个行动有时间限制
- 增加游戏紧张感
- 考验玩家的快速决策能力

#### 12.4.2 隐藏信息
- 部分单位属性不完全可见
- 增加信息收集的重要性
- 提高游戏的不确定性

#### 12.4.3 多重胜利条件
- 同时设置多个胜利路径
- 增加战略选择的多样性
- 避免单一最优策略

控制wei阵营,获得胜利。"""
    try:
        agent = ChatAgent()

        res = await agent.chat(
            task=goal, tools=[plan_task, available_actions, perform_action]
        )
        print(res)
    except Exception as e:
        print("执行任务时发生错误:", e)


async def get_response(request_id):
    """获取动作执行的响应"""

    print(f"等待响应: {request_id}")
    while not RemoteContext.get_id_map().get(request_id, None):
        await asyncio.sleep(0.1)  # 等待响应
    response = RemoteContext.get_id_map().pop(request_id)
    print(f"响应结果: {response}")

    return response


async def list_action(parts):
    """列出可用动作"""
    print("获取可用动作列表...")
    actions = await available_actions()
    print(f"可用动作: {actions}")


@tool
async def perform_action(action: str, params: Any):
    """执行动作"""
    print(f"🚀 执行动作: {action}, 参数: {params}")

    response = None

    client = RemoteContext.get_client()
    print(f"当前客户端: {client}")

    success = await client.send_action(action, params)
    print(f"执行动作的立刻结果 - success: {success}")
    response = await get_response(success)

    if response:
        print_json(data=response)
    return response


@tool
async def available_actions() -> list[Dict[str, Any]]:
    """获取当前可用的动作"""

    result = await perform_action("action_list", {})

    return result


async def run_action(parts):
    """执行指定动作"""
    rule = """游戏规则:
# 阵营
有两方阵营，wei 和 shu
所有单位同时进行操作
# 地图
地图大小：通常为不超过50x50六边形格子,以(0,0)为地图中心
# 单位
每个阵营开始时拥有若干个单位
初始单位包含步兵、骑兵、弓兵的组合
# 阶段
可以任意顺序操作所有己方单位
每个单位可进行移动、攻击、建造、使用技能等动作
可以多次在不同单位间切换操作
如果无法行动则结束回合
"""
    await chat(["chat", rule + "控shu阵营,消灭敌人,获得胜利。"])


ACTION = {
    "chat": chat,
    "message": message,
    "list": list_action,
    "run": run_action,
    "raw": raw_llm,
}


async def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Star Client Agent 演示程序")

    parser.add_argument(
        "--server-url",
        default="ws://localhost:8000/ws/metaverse",
        help="服务器地址 (默认: ws://localhost:8000/ws/metaverse)",
    )
    parser.add_argument(
        "--env-id", type=str, default="env_1", help="环境ID (默认: env_1)"
    )
    parser.add_argument(
        "--agent-id", type=str, default="agent_2", help="Agent ID (默认: 1)"
    )

    args = parser.parse_args()

    console.print(f"📡 服务器: {args.server_url}")
    console.print(f"🌍 环境ID: {args.env_id}")
    console.print(f"🆔 Agent ID: {args.agent_id}")
    console.print("=" * 60)

    # 创建演示实例
    demo = AgentDemo(args.server_url, args.env_id, args.agent_id)
    console.print("🎮 交互式模式", style="bold cyan")
    await demo.run_interactive_demo()


if __name__ == "__main__":
    asyncio.run(main())
