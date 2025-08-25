from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from collections import deque
import time
import threading
from enum import Enum

from models.control_commands import ControlCommand
from models.robot_state import RobotState


class ExecutionStatus(Enum):
    IDLE = "idle"
    EXECUTING = "executing"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"


class CommandStatus(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class ActionState:
    """Current state of the action module"""
    execution_status: ExecutionStatus = ExecutionStatus.IDLE
    is_executing: bool = False
    has_active_trajectory: bool = False
    emergency_stop_active: bool = False
    
    # Trajectory execution state
    trajectory_start_time: float = 0.0
    execution_progress: float = 0.0  # 0.0 to 1.0
    
    # Command buffer state
    commands_in_buffer: int = 0
    total_commands_generated: int = 0
    
    # Performance metrics
    execution_errors: int = 0
    successful_executions: int = 0
    average_execution_time: float = 0.0
    
    # Timing
    last_update_time: float = field(default_factory=time.time)
    last_command_time: float = 0.0
    
    def get_success_rate(self) -> float:
        """Get execution success rate"""
        total = self.successful_executions + self.execution_errors
        if total == 0:
            return 1.0
        return self.successful_executions / total
    
    def is_active(self) -> bool:
        """Check if module is actively executing commands"""
        return self.execution_status in [ExecutionStatus.EXECUTING]
    
    def update_metrics(self, success: bool, execution_time: float):
        """Update performance metrics"""
        if success:
            self.successful_executions += 1
        else:
            self.execution_errors += 1
        
        # Update average execution time (running average)
        if self.average_execution_time == 0:
            self.average_execution_time = execution_time
        else:
            total_executions = self.successful_executions + self.execution_errors
            self.average_execution_time = ((self.average_execution_time * (total_executions - 1)) + execution_time) / total_executions


@dataclass
class ExecutionContext:
    """Context information for command execution"""
    current_robot_state: Optional[RobotState] = None
    
    # Control parameters
    control_frequency: float = 100.0  # Hz
    position_tolerance: float = 0.001  # meters
    orientation_tolerance: float = 0.01  # radians
    velocity_tolerance: float = 0.001  # m/s
    
    # Safety parameters
    max_acceleration: float = 1.0  # m/s²
    max_jerk: float = 10.0  # m/s³
    emergency_stop_deceleration: float = 5.0  # m/s²
    
    # Workspace limits
    workspace_bounds: Dict[str, float] = field(default_factory=lambda: {
        'x_min': 0.1, 'x_max': 0.8,
        'y_min': -0.5, 'y_max': 0.5,
        'z_min': 0.1, 'z_max': 0.8
    })
    
    # Execution state
    last_command_timestamp: float = 0.0
    command_timeout: float = 1.0  # seconds
    
    def is_position_safe(self, position) -> bool:
        """Check if position is within safe workspace"""
        try:
            bounds = self.workspace_bounds
            return (bounds['x_min'] <= position[0] <= bounds['x_max'] and
                   bounds['y_min'] <= position[1] <= bounds['y_max'] and
                   bounds['z_min'] <= position[2] <= bounds['z_max'])
        except:
            return False
    
    def is_emergency_stop_needed(self) -> bool:
        """Check if emergency stop should be triggered"""
        if not self.current_robot_state:
            return False
        
        # Check for collision detection
        if self.current_robot_state.is_collision_detected:
            return True
        
        # Check if robot is outside safe workspace
        if self.current_robot_state.end_effector_pose:
            position = self.current_robot_state.end_effector_pose.position
            if not self.is_position_safe(position):
                return True
        
        return False


@dataclass
class CommandExecution:
    """Represents the execution of a single command"""
    command: ControlCommand
    status: CommandStatus = CommandStatus.PENDING
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    execution_time: Optional[float] = None
    
    def mark_completed(self):
        """Mark command as completed"""
        self.status = CommandStatus.COMPLETED
        self.end_time = time.time()
        self.execution_time = self.end_time - self.start_time
    
    def mark_failed(self, error_message: str):
        """Mark command as failed"""
        self.status = CommandStatus.FAILED
        self.end_time = time.time()
        self.error_message = error_message
        self.execution_time = self.end_time - self.start_time
    
    def is_expired(self, timeout: float = 1.0) -> bool:
        """Check if command has expired"""
        return (time.time() - self.start_time) > timeout
    
    def get_age(self) -> float:
        """Get age of command in seconds"""
        return time.time() - self.start_time


class CommandBuffer:
    """Thread-safe command buffer for managing pending commands"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.commands: deque = deque(maxlen=max_size)
        self.command_history: deque = deque(maxlen=100)  # Keep history for debugging
        self._lock = threading.Lock() if 'threading' in globals() else None
    
    def add_command(self, command: ControlCommand):
        """Add command to buffer"""
        try:
            if self._lock:
                with self._lock:
                    self.commands.append(CommandExecution(command))
            else:
                self.commands.append(CommandExecution(command))
        except Exception as e:
            print(f"Error adding command to buffer: {e}")
    
    def get_next_command(self) -> Optional[CommandExecution]:
        """Get next command from buffer"""
        try:
            if self._lock:
                with self._lock:
                    if self.commands:
                        return self.commands.popleft()
            else:
                if self.commands:
                    return self.commands.popleft()
            return None
        except Exception as e:
            print(f"Error getting next command: {e}")
            return None
    
    def get_commands(self, max_count: Optional[int] = None, 
                    max_age: float = 1.0) -> List[ControlCommand]:
        """Get multiple commands from buffer"""
        try:
            commands = []
            count = 0
            
            if self._lock:
                with self._lock:
                    while self.commands and (max_count is None or count < max_count):
                        cmd_exec = self.commands[0]  # Peek at first command
                        
                        # Check if command is too old
                        if cmd_exec.get_age() > max_age:
                            # Remove expired command
                            expired = self.commands.popleft()
                            expired.status = CommandStatus.EXPIRED
                            self.command_history.append(expired)
                            continue
                        
                        # Take the command
                        cmd_exec = self.commands.popleft()
                        cmd_exec.status = CommandStatus.EXECUTING
                        commands.append(cmd_exec.command)
                        self.command_history.append(cmd_exec)
                        count += 1
            else:
                while self.commands and (max_count is None or count < max_count):
                    cmd_exec = self.commands[0]  # Peek at first command
                    
                    # Check if command is too old
                    if cmd_exec.get_age() > max_age:
                        # Remove expired command
                        expired = self.commands.popleft()
                        expired.status = CommandStatus.EXPIRED
                        self.command_history.append(expired)
                        continue
                    
                    # Take the command
                    cmd_exec = self.commands.popleft()
                    cmd_exec.status = CommandStatus.EXECUTING
                    commands.append(cmd_exec.command)
                    self.command_history.append(cmd_exec)
                    count += 1
            
            return commands
            
        except Exception as e:
            print(f"Error getting commands: {e}")
            return []
    
    def clear(self):
        """Clear all commands from buffer"""
        try:
            if self._lock:
                with self._lock:
                    self.commands.clear()
            else:
                self.commands.clear()
        except Exception as e:
            print(f"Error clearing command buffer: {e}")
    
    def size(self) -> int:
        """Get current buffer size"""
        try:
            if self._lock:
                with self._lock:
                    return len(self.commands)
            else:
                return len(self.commands)
        except:
            return 0
    
    def is_empty(self) -> bool:
        """Check if buffer is empty"""
        return self.size() == 0
    
    def is_full(self) -> bool:
        """Check if buffer is full"""
        return self.size() >= self.max_size
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get buffer statistics"""
        try:
            total_commands = len(self.command_history)
            if total_commands == 0:
                return {
                    'total_commands': 0,
                    'completed': 0,
                    'failed': 0,
                    'expired': 0,
                    'success_rate': 1.0,
                    'current_buffer_size': self.size()
                }
            
            completed = sum(1 for cmd in self.command_history if cmd.status == CommandStatus.COMPLETED)
            failed = sum(1 for cmd in self.command_history if cmd.status == CommandStatus.FAILED)
            expired = sum(1 for cmd in self.command_history if cmd.status == CommandStatus.EXPIRED)
            
            success_rate = completed / (completed + failed) if (completed + failed) > 0 else 1.0
            
            return {
                'total_commands': total_commands,
                'completed': completed,
                'failed': failed,
                'expired': expired,
                'success_rate': success_rate,
                'current_buffer_size': self.size()
            }
            
        except Exception as e:
            print(f"Error getting buffer statistics: {e}")
            return {}


@dataclass
class ActuatorState:
    """State of individual actuator"""
    actuator_id: str
    actuator_type: str  # joint, gripper, end_effector
    current_position: float = 0.0
    target_position: float = 0.0
    current_velocity: float = 0.0
    target_velocity: float = 0.0
    current_effort: float = 0.0
    is_moving: bool = False
    has_error: bool = False
    error_code: Optional[int] = None
    error_message: Optional[str] = None
    last_update: float = field(default_factory=time.time)
    
    def is_at_target(self, position_tolerance: float = 0.001,
                    velocity_tolerance: float = 0.001) -> bool:
        """Check if actuator is at target position and velocity"""
        position_ok = abs(self.current_position - self.target_position) <= position_tolerance
        velocity_ok = abs(self.current_velocity - self.target_velocity) <= velocity_tolerance
        return position_ok and velocity_ok
    
    def update_state(self, position: float, velocity: float = 0.0, effort: float = 0.0):
        """Update actuator state"""
        self.current_position = position
        self.current_velocity = velocity
        self.current_effort = effort
        self.last_update = time.time()
        
        # Update moving flag
        self.is_moving = abs(velocity) > 0.001  # Small threshold for noise


@dataclass
class SystemLimits:
    """System-wide limits and constraints"""
    # Position limits
    max_reach: float = 0.8  # meters
    workspace_center: List[float] = field(default_factory=lambda: [0.5, 0.0, 0.5])
    
    # Velocity limits
    max_cartesian_velocity: float = 0.2  # m/s
    max_joint_velocity: float = 2.0  # rad/s
    
    # Acceleration limits
    max_cartesian_acceleration: float = 1.0  # m/s²
    max_joint_acceleration: float = 5.0  # rad/s²
    
    # Safety limits
    collision_threshold: float = 0.02  # meters
    force_threshold: float = 50.0  # Newtons
    
    # Timing limits
    command_timeout: float = 0.5  # seconds
    trajectory_timeout: float = 30.0  # seconds
    
    def validate_position(self, position) -> bool:
        """Validate if position is within limits"""
        try:
            center = self.workspace_center
            distance = ((position[0] - center[0])**2 + 
                       (position[1] - center[1])**2 + 
                       (position[2] - center[2])**2)**0.5
            return distance <= self.max_reach
        except:
            return False
    
    def validate_velocity(self, velocity) -> bool:
        """Validate if velocity is within limits"""
        try:
            speed = (velocity[0]**2 + velocity[1]**2 + velocity[2]**2)**0.5
            return speed <= self.max_cartesian_velocity
        except:
            return False