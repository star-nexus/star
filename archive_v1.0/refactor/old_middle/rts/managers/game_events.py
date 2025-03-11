class Event:
    """基本事件类"""

    pass


class GameStartEvent(Event):
    """游戏开始事件"""

    def __init__(self):
        super().__init__()


class GameOverEvent(Event):
    """游戏结束事件"""

    def __init__(self, winner_faction_id):
        super().__init__()
        self.winner_faction_id = winner_faction_id


class GamePauseEvent(Event):
    """游戏暂停事件"""

    def __init__(self):
        super().__init__()


class GameResumeEvent(Event):
    """游戏恢复事件"""

    def __init__(self):
        super().__init__()


class StateChangeEvent(Event):
    """状态改变事件"""

    def __init__(self, previous_state, new_state):
        super().__init__()
        self.previous_state = previous_state
        self.new_state = new_state
