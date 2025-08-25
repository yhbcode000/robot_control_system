from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import numpy as np
from enum import Enum
from .base import BaseMessage, MessageType, Priority
from .control_commands import JointCommand, CartesianCommand


class PlanningStatus(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    READY = "ready"
    EXECUTING = "executing"
    FAILED = "failed"


@dataclass
class Waypoint(BaseMessage):
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    orientation: np.ndarray = field(default_factory=lambda: np.array([0, 0, 0, 1]))  # quaternion
    joint_positions: Optional[np.ndarray] = None
    timestamp_offset: float = 0.0  # time from start
    velocity_constraint: float = 1.0  # max velocity scale
    
    def __post_init__(self):
        self.message_type = MessageType.PLAN


@dataclass
class Trajectory(BaseMessage):
    waypoints: List[Waypoint] = field(default_factory=list)
    joint_trajectory: List[JointCommand] = field(default_factory=list)
    cartesian_trajectory: List[CartesianCommand] = field(default_factory=list)
    total_duration: float = 0.0
    status: PlanningStatus = PlanningStatus.IDLE
    
    def __post_init__(self):
        self.message_type = MessageType.PLAN
    
    def add_waypoint(self, waypoint: Waypoint):
        self.waypoints.append(waypoint)
        self.total_duration = max(self.total_duration, waypoint.timestamp_offset)
    
    def is_empty(self) -> bool:
        return len(self.waypoints) == 0 and len(self.joint_trajectory) == 0
    
    def get_waypoint_at_time(self, t: float) -> Optional[Waypoint]:
        for waypoint in self.waypoints:
            if waypoint.timestamp_offset >= t:
                return waypoint
        return None


@dataclass
class PlanRequest(BaseMessage):
    target_position: Optional[np.ndarray] = None
    target_orientation: Optional[np.ndarray] = None
    target_joints: Optional[np.ndarray] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    planning_algorithm: str = "rrt"
    max_planning_time: float = 5.0
    
    def __post_init__(self):
        self.message_type = MessageType.PLAN
        self.priority = Priority.NORMAL


@dataclass
class PlanResponse(BaseMessage):
    request_id: str = ""
    trajectory: Optional[Trajectory] = None
    success: bool = False
    error_message: str = ""
    planning_time: float = 0.0
    
    def __post_init__(self):
        self.message_type = MessageType.PLAN


@dataclass
class MotionPlan(BaseMessage):
    current_trajectory: Optional[Trajectory] = None
    pending_requests: List[PlanRequest] = field(default_factory=list)
    execution_progress: float = 0.0  # 0.0 to 1.0
    status: PlanningStatus = PlanningStatus.IDLE
    
    def __post_init__(self):
        self.message_type = MessageType.PLAN
    
    def has_active_trajectory(self) -> bool:
        return (self.current_trajectory is not None 
                and not self.current_trajectory.is_empty()
                and self.status == PlanningStatus.EXECUTING)
    
    def add_request(self, request: PlanRequest):
        self.pending_requests.append(request)
    
    def get_next_request(self) -> Optional[PlanRequest]:
        if self.pending_requests:
            return self.pending_requests.pop(0)
        return None