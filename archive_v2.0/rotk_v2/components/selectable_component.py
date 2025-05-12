class SelectableComponent:
    """
    可选择组件，用于标记实体是否可被选择
    """
    def __init__(self, selected=False, selectable=True):
        self.selected = selected  # 是否被选中
        self.selectable = selectable  # 是否可被选择