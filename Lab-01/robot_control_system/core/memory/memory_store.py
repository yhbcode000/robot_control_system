import threading
from typing import Any, Dict, Optional, Callable
import time
from collections import defaultdict

from .memory_types import (
    MemoryNamespace, HeartbeatInfo, ThreadHealth, 
    ModuleMetrics, SystemMetrics, HealthStatus, ModuleStatus
)


class GlobalMemory:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._namespaces = {}
        self._global_observers = []
        self._namespace_locks = defaultdict(threading.RLock)
        
        # Initialize default namespaces
        self._init_default_namespaces()
        
    def _init_default_namespaces(self):
        default_namespaces = [
            'input_buffer',
            'sensor_state', 
            'planned_trajectory',
            'action_commands',
            'output_signals',
            'system_status',
            'health_status',
            'module_heartbeats'
        ]
        
        for ns_name in default_namespaces:
            self._namespaces[ns_name] = MemoryNamespace()
            
        # Initialize health status
        self._namespaces['health_status'].data = {
            'thread_health': {},
            'module_metrics': {},
            'system_metrics': None,
            'health_score': 100.0
        }
    
    @classmethod
    def get_instance(cls) -> 'GlobalMemory':
        return cls()
    
    def get_namespace(self, namespace: str) -> MemoryNamespace:
        if namespace not in self._namespaces:
            with self._namespace_locks[namespace]:
                if namespace not in self._namespaces:
                    self._namespaces[namespace] = MemoryNamespace()
        return self._namespaces[namespace]
    
    def update(self, namespace: str, key: str, value: Any):
        with self._namespace_locks[namespace]:
            ns = self.get_namespace(namespace)
            ns.update(key, value)
            self._notify_global_observers(namespace, key, value)
    
    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        ns = self.get_namespace(namespace)
        return ns.get(key, default)
    
    def subscribe_to_namespace(self, namespace: str, callback: Callable):
        ns = self.get_namespace(namespace)
        ns.subscribe(callback)
    
    def subscribe_global(self, callback: Callable):
        self._global_observers.append(callback)
    
    def _notify_global_observers(self, namespace: str, key: str, value: Any):
        for observer in self._global_observers:
            try:
                observer(namespace, key, value)
            except Exception as e:
                print(f"Global observer notification failed: {e}")
    
    # Convenience methods for health monitoring
    def update_module_heartbeat(self, module_name: str, heartbeat_info: Dict):
        with self._namespace_locks['module_heartbeats']:
            heartbeats = self.get('module_heartbeats', 'heartbeats', {})
            heartbeats[module_name] = HeartbeatInfo(
                timestamp=heartbeat_info.get('timestamp', time.time()),
                error_count=heartbeat_info.get('error_count', 0),
                avg_processing_time=heartbeat_info.get('avg_processing_time', 0.0)
            )
            self.update('module_heartbeats', 'heartbeats', heartbeats)
    
    def get_module_heartbeat(self, module_name: str) -> Optional[HeartbeatInfo]:
        heartbeats = self.get('module_heartbeats', 'heartbeats', {})
        return heartbeats.get(module_name)
    
    def update_thread_health(self, module_name: str, health: ThreadHealth):
        with self._namespace_locks['health_status']:
            health_status = self.get('health_status', 'data', {})
            if 'thread_health' not in health_status:
                health_status['thread_health'] = {}
            health_status['thread_health'][module_name] = health
            self.update('health_status', 'data', health_status)
    
    def update_module_metrics(self, module_name: str, metrics: ModuleMetrics):
        with self._namespace_locks['health_status']:
            health_status = self.get('health_status', 'data', {})
            if 'module_metrics' not in health_status:
                health_status['module_metrics'] = {}
            health_status['module_metrics'][module_name] = metrics
            self.update('health_status', 'data', health_status)
    
    def update_system_metrics(self, metrics: SystemMetrics):
        with self._namespace_locks['health_status']:
            health_status = self.get('health_status', 'data', {})
            health_status['system_metrics'] = metrics
            self.update('health_status', 'data', health_status)
    
    def get_health_status(self) -> Dict:
        return self.get('health_status', 'data', {})
    
    def clear_namespace(self, namespace: str):
        with self._namespace_locks[namespace]:
            if namespace in self._namespaces:
                self._namespaces[namespace].data.clear()
    
    def get_all_namespaces(self) -> list:
        return list(self._namespaces.keys())