class Entity:
    """
    实体：游戏对象的唯一标识符
    在ECS架构中仅作为一个标识符，不直接存储组件数据
    实体通过唯一ID标识，组件数据存储在World中与实体关联
    """

    _id_counter = 0

    def __init__(self):
        self.id = Entity._id_counter
        Entity._id_counter += 1

    def __hash__(self):
        return hash(self.id)
