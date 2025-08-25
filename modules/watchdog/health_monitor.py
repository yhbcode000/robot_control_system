import time
from typing import Dict, Optional, List
from dataclasses import dataclass
import threading

from core.memory.memory_store import GlobalMemory
from core.memory.memory_types import ModuleStatus, HeartbeatInfo
from .models import ModuleHealth, FailureType
from .metrics import ModuleMetricsTracker


class HealthMonitor:
    def __init__(self, config: Dict):
        self.config = config
        self.memory = GlobalMemory.get_instance()
        self.module_trackers: Dict[str, ModuleMetricsTracker] = {}
        self.heartbeat_timeout = config.get('heartbeat_timeout', 5.0)
        self.heartbeat_warning = config.get('heartbeat_warning', 2.0)
        self._lock = threading.Lock()
    
    def register_module(self, module_name: str):
        with self._lock:
            if module_name not in self.module_trackers:
                self.module_trackers[module_name] = ModuleMetricsTracker(module_name)
    
    def check_module_health(self, module_name: str) -> ModuleHealth:
        # Get heartbeat info
        heartbeat = self.memory.get_module_heartbeat(module_name)
        current_time = time.time()
        
        if heartbeat is None:
            return ModuleHealth(
                module_name=module_name,
                is_healthy=False,
                last_heartbeat=0,
                heartbeat_age=float('inf'),
                error_rate=0,
                cpu_usage=0,
                memory_usage=0,
                queue_size=0,
                processing_time=0,
                consecutive_errors=0,
                health_score=0
            )
        
        heartbeat_age = current_time - heartbeat.timestamp
        
        # Get module metrics
        tracker = self.module_trackers.get(module_name)
        metrics = tracker.get_metrics() if tracker else {}
        
        # Calculate health score
        health_score = self._calculate_health_score(
            heartbeat_age=heartbeat_age,
            error_rate=metrics.get('error_rate', 0),
            consecutive_errors=heartbeat.consecutive_misses,
            processing_time=heartbeat.avg_processing_time
        )
        
        # Determine if healthy
        is_healthy = (
            heartbeat_age < self.heartbeat_timeout and
            health_score > 50 and
            heartbeat.consecutive_misses < 5
        )
        
        return ModuleHealth(
            module_name=module_name,
            is_healthy=is_healthy,
            last_heartbeat=heartbeat.timestamp,
            heartbeat_age=heartbeat_age,
            error_rate=metrics.get('error_rate', 0),
            cpu_usage=0,  # Will be updated by system metrics
            memory_usage=0,  # Will be updated by system metrics
            queue_size=0,
            processing_time=heartbeat.avg_processing_time,
            consecutive_errors=heartbeat.consecutive_misses,
            health_score=health_score
        )
    
    def _calculate_health_score(self, heartbeat_age: float, error_rate: float,
                                consecutive_errors: int, processing_time: float) -> float:
        score = 100.0
        
        # Heartbeat age penalty
        if heartbeat_age > self.heartbeat_warning:
            score -= min(50, (heartbeat_age - self.heartbeat_warning) * 10)
        
        # Error rate penalty
        score -= min(30, error_rate * 10)
        
        # Consecutive errors penalty
        score -= min(20, consecutive_errors * 5)
        
        # Processing time penalty (if too slow)
        target_processing_time = 0.01  # 10ms target
        if processing_time > target_processing_time:
            score -= min(20, (processing_time - target_processing_time) * 100)
        
        return max(0, score)
    
    def detect_failures(self, module_health: ModuleHealth) -> List[FailureType]:
        failures = []
        
        # Check heartbeat timeout
        if module_health.heartbeat_age > self.heartbeat_timeout:
            failures.append(FailureType.HEARTBEAT_TIMEOUT)
        
        # Check if thread is frozen
        if module_health.heartbeat_age > self.heartbeat_timeout * 2:
            failures.append(FailureType.FROZEN_THREAD)
        
        # Check error rate
        if module_health.error_rate > 1.0:  # More than 1 error per second
            failures.append(FailureType.HIGH_ERROR_RATE)
        
        # Check performance degradation
        if module_health.processing_time > 0.1:  # More than 100ms
            failures.append(FailureType.PERFORMANCE_DEGRADATION)
        
        # Check CPU usage (if available)
        if module_health.cpu_usage > 80:
            failures.append(FailureType.CPU_OVERLOAD)
        
        # Check memory usage (if available and growing)
        # This would need historical data to properly detect
        
        # Check queue size
        if module_health.queue_size > 1000:
            failures.append(FailureType.QUEUE_OVERFLOW)
        
        return failures
    
    def get_module_status(self, module_health: ModuleHealth) -> ModuleStatus:
        if not module_health.is_healthy:
            if module_health.heartbeat_age > self.heartbeat_timeout * 2:
                return ModuleStatus.DEAD
            elif module_health.heartbeat_age > self.heartbeat_timeout:
                return ModuleStatus.FROZEN
            elif module_health.health_score < 30:
                return ModuleStatus.DEGRADED
        
        if module_health.health_score > 80:
            return ModuleStatus.HEALTHY
        elif module_health.health_score > 50:
            return ModuleStatus.DEGRADED
        else:
            return ModuleStatus.FROZEN
    
    def update_module_metrics(self, module_name: str, processing_time: float = None,
                            error: bool = False):
        tracker = self.module_trackers.get(module_name)
        if tracker:
            if processing_time is not None:
                tracker.record_message(processing_time)
            if error:
                tracker.record_error()