"""
围棋游戏AI模块
"""

import random
import math
from typing import List, Tuple, Optional
from .components import StoneColor, GameBoard


class GoAI:
    """围棋AI基类"""

    def __init__(self, color: StoneColor, difficulty: str = "medium"):
        self.color = color
        self.difficulty = difficulty
        self.opponent_color = (
            StoneColor.WHITE if color == StoneColor.BLACK else StoneColor.BLACK
        )

    def get_move(self, board: GameBoard) -> Optional[Tuple[int, int]]:
        """获取AI的下一步移动"""
        if self.difficulty == "easy":
            return self._random_move(board)
        elif self.difficulty == "medium":
            return self._strategic_move(board)
        else:  # hard
            return self._advanced_move(board)

    def _random_move(self, board: GameBoard) -> Optional[Tuple[int, int]]:
        """随机移动"""
        empty_positions = []
        for y in range(board.size):
            for x in range(board.size):
                if board.board[y][x] == StoneColor.EMPTY:
                    # 检查是否是合法移动
                    if self._is_legal_move(board, x, y, self.color):
                        empty_positions.append((x, y))

        if empty_positions:
            return random.choice(empty_positions)
        return None

    def _strategic_move(self, board: GameBoard) -> Optional[Tuple[int, int]]:
        """策略性移动"""
        # 1. 优先防守 - 阻止对手形成威胁
        defensive_move = self._find_defensive_move(board)
        if defensive_move:
            return defensive_move

        # 2. 寻找攻击机会 - 吃掉对手棋子
        attack_move = self._find_attack_move(board)
        if attack_move:
            return attack_move

        # 3. 占据重要位置
        strategic_move = self._find_strategic_position(board)
        if strategic_move:
            return strategic_move

        # 4. 随机移动
        return self._random_move(board)

    def _advanced_move(self, board: GameBoard) -> Optional[Tuple[int, int]]:
        """高级移动算法"""
        # 使用简化的蒙特卡洛树搜索
        best_move = None
        best_score = -float("inf")

        empty_positions = self._get_empty_positions(board)

        for pos in empty_positions[:10]:  # 限制搜索范围
            score = self._evaluate_position(board, pos)
            if score > best_score:
                best_score = score
                best_move = pos

        return best_move

    def _find_defensive_move(self, board: GameBoard) -> Optional[Tuple[int, int]]:
        """寻找防守移动"""
        # 检查对手是否有即将被吃掉的威胁
        for y in range(board.size):
            for x in range(board.size):
                if board.board[y][x] == StoneColor.EMPTY:
                    # 检查是否是合法移动并且能阻止对手吃子
                    if self._is_legal_move(
                        board, x, y, self.color
                    ) and self._would_capture(board, x, y, self.opponent_color):
                        return (x, y)
        return None

    def _find_attack_move(self, board: GameBoard) -> Optional[Tuple[int, int]]:
        """寻找攻击移动"""
        # 寻找可以吃掉对手棋子的位置
        for y in range(board.size):
            for x in range(board.size):
                if board.board[y][x] == StoneColor.EMPTY:
                    if self._is_legal_move(
                        board, x, y, self.color
                    ) and self._would_capture(board, x, y, self.color):
                        return (x, y)
        return None

    def _find_strategic_position(self, board: GameBoard) -> Optional[Tuple[int, int]]:
        """寻找战略位置"""
        # 优先选择角落和边缘位置
        strategic_positions = [
            (3, 3),
            (3, 15),
            (15, 3),
            (15, 15),  # 角落附近
            (9, 9),  # 中心
            (3, 9),
            (9, 3),
            (15, 9),
            (9, 15),  # 边缘中心
        ]

        for x, y in strategic_positions:
            if board.board[y][x] == StoneColor.EMPTY and self._is_legal_move(
                board, x, y, self.color
            ):
                return (x, y)

        return None

    def _would_capture(
        self, board: GameBoard, x: int, y: int, color: StoneColor
    ) -> bool:
        """检查在指定位置下棋是否会吃掉对手棋子"""
        # 创建临时棋盘状态
        temp_board = [row[:] for row in board.board]
        temp_board[y][x] = color

        opponent_color = (
            StoneColor.WHITE if color == StoneColor.BLACK else StoneColor.BLACK
        )

        # 检查四个方向
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if (
                0 <= nx < board.size
                and 0 <= ny < board.size
                and temp_board[ny][nx] == opponent_color
            ):
                # 检查这个对手棋群是否会被吃掉
                group = self._get_group_from_board(temp_board, nx, ny)
                if not self._has_liberty_in_board(temp_board, group):
                    return True

        return False

    def _is_legal_move(
        self, board: GameBoard, x: int, y: int, color: StoneColor
    ) -> bool:
        """检查是否是合法移动（考虑围棋规则）"""
        # 位置必须为空
        if board.board[y][x] != StoneColor.EMPTY:
            return False

        # 创建临时棋盘状态
        temp_board = [row[:] for row in board.board]
        temp_board[y][x] = color

        # 检查是否能吃掉对手棋子
        opponent_color = (
            StoneColor.WHITE if color == StoneColor.BLACK else StoneColor.BLACK
        )
        can_capture = False

        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if (
                0 <= nx < board.size
                and 0 <= ny < board.size
                and temp_board[ny][nx] == opponent_color
            ):
                # 检查对手棋群是否没有气
                opponent_group = self._get_group_from_board(temp_board, nx, ny)
                if not self._has_liberty_in_board(temp_board, opponent_group):
                    can_capture = True
                    break

        # 如果能吃掉对手棋子，则是合法移动
        if can_capture:
            return True

        # 检查自己的棋群是否有气（防止自杀）
        own_group = self._get_group_from_board(temp_board, x, y)
        return self._has_liberty_in_board(temp_board, own_group)

    def _get_empty_positions(self, board: GameBoard) -> List[Tuple[int, int]]:
        """获取所有合法的空位置"""
        positions = []
        for y in range(board.size):
            for x in range(board.size):
                if board.board[y][x] == StoneColor.EMPTY and self._is_legal_move(
                    board, x, y, self.color
                ):
                    positions.append((x, y))
        return positions

    def _evaluate_position(self, board: GameBoard, pos: Tuple[int, int]) -> float:
        """评估位置价值"""
        x, y = pos
        score = 0.0

        # 基础位置价值
        center_x, center_y = board.size // 2, board.size // 2
        distance_from_center = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
        score += 1.0 / (1.0 + distance_from_center * 0.1)

        # 检查是否能吃掉对手棋子
        if self._would_capture(board, x, y, self.color):
            score += 5.0

        # 检查是否会被对手吃掉
        if self._would_be_captured(board, x, y, self.color):
            score -= 3.0

        return score

    def _would_be_captured(
        self, board: GameBoard, x: int, y: int, color: StoneColor
    ) -> bool:
        """检查在指定位置下棋后是否会被吃掉"""
        # 创建临时棋盘
        temp_board = [row[:] for row in board.board]
        temp_board[y][x] = color

        # 获取这个位置的棋群
        group = self._get_group_from_board(temp_board, x, y)

        # 检查是否有气
        return not self._has_liberty_in_board(temp_board, group)

    def _get_group_from_board(
        self, board: List[List[StoneColor]], x: int, y: int
    ) -> List[Tuple[int, int]]:
        """从指定棋盘获取棋群"""
        color = board[y][x]
        if color == StoneColor.EMPTY:
            return []

        visited = set()
        group = []
        stack = [(x, y)]

        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue

            visited.add((cx, cy))
            group.append((cx, cy))

            directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
            for dx, dy in directions:
                nx, ny = cx + dx, cy + dy
                if (
                    0 <= nx < len(board[0])
                    and 0 <= ny < len(board)
                    and (nx, ny) not in visited
                    and board[ny][nx] == color
                ):
                    stack.append((nx, ny))

        return group

    def _has_liberty_in_board(
        self, board: List[List[StoneColor]], group: List[Tuple[int, int]]
    ) -> bool:
        """检查棋群在指定棋盘中是否有气"""
        for x, y in group:
            directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
            for dx, dy in directions:
                nx, ny = x + dx, y + dy
                if (
                    0 <= nx < len(board[0])
                    and 0 <= ny < len(board)
                    and board[ny][nx] == StoneColor.EMPTY
                ):
                    return True
        return False
