import re
import time
from cyber import *


def replace_content(content: str, map_content: str, unit_content: str):
    return content.replace("{{地图}}", map_content).replace("{{棋子}}", unit_content)


# 正则分析结果，把res 进行截取保存
def get_ins(text):
    pattern = r"---指令开始---(.*?)---指令结束---"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[0]
    else:
        return None


key_config_path = "configs/keys/key.toml"
agent_config_path = "configs/agents/agent.toml"


def main():
    print("Hello, RotTK!")
    npc = Agent(key_config_path=key_config_path, agent_config_path=agent_config_path)
    system = """
            你是一个战棋统帅,目标快速消灭对方全部敌人，通过控制每一个棋子的移动和攻击来实现。
            我会提供给你棋局状态，你来思考并作出决策。我还会提供给你游戏规则，你需要注意规则。

            游戏单位克制关系
            ```
            山 克 平
            平 克 水
            水 克 山
            ```

            注意我方移动的时候，敌方也在移动。快点打。激烈一些。
            """
    prompt_r = """
            你是R Force方统帅,R_* 都是你可以控制的棋子,这是当前棋局的基础信息
            {{地图}}

            这是全部棋子信息:
            {{棋子}}

            请你为了赢下游戏，做出指示。

            回复格式设定为: unit_id action param...
            move命令： <unit_id> move ty tx
            attack命令：<unit_id> attack target_unit_id
            例子:
                1 move 1 1
                2 attack 1
            
            纯指令部分用---tag---标识出来
            ---指令开始---
            [1-10个指令]
            ---指令结束---
            """
    prompt_w = """
            你是W Force方统帅,W_* 都是你可以控制的棋子,这是当前棋局的基础信息
            {{地图}}

            这是全部棋子信息:
            {{棋子}}

            请你为了赢下游戏，做出指示。

            回复格式设定为: unit_id(int) action param...
            move命令： <unit_id> move ty tx
            attack命令：<unit_id> attack target_unit_id
            例子:
                1 move 1 1
                2 attack 1
            

            纯指令部分用---tag---标识出来
            ---指令开始---
            [1-10个指令]
            ---指令结束---
            """
    his_r = []
    his_w = []
    while True:

        # 读取文件
        with open("run_log/env_status.txt", "r") as f:
            env_state = f.read()
            print(env_state)

        print("----------------------------------")
        with open("run_log/unit_status.txt", "r") as f:
            unit_state = f.read()
            print(unit_state)

        prompt_r = replace_content(prompt_r, env_state, unit_state)
        prompt_w = replace_content(prompt_w, env_state, unit_state)

        res_r, his_r = npc.chat(system=system, prompt=prompt_r)
        print("---------------red-------------------")
        print(res_r)
        res_w, his_w = npc.chat(system=system, prompt=prompt_w)
        print("---------------white-------------------")
        print(res_w)

        # 保存到文件
        with open("unit_action.txt", "w") as f:
            f.write(get_ins(res_r))
            f.write(get_ins(res_w))
        # 10s 运行一次
        time.sleep(10)


if __name__ == "__main__":
    main()
