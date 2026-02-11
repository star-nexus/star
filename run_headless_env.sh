#!/bin/bash
# 开启 Headless 模式运行环境
# HEADLESS=1 环境变量确保 GameEngine 初始化时不创建图形窗口
# --headless 参数确保跳过开始界面，直接进入游戏逻辑

export HEADLESS=1
uv run rotk_env/main.py --headless "$@"
