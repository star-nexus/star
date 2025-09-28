# Tournament Makefile - 支持模式选择
# 使用 make X-Y 的格式启动第X场比赛的第Y局

# 环境测试
test-turn:
	./tournament.sh headless turn
test-real:
	./tournament.sh headless real
test-both:
	./tournament.sh headless both

# 环境启动 (GUI模式)
env:
	./tournament.sh env

# 前20场比赛的快捷方式
1-1: ; ./tournament.sh 1 1
1-2: ; ./tournament.sh 1 2
1-3: ; ./tournament.sh 1 3
2-1: ; ./tournament.sh 2 1
2-2: ; ./tournament.sh 2 2
2-3: ; ./tournament.sh 2 3
3-1: ; ./tournament.sh 3 1
3-2: ; ./tournament.sh 3 2
3-3: ; ./tournament.sh 3 3
4-1: ; ./tournament.sh 4 1
4-2: ; ./tournament.sh 4 2
4-3: ; ./tournament.sh 4 3
5-1: ; ./tournament.sh 5 1
5-2: ; ./tournament.sh 5 2
5-3: ; ./tournament.sh 5 3
6-1: ; ./tournament.sh 6 1
6-2: ; ./tournament.sh 6 2
6-3: ; ./tournament.sh 6 3
7-1: ; ./tournament.sh 7 1
7-2: ; ./tournament.sh 7 2
7-3: ; ./tournament.sh 7 3
8-1: ; ./tournament.sh 8 1
8-2: ; ./tournament.sh 8 2
8-3: ; ./tournament.sh 8 3
9-1: ; ./tournament.sh 9 1
9-2: ; ./tournament.sh 9 2
9-3: ; ./tournament.sh 9 3
10-1: ; ./tournament.sh 10 1
10-2: ; ./tournament.sh 10 2
10-3: ; ./tournament.sh 10 3
11-1: ; ./tournament.sh 11 1
11-2: ; ./tournament.sh 11 2
11-3: ; ./tournament.sh 11 3
12-1: ; ./tournament.sh 12 1
12-2: ; ./tournament.sh 12 2
12-3: ; ./tournament.sh 12 3
13-1: ; ./tournament.sh 13 1
13-2: ; ./tournament.sh 13 2
13-3: ; ./tournament.sh 13 3
14-1: ; ./tournament.sh 14 1
14-2: ; ./tournament.sh 14 2
14-3: ; ./tournament.sh 14 3
15-1: ; ./tournament.sh 15 1
15-2: ; ./tournament.sh 15 2
15-3: ; ./tournament.sh 15 3
16-1: ; ./tournament.sh 16 1
16-2: ; ./tournament.sh 16 2
16-3: ; ./tournament.sh 16 3
17-1: ; ./tournament.sh 17 1
17-2: ; ./tournament.sh 17 2
17-3: ; ./tournament.sh 17 3
18-1: ; ./tournament.sh 18 1
18-2: ; ./tournament.sh 18 2
18-3: ; ./tournament.sh 18 3
19-1: ; ./tournament.sh 19 1
19-2: ; ./tournament.sh 19 2
19-3: ; ./tournament.sh 19 3
20-1: ; ./tournament.sh 20 1
20-2: ; ./tournament.sh 20 2
20-3: ; ./tournament.sh 20 3

# 通用规则 - 通过模式匹配处理其他场次 (默认回合制)
%:
	@echo "$@" | grep -E '^[0-9]+-[0-9]+$$' > /dev/null && \
	match=$$(echo "$@" | cut -d'-' -f1) && \
	game=$$(echo "$@" | cut -d'-' -f2) && \
	./tournament.sh $$match $$game turn || \
	(echo "无效的目标: $@" && echo "使用格式: make X-Y (X=1-91, Y=1-3)" && false)

# 实时制规则
real-%:
	@target=$$(echo "$@" | sed 's/^real-//') && \
	echo "$$target" | grep -E '^[0-9]+-[0-9]+$$' > /dev/null && \
	match=$$(echo "$$target" | cut -d'-' -f1) && \
	game=$$(echo "$$target" | cut -d'-' -f2) && \
	./tournament.sh $$match $$game real || \
	(echo "无效的目标: $@" && echo "使用格式: make real-X-Y (X=1-91, Y=1-3)" && false)

# 干运行规则 (实时制) - 必须在干运行规则(回合制)之前
dry-real-%:
	@target=$$(echo "$@" | sed 's/^dry-real-//') && \
	echo "$$target" | grep -E '^[0-9]+-[0-9]+$$' > /dev/null && \
	match=$$(echo "$$target" | cut -d'-' -f1) && \
	game=$$(echo "$$target" | cut -d'-' -f2) && \
	./tournament.sh $$match $$game real dry || \
	(echo "无效的目标: $@" && echo "使用格式: make dry-real-X-Y (X=1-91, Y=1-3)" && false)

# 干运行规则 (回合制)
dry-%:
	@target=$$(echo "$@" | sed 's/^dry-//') && \
	echo "$$target" | grep -E '^[0-9]+-[0-9]+$$' > /dev/null && \
	match=$$(echo "$$target" | cut -d'-' -f1) && \
	game=$$(echo "$$target" | cut -d'-' -f2) && \
	./tournament.sh $$match $$game turn dry || \
	(echo "无效的目标: $@" && echo "使用格式: make dry-X-Y (X=1-91, Y=1-3)" && false)

# 显示帮助
help:
	@echo "Tournament Makefile 使用说明:"
	@echo ""
	@echo "环境测试:"
	@echo "  make test-turn          - 测试回合制AI vs AI"
	@echo "  make test-real          - 测试实时制AI vs AI"
	@echo "  make test-both          - 测试两种模式"
	@echo ""
	@echo "启动环境:"
	@echo "  make env                - 启动游戏环境(GUI模式)"
	@echo ""  
	@echo "启动比赛 (回合制模式):"
	@echo "  make X-Y                - 启动第X场比赛的第Y局 (回合制)"
	@echo "                            X: 场次 (1-91)"
	@echo "                            Y: 局数 (1-3)"
	@echo ""
	@echo "启动比赛 (实时制模式):"
	@echo "  make real-X-Y           - 启动第X场比赛的第Y局 (实时制)"
	@echo ""
	@echo "示例:"
	@echo "  make 1-1                - 第1场第1局 (回合制)"
	@echo "  make real-1-1           - 第1场第1局 (实时制)"
	@echo "  make 15-2               - 第15场第2局 (回合制)" 
	@echo "  make real-91-3          - 第91场第3局 (实时制)"
	@echo ""
	@echo "干运行 (查看命令但不执行):"
	@echo "  make dry-1-1            - 查看第1场第1局的启动命令 (回合制)"
	@echo "  make dry-real-1-1       - 查看第1场第1局的启动命令 (实时制)"
	@echo ""
	@echo "直接使用shell脚本:"
	@echo "  ./tournament.sh X Y              - 启动第X场第Y局 (默认回合制)"
	@echo "  ./tournament.sh X Y turn         - 启动第X场第Y局 (回合制)"
	@echo "  ./tournament.sh X Y real         - 启动第X场第Y局 (实时制)"
	@echo "  ./tournament.sh X Y turn dry     - 干运行第X场第Y局 (回合制)"
	@echo "  ./tournament.sh X Y real dry     - 干运行第X场第Y局 (实时制)"
	@echo ""
	@echo "注意: 第3局只有在前两局1-1平局时才需要进行"

# 默认目标
.DEFAULT_GOAL := help

# 声明伪目标
.PHONY: env help test-turn test-real test-both