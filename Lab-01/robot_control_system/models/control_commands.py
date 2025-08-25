from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import numpy as np
from enum import Enum
from .base import BaseMessage, MessageType, Priority


class ControlMode(Enum):
    POSITION = "position"
    VELOCITY = "velocity"
    TORQUE = "torque"
    TRAJECTORY = "trajectory"


class CommandType(Enum):
    JOINT = "joint"
    CARTESIAN = "cartesian"
    GRIPPER = "gripper"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class JointCommand(BaseMessage):
    joint_names: List[str] = field(default_factory=list)
    positions: Optional[np.ndarray] = None
    velocities: Optional[np.ndarray] = None
    efforts: Optional[np.ndarray] = None
    control_mode: ControlMode = ControlMode.POSITION
    
    def __post_init__(self):
        self.message_type = MessageType.ACTION
    
    def validate(self) -> bool:
        if not self.joint_names:
            return False
        
        if self.control_mode == ControlMode.POSITION and self.positions is None:
            return False
        if self.control_mode == ControlMode.VELOCITY and self.velocities is None:
            return False
        if self.control_mode == ControlMode.TORQUE and self.efforts is None:
            return False
        
        return True


@dataclass
class CartesianCommand(BaseMessage):
    position: Optional[np.ndarray] = None  # x, y, z
    orientation: Optional[np.ndarray] = None  # quaternion
    linear_velocity: Optional[np.ndarray] = None
    angular_velocity: Optional[np.ndarray] = None
    control_mode: ControlMode = ControlMode.POSITION
    
    def __post_init__(self):
        self.message_type = MessageType.ACTION
    
    def validate(self) -> bool:
        if self.control_mode == ControlMode.POSITION:
            return self.position is not None
        elif self.control_mode == ControlMode.VELOCITY:
            return self.linear_velocity is not None or self.angular_velocity is not None
        return False


@dataclass
class GripperCommand(BaseMessage):
    position: float = 0.0  # 0 = closed, 1 = open
    force: float = 1.0  # normalized force
    
    def __post_init__(self):
        self.message_type = MessageType.ACTION
        self.priority = Priority.NORMAL


@dataclass
class VelocityCommand(BaseMessage):
    linear: np.ndarray = field(default_factory=lambda: np.zeros(3))
    angular: np.ndarray = field(default_factory=lambda: np.zeros(3))
    
    def __post_init__(self):
        self.message_type = MessageType.ACTION


@dataclass
class EmergencyStopCommand(BaseMessage):
    reason: str = "Manual emergency stop"
    
    def __post_init__(self):
        self.message_type = MessageType.ACTION
        self.priority = Priority.CRITICAL


@dataclass
class ControlCommand(BaseMessage):
    command_type: CommandType = CommandType.JOINT
    joint_command: Optional[JointCommand] = None
    cartesian_command: Optional[CartesianCommand] = None
    gripper_command: Optional[GripperCommand] = None
    emergency_stop: Optional[EmergencyStopCommand] = None
    
    def __post_init__(self):
        self.message_type = MessageType.ACTION
        
        # Set priority based on command type
        if self.emergency_stop:
            self.priority = Priority.CRITICAL
            self.command_type = CommandType.EMERGENCY_STOP
    
    def validate(self) -> bool:
        if self.command_type == CommandType.JOINT:
            return self.joint_command is not None and self.joint_command.validate()
        elif self.command_type == CommandType.CARTESIAN:
            return self.cartesian_command is not None and self.cartesian_command.validate()
        elif self.command_type == CommandType.GRIPPER:
            return self.gripper_command is not None
        elif self.command_type == CommandType.EMERGENCY_STOP:
            return self.emergency_stop is not None
        return False