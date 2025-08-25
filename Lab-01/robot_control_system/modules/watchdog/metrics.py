import psutil
import time
from typing import Dict, Any, Optional
import threading
from collections import deque


class SystemMetricsCollector:
    def __init__(self):
        self.process = psutil.Process()
        self.start_time = time.time()
        self.metrics_history = deque(maxlen=100)
        self._lock = threading.Lock()
    
    def collect_system_metrics(self) -> Dict[str, Any]:
        try:
            with self._lock:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                
                # Process-specific metrics
                process_cpu = self.process.cpu_percent()
                process_memory = self.process.memory_info().rss / 1024 / 1024  # MB
                
                # Thread count
                thread_count = threading.active_count()
                
                metrics = {
                    'system_cpu_percent': cpu_percent,
                    'system_memory_percent': memory.percent,
                    'system_memory_available_mb': memory.available / 1024 / 1024,
                    'process_cpu_percent': process_cpu,
                    'process_memory_mb': process_memory,
                    'thread_count': thread_count,
                    'uptime': time.time() - self.start_time,
                    'timestamp': time.time()
                }
                
                self.metrics_history.append(metrics)
                return metrics
                
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': time.time()
            }
    
    def get_thread_metrics(self, thread: threading.Thread) -> Optional[Dict[str, Any]]:
        if not thread or not thread.is_alive():
            return None
        
        try:
            # Note: Getting per-thread CPU/memory is platform-specific and complex
            # This is a simplified version
            return {
                'thread_name': thread.name,
                'is_alive': thread.is_alive(),
                'is_daemon': thread.daemon,
                'ident': thread.ident
            }
        except Exception:
            return None
    
    def calculate_average_metrics(self, window_size: int = 10) -> Dict[str, float]:
        with self._lock:
            if not self.metrics_history:
                return {}
            
            recent_metrics = list(self.metrics_history)[-window_size:]
            
            if not recent_metrics:
                return {}
            
            avg_metrics = {}
            keys = ['system_cpu_percent', 'process_cpu_percent', 'process_memory_mb']
            
            for key in keys:
                values = [m.get(key, 0) for m in recent_metrics if key in m]
                if values:
                    avg_metrics[f'avg_{key}'] = sum(values) / len(values)
            
            return avg_metrics


class ModuleMetricsTracker:
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.message_count = 0
        self.error_count = 0
        self.last_reset = time.time()
        self.processing_times = deque(maxlen=100)
        self.error_times = deque(maxlen=100)
        self._lock = threading.Lock()
    
    def record_message(self, processing_time: float):
        with self._lock:
            self.message_count += 1
            self.processing_times.append(processing_time)
    
    def record_error(self):
        with self._lock:
            self.error_count += 1
            self.error_times.append(time.time())
    
    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            current_time = time.time()
            time_window = current_time - self.last_reset
            
            # Calculate rates
            message_rate = self.message_count / time_window if time_window > 0 else 0
            error_rate = self.error_count / time_window if time_window > 0 else 0
            
            # Calculate average processing time
            avg_processing_time = (
                sum(self.processing_times) / len(self.processing_times)
                if self.processing_times else 0
            )
            
            # Calculate recent error rate (last 10 seconds)
            recent_errors = [t for t in self.error_times if current_time - t < 10]
            recent_error_rate = len(recent_errors) / 10.0
            
            return {
                'module_name': self.module_name,
                'message_count': self.message_count,
                'error_count': self.error_count,
                'message_rate': message_rate,
                'error_rate': error_rate,
                'recent_error_rate': recent_error_rate,
                'avg_processing_time': avg_processing_time,
                'time_window': time_window
            }
    
    def reset(self):
        with self._lock:
            self.message_count = 0
            self.error_count = 0
            self.last_reset = time.time()