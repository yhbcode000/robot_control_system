from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import numpy as np
from .base import BaseMessage, MessageType


@dataclass
class InputMessage(BaseMessage):
    def __post_init__(self):
        self.message_type = MessageType.INPUT


@dataclass
class KeyboardInput(InputMessage):
    key: str = ""
    is_pressed: bool = False
    modifiers: List[str] = field(default_factory=list)  # ctrl, alt, shift, etc.
    
    def has_modifier(self, modifier: str) -> bool:
        return modifier.lower() in [m.lower() for m in self.modifiers]


@dataclass
class MouseInput(InputMessage):
    x: int = 0
    y: int = 0
    dx: int = 0  # delta x
    dy: int = 0  # delta y
    button: Optional[str] = None  # 'left', 'right', 'middle'
    is_pressed: bool = False
    scroll_delta: int = 0


@dataclass
class SensorMessage(BaseMessage):
    def __post_init__(self):
        self.message_type = MessageType.SENSOR


@dataclass
class ForceTorqueSensor(SensorMessage):
    force: np.ndarray = field(default_factory=lambda: np.zeros(3))  # fx, fy, fz
    torque: np.ndarray = field(default_factory=lambda: np.zeros(3))  # tx, ty, tz
    
    @property
    def force_magnitude(self) -> float:
        return np.linalg.norm(self.force)
    
    @property
    def torque_magnitude(self) -> float:
        return np.linalg.norm(self.torque)


@dataclass
class ProximitySensor(SensorMessage):
    distance: float = float('inf')
    is_detected: bool = False
    sensor_name: str = ""
    
    def is_close(self, threshold: float = 0.1) -> bool:
        return self.is_detected and self.distance < threshold


@dataclass
class CameraSensor(SensorMessage):
    image: Optional[np.ndarray] = None
    width: int = 0
    height: int = 0
    channels: int = 0
    camera_name: str = ""
    
    def has_image(self) -> bool:
        return self.image is not None and self.image.size > 0


@dataclass
class IMUSensor(SensorMessage):
    linear_acceleration: np.ndarray = field(default_factory=lambda: np.zeros(3))
    angular_velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    orientation: np.ndarray = field(default_factory=lambda: np.array([0, 0, 0, 1]))  # quaternion
    
    @property
    def acceleration_magnitude(self) -> float:
        return np.linalg.norm(self.linear_acceleration)


@dataclass
class SensorBundle(BaseMessage):
    force_torque: Optional[ForceTorqueSensor] = None
    proximity: List[ProximitySensor] = field(default_factory=list)
    cameras: List[CameraSensor] = field(default_factory=list)
    imu: Optional[IMUSensor] = None
    custom_sensors: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.message_type = MessageType.SENSOR
    
    def has_collision_risk(self) -> bool:
        for prox in self.proximity:
            if prox.is_close():
                return True
        return False