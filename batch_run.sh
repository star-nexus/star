#!/bin/bash
# 批量运行 Headless 模式测试脚本
# 用法: ./batch_run.sh [次数] [其他参数...]

COUNT=${1:-10}  # 默认运行10次
shift  # 移除第一个参数(次数)，剩余参数传递给 run_headless_env.sh

echo "Starting batch run of $COUNT games..."

for ((i=1; i<=COUNT; i++))
do
    echo "----------------------------------------"
    echo "Running game $i / $COUNT"
    echo "----------------------------------------"
    
    # 运行单局游戏
    ./run_headless_env.sh "$@"
    
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -ne 0 ]; then
        echo "Game $i failed with exit code $EXIT_CODE"
        # 可以选择在这里退出，或者继续运行
        # exit $EXIT_CODE
    else
        echo "Game $i completed successfully"
    fi
    
    # 可选：短暂休眠，确保资源释放
    sleep 2
done

echo "Batch run completed."
