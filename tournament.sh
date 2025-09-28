#!/bin/bash

# Tournament Shell Script
# 使用 ./tournament.sh X Y 的格式启动第X场比赛的第Y局

if [ "$#" -eq 0 ]; then
    echo "Tournament 启动脚本使用说明:"
    echo ""
    echo "启动环境:"
    echo "  ./tournament.sh env             - 启动游戏环境(GUI模式)"
    echo ""
    echo "环境测试 (headless模式):"
    echo "  ./tournament.sh headless turn       - 测试回合制AI vs AI"
    echo "  ./tournament.sh headless real       - 测试实时制AI vs AI"
    echo "  ./tournament.sh headless both       - 测试两种模式"
    echo ""
    echo "启动比赛:"
    echo "  ./tournament.sh X Y             - 启动第X场比赛的第Y局"
    echo "                                    X: 场次 (1-91)"
    echo "                                    Y: 局数 (1-3)"
    echo ""
    echo "示例:"
    echo "  ./tournament.sh 1 1             - 第1场第1局"
    echo "  ./tournament.sh 15 2            - 第15场第2局"
    echo "  ./tournament.sh 91 3            - 第91场第3局"
    echo ""
    echo "干运行 (查看命令但不执行):"
    echo "  ./tournament.sh 1 1 dry         - 查看第1场第1局的启动命令"
    echo ""
    echo "注意: 第3局只有在前两局1-1平局时才需要进行"
    exit 0
fi

if [ "$1" = "env" ]; then
    echo "启动游戏环境(GUI模式)..."
    uv run rotk_env/main.py
    exit 0
fi

if [ "$1" = "headless" ]; then
    echo "开始环境测试 (headless模式)..."
    
    if [ "$2" = "turn" ] || [ "$2" = "both" ]; then
        echo ""
        echo "=== 测试回合制模式 AI vs AI ==="
        echo "启动参数: --headless --mode turn_based --players ai_vs_ai"
        echo "开始测试..."
        
        start_time=$(date +%s)
        # SDL_VIDEODRIVER=dummy 
        uv run rotk_env/main.py --headless --mode turn_based --players ai_vs_ai
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        
        echo "回合制测试完成，耗时: ${duration}秒"
        
        if [ "$2" = "both" ]; then
            echo ""
            echo "等待3秒后开始下一个测试..."
            sleep 3
        fi
    fi
    
    if [ "$2" = "real" ] || [ "$2" = "both" ]; then
        echo ""
        echo "=== 测试实时制模式 AI vs AI ==="
        echo "启动参数: --headless --mode real_time --players ai_vs_ai"
        echo "开始测试..."
        
        start_time=$(date +%s)
        # SDL_VIDEODRIVER=dummy 
        uv run rotk_env/main.py --headless --mode real_time --players ai_vs_ai
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        
        echo "实时制测试完成，耗时: ${duration}秒"
    fi
    
    if [ "$2" != "turn" ] && [ "$2" != "real" ] && [ "$2" != "both" ]; then
        echo "错误: 无效的测试模式"
        echo "支持的测试模式: turn, real, both"
        echo "使用方法:"
        echo "  ./tournament.sh test turn   - 测试回合制"
        echo "  ./tournament.sh test real   - 测试实时制" 
        echo "  ./tournament.sh test both   - 测试两种模式"
        exit 1
    fi
    
    echo ""
    echo "环境测试完成！"
    exit 0
fi

if [ "$#" -lt 2 ]; then
    echo "错误: 需要提供场次和局数"
    echo "使用方法: ./tournament.sh X Y [dry]"
    exit 1
fi

MATCH=$1
GAME=$2
DRY_RUN=""

if [ "$3" = "dry" ]; then
    DRY_RUN="--dry-run"
fi

echo "启动第 $MATCH 场比赛的第 $GAME 局..."
python tournament_launcher.py --match $MATCH --game $GAME $DRY_RUN