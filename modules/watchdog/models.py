from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any
import time


class RecoveryStrategy(Enum):
    RESTART = "restart"          # Kill and restart thread
    RESET = "reset"              # Reset module state, keep thread
    DEGRADE = "degrade"          # Reduce functionality
    ISOLATE = "isolate"          # Disconnect from system
    EMERGENCY_STOP = "stop"      # Stop entire system
    NONE = "none"                # No action


class FailureType(Enum):
    HEARTBEAT_TIMEOUT = "heartbeat_timeout"
    HIGH_ERROR_RATE = "high_error_rate"
    MEMORY_LEAK = "memory_leak"
    CPU_OVERLOAD = "cpu_overload"
    QUEUE_OVERFLOW = "queue_overflow"
    CRITICAL_ERROR = "critical_error"
    FROZEN_THREAD = "frozen_thread"
    PERFORMANCE_DEGRADATION = "performance_degradation"


@dataclass
class FailureEvent:
    module_name: str
    failure_type: FailureType
    timestamp: float = field(default_factory=time.time)
    description: str = ""
    severity: int = 1  # 1-5, 5 being most severe
    recovery_attempted: bool = False
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.NONE
    recovery_successful: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModuleHealth:
    module_name: str
    is_healthy: bool
    last_heartbeat: float
    heartbeat_age: float
    error_rate: float  # errors per second
    cpu_usage: float  # percentage
    memory_usage: float  # MB
    queue_size: int
    processing_time: float  # average in seconds
    consecutive_errors: int
    health_score: float  # 0-100


@dataclass
class SystemHealthReport:
    timestamp: float = field(default_factory=time.time)
    overall_health_score: float = 100.0
    module_health: Dict[str, ModuleHealth] = field(default_factory=dict)
    active_failures: list = field(default_factory=list)
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    uptime: float = 0.0
    total_errors: int = 0
    total_recoveries: int = 0