"""Compatibility wrapper for SQLite memory store to maintain existing interface"""

from typing import Any, Dict, Optional, Callable
from .sqlite_memory_store import SQLiteMemoryStore
from .memory_types import (
    MemoryNamespace, HeartbeatInfo, ThreadHealth, 
    ModuleMetrics, SystemMetrics, HealthStatus, ModuleStatus
)

class SQLiteMemoryNamespace:
    """Wrapper to mimic MemoryNamespace interface"""
    
    def __init__(self, memory_store: SQLiteMemoryStore, namespace: str):
        self.memory_store = memory_store
        self.namespace = namespace
    
    def update(self, key: str, value: Any):
        """Update a key-value pair"""
        self.memory_store.update(self.namespace, key, value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value"""
        return self.memory_store.get(self.namespace, key, default)
    
    @property
    def data(self) -> Dict[str, Any]:
        """Get all data in namespace"""
        return self.memory_store.get_namespace(self.namespace)
    
    @data.setter
    def data(self, value: Dict[str, Any]):
        """Set namespace data"""
        # Clear existing data and set new
        self.memory_store.clear_namespace(self.namespace)
        for k, v in value.items():
            self.memory_store.update(self.namespace, k, v)

class GlobalMemory:
    """SQLite-backed global memory that maintains the original interface"""
    
    _instance = None
    _lock = None
    
    def __new__(cls):
        if cls._instance is None:
            import threading
            if cls._lock is None:
                cls._lock = threading.Lock()
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.memory_store = SQLiteMemoryStore.get_instance()
        self._namespace_cache = {}
        
    @classmethod
    def get_instance(cls) -> 'GlobalMemory':
        return cls()
    
    def get_namespace(self, namespace: str) -> SQLiteMemoryNamespace:
        """Get a namespace wrapper"""
        if namespace not in self._namespace_cache:
            self._namespace_cache[namespace] = SQLiteMemoryNamespace(self.memory_store, namespace)
        return self._namespace_cache[namespace]
    
    def update(self, namespace: str, key: str, value: Any):
        """Update a value"""
        self.memory_store.update(namespace, key, value)
    
    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        """Get a value"""
        return self.memory_store.get(namespace, key, default)
    
    def subscribe_to_namespace(self, namespace: str, callback: Callable):
        """Subscribe to namespace changes"""
        self.memory_store.subscribe_to_namespace(namespace, callback)
    
    def unsubscribe_from_namespace(self, namespace: str, callback: Callable):
        """Unsubscribe from namespace changes"""
        self.memory_store.unsubscribe_from_namespace(namespace, callback)
    
    def subscribe_global(self, callback: Callable):
        """Subscribe to all changes"""
        self.memory_store.subscribe_global(callback)
    
    # Health monitoring methods (enhanced with SQLite)
    def update_heartbeat(self, module_name: str, heartbeat_info: HeartbeatInfo):
        """Update module heartbeat"""
        self.memory_store.update_heartbeat(
            module_name, 
            heartbeat_info.status.value if hasattr(heartbeat_info.status, 'value') else str(heartbeat_info.status),
            {
                'thread_id': heartbeat_info.thread_id,
                'last_seen': heartbeat_info.last_seen,
                'performance_data': heartbeat_info.performance_data.__dict__ if heartbeat_info.performance_data else {}
            }
        )
        
        # Also store in memory namespace for backward compatibility
        self.update('module_heartbeats', module_name, heartbeat_info)
    
    def get_module_heartbeat(self, module_name: str) -> Optional[HeartbeatInfo]:
        """Get module heartbeat"""
        return self.get('module_heartbeats', module_name)
    
    def update_thread_health(self, thread_id: str, health_info: ThreadHealth):
        """Update thread health"""
        self.update('health_status', f'thread_{thread_id}', health_info)
    
    def update_module_metrics(self, module_name: str, metrics: ModuleMetrics):
        """Update module metrics"""
        self.update('health_status', f'metrics_{module_name}', metrics)
        
        # Also log to SQLite metrics table
        self.memory_store.log_system_metrics({
            'module': module_name,
            'cpu_usage': getattr(metrics, 'cpu_usage', 0.0),
            'memory_usage': getattr(metrics, 'memory_usage', 0.0),
            'error_count': getattr(metrics, 'error_count', 0),
            'latency_ms': getattr(metrics, 'avg_latency', 0.0) * 1000,
            'active_modules': 1
        })
    
    def update_system_metrics(self, metrics: SystemMetrics):
        """Update system metrics"""
        self.update('health_status', 'system_metrics', metrics)
        
        # Log to SQLite
        self.memory_store.log_system_metrics({
            'cpu_usage': getattr(metrics, 'cpu_usage', 0.0),
            'memory_usage': getattr(metrics, 'memory_usage', 0.0),
            'latency_ms': getattr(metrics, 'avg_response_time', 0.0) * 1000,
            'active_modules': getattr(metrics, 'active_modules', 0),
            'total_commands': getattr(metrics, 'total_commands', 0),
            'uptime_seconds': getattr(metrics, 'uptime_seconds', 0)
        })
    
    def get_health_status(self) -> HealthStatus:
        """Get overall health status"""
        return self.get('health_status', 'overall', HealthStatus.UNKNOWN)
    
    def set_health_status(self, status: HealthStatus):
        """Set overall health status"""
        self.update('health_status', 'overall', status)
    
    # Enhanced SQLite-specific methods
    def log_command(self, command_type: str, command_data: Any, source_module: str):
        """Log a command for debugging/auditing"""
        self.memory_store.log_command(command_type, command_data, source_module)
    
    def get_command_history(self, limit: int = 100):
        """Get recent command history"""
        return self.memory_store.get_command_history(limit)
    
    def get_memory_stats(self) -> Dict:
        """Get memory store statistics"""
        return self.memory_store.get_stats()
    
    def cleanup_old_data(self, older_than_hours: float = 1.0):
        """Clean up old data"""
        self.memory_store.cleanup_old_data(older_than_hours * 3600)
    
    def close(self):
        """Close the memory store"""
        self.memory_store.close()
    
    # Backward compatibility methods
    def _notify_global_observers(self, namespace: str, key: str, value: Any):
        """Backward compatibility - observers are handled by SQLite store"""
        pass