#!/usr/bin/env python3
"""
Tournament Match Launcher
启动锦标赛对战的Python脚本

使用方法:
python tournament_launcher.py --match 1 --game 1
"""

import json
import sys
import argparse
import subprocess
import time
from pathlib import Path


def load_tournament_data():
    """加载锦标赛数据"""
    json_file = Path(__file__).parent / "tournament_schedule.json"
    
    if not json_file.exists():
        print(f"错误: 找不到赛程文件 {json_file}")
        sys.exit(1)
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"错误: 读取赛程文件失败: {e}")
        sys.exit(1)


def find_match_game(tournament_data, match_id, game_num):
    """查找指定场次和游戏"""
    matches = tournament_data.get("tournament", {}).get("matches", [])
    
    # 查找指定场次
    target_match = None
    for match in matches:
        if match["match_id"] == match_id:
            target_match = match
            break
    
    if not target_match:
        print(f"错误: 找不到第 {match_id} 场比赛")
        return None
    
    # 查找指定游戏
    games = target_match.get("games", [])
    target_game = None
    for game in games:
        if game["game"] == game_num:
            target_game = game
            break
    
    if not target_game:
        print(f"错误: 第 {match_id} 场比赛中找不到第 {game_num} 局")
        return None
    
    return target_match, target_game


def generate_agent_id(model_name, faction):
    """生成agent ID"""
    # 将模型名转换为适合的ID格式
    clean_name = model_name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")
    return f"agent_{clean_name}_{faction}"


def launch_env(match_data, game_data, mode = "turn_based",dry_run=False):
    """启动游戏环境"""
    env_id = f"env_match_{match_data['match_id']}_game_{game_data['game']}"
    
    # 环境启动命令
    env_cmd = [
        "uv", "run", "rotk_env/main.py",
        "--headless",
        "--mode", mode,
        "--players", "ai_vs_ai",
        "--env_id", env_id
    ]
    
    print(f"\n=== 启动游戏环境 ===")
    print(f"环境ID: {env_id}")
    print(f"启动命令: SDL_VIDEODRIVER=dummy {' '.join(env_cmd)}")
    
    if dry_run:
        print("=== 干运行模式: 不实际启动环境 ===")
        return None
    else:
        print(f"正在启动游戏环境...")
        
        # 设置环境变量
        import os
        env = os.environ.copy()
        env['SDL_VIDEODRIVER'] = 'dummy'
        
        env_process = subprocess.Popen(env_cmd, env=env)
        
        print(f"游戏环境已启动! 进程ID: {env_process.pid}")
        print(f"等待环境初始化...")
        time.sleep(5)  # 等待环境完全启动
        
        return env_process


def launch_agents(match_data, game_data, dry_run=False):
    """启动对战的两个agent"""
    wei_model = game_data["wei"]
    shu_model = game_data["shu"]
    wei_model_id = game_data["wei_model_id"]
    shu_model_id = game_data["shu_model_id"]
    
    # 生成agent ID
    wei_agent_id = generate_agent_id(wei_model, "wei")
    shu_agent_id = generate_agent_id(shu_model, "shu")
    
    print(f"\n=== 第 {match_data['match_id']} 场比赛 - 第 {game_data['game']} 局 ===")
    print(f"Wei阵营: {wei_model} (模型: {wei_model_id})")
    print(f"Shu阵营: {shu_model} (模型: {shu_model_id})")
    print(f"Agent IDs: {wei_agent_id} vs {shu_agent_id}")
    
    # Wei阵营启动命令
    wei_cmd = [
        "uv", "run", "rotk_agent/qwen3_agent.py",
        "--env-id", f"env_match_{match_data['match_id']}_game_{game_data['game']}",
        "--agent-id", wei_agent_id,
        "--faction", "wei",
        "--provider", "infinigence",
        "--model_id", wei_model_id
    ]
    
    # Shu阵营启动命令
    shu_cmd = [
        "uv", "run", "rotk_agent/qwen3_agent.py",
        "--env-id", f"env_match_{match_data['match_id']}_game_{game_data['game']}",
        "--agent-id", shu_agent_id,
        "--faction", "shu",
        "--provider", "infinigence",
        "--model_id", shu_model_id
    ]
    
    print(f"\n启动Wei阵营:")
    print(" ".join(wei_cmd))
    print(f"\n启动Shu阵营:")
    print(" ".join(shu_cmd))
    print(f"\n请在两个终端分别运行上述命令")
    
    # 可选: 自动启动 (需要用户确认)
    if dry_run:
        print("=== 干运行模式: 不实际启动进程 ===")
        return
    else:
        print(f"\n正在启动Wei阵营...")
        wei_process = subprocess.Popen(wei_cmd)
        
        time.sleep(2)  # 等待Wei阵营启动
        
        print(f"正在启动Shu阵营...")
        shu_process = subprocess.Popen(shu_cmd)
        
        print(f"\n两个agents已启动!")
        print(f"Wei进程ID: {wei_process.pid}")
        print(f"Shu进程ID: {shu_process.pid}")
        print(f"\n使用 Ctrl+C 或 kill 命令来停止进程")
        
        try:
            # 等待进程结束
            wei_process.wait()
            shu_process.wait()
        except KeyboardInterrupt:
            print(f"\n正在终止进程...")
            wei_process.terminate()
            shu_process.terminate()


def main():
    parser = argparse.ArgumentParser(description="启动锦标赛对战")
    # parser.add_argument("--headless", action="store_true", help="以无头模式运行环境")
    parser.add_argument("--mode", choices=["turn_based", "real_time"], default="turn_based", help="游戏模式")
    parser.add_argument("--match", type=int, required=True, help="场次编号 (1-91)")
    parser.add_argument("--game", type=int, required=True, help="游戏编号 (1-3)")
    parser.add_argument("--dry-run", action="store_true", help="只显示命令，不实际启动")
    
    args = parser.parse_args()
    
    # 验证参数
    if args.match < 1 or args.match > 91:
        print("错误: 场次编号必须在 1-91 之间")
        sys.exit(1)
    
    if args.game < 1 or args.game > 3:
        print("错误: 游戏编号必须在 1-3 之间")
        sys.exit(1)
    
    # 加载锦标赛数据
    tournament_data = load_tournament_data()
    
    # 查找对战信息
    result = find_match_game(tournament_data, args.match, args.game)
    if not result:
        sys.exit(1)
    
    match_data, game_data = result


    
    # 检查是否是加时赛
    if game_data.get("condition") == "tie_breaker":
        # confirm = input(f"这是第 {args.match} 场的加时赛第3局，只有在前两局1-1平局时才需要进行。确认继续? (y/N): ")
        # if confirm.strip().lower() != 'y':
        #     print("已取消")
        #     sys.exit(0)
        pass
    
    # 启动环境和agents
    if args.dry_run:
        print("=== 干运行模式 ===")
        launch_env(match_data, game_data, mode=args.mode, dry_run=True)
        launch_agents(match_data, game_data, dry_run=True)
    else:
        env_process = launch_env(match_data, game_data, mode=args.mode, dry_run=False)
        try:
            launch_agents(match_data, game_data)
        finally:
            # 确保环境进程被清理
            if env_process and env_process.poll() is None:
                print("\n正在清理环境进程...")
                env_process.terminate()
                try:
                    env_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    env_process.kill()


if __name__ == "__main__":
    main()