#!/bin/bash

# Tournament Multi-Terminal Launcher
# 在不同终端启动锦标赛对战
# 使用方法: ./multi_terminal_launcher.sh --help

set -e

# 脚本配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOURNAMENT_JSON="$SCRIPT_DIR/tournament_schedule.json"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${PURPLE}$1${NC}"
}

# 显示帮助信息
show_help() {
    echo "Tournament Multi-Terminal Launcher"
    echo "=================================="
    echo ""
    echo "用法:"
    echo "  $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --match X              启动第X场比赛的所有局数 (1-91)"
    echo "  --matches X,Y,Z        启动多个比赛场次"
    echo "  --game N               只启动指定局数 (1-3), 与--match配合使用"
    echo "  --mode MODE            游戏模式: turn_based 或 real_time (默认: turn_based)"
    echo "  --terminal-type TYPE   终端类型: gnome, xterm, iterm, auto (默认: auto)"
    echo "  --dry-run              只显示将要执行的命令，不实际启动"
    echo "  --help                 显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 --match 1                          # 启动第1场的所有3局"
    echo "  $0 --match 1 --game 1                 # 只启动第1场第1局"
    echo "  $0 --matches 1,2,3                    # 启动第1,2,3场的所有局"
    echo "  $0 --match 1 --mode real_time         # 实时制模式"
    echo "  $0 --match 1 --terminal-type iterm    # 使用iTerm终端"
    echo "  $0 --match 1 --dry-run                # 干运行模式"
    echo ""
    echo "支持的终端类型:"
    echo "  gnome     - GNOME Terminal (Linux)"
    echo "  xterm     - XTerm (Linux/macOS)"
    echo "  terminal  - macOS系统终端"
    echo "  iterm     - iTerm2 (macOS)"
    echo "  auto      - 自动检测系统终端"
    echo ""
}

# 检测系统终端类型
detect_terminal_type() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS - 检查可用的终端
        if osascript -e 'tell application "System Events" to get name of processes' | grep -q "iTerm2"; then
            echo "iterm"
        elif osascript -e 'tell application "System Events" to get name of processes' | grep -q "Terminal"; then
            echo "terminal"
        elif command -v xterm >/dev/null 2>&1; then
            echo "xterm"
        else
            echo "terminal"  # 默认使用系统终端
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v gnome-terminal >/dev/null 2>&1; then
            echo "gnome"
        else
            echo "xterm"
        fi
    else
        echo "xterm"
    fi
}

# 在新终端中执行命令
execute_in_terminal() {
    local title="$1"
    local command="$2"
    local terminal_type="$3"
    
    case "$terminal_type" in
        "gnome")
            gnome-terminal --title="$title" -- bash -c "cd '$SCRIPT_DIR' && $command; echo '按任意键关闭...'; read -n 1"
            ;;
        "xterm")
            xterm -title "$title" -e bash -c "cd '$SCRIPT_DIR' && $command; echo '按任意键关闭...'; read -n 1" &
            ;;
        "terminal")
            # macOS系统终端
            osascript -e "
            tell application \"Terminal\"
                activate
                do script \"cd '$SCRIPT_DIR' && $command\"
                set custom title of front window to \"$title\"
            end tell"
            ;;
        "iterm")
            # iTerm2
            if ! osascript -e 'tell application "System Events" to get name of processes' | grep -q "iTerm2"; then
                print_warning "iTerm2 未运行，尝试启动..."
                open -a "iTerm" 2>/dev/null || open -a "iTerm2" 2>/dev/null || {
                    print_error "无法启动iTerm，fallback到系统终端"
                    execute_in_terminal "$title" "$command" "terminal"
                    return
                }
                sleep 2
            fi
            
            osascript -e "
            tell application \"iTerm\"
                activate
                create window with default profile
                tell current session of current window
                    write text \"cd '$SCRIPT_DIR'\"
                    write text \"$command\"
                    set name to \"$title\"
                end tell
            end tell" 2>/dev/null || {
                print_warning "iTerm启动失败，使用系统终端"
                execute_in_terminal "$title" "$command" "terminal"
            }
            ;;
        *)
            print_error "不支持的终端类型: $terminal_type"
            return 1
            ;;
    esac
}

# 检查锦标赛数据文件
check_tournament_file() {
    if [[ ! -f "$TOURNAMENT_JSON" ]]; then
        print_error "找不到锦标赛数据文件: $TOURNAMENT_JSON"
        exit 1
    fi
}

# 解析锦标赛数据
parse_tournament_data() {
    local match_id="$1"
    local game_num="$2"
    
    # 使用python解析JSON (更可靠)
    python3 <<EOF
import json
import sys

try:
    with open('$TOURNAMENT_JSON', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    matches = data.get('tournament', {}).get('matches', [])
    
    target_match = None
    for match in matches:
        if match['match_id'] == $match_id:
            target_match = match
            break
    
    if not target_match:
        print(f"ERROR: 找不到第 $match_id 场比赛", file=sys.stderr)
        sys.exit(1)
    
    if $game_num == 0:
        # 输出所有局数
        for game in target_match['games']:
            print(f"{game['game']}|{game['wei']}|{game['shu']}|{game['wei_model_id']}|{game['shu_model_id']}")
    else:
        # 输出特定局数
        target_game = None
        for game in target_match['games']:
            if game['game'] == $game_num:
                target_game = game
                break
        
        if not target_game:
            print(f"ERROR: 第 $match_id 场比赛中找不到第 $game_num 局", file=sys.stderr)
            sys.exit(1)
        
        print(f"{target_game['game']}|{target_game['wei']}|{target_game['shu']}|{target_game['wei_model_id']}|{target_game['shu_model_id']}")

except Exception as e:
    print(f"ERROR: 解析锦标赛数据失败: {e}", file=sys.stderr)
    sys.exit(1)
EOF
}

# 生成Agent ID
generate_agent_id() {
    local model_name="$1"
    local faction="$2"
    local env_id="$3"
    
    # 将模型名转换为适合的ID格式
    local clean_name=$(echo "$model_name" | tr '[:upper:]' '[:lower:]' | sed 's/[ \.-]/_/g')
    echo "agent_${clean_name}_${faction}_${env_id}"
}

# 启动单局比赛
launch_single_game() {
    local match_id="$1"
    local game_num="$2"
    local mode="$3"
    local terminal_type="$4"
    local dry_run="$5"
    
    print_header "=== 启动第 $match_id 场比赛 - 第 $game_num 局 ==="
    
    # 解析比赛数据
    local game_data
    game_data=$(parse_tournament_data "$match_id" "$game_num")
    
    if [[ $? -ne 0 ]]; then
        print_error "解析比赛数据失败"
        return 1
    fi
    
    # 解析数据字段
    IFS='|' read -r game_id wei_model shu_model wei_model_id shu_model_id <<< "$game_data"
    
    local env_id="env_match_${match_id}_game_${game_num}"
    local wei_agent_id=$(generate_agent_id "$wei_model" "wei" "$env_id")
    local shu_agent_id=$(generate_agent_id "$shu_model" "shu" "$env_id")
    
    print_info "对战信息:"
    echo "  环境ID: $env_id"
    echo "  Wei阵营: $wei_model (模型: $wei_model_id)"
    echo "  Shu阵营: $shu_model (模型: $shu_model_id)"
    echo "  游戏模式: $mode"
    echo ""
    
    # 生成启动命令
    local env_cmd="SDL_VIDEODRIVER=dummy uv run rotk_env/main.py --headless --mode $mode --players ai_vs_ai --env_id $env_id"
    local wei_cmd="uv run rotk_agent/qwen3_agent.py --env-id $env_id --agent-id $wei_agent_id --faction wei --provider infinigence --model_id $wei_model_id"
    local shu_cmd="uv run rotk_agent/qwen3_agent.py --env-id $env_id --agent-id $shu_agent_id --faction shu --provider infinigence --model_id $shu_model_id"
    
    if [[ "$dry_run" == "true" ]]; then
        print_warning "=== 干运行模式: 只显示命令 ==="
        echo ""
        print_info "环境启动命令:"
        echo "  终端标题: ENV-$env_id"
        echo "  命令: $env_cmd"
        echo ""
        print_info "Wei Agent启动命令:"
        echo "  终端标题: WEI-$wei_agent_id"
        echo "  命令: $wei_cmd"
        echo ""
        print_info "Shu Agent启动命令:"
        echo "  终端标题: SHU-$shu_agent_id"
        echo "  命令: $shu_cmd"
        echo ""
        return 0
    fi
    
    # 实际启动
    print_info "启动游戏环境..."
    execute_in_terminal "ENV-$env_id" "$env_cmd" "$terminal_type"
    sleep 2
    
    print_info "等待环境初始化..."
    sleep 3
    
    print_info "启动Wei Agent..."
    execute_in_terminal "WEI-$wei_agent_id" "$wei_cmd" "$terminal_type"
    sleep 1
    
    print_info "启动Shu Agent..."
    execute_in_terminal "SHU-$shu_agent_id" "$shu_cmd" "$terminal_type"
    
    print_success "第 $match_id 场第 $game_num 局已启动完成！"
    echo ""
}

# 启动多局比赛
launch_match() {
    local match_id="$1"
    local specific_game="$2"
    local mode="$3"
    local terminal_type="$4"
    local dry_run="$5"
    
    if [[ "$specific_game" != "0" ]]; then
        # 只启动特定局数
        launch_single_game "$match_id" "$specific_game" "$mode" "$terminal_type" "$dry_run"
    else
        # 启动所有局数
        print_header "=== 启动第 $match_id 场比赛的所有局数 ==="
        
        for game_num in 1 2 3; do
            launch_single_game "$match_id" "$game_num" "$mode" "$terminal_type" "$dry_run"
            
            if [[ "$dry_run" != "true" && "$game_num" -lt 3 ]]; then
                print_info "等待 5 秒后启动下一局..."
                sleep 5
            fi
        done
    fi
}

# 主函数
main() {
    local matches=""
    local specific_game="0"
    local mode="turn_based"
    local terminal_type="auto"
    local dry_run="false"
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --match)
                matches="$2"
                shift 2
                ;;
            --matches)
                matches="$2"
                shift 2
                ;;
            --game)
                specific_game="$2"
                shift 2
                ;;
            --mode)
                mode="$2"
                shift 2
                ;;
            --terminal-type)
                terminal_type="$2"
                shift 2
                ;;
            --dry-run)
                dry_run="true"
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                print_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 检查必需参数
    if [[ -z "$matches" ]]; then
        print_error "必须指定 --match 或 --matches 参数"
        show_help
        exit 1
    fi
    
    # 验证游戏模式
    if [[ "$mode" != "turn_based" && "$mode" != "real_time" ]]; then
        print_error "无效的游戏模式: $mode"
        print_error "支持的模式: turn_based, real_time"
        exit 1
    fi
    
    # 验证局数
    if [[ "$specific_game" != "0" && ("$specific_game" -lt 1 || "$specific_game" -gt 3) ]]; then
        print_error "无效的局数: $specific_game"
        print_error "局数必须在 1-3 之间，或使用 0 表示所有局"
        exit 1
    fi
    
    # 自动检测终端类型
    if [[ "$terminal_type" == "auto" ]]; then
        terminal_type=$(detect_terminal_type)
        print_info "自动检测的终端类型: $terminal_type"
    fi
    
    # 检查锦标赛数据文件
    check_tournament_file
    
    print_header "Tournament Multi-Terminal Launcher"
    print_header "================================="
    echo ""
    print_info "配置信息:"
    echo "  场次: $matches"
    echo "  局数: $([ "$specific_game" == "0" ] && echo "全部(1,2,3)" || echo "$specific_game")"
    echo "  模式: $mode"
    echo "  终端: $terminal_type"
    echo "  干运行: $dry_run"
    echo ""
    
    # 解析场次列表
    IFS=',' read -ra MATCH_ARRAY <<< "$matches"
    
    for match_id in "${MATCH_ARRAY[@]}"; do
        # 验证场次范围
        if [[ "$match_id" -lt 1 || "$match_id" -gt 91 ]]; then
            print_error "无效的场次: $match_id"
            print_error "场次必须在 1-91 之间"
            continue
        fi
        
        launch_match "$match_id" "$specific_game" "$mode" "$terminal_type" "$dry_run"
        
        # 如果是多场比赛且不是干运行，则等待一段时间
        if [[ ${#MATCH_ARRAY[@]} -gt 1 && "$dry_run" != "true" ]]; then
            print_info "等待 10 秒后启动下一场比赛..."
            sleep 10
        fi
    done
    
    if [[ "$dry_run" != "true" ]]; then
        print_success "所有比赛已启动完成！"
        print_info "请在各个终端中监控比赛进度"
    else
        print_success "干运行完成！"
    fi
}

# 脚本入口点
main "$@"