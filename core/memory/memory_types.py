from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import time
from collections import deque


class ModuleStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FROZEN = "frozen"
    DEAD = "dead"
    UNKNOWN = "unknown"


@dataclass
class HeartbeatInfo:
    timestamp: float
    error_count: int = 0
    avg_processing_time: float = 0.0
    consecutive_misses: int = 0
    
    @property
    def age(self) -> float:
        return time.time() - self.timestamp


@dataclass
class ThreadHealth:
    module_name: str
    status: ModuleStatus
    last_heartbeat: float
    consecutive_misses: int
    cpu_usage: float
    memory_usage: float
    response_time: float
    error_count: int = 0
    message_queue_size: int = 0


@dataclass
class ModuleMetrics:
    module_name: str
    last_heartbeat: float
    processing_time: float
    error_count: int
    throughput: float
    queue_size: int = 0
    cpu_percent: float = 0.0
    memory_mb: float = 0.0


@dataclass
class SystemMetrics:
    cpu_usage: float
    memory_usage: float
    message_queue_size: int
    latency: float
    uptime: float
    total_messages: int
    fps: float


@dataclass
class HealthStatus:
    thread_health: Dict[str, ThreadHealth] = field(default_factory=dict)
    module_metrics: Dict[str, ModuleMetrics] = field(default_factory=dict)
    system_metrics: Optional[SystemMetrics] = None
    health_score: float = 100.0


@dataclass 
class MemoryNamespace:
    data: Dict[str, Any] = field(default_factory=dict)
    observers: List[Callable] = field(default_factory=list)
    history: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def update(self, key: str, value: Any):
        old_value = self.data.get(key)
        self.data[key] = value
        self.history.append({
            'timestamp': time.time(),
            'key': key,
            'old_value': old_value,
            'new_value': value
        })
        self._notify_observers(key, value)
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)
    
    def subscribe(self, callback: Callable):
        self.observers.append(callback)
    
    def unsubscribe(self, callback: Callable):
        if callback in self.observers:
            self.observers.remove(callback)
    
    def _notify_observers(self, key: str, value: Any):
        for observer in self.observers:
            try:
                observer(key, value)
            except Exception as e:
                print(f"Observer notification failed: {e}")