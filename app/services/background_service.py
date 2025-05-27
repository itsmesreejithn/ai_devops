import threading
from typing import Dict, Any, Callable

class BackgroundTaskManager:
    """Manages background tasks and their status."""
    
    _tasks = {}
    _lock = threading.Lock()
    
    @classmethod
    def run_task(cls, task_id: str, func: Callable, *args, **kwargs) -> None:
        """Run a function in a background thread and store its status."""
        def wrapper():
            try:
                result = func(*args, **kwargs)
                with cls._lock:
                    cls._tasks[task_id] = {
                        "status": "completed",
                        "result": result,
                        "error": None
                    }
            except Exception as e:
                with cls._lock:
                    cls._tasks[task_id] = {
                        "status": "failed",
                        "result": None,
                        "error": str(e)
                    }
        
        # Initialize task status
        with cls._lock:
            cls._tasks[task_id] = {
                "status": "running",
                "result": None,
                "error": None
            }
        
        # Start background thread
        thread = threading.Thread(target=wrapper)
        thread.daemon = True
        thread.start()
    
    @classmethod
    def get_task_status(cls, task_id: str) -> Dict[str, Any]:
        """Get the status of a background task."""
        with cls._lock:
            return cls._tasks.get(task_id, {"status": "not_found"})