import subprocess
import time
import os
import signal
import sys
import argparse
from typing import Optional, Tuple

try:
    import toml
except ImportError:
    toml = None


def _validate_providers(wei: str, shu: str, config_path: str = ".configs.toml") -> Tuple[bool, str]:
    """校验 provider 是否存在于 .configs.toml 且含有 model_id。返回 (True, '') 或 (False, '错误信息')。"""
    if not os.path.exists(config_path):
        return False, f"Config file not found: {config_path}"
    if toml is None:
        return False, "toml package required for provider validation. Install with: pip install toml"
    try:
        config = toml.load(config_path)
    except Exception as e:
        return False, f"Cannot load config {config_path}: {e}"
    for label, prov in [("Wei", wei), ("Shu", shu)]:
        if prov not in config:
            return False, f"Provider '{prov}' ({label}) not found in {config_path}. Check model name in match list (e.g. typo: siliconflow_kimi_instruc -> siliconflow_kimi_instruct)."
        entry = config[prov]
        if not isinstance(entry, dict):
            return False, f"Provider '{prov}' ({label}) is not a valid section in {config_path}."
        if "model_id" not in entry:
            return False, f"Provider '{prov}' ({label}) has no 'model_id' in {config_path}."
    return True, ""


def _find_recent_report(start_time: float) -> Optional[str]:
    report_dir = "settlement_reports"
    if not os.path.isdir(report_dir):
        return None

    newest_path = None
    newest_mtime = start_time
    for filename in os.listdir(report_dir):
        if not filename.startswith("report_"):
            continue
        path = os.path.join(report_dir, filename)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime >= newest_mtime:
            newest_mtime = mtime
            newest_path = path

    return newest_path


def _wait_for_env_ready(env_log_path: str, env_process: subprocess.Popen, timeout: int = 60) -> bool:
    """Wait for environment to be ready before starting agents."""
    ready_markers = ("LLMSystem connected", "Game started!")
    deadline = time.time() + timeout

    while time.time() < deadline:
        if env_process.poll() is not None:
            return False

        try:
            if os.path.exists(env_log_path):
                with open(env_log_path, "r") as f:
                    content = f.read()
                if any(marker in content for marker in ready_markers):
                    return True
        except OSError:
            pass

        time.sleep(1)

    return False


def run_match(
    wei_model,
    shu_model,
    match_index,
    mode="turn_based",
    players="ai_vs_ai",
    timeout=None,
    report_wait=60,
):
    print(
        f"\n>>> Starting Match {match_index}: "
        f"Wei({wei_model}) vs Shu({shu_model}) | Mode: {mode} | Players: {players}"
    )

    # 开跑前校验 provider 是否在 .configs.toml 中存在，避免因模型名填错导致 Agent 无限重试
    ok, err = _validate_providers(wei_model, shu_model)
    if not ok:
        print(f"  ERROR: {err}")
        print("  Skipping this match. Fix match_list and .configs.toml.")
        return

    # 为本次对局生成唯一 env_id，避免多 shell 并行跑 auto_test 时与其它进程的 ENV 冲突。
    # 同一 auto_test 进程内对局串行，同一时刻仅一个 ENV，故用进程 PID 即可。
    pid = os.getpid()
    env_id = f"env_{pid}"
    # 日志按 run 隔离：logs/run_{pid}/，多进程并行时各写各目录，不互相覆盖
    log_dir = f"logs/run_{pid}"
    os.makedirs(log_dir, exist_ok=True)

    # 1. 启动环境 (Headless)，通过 --env-id 显式传入，run_headless_env 透传 $@ 给 main.py
    env_cmd = [
        "./run_headless_env.sh",
        "--env-id", env_id,
        "--players", players,
        "--mode", mode,
        "--scenario", "default"
    ]
    
    env_log_path = f"{log_dir}/match_{match_index}_env.log"
    wei_log_path = f"{log_dir}/match_{match_index}_wei.log"
    shu_log_path = f"{log_dir}/match_{match_index}_shu.log"
    
    env_log = open(env_log_path, "w")
    wei_log = open(wei_log_path, "w")
    shu_log = open(shu_log_path, "w")

    print(f"  Launching Environment (Log: {env_log_path}, ENV_ID={env_id})...")
    start_time = time.time()
    env_vars = os.environ.copy()
    env_vars["PYTHONUNBUFFERED"] = "1"
    env_process = subprocess.Popen(
        env_cmd,
        stdout=env_log,
        stderr=subprocess.STDOUT,
        env=env_vars,
    )
    
    # 等待环境完成初始化（WebSocket 服务启动）
    if not _wait_for_env_ready(env_log_path, env_process, timeout=60):
        print("  Environment did not become ready in time. Terminating...")
        env_process.terminate()
        cleanup(env_process, None, None)
        env_log.close()
        wei_log.close()
        shu_log.close()
        return
    
    # 2. 启动 Wei Agent
    # agent_id 按 run 隔离，避免多 auto_test 并行时与同一 Hub 上其它 run 的 agent_id 冲突
    wei_agent_id = f"agent_wei_{match_index}_{pid}"
    shu_agent_id = f"agent_shu_{match_index}_{pid}"
    print(f"  Launching Wei Agent ({wei_model}) (Log: {wei_log_path})...")

    wei_cmd = [
        "./run_agent_generic.sh",
        env_id,         # ENV_ID，与本次 ENV 的 ENV_ID 一致，确保连到同一局
        wei_agent_id,  # AGENT_ID
        "wei",         # FACTION
        wei_model,     # PROVIDER
        mode           # MODE
    ]
    wei_start_time = time.time()
    wei_process = subprocess.Popen(wei_cmd, stdout=wei_log, stderr=subprocess.STDOUT)

    # 3. 启动 Shu Agent
    print(f"  Launching Shu Agent ({shu_model}) (Log: {shu_log_path})...")
    shu_cmd = [
        "./run_agent_generic.sh",
        env_id,         # ENV_ID，与本次 ENV 的 ENV_ID 一致
        shu_agent_id,  # AGENT_ID
        "shu",         # FACTION
        shu_model,     # PROVIDER
        mode           # MODE
    ]
    shu_start_time = time.time()
    shu_process = subprocess.Popen(shu_cmd, stdout=shu_log, stderr=subprocess.STDOUT)

    # 4. 监控环境进程
    try:
        print("  Match in progress... waiting for environment to exit.")
        timed_out = False
        agent_failed = False
        startup_failure = False
        start_wait = time.time()
        startup_grace_s = 60  # Agent 在 60s 内非零退出视为启动失败（如 LLM 配置错误）

        while True:
            if env_process.poll() is not None:
                break

            # Agent 启动失败：配置错误等会导致进程快速非零退出，直接终止本局
            if wei_process.poll() is not None and wei_process.returncode != 0 and (time.time() - wei_start_time) < startup_grace_s:
                print(f"  Wei Agent failed to start (exit code {wei_process.returncode}). Likely invalid LLM provider/config. Aborting match.")
                startup_failure = True
                env_process.terminate()
                break
            if shu_process.poll() is not None and shu_process.returncode != 0 and (time.time() - shu_start_time) < startup_grace_s:
                print(f"  Shu Agent failed to start (exit code {shu_process.returncode}). Likely invalid LLM provider/config. Aborting match.")
                startup_failure = True
                env_process.terminate()
                break

            # 检查是否所有Agent都退出了
            if wei_process.poll() is not None and shu_process.poll() is not None:
                print("  Both agents exited. Waiting for environment to finish...")
                # 给ENV一些时间来完成结算和退出
                try:
                    env_process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    print("  Environment running too long after agents exited. Terminating...")
                    env_process.terminate()
                break
            
            # 如果只是单个Agent退出，先记录，但不立即杀死ENV，也许另一个Agent还在收尾
            if wei_process.poll() is not None and not agent_failed:
                print("  Wei Agent exited.")
                agent_failed = True
            if shu_process.poll() is not None and not agent_failed:
                print("  Shu Agent exited.")
                agent_failed = True

            if timeout is not None and timeout > 0:
                if time.time() - start_wait >= timeout:
                    timed_out = True
                    print("  TIMEOUT! Terminating environment...")
                    env_process.terminate()
                    break

            time.sleep(1)

        # 等待环境进程真正退出
        try:
            env_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print("  Environment did not exit after terminate; killing now.")
            env_process.kill()
            env_process.wait(timeout=10)

        if startup_failure:
            print("  Match aborted: agent failed to start (invalid LLM config).")
        elif timed_out:
            print("  Environment exited due to timeout.")
        elif agent_failed:
            print("  Environment exited due to agent failure.")
        else:
            print("  Environment exited normally.")

            # 等待结算报告写入完成
            if report_wait > 0:
                print(f"  Waiting for settlement report (up to {report_wait}s)...")
                deadline = time.time() + report_wait
                report_path = None
                while time.time() < deadline:
                    report_path = _find_recent_report(start_time)
                    if report_path:
                        print(f"  Report generated: {report_path}")
                        break
                    time.sleep(1)
                if report_path is None:
                    print("  Warning: No new settlement report detected.")
        
    except subprocess.TimeoutExpired:
        print("  TIMEOUT! Killing environment.")
        env_process.kill()
    except KeyboardInterrupt:
        print("  Interrupted by user.")
        cleanup(env_process, wei_process, shu_process)
        # 关闭文件句柄
        env_log.close()
        wei_log.close()
        shu_log.close()
        sys.exit(1)
    finally:
        # 5. 清理：无论如何，结束后杀掉 Agents
        print("  Cleaning up processes...")
        cleanup(env_process, wei_process, shu_process)
        
        # 关闭日志文件
        env_log.close()
        wei_log.close()
        shu_log.close()

def cleanup(env, wei, shu):
    """终止所有子进程"""
    for p in [env, wei, shu]:
        if p and p.poll() is None: # 如果进程还在运行
            try:
                # 发送 SIGTERM
                p.terminate()
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill() # 强杀
            except Exception as e:
                print(f"Error killing process: {e}")

def main():
    parser = argparse.ArgumentParser(description="Batch run StarBench matches")
    parser.add_argument("--list", default="match_list.txt", help="Path to match list file")
    parser.add_argument("--mode", default="turn_based", choices=["turn_based", "real_time"], help="Game mode")
    parser.add_argument("--players", default="ai_vs_ai", choices=["human_vs_ai", "ai_vs_ai", "three_kingdoms"], help="Player configuration")
    parser.add_argument("--timeout", type=int, default=0, help="Environment timeout in seconds (0 = no timeout)")
    parser.add_argument("--report-wait", type=int, default=60, help="Seconds to wait for settlement report after env exit")
    args = parser.parse_args()

    if not os.path.exists(args.list):
        print(f"Error: Match list file '{args.list}' not found.")
        print("Please create it with format: WEI_PROVIDER,SHU_PROVIDER (one match per line)")
        return

    with open(args.list, "r") as f:
        matches = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    print(f"Loaded {len(matches)} matches from {args.list}.")

    for i, match in enumerate(matches):
        try:
            parts = match.split(",")
            if len(parts) >= 2:
                wei = parts[0].strip()
                shu = parts[1].strip()
                run_match(
                    wei,
                    shu,
                    i + 1,
                    mode=args.mode,
                    players=args.players,
                    timeout=None if args.timeout <= 0 else args.timeout,
                    report_wait=args.report_wait,
                )
                
                # 局间休息，确保端口释放
                print("  Cooling down for 5 seconds...")
                time.sleep(5)
            else:
                print(f"Skipping invalid line: {match}")
                
        except ValueError:
            print(f"Skipping invalid line: {match}")
            continue

if __name__ == "__main__":
    main()
