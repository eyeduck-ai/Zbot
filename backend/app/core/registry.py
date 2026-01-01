"""Task Registry - 支援 class-based 和 function-based task 註冊"""
from typing import Dict, Type, Any, Optional, List, Union, Callable
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class TaskRegistry:
    """統一任務註冊中心。
    
    支援兩種任務類型：
    1. Class-based: CrawlerTask 子類別 (舊版，向後相容)
    2. Function-based: @crawler_task 裝飾的 async function (新版)
    """
    _instance = None
    _tasks: Dict[str, Any] = {}  # id -> task (class instance or function)
    
    CRAWLERS = _tasks  # Alias for compatibility

    _module_map: Dict[str, List[str]] = {}  # module alias -> [Task IDs]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskRegistry, cls).__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, task_or_func: Union[Any, Type, Callable]):
        """
        註冊任務。
        
        支援:
        - CrawlerTask instance
        - CrawlerTask class (會自動 instantiate)
        - @crawler_task 裝飾的 function
        """
        # Function-based task (有 is_crawler_task 屬性)
        if callable(task_or_func) and hasattr(task_or_func, 'is_crawler_task'):
            task = task_or_func
            task_id = task.id
            module_name = task.__module__
        # Class-based task (CrawlerTask 子類別)
        elif isinstance(task_or_func, type):
            try:
                task = task_or_func()  # Instantiate
            except Exception as e:
                logger.error(f"Failed to instantiate task {task_or_func}: {e}")
                return
            task_id = task.id
            module_name = task.__module__
        # Already instantiated class-based task
        elif hasattr(task_or_func, 'id'):
            task = task_or_func
            task_id = task.id
            module_name = task.__module__
        else:
            logger.error(f"Cannot register unknown task type: {type(task_or_func)}")
            return
            
        cls._tasks[task_id] = task
        logger.info(f"Registered {task_id}. Total: {len(cls._tasks)}")
        
        # Track Module Alias
        try:
            alias = module_name.split('.')[-1]
            if alias not in cls._module_map:
                cls._module_map[alias] = []
            if task_id not in cls._module_map[alias]:
                cls._module_map[alias].append(task_id)
        except Exception as e:
            logger.warning(f"Failed to map module for task {task_id}: {e}")

    @classmethod
    def get_tasks_by_module(cls, alias: str) -> List[str]:
        return cls._module_map.get(alias, [])
    
    @classmethod
    def get_all_module_aliases(cls) -> List[str]:
        return list(cls._module_map.keys())

    @classmethod
    def get(cls, task_id: str) -> Optional[Any]:
        return cls._tasks.get(task_id)
    
    @classmethod
    def get_task(cls, task_id: str) -> Optional[Any]:
        return cls.get(task_id)

    @classmethod
    def list_tasks(cls) -> List[Dict[str, Any]]:
        """列出所有註冊的任務。"""
        results = []
        for t in cls._tasks.values():
            # 取得共通屬性 (class-based 和 function-based 都有)
            task_info = {
                "id": t.id,
                "name": t.name,
                "description": getattr(t, 'description', ''),
                "module": t.__module__.split('.')[-1],
            }
            
            # params_schema
            params_model = getattr(t, 'params_model', None)
            if params_model:
                task_info["params_schema"] = params_model.model_json_schema()
            else:
                task_info["params_schema"] = {}
                
            results.append(task_info)
        return results
    
    @classmethod
    def is_function_based(cls, task_id: str) -> bool:
        """檢查任務是否為 function-based。"""
        task = cls._tasks.get(task_id)
        return task is not None and hasattr(task, 'is_crawler_task')
