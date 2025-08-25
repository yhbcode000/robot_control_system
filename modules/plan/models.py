from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import numpy as np
import time
from enum import Enum


class PlannerType(Enum):
    SIMPLE = "simple"
    RRT = "rrt"
    RRT_STAR = "rrt_star"
    PRM = "prm"
    DIRECT = "direct"


class ConstraintType(Enum):
    POSITION = "position"
    ORIENTATION = "orientation"
    JOINT_LIMITS = "joint_limits"
    VELOCITY = "velocity"
    ACCELERATION = "acceleration"
    OBSTACLE_AVOIDANCE = "obstacle_avoidance"
    WORKSPACE_BOUNDS = "workspace_bounds"


@dataclass
class PlannerConfig:
    """Configuration for trajectory planners"""
    planner_type: PlannerType = PlannerType.SIMPLE
    max_planning_time: float = 1.0
    max_iterations: int = 1000
    step_size: float = 0.01
    goal_threshold: float = 0.005
    
    # Velocity and acceleration limits
    max_linear_velocity: float = 0.1
    max_angular_velocity: float = 0.5
    max_linear_acceleration: float = 0.2
    max_angular_acceleration: float = 1.0
    
    # Workspace constraints
    workspace_bounds: Dict[str, float] = field(default_factory=lambda: {
        'x_min': 0.1, 'x_max': 0.8,
        'y_min': -0.5, 'y_max': 0.5,
        'z_min': 0.1, 'z_max': 0.8
    })
    
    # Safety margins
    obstacle_margin: float = 0.05
    self_collision_margin: float = 0.02
    
    # Smoothing parameters
    smoothing_enabled: bool = True
    smoothing_iterations: int = 10
    smoothing_factor: float = 0.1


@dataclass
class Constraint:
    """Represents a planning constraint"""
    constraint_type: ConstraintType
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_hard: bool = True  # Hard constraint (must be satisfied) vs soft constraint
    weight: float = 1.0   # Weight for soft constraints
    
    def evaluate(self, state: np.ndarray) -> bool:
        """Evaluate if state satisfies constraint"""
        # This would be implemented based on constraint type
        return True  # Placeholder


@dataclass
class PlanningContext:
    """Context information for planning"""
    # Current robot state
    current_position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    current_orientation: np.ndarray = field(default_factory=lambda: np.array([0, 0, 0, 1]))
    current_joint_positions: np.ndarray = field(default_factory=lambda: np.zeros(6))
    current_velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    
    # Robot properties
    gripper_state: float = 0.0
    is_moving: bool = False
    emergency_stop: bool = False
    
    # Environment context
    obstacles: List[Dict[str, Any]] = field(default_factory=list)
    workspace_min: np.ndarray = field(default_factory=lambda: np.array([0.1, -0.5, 0.1]))
    workspace_max: np.ndarray = field(default_factory=lambda: np.array([0.8, 0.5, 0.8]))
    
    # Planning constraints
    active_constraints: List[Constraint] = field(default_factory=list)
    
    # Performance tracking
    last_planning_time: float = 0.0
    planning_success_rate: float = 1.0
    
    def add_constraint(self, constraint: Constraint):
        """Add a planning constraint"""
        self.active_constraints.append(constraint)
    
    def remove_constraint(self, constraint_type: ConstraintType):
        """Remove constraints of a specific type"""
        self.active_constraints = [c for c in self.active_constraints if c.constraint_type != constraint_type]
    
    def is_position_valid(self, position: np.ndarray) -> bool:
        """Check if position is within workspace bounds"""
        try:
            return (np.all(position >= self.workspace_min) and 
                   np.all(position <= self.workspace_max))
        except:
            return False
    
    def get_distance_to_obstacle(self, position: np.ndarray) -> float:
        """Get minimum distance to any obstacle"""
        if not self.obstacles:
            return float('inf')
        
        min_distance = float('inf')
        for obstacle in self.obstacles:
            # Simplified obstacle distance calculation
            # In practice, this would be more sophisticated
            if 'position' in obstacle and 'radius' in obstacle:
                obs_pos = np.array(obstacle['position'])
                obs_radius = obstacle['radius']
                distance = np.linalg.norm(position - obs_pos) - obs_radius
                min_distance = min(min_distance, distance)
        
        return min_distance


@dataclass
class PlanningMetrics:
    """Metrics for planning performance"""
    total_requests: int = 0
    successful_plans: int = 0
    failed_plans: int = 0
    average_planning_time: float = 0.0
    planning_times: List[float] = field(default_factory=list)
    
    # Quality metrics
    average_path_length: float = 0.0
    average_smoothness: float = 0.0
    
    def record_planning_attempt(self, success: bool, planning_time: float, 
                              path_length: Optional[float] = None):
        """Record a planning attempt"""
        self.total_requests += 1
        self.planning_times.append(planning_time)
        
        if success:
            self.successful_plans += 1
            if path_length is not None:
                # Update running average
                if self.average_path_length == 0:
                    self.average_path_length = path_length
                else:
                    self.average_path_length = (self.average_path_length * (self.successful_plans - 1) + path_length) / self.successful_plans
        else:
            self.failed_plans += 1
        
        # Update average planning time
        self.average_planning_time = sum(self.planning_times) / len(self.planning_times)
        
        # Limit history size
        if len(self.planning_times) > 1000:
            self.planning_times = self.planning_times[-100:]  # Keep last 100
    
    def get_success_rate(self) -> float:
        """Get planning success rate"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_plans / self.total_requests


@dataclass
class PathSegment:
    """Represents a segment of a planned path"""
    start_position: np.ndarray
    end_position: np.ndarray
    start_orientation: np.ndarray
    end_orientation: np.ndarray
    duration: float
    segment_type: str = "linear"  # linear, circular, spline
    constraints: List[Constraint] = field(default_factory=list)
    
    def get_length(self) -> float:
        """Get length of path segment"""
        return np.linalg.norm(self.end_position - self.start_position)
    
    def interpolate(self, t: float) -> tuple:
        """Interpolate position and orientation at parameter t (0 to 1)"""
        if not (0 <= t <= 1):
            t = max(0, min(1, t))
        
        position = self.start_position + t * (self.end_position - self.start_position)
        
        # Simple linear interpolation for orientation (should use SLERP for quaternions)
        orientation = self.start_orientation + t * (self.end_orientation - self.start_orientation)
        # Normalize quaternion
        if len(orientation) == 4:
            orientation = orientation / np.linalg.norm(orientation)
        
        return position, orientation


@dataclass
class CollisionObject:
    """Represents an object in the environment that could cause collisions"""
    name: str
    object_type: str  # box, sphere, cylinder, mesh
    position: np.ndarray
    orientation: np.ndarray = field(default_factory=lambda: np.array([0, 0, 0, 1]))
    dimensions: np.ndarray = field(default_factory=lambda: np.zeros(3))  # width, height, depth for box
    radius: float = 0.0  # for sphere/cylinder
    is_static: bool = True
    
    def distance_to_point(self, point: np.ndarray) -> float:
        """Calculate minimum distance from point to object"""
        # Simplified distance calculation
        if self.object_type == "sphere":
            return max(0, np.linalg.norm(point - self.position) - self.radius)
        elif self.object_type == "box":
            # Simple box distance (not exact)
            diff = np.abs(point - self.position) - self.dimensions / 2
            return np.linalg.norm(np.maximum(diff, 0))
        else:
            # Default to point distance
            return np.linalg.norm(point - self.position)


@dataclass
class PlanningProblem:
    """Defines a complete planning problem"""
    start_position: np.ndarray
    start_orientation: np.ndarray
    goal_position: np.ndarray
    goal_orientation: np.ndarray
    
    # Optional joint space definition
    start_joints: Optional[np.ndarray] = None
    goal_joints: Optional[np.ndarray] = None
    joint_names: List[str] = field(default_factory=list)
    
    # Planning constraints
    constraints: List[Constraint] = field(default_factory=list)
    collision_objects: List[CollisionObject] = field(default_factory=list)
    
    # Planning parameters
    max_planning_time: float = 5.0
    planner_config: Optional[PlannerConfig] = None
    
    def is_valid(self) -> bool:
        """Check if planning problem is well-defined"""
        try:
            # Check required fields
            if self.start_position is None or self.goal_position is None:
                return False
            if self.start_orientation is None or self.goal_orientation is None:
                return False
            
            # Check dimensions
            if len(self.start_position) != 3 or len(self.goal_position) != 3:
                return False
            if len(self.start_orientation) != 4 or len(self.goal_orientation) != 4:
                return False
            
            # Check joint space consistency if provided
            if self.start_joints is not None and self.goal_joints is not None:
                if len(self.start_joints) != len(self.goal_joints):
                    return False
                if len(self.joint_names) != len(self.start_joints):
                    return False
            
            return True
            
        except Exception:
            return False
    
    def get_distance_to_goal(self, position: np.ndarray) -> float:
        """Get distance from position to goal"""
        return np.linalg.norm(position - self.goal_position)