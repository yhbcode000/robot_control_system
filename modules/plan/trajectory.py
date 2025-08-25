import numpy as np
import time
from typing import List, Optional, Dict, Any
from models.planning_data import Trajectory, Waypoint, PlanningStatus
from models.control_commands import JointCommand, CartesianCommand, ControlMode


class TrajectoryGenerator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_velocity = config.get('max_velocity', 0.1)  # m/s
        self.max_acceleration = config.get('max_acceleration', 0.2)  # m/s²
        self.max_angular_velocity = config.get('max_angular_velocity', 0.5)  # rad/s
        
    def generate_linear_trajectory(self, start_position: np.ndarray, end_position: np.ndarray,
                                 start_orientation: np.ndarray, end_orientation: np.ndarray,
                                 duration: float, steps: int = 10) -> Trajectory:
        """Generate a linear trajectory between two poses"""
        try:
            trajectory = Trajectory()
            
            if steps < 2:
                steps = 2
            
            # Create waypoints
            for i in range(steps):
                t = i / (steps - 1)  # 0 to 1
                
                # Linear interpolation for position
                position = start_position + t * (end_position - start_position)
                
                # SLERP for orientation (simplified - using linear interpolation)
                orientation = self._interpolate_quaternion(start_orientation, end_orientation, t)
                
                # Create waypoint
                waypoint = Waypoint(
                    position=position,
                    orientation=orientation,
                    timestamp_offset=t * duration
                )
                
                trajectory.add_waypoint(waypoint)
            
            # Generate corresponding Cartesian commands
            trajectory.cartesian_trajectory = self._waypoints_to_cartesian_commands(trajectory.waypoints)
            
            trajectory.total_duration = duration
            trajectory.status = PlanningStatus.READY
            
            return trajectory
            
        except Exception as e:
            print(f"Error generating linear trajectory: {e}")
            return Trajectory()
    
    def generate_rotation_trajectory(self, position: np.ndarray, start_orientation: np.ndarray,
                                   end_orientation: np.ndarray, duration: float, 
                                   steps: int = 10) -> Trajectory:
        """Generate a pure rotation trajectory"""
        try:
            trajectory = Trajectory()
            
            if steps < 2:
                steps = 2
            
            # Create waypoints
            for i in range(steps):
                t = i / (steps - 1)  # 0 to 1
                
                # Keep position constant
                waypoint_position = position.copy()
                
                # Interpolate orientation
                orientation = self._interpolate_quaternion(start_orientation, end_orientation, t)
                
                # Create waypoint
                waypoint = Waypoint(
                    position=waypoint_position,
                    orientation=orientation,
                    timestamp_offset=t * duration
                )
                
                trajectory.add_waypoint(waypoint)
            
            # Generate corresponding Cartesian commands
            trajectory.cartesian_trajectory = self._waypoints_to_cartesian_commands(trajectory.waypoints)
            
            trajectory.total_duration = duration
            trajectory.status = PlanningStatus.READY
            
            return trajectory
            
        except Exception as e:
            print(f"Error generating rotation trajectory: {e}")
            return Trajectory()
    
    def generate_joint_trajectory(self, start_joints: np.ndarray, end_joints: np.ndarray,
                                joint_names: List[str], duration: float, 
                                steps: int = 10) -> Trajectory:
        """Generate a joint-space trajectory"""
        try:
            trajectory = Trajectory()
            
            if steps < 2:
                steps = 2
            
            if len(start_joints) != len(end_joints) or len(start_joints) != len(joint_names):
                raise ValueError("Joint arrays and names must have same length")
            
            # Create joint trajectory
            for i in range(steps):
                t = i / (steps - 1)  # 0 to 1
                
                # Linear interpolation for joint positions
                joint_positions = start_joints + t * (end_joints - start_joints)
                
                # Create joint command
                joint_cmd = JointCommand(
                    joint_names=joint_names,
                    positions=joint_positions,
                    control_mode=ControlMode.POSITION
                )
                joint_cmd.timestamp = time.time() + t * duration
                
                trajectory.joint_trajectory.append(joint_cmd)
            
            trajectory.total_duration = duration
            trajectory.status = PlanningStatus.READY
            
            return trajectory
            
        except Exception as e:
            print(f"Error generating joint trajectory: {e}")
            return Trajectory()
    
    def generate_smooth_trajectory(self, waypoints: List[Waypoint], 
                                 smoothing_factor: float = 0.5) -> Trajectory:
        """Generate a smooth trajectory through multiple waypoints"""
        try:
            if len(waypoints) < 2:
                return Trajectory()
            
            trajectory = Trajectory()
            
            # For now, just connect waypoints linearly
            # In a real implementation, you'd use splines or other smoothing techniques
            total_duration = waypoints[-1].timestamp_offset
            
            # Add original waypoints
            for waypoint in waypoints:
                trajectory.add_waypoint(waypoint)
            
            # Generate commands
            trajectory.cartesian_trajectory = self._waypoints_to_cartesian_commands(waypoints)
            
            trajectory.total_duration = total_duration
            trajectory.status = PlanningStatus.READY
            
            return trajectory
            
        except Exception as e:
            print(f"Error generating smooth trajectory: {e}")
            return Trajectory()
    
    def _interpolate_quaternion(self, q1: np.ndarray, q2: np.ndarray, t: float) -> np.ndarray:
        """Simple quaternion interpolation (LERP, not SLERP for simplicity)"""
        try:
            if len(q1) != 4 or len(q2) != 4:
                # If not quaternions, return q1
                return q1.copy()
            
            # Simple linear interpolation (not mathematically correct for quaternions)
            # In practice, use proper SLERP
            result = q1 + t * (q2 - q1)
            
            # Normalize
            norm = np.linalg.norm(result)
            if norm > 0:
                result = result / norm
            else:
                result = np.array([0, 0, 0, 1])  # Default quaternion
            
            return result
            
        except Exception as e:
            print(f"Error interpolating quaternion: {e}")
            return q1.copy()
    
    def _waypoints_to_cartesian_commands(self, waypoints: List[Waypoint]) -> List[CartesianCommand]:
        """Convert waypoints to Cartesian commands"""
        commands = []
        
        try:
            for waypoint in waypoints:
                cmd = CartesianCommand(
                    position=waypoint.position,
                    orientation=waypoint.orientation,
                    control_mode=ControlMode.POSITION
                )
                cmd.timestamp = time.time() + waypoint.timestamp_offset
                commands.append(cmd)
            
        except Exception as e:
            print(f"Error converting waypoints to commands: {e}")
        
        return commands
    
    def calculate_trajectory_time(self, start_pos: np.ndarray, end_pos: np.ndarray,
                                max_velocity: Optional[float] = None) -> float:
        """Calculate minimum time needed for trajectory given velocity constraints"""
        try:
            max_vel = max_velocity or self.max_velocity
            
            distance = np.linalg.norm(end_pos - start_pos)
            
            # Simple time calculation (no acceleration phase considered)
            if max_vel > 0:
                return distance / max_vel
            else:
                return 1.0  # Default 1 second
                
        except Exception as e:
            print(f"Error calculating trajectory time: {e}")
            return 1.0
    
    def validate_trajectory(self, trajectory: Trajectory) -> bool:
        """Validate trajectory for safety and feasibility"""
        try:
            if trajectory.is_empty():
                return False
            
            # Check waypoints
            for waypoint in trajectory.waypoints:
                # Check position bounds (these should be configurable)
                if not self._is_position_valid(waypoint.position):
                    return False
                
                # Check orientation is valid quaternion
                if not self._is_quaternion_valid(waypoint.orientation):
                    return False
            
            # Check velocity constraints
            if not self._check_velocity_constraints(trajectory):
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating trajectory: {e}")
            return False
    
    def _is_position_valid(self, position: np.ndarray) -> bool:
        """Check if position is within valid bounds"""
        try:
            if len(position) != 3:
                return False
            
            # Simple bounds check (should be configurable)
            min_bounds = np.array([0.0, -1.0, 0.0])
            max_bounds = np.array([1.0, 1.0, 1.0])
            
            return np.all(position >= min_bounds) and np.all(position <= max_bounds)
            
        except Exception:
            return False
    
    def _is_quaternion_valid(self, orientation: np.ndarray) -> bool:
        """Check if orientation is a valid quaternion"""
        try:
            if len(orientation) != 4:
                return False
            
            # Check if normalized (approximately)
            norm = np.linalg.norm(orientation)
            return abs(norm - 1.0) < 0.1
            
        except Exception:
            return False
    
    def _check_velocity_constraints(self, trajectory: Trajectory) -> bool:
        """Check if trajectory violates velocity constraints"""
        try:
            waypoints = trajectory.waypoints
            if len(waypoints) < 2:
                return True
            
            for i in range(1, len(waypoints)):
                prev = waypoints[i-1]
                curr = waypoints[i]
                
                dt = curr.timestamp_offset - prev.timestamp_offset
                if dt <= 0:
                    continue
                
                # Check linear velocity
                dp = curr.position - prev.position
                velocity = np.linalg.norm(dp) / dt
                
                if velocity > self.max_velocity * 2:  # Allow some margin
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error checking velocity constraints: {e}")
            return True  # Default to valid if check fails