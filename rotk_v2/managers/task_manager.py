import uuid
import time

class Task:
    def __init__(self, task_type, description, target_position=None, target_unit=None, units=None):
        self.id = str(uuid.uuid4())
        self.task_type = task_type  # attack, defend, move, patrol
        self.description = description
        self.target_position = target_position  # (x, y)
        self.target_unit = target_unit  # 目标单位ID
        self.units = units or []  # 执行任务的单位ID列表
        self.status = "pending"  # pending, in_progress, completed, failed
        self.progress = 0.0  # 0.0 - 1.0
        self.start_time = None
        self.end_time = None
        
    def start(self):
        """开始任务"""
        self.status = "in_progress"
        self.start_time = time.time()
        
    def complete(self):
        """完成任务"""
        self.status = "completed"
        self.progress = 1.0
        self.end_time = time.time()
        
    def fail(self):
        """任务失败"""
        self.status = "failed"
        self.end_time = time.time()
        
    def update_progress(self, progress):
        """更新任务进度"""
        self.progress = max(0.0, min(1.0, progress))
        
    def get_duration(self):
        """获取任务持续时间"""
        if not self.start_time:
            return 0
            
        end = self.end_time or time.time()
        return end - self.start_time

class TaskManager:
    def __init__(self, engine):
        self.engine = engine
        self.tasks = {}  # 任务ID -> 任务对象
        self.active_tasks = []  # 活动任务ID列表
        self.completed_tasks = []  # 已完成任务ID列表
        self.failed_tasks = []  # 失败任务ID列表
        
    def create_task(self, task_type, description, target_position=None, target_unit=None, units=None):
        """创建新任务"""
        task = Task(task_type, description, target_position, target_unit, units)
        self.tasks[task.id] = task
        self.active_tasks.append(task.id)
        return task.id
        
    def get_task(self, task_id):
        """获取任务对象"""
        return self.tasks.get(task_id)
        
    def start_task(self, task_id):
        """开始任务"""
        task = self.get_task(task_id)
        if task and task.status == "pending":
            task.start()
            
            # 通知单位执行任务
            unit_manager = self.engine.scene_manager.current_scene.unit_manager
            for unit_id in task.units:
                ai = unit_manager.get_unit_component(unit_id, "ai")
                if ai:
                    if task.task_type == "attack" and task.target_unit:
                        ai.set_target(task.target_unit)
                        ai.set_state("attacking")
                    elif task.task_type == "move" and task.target_position:
                        ai.set_path([task.target_position])
                        ai.set_state("moving")
                    elif task.task_type == "defend":
                        ai.set_state("defending")
                        
    def complete_task(self, task_id):
        """完成任务"""
        task = self.get_task(task_id)
        if task and task.status == "in_progress":
            task.complete()
            self.active_tasks.remove(task_id)
            self.completed_tasks.append(task_id)
            
    def fail_task(self, task_id):
        """任务失败"""
        task = self.get_task(task_id)
        if task and task.status == "in_progress":
            task.fail()
            self.active_tasks.remove(task_id)
            self.failed_tasks.append(task_id)
            
    def cancel_task(self, task_id):
        """取消任务"""
        task = self.get_task(task_id)
        if task and (task.status == "pending" or task.status == "in_progress"):
            task.fail()
            if task_id in self.active_tasks:
                self.active_tasks.remove(task_id)
            self.failed_tasks.append(task_id)
            
    def update_tasks(self, dt):
        """更新所有任务"""
        for task_id in list(self.active_tasks):
            task = self.get_task(task_id)
            if not task:
                continue
                
            # 检查任务是否应该完成或失败
            if task.status == "in_progress":
                self.check_task_status(task)
                
    def check_task_status(self, task):
        """检查任务状态"""
        unit_manager = self.engine.scene_manager.current_scene.unit_manager
        
        # 检查执行任务的单位是否都还存在
        alive_units = []
        for unit_id in task.units:
            if unit_id in unit_manager.unit_components:
                alive_units.append(unit_id)
                
        # 更新任务单位列表
        task.units = alive_units
        
        # 如果没有单位，任务失败
        if not task.units:
            self.fail_task(task.id)
            return
            
        # 根据任务类型检查完成条件
        if task.task_type == "attack":
            # 检查目标单位是否存在
            if task.target_unit and task.target_unit not in unit_manager.unit_components:
                # 目标已被消灭，任务完成
                self.complete_task(task.id)
                
        elif task.task_type == "move":
            # 检查是否所有单位都到达目标位置
            if task.target_position:
                all_arrived = True
                for unit_id in task.units:
                    transform = unit_manager.get_unit_component(unit_id, "transform")
                    if transform:
                        # 计算到目标的距离
                        tx, ty = task.target_position
                        dx = tx - transform.x
                        dy = ty - transform.y
                        distance = (dx**2 + dy**2)**0.5
                        
                        if distance > 50:  # 如果距离大于50米，认为未到达
                            all_arrived = False
                            break
                            
                if all_arrived:
                    # 所有单位都到达目标位置，任务完成
                    self.complete_task(task.id)
                    
        elif task.task_type == "defend":
            # 防御任务通常不会自动完成，需要手动取消
            pass
            
        elif task.task_type == "patrol":
            # 巡逻任务通常不会自动完成，需要手动取消
            pass
            
    def get_active_tasks(self):
        """获取所有活动任务"""
        return [self.get_task(task_id) for task_id in self.active_tasks]
        
    def get_completed_tasks(self):
        """获取所有已完成任务"""
        return [self.get_task(task_id) for task_id in self.completed_tasks]
        
    def get_failed_tasks(self):
        """获取所有失败任务"""
        return [self.get_task(task_id) for task_id in self.failed_tasks]
        
    def get_task_stats(self):
        """获取任务统计信息"""
        return {
            "active": len(self.active_tasks),
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks),
            "total": len(self.tasks)
        }