from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from abc import ABC
import time
from enum import Enum


class MessageType(Enum):
    INPUT = "input"
    SENSOR = "sensor"
    PLAN = "plan"
    ACTION = "action"
    OUTPUT = "output"
    SYSTEM = "system"
    HEALTH = "health"


class Priority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class BaseMessage(ABC):
    timestamp: float = field(default_factory=time.time)
    message_type: MessageType = MessageType.SYSTEM
    priority: Priority = Priority.NORMAL
    source_module: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def age(self) -> float:
        return time.time() - self.timestamp
    
    def is_expired(self, max_age: float = 1.0) -> bool:
        return self.age() > max_age