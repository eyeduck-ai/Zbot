from typing import Dict, Type, Any, Optional, List, Union
from pydantic import BaseModel
import logging
from vghsdk.core import CrawlerTask

logger = logging.getLogger(__name__)

class TaskRegistry:
    _instance = None
    _tasks: Dict[str, CrawlerTask] = {}
    
    CRAWLERS = _tasks # Alias for compatibility

    _module_map: Dict[str, List[str]] = {} # Alias -> [Task IDs]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskRegistry, cls).__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, task_or_cls: Union[CrawlerTask, Type[CrawlerTask]]):
        """
        Register a task. Accepts either an instance or a class.
        If class, instantiates it.
        """
        if isinstance(task_or_cls, type):
            try:
                 task = task_or_cls() # Instantiate
            except Exception as e:
                 logger.error(f"Failed to instantiate task {task_or_cls}: {e}")
                 return
        else:
            task = task_or_cls
            
        if task.id in cls._tasks:
            # logger.warning(f"Task {task.id} already registered. Overwriting.")
            pass
            
        cls._tasks[task.id] = task
        logger.info(f"Registered {task.id}. Total: {len(cls._tasks)}")
        
        # Track Module Alias
        try:
            # e.g. 'vghsdk.modules.patient' -> 'patient'
            # e.g. 'app.tasks.ivi' -> 'ivi'
            module_name = task.__module__
            alias = module_name.split('.')[-1]
            
            if alias not in cls._module_map:
                cls._module_map[alias] = []
            
            if task.id not in cls._module_map[alias]:
                cls._module_map[alias].append(task.id)
                
        except Exception as e:
            logger.warning(f"Failed to map module for task {task.id}: {e}")

    @classmethod
    def get_tasks_by_module(cls, alias: str) -> List[str]:
        return cls._module_map.get(alias, [])
    
    @classmethod
    def get_all_module_aliases(cls) -> List[str]:
        return list(cls._module_map.keys())

    @classmethod
    def get(cls, task_id: str) -> Optional[CrawlerTask]:
        return cls._tasks.get(task_id)
    
    @classmethod
    def get_task(cls, task_id: str) -> Optional[CrawlerTask]:
        return cls.get(task_id)

    @classmethod
    def list_tasks(cls) -> List[Dict[str, Any]]:
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "module": t.__module__.split('.')[-1], # Expose module for debugging
                "params_schema": t.params_model.model_json_schema() if t.params_model else {}
            }
            for t in cls._tasks.values()
        ]
