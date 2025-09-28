#!/usr/bin/env python3
"""
生成完整的锦标赛赛程JSON文件
"""

import json
from itertools import combinations

# 模型列表
models = [
    {"id": 1, "name": "Gemini 2.5 pro", "model_id": "gemini-2.5-pro"},
    {"id": 2, "name": "grok-3 beta", "model_id": "grok-3-beta"},
    {"id": 3, "name": "gpt-4o", "model_id": "gpt-4o"},
    {"id": 4, "name": "Sonnet 4", "model_id": "claude-sonnet-4-20250514"},
    {"id": 5, "name": "GLM4.5", "model_id": "glm-4.5"},
    {"id": 6, "name": "GLM-4.5-Air", "model_id": "glm-4.5-air"},
    {"id": 7, "name": "Kimi 2", "model_id": "kimi-2"},
    {"id": 8, "name": "DeepSeek-R1", "model_id": "deepseek-r1"},
    {"id": 9, "name": "DeepSeek-V3.1-Terminus", "model_id": "deepseek-v3.1-terminus"},
    {"id": 10, "name": "Qwen3-Next-80B-A3B-Instruct", "model_id": "qwen3-next-80b-a3b-instruct"},
    {"id": 11, "name": "Qwen3-Next-80B-A3B-Thinking", "model_id": "qwen3-next-80b-a3b-thinking"},
    {"id": 12, "name": "gpt-oss-20b", "model_id": "gpt-oss-20b"},
    {"id": 13, "name": "gpt-oss-120b", "model_id": "gpt-oss-120b"},
    {"id": 14, "name": "llama-33-70b-instruct", "model_id": "llama-33-70b-instruct"}
]

def generate_matches():
    """生成所有91场比赛"""
    matches = []
    match_id = 1
    
    # 生成所有两两组合 (C(14,2) = 91)
    for model_a, model_b in combinations(models, 2):
        match = {
            "match_id": match_id,
            "model_a": {"id": model_a["id"], "name": model_a["name"]},
            "model_b": {"id": model_b["id"], "name": model_b["name"]},
            "games": [
                {
                    "game": 1,
                    "wei": model_a["name"],
                    "shu": model_b["name"],
                    "wei_model_id": model_a["model_id"],
                    "shu_model_id": model_b["model_id"]
                },
                {
                    "game": 2,
                    "wei": model_b["name"],
                    "shu": model_a["name"],
                    "wei_model_id": model_b["model_id"],
                    "shu_model_id": model_a["model_id"]
                },
                {
                    "game": 3,
                    "wei": model_a["name"],
                    "shu": model_b["name"],
                    "wei_model_id": model_a["model_id"],
                    "shu_model_id": model_b["model_id"],
                    "condition": "tie_breaker"
                }
            ]
        }
        matches.append(match)
        match_id += 1
    
    return matches

def main():
    # 生成完整的锦标赛数据
    tournament_data = {
        "tournament": {
            "name": "三国策略游戏 AI 模型锦标赛",
            "format": "双循环积分赛",
            "rounds": 2,
            "models": models,
            "matches": generate_matches()
        }
    }
    
    # 写入JSON文件
    with open("tournament_schedule_full.json", "w", encoding="utf-8") as f:
        json.dump(tournament_data, f, ensure_ascii=False, indent=2)
    
    print(f"已生成完整的锦标赛赛程，共 {len(tournament_data['tournament']['matches'])} 场比赛")
    
    # 打印前几场和后几场作为验证
    matches = tournament_data['tournament']['matches']
    print(f"\n前3场比赛:")
    for i in range(3):
        match = matches[i]
        print(f"第{match['match_id']}场: {match['model_a']['name']} vs {match['model_b']['name']}")
    
    print(f"\n后3场比赛:")
    for i in range(-3, 0):
        match = matches[i]
        print(f"第{match['match_id']}场: {match['model_a']['name']} vs {match['model_b']['name']}")

if __name__ == "__main__":
    main()