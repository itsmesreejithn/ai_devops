import threading
from typing import Dict, Any, Callable
from langgraph.errors import GraphInterrupt

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
                print(f"Exception occured: {e}")
                # Check if it's an interrupt exception
                if "Interrupt" in str(e) or "interrupt" in str(e).lower():
                    with cls._lock:
                        cls._tasks[task_id] = {
                            "status": "waiting_for_human",
                            "result": None,
                            "error": None,
                            "interrupt_message": str(e),
                            "thread_id": kwargs.get("thread_id", task_id),
                            "resumable": True
                        }
                else:
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
    
    @classmethod
    def update_task_status(cls, task_id: str, status: str, result: Any = None, error: str = None) -> None:
        """Update the status of a background task."""
        with cls._lock:
            if task_id in cls._tasks:
                cls._tasks[task_id].update({
                    "status": status,
                    "result": result,
                    "error": error
                })
