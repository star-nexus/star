from concurrent.futures import ThreadPoolExecutor
import os
import re
from typing import Optional, List, Tuple


class AIController:
    def __init__(self):
        # simple
        self.action_file = "run_log/unit_action.txt"
        # multi
        # 线程池（用于执行同步网络请求）
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        # 任务队列和结果队列
        self.pending_futures = []

    def load_actions(self, id=-1) -> List[Tuple[int, str, tuple]]:
        """
        Load and parse actions from the action file.
        Returns list of (unit_id, action_type, params) tuples.
        """
        if id != -1:
            self.action_file = f"run_log/action{id}.txt"
        else:
            self.action_file = "run_log/unit_action.txt"
        if not os.path.exists(self.action_file):
            return []

        actions = []
        with open(self.action_file, "r") as f:
            for line in f.readlines():
                parts = line.strip().split()
                if len(parts) < 2:
                    continue

                unit_id = int(parts[0])
                action = parts[1]

                if action == "move" and len(parts) == 4:
                    params = (int(parts[2]), int(parts[3]))
                    actions.append((unit_id, action, params))
                elif action == "attack" and len(parts) == 3:
                    params = [int(parts[2])]
                    actions.append((unit_id, action, params))

        return actions

    def execute_actions(self, game_controller, id=-1):
        """
        Execute all pending AI actions
        """
        actions = self.load_actions()
        for unit_id, action, params in actions:
            game_controller.unit_controller.load_action(unit_id, action, params)
        for (
            uid,
            _,
        ) in game_controller.unit_controller.unit_manager.unit_all_info.copy().items():
            game_controller.unit_controller.selected_unit_id = uid
            game_controller.unit_controller.step()

    def future_execute_actions(self, game_controller):
        """
        Execute all pending AI actions
        """
        for (
            uid,
            _,
        ) in game_controller.unit_controller.unit_manager.unit_all_info.copy().items():
            actions = self.load_actions(uid)
            print(f"Unit {uid} actions: {actions}")
            # self.execute_actions(game_controller, id)
            for unit_id, action, params in actions:
                game_controller.unit_controller.load_action(unit_id, action, params)
                # for uid, _ in game_controller.unit_controller.unit_all_info.copy().items():

            game_controller.unit_controller.selected_unit_id = uid
            game_controller.unit_controller.step()

    def multi_agent_think(self, game_controller):
        env_status = game_controller.unit_controller.environment_map
        agent_status = game_controller.unit_controller.unit_manager.unit_all_info

        # 获取所有代理的 ID 列表
        agent_ids_in_pending = [id for id, future in self.pending_futures]

        for agent in game_controller.unit_controller.unit_manager.agents:
            id = agent.id
            if id not in agent_ids_in_pending:
                print(f"Agent {id} 正在思考...")
                obs = f"""
你的 id 是 {id}
棋盘情况:
    地图信息:
        {env_status}
    单位信息:
        {agent_status}
"""
                with open(f"run_log/obs{id}.txt", "w") as f:
                    f.write(obs)
                future = self.thread_pool.submit(
                    agent.step,
                    obs,
                )  # 提交任务
                self.pending_futures.append((id, future))
            else:
                print(f"Agent {id} 已经在 pending 中，跳过思考...")

    def multi_agent_do(self, game_controller):
        completed = []
        for id, future in self.pending_futures:
            if future.done():
                agent_id, result = future.result()
                assert agent_id == id
                completed.append((id, future))
        for id, future in completed:
            self.pending_futures.remove((id, future))

        def re_ins():
            for id, future in completed:
                agent_id, result = future.result()
                assert agent_id == id
                actions = []
                pattern = r"---指令开始---(.*?)---指令结束---"
                matches = re.findall(pattern, result, re.DOTALL)
                if matches:
                    ins = matches[0]
                    for line in ins.split("\n"):
                        parts = line.strip().split()
                        if len(parts) < 2:
                            continue

                        unit_id = int(parts[0])
                        action = parts[1]

                        if action == "move" and len(parts) == 4:
                            params = (int(parts[2]), int(parts[3]))
                            actions.append((unit_id, action, params))
                        elif action == "attack" and len(parts) == 3:
                            params = [int(parts[2])]
                            actions.append((unit_id, action, params))
                    with open(f"run_log/action{id}.txt", "w") as f:
                        # 写入 actions
                        for unit_id, action, params in actions:
                            f.write(
                                f"{unit_id} {action} {' '.join(map(str, params))}\n"
                            )
                else:
                    continue

        re_ins()
        self.future_execute_actions(game_controller)

        return completed
