"""
围棋游戏配置文件
"""

# 游戏窗口设置
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
WINDOW_TITLE = "围棋游戏 - Go Game"
FPS = 60

# 棋盘设置
BOARD_SIZE = 19  # 标准19x19围棋
BOARD_START_X = 50
BOARD_START_Y = 50
GRID_SIZE = 30
STONE_RADIUS = 12

# 颜色设置
COLORS = {
    "background": (139, 69, 19),  # 棕色背景
    "board_line": (0, 0, 0),  # 黑色网格线
    "black_stone": (0, 0, 0),  # 黑子
    "white_stone": (255, 255, 255),  # 白子
    "stone_border": (100, 100, 100),  # 棋子边框
    "hover": (255, 255, 0),  # 悬停效果
    "text": (255, 255, 255),  # 文字颜色
    "text_highlight": (255, 255, 0),  # 高亮文字
    "menu_bg": (139, 69, 19),  # 菜单背景
}

# AI设置
AI_SETTINGS = {
    "enabled": True,
    "default_difficulty": "medium",  # easy, medium, hard
    "thinking_time": {"easy": 0.5, "medium": 1.0, "hard": 2.0},
}

# 星位坐标 (标准围棋星位)
STAR_POINTS = [
    (3, 3),
    (3, 9),
    (3, 15),  # 左侧
    (9, 3),
    (9, 9),
    (9, 15),  # 中间
    (15, 3),
    (15, 9),
    (15, 15),  # 右侧
]

# 字体设置
FONT_SIZES = {"title": 72, "menu": 48, "ui": 24, "instruction": 20}

# 音效设置（预留）
AUDIO_SETTINGS = {
    "enabled": True,
    "volume": 0.7,
    "sound_effects": {
        "stone_place": None,  # 放子音效
        "capture": None,  # 吃子音效
        "game_end": None,  # 游戏结束音效
    },
}

# 调试设置
DEBUG = {
    "show_coordinates": False,  # 显示坐标
    "show_groups": False,  # 显示棋群
    "show_liberties": False,  # 显示气
    "ai_thinking_visible": True,  # 显示AI思考状态
}

# 游戏规则设置
GAME_RULES = {
    "komi": 6.5,  # 贴目
    "handicap": 0,  # 让子数
    "time_limit": None,  # 时间限制（秒，None为无限制）
    "pass_to_end": 2,  # 连续pass次数结束游戏
    "suicide_allowed": False,  # 是否允许自杀
    "ko_rule": True,  # 是否启用打劫规则
}
