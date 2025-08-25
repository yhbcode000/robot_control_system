from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import numpy as np
from .base import BaseMessage, MessageType


@dataclass
class JointState(BaseMessage):
    joint_names: List[str] = field(default_factory=list)
    positions: np.ndarray = field(default_factory=lambda: np.array([]))
    velocities: np.ndarray = field(default_factory=lambda: np.array([]))
    efforts: np.ndarray = field(default_factory=lambda: np.array([]))
    
    def __post_init__(self):
        self.message_type = MessageType.SENSOR
    
    def get_joint_position(self, joint_name: str) -> Optional[float]:
        if joint_name in self.joint_names:
            idx = self.joint_names.index(joint_name)
            return self.positions[idx] if idx < len(self.positions) else None
        return None


@dataclass
class EndEffectorPose(BaseMessage):
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))  # x, y, z
    orientation: np.ndarray = field(default_factory=lambda: np.array([0, 0, 0, 1]))  # quaternion
    linear_velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    angular_velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    
    def __post_init__(self):
        self.message_type = MessageType.SENSOR
    
    @property
    def x(self) -> float:
        return self.position[0]
    
    @property
    def y(self) -> float:
        return self.position[1]
    
    @property
    def z(self) -> float:
        return self.position[2]


@dataclass 
class RobotState(BaseMessage):
    joint_state: Optional[JointState] = None
    end_effector_pose: Optional[EndEffectorPose] = None
    gripper_state: float = 0.0  # 0 = closed, 1 = open
    is_moving: bool = False
    is_collision_detected: bool = False
    emergency_stop: bool = False
    
    def __post_init__(self):
        self.message_type = MessageType.SENSOR
    
    def is_safe(self) -> bool:
        return not self.is_collision_detected and not self.emergency_stop