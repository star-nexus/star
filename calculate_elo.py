import json
import os
import math
import csv
import random
import statistics
from datetime import datetime
from collections import defaultdict
import glob

class EloSystem:
    def __init__(self, k_factor=32, initial_rating=1000):
        self.k = k_factor
        self.initial_rating = initial_rating
        # 每次 reset 后重新初始化
        self.reset()

    def reset(self):
        self.ratings = defaultdict(lambda: self.initial_rating)
        self.games_played = defaultdict(int)

    def get_rating(self, model_name):
        return self.ratings[model_name]

    def expected_score(self, rating_a, rating_b):
        """计算 A 对 B 的预期胜率"""
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

    def update(self, model_a, model_b, actual_score_a, multiplier=1.0):
        """
        更新分数 (单步)
        """
        ra = self.ratings[model_a]
        rb = self.ratings[model_b]

        ea = self.expected_score(ra, rb)
        
        # 统一 K 值，不再动态调整
        k_val = self.k
        
        # 核心公式：Delta = K * M * (S - E)
        delta_a = k_val * multiplier * (actual_score_a - ea)
        delta_b = k_val * multiplier * ((1 - actual_score_a) - (1 - ea)) 

        # 更新分数
        self.ratings[model_a] += delta_a
        self.ratings[model_b] += delta_b

        # 更新场次
        self.games_played[model_a] += 1
        self.games_played[model_b] += 1
        
        return delta_a, delta_b

class ReportAnalyzer:
    def __init__(self, report_dir="settlement_reports"):
        self.report_dir = report_dir
        self.max_duration = 3600.0  # 默认最大对局时间（秒）
        self.alpha = 0.5  # 战损权重
        self.beta = 0.5   # 时间权重
        self.bootstrap_iterations = 1000  # 蒙特卡洛模拟次数

    def load_reports_by_mode(self):
        """加载报告并按模式分类"""
        files = glob.glob(os.path.join(self.report_dir, "*.json"))
        reports_by_mode = defaultdict(list)
        
        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as f_obj:
                    data = json.load(f_obj)
                    if "winner_faction" in data and "model_info" in data:
                        # 获取游戏模式，默认为 'unknown'
                        mode = data.get("game_mode", "unknown")
                        
                        if "real" in mode.lower():
                            mode_key = "real_time"
                        elif "turn" in mode.lower():
                            mode_key = "turn_based"
                        else:
                            mode_key = "unknown"
                            
                        reports_by_mode[mode_key].append(data)
            except Exception as e:
                print(f"[Warning] Failed to load {f}: {e}")
        return reports_by_mode

    def calculate_pw_multiplier(self, report):
        """计算 PW-Elo 的表现乘数 M"""
        winner = report.get("winner_faction")
        if report.get("is_tie") or winner not in ["wei", "shu", "wu"]:
            return 1.0

        units_info = report.get("units_info", {}).get(winner, {})
        total_units = units_info.get("total_units", 5)
        surviving_units = units_info.get("surviving_units", 0)
        
        if total_units <= 0: total_units = 5
        u_score = surviving_units / total_units
        
        # 安全获取 duration，处理 None 或非数字的情况
        duration = report.get("game_duration_seconds")
        if duration is None or not isinstance(duration, (int, float)):
            duration = self.max_duration # 缺失数据按最差情况处理
            
        t_score = 1.0 - min(duration / self.max_duration, 1.0)

        m_multiplier = 1.0 + (self.alpha * u_score) + (self.beta * t_score)
        return m_multiplier

    def process_reports_sequence(self, reports, elo_system, is_pw=False):
        """处理给定的报告序列，计算一轮最终分"""
        elo_system.reset()
        
        for report in reports:
            model_wei = report["model_info"].get("wei", "Unknown-Wei")
            model_shu = report["model_info"].get("shu", "Unknown-Shu")
            
            if "placeholder" in model_wei or "placeholder" in model_shu:
                continue

            winner_faction = report.get("winner_faction")
            if report.get("is_tie"):
                score_wei = 0.5
            elif winner_faction == "wei":
                score_wei = 1.0
            elif winner_faction == "shu":
                score_wei = 0.0
            else:
                continue

            multiplier = self.calculate_pw_multiplier(report) if is_pw else 1.0
            elo_system.update(model_wei, model_shu, score_wei, multiplier=multiplier)

        return elo_system.ratings.copy(), elo_system.games_played.copy()

    def run_bootstrap_analysis(self, reports, mode_name="General"):
        if not reports:
            print(f"[{mode_name}] No reports found.")
            return [], []

        print(f"[{mode_name}] Loaded {len(reports)} match reports.")
        print(f"[{mode_name}] Running {self.bootstrap_iterations} bootstrap iterations...")
        
        std_elo = EloSystem(k_factor=32, initial_rating=1000)
        pw_elo = EloSystem(k_factor=32, initial_rating=1000)

        # 存储所有轮次的结果
        std_results = defaultdict(list)
        pw_results = defaultdict(list)
        games_counts = defaultdict(int)

        # 1. 蒙特卡洛模拟
        for i in range(self.bootstrap_iterations):
            # 随机打乱报告顺序 (创建副本以免影响原列表)
            shuffled_reports = list(reports)
            random.shuffle(shuffled_reports)
            
            # 计算 Standard Elo
            ratings_std, counts = self.process_reports_sequence(shuffled_reports, std_elo, is_pw=False)
            for m, r in ratings_std.items():
                std_results[m].append(r)
                if i == 0: games_counts[m] = counts[m]

            # 计算 PW-Elo
            ratings_pw, _ = self.process_reports_sequence(shuffled_reports, pw_elo, is_pw=True)
            for m, r in ratings_pw.items():
                pw_results[m].append(r)

        # 2. 统计结果
        final_stats_std = self.aggregate_stats(std_results, games_counts)
        final_stats_pw = self.aggregate_stats(pw_results, games_counts)
        
        return final_stats_std, final_stats_pw

    def aggregate_stats(self, results, games_counts):
        """计算均值和标准差"""
        stats = []
        for model, ratings in results.items():
            mean_rating = statistics.mean(ratings)
            stdev = statistics.stdev(ratings) if len(ratings) > 1 else 0.0
            stats.append({
                "model": model,
                "rating": mean_rating,
                "stdev": stdev,
                "games": games_counts[model]
            })
        return stats

    def save_leaderboard_csv(self, stats, filename):
        if not stats: return
        # 按分数排序
        stats.sort(key=lambda x: x["rating"], reverse=True)
        keys = ["rank", "model", "rating", "stdev", "games"]
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for rank, item in enumerate(stats, 1):
                row = item.copy()
                row["rank"] = rank
                row["rating"] = f"{item['rating']:.1f}"
                row["stdev"] = f"{item['stdev']:.1f}"
                writer.writerow(row)
        print(f"Leaderboard saved to {filename}")

def print_leaderboard(stats, title="Leaderboard"):
    print(f"\n=== {title} ===")
    if not stats:
        print("No data available.")
        return

    # 按分数降序排列
    stats.sort(key=lambda x: x["rating"], reverse=True)
    
    print(f"{'Rank':<4} | {'Model Name':<50} | {'Rating (Mean ± Std)':<20} | {'Games':<5}")
    print("-" * 90)
    for rank, item in enumerate(stats, 1):
        rating_str = f"{item['rating']:.1f} ± {item['stdev']:.1f}"
        print(f"{rank:<4} | {item['model']:<50} | {rating_str:<20} | {item['games']:<5}")
    print("-" * 90)

if __name__ == "__main__":
    analyzer = ReportAnalyzer()
    
    # 1. 加载并分类
    reports_map = analyzer.load_reports_by_mode()
    
    # 2. 针对 Turn-Based 模式计算
    print("\n>>> Processing Turn-Based Mode <<<")
    tb_reports = reports_map.get("turn_based", [])
    tb_stats_std, tb_stats_pw = analyzer.run_bootstrap_analysis(tb_reports, "Turn-Based")
    
    print_leaderboard(tb_stats_std, "Turn-Based: Standard Elo (Bootstrap)")
    print_leaderboard(tb_stats_pw, "Turn-Based: PW-Elo (Bootstrap)")
    analyzer.save_leaderboard_csv(tb_stats_std, "leaderboard_turn_based_std.csv")
    analyzer.save_leaderboard_csv(tb_stats_pw, "leaderboard_turn_based_pw.csv")

    # 3. 针对 Real-Time 模式计算
    print("\n>>> Processing Real-Time Mode <<<")
    rt_reports = reports_map.get("real_time", [])
    rt_stats_std, rt_stats_pw = analyzer.run_bootstrap_analysis(rt_reports, "Real-Time")
    
    print_leaderboard(rt_stats_std, "Real-Time: Standard Elo (Bootstrap)")
    print_leaderboard(rt_stats_pw, "Real-Time: PW-Elo (Bootstrap)")
    analyzer.save_leaderboard_csv(rt_stats_std, "leaderboard_real_time_std.csv")
    analyzer.save_leaderboard_csv(rt_stats_pw, "leaderboard_real_time_pw.csv")
