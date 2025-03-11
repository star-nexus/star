from enum import Enum, auto
from .game_events import GameOverEvent


class GameState(Enum):
    """游戏状态枚举"""

    MAIN_MENU = auto()
    LOADING = auto()
    PLAYING = auto()
    PAUSED = auto()
    VICTORY = auto()
    DEFEAT = auto()
    GAME_OVER = auto()


class GameStateManager:
    """管理游戏状态和状态转换"""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = GameStateManager()
        return cls._instance

    def __init__(self):
        if GameStateManager._instance is not None:
            raise Exception("GameStateManager is a singleton!")

        self.current_state = GameState.MAIN_MENU
        self.prev_state = None
        self.winner_faction = None
        self.player_faction = None
        self._state_change_callbacks = {}
        self._state_enter_callbacks = {state: [] for state in GameState}
        self._state_exit_callbacks = {state: [] for state in GameState}

    def set_player_faction(self, faction_id):
        """设置玩家阵营ID"""
        self.player_faction = faction_id

    def change_state(self, new_state, **kwargs):
        """改变游戏状态"""
        if new_state == self.current_state:
            return

        # 执行退出当前状态的回调
        for callback in self._state_exit_callbacks.get(self.current_state, []):
            callback(self.current_state)

        self.prev_state = self.current_state
        self.current_state = new_state

        # 执行进入新状态的回调
        for callback in self._state_enter_callbacks.get(new_state, []):
            callback(new_state, **kwargs)

        # 执行状态变更回调
        for callback in self._state_change_callbacks.get(self.prev_state, {}).get(
            new_state, []
        ):
            callback(self.prev_state, new_state, **kwargs)

    def is_state(self, state):
        """检查当前是否为指定状态"""
        return self.current_state == state

    def on_state_enter(self, state, callback):
        """注册状态进入回调"""
        self._state_enter_callbacks[state].append(callback)

    def on_state_exit(self, state, callback):
        """注册状态退出回调"""
        self._state_exit_callbacks[state].append(callback)

    def on_state_change(self, from_state, to_state, callback):
        """注册状态变更回调"""
        if from_state not in self._state_change_callbacks:
            self._state_change_callbacks[from_state] = {}
        if to_state not in self._state_change_callbacks[from_state]:
            self._state_change_callbacks[from_state][to_state] = []
        self._state_change_callbacks[from_state][to_state].append(callback)

    def handle_game_over(self, event):
        """处理游戏结束事件"""
        if isinstance(event, GameOverEvent):
            self.winner_faction = event.winner_faction_id

            if self.winner_faction == self.player_faction:
                self.change_state(GameState.VICTORY, winner=self.winner_faction)
            else:
                self.change_state(GameState.DEFEAT, winner=self.winner_faction)

    def start_new_game(self):
        """开始新游戏"""
        self.change_state(GameState.LOADING)
        # 这里应该有加载游戏资源的逻辑
        self.change_state(GameState.PLAYING)

    def pause_game(self):
        """暂停游戏"""
        if self.current_state == GameState.PLAYING:
            self.change_state(GameState.PAUSED)

    def resume_game(self):
        """恢复游戏"""
        if self.current_state == GameState.PAUSED:
            self.change_state(GameState.PLAYING)

    def return_to_main_menu(self):
        """返回主菜单"""
        self.change_state(GameState.MAIN_MENU)
