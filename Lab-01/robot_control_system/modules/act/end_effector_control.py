"""End-effector position control using inverse kinematics"""

import numpy as np
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from modules.kinematics.inverse_kinematics import InverseKinematics
from models.control_commands import ControlCommand, JointCommand, CommandType
from models.robot_state import RobotState

@dataclass
class EndEffectorTarget:
    """End-effector target position and orientation"""
    position: np.ndarray
    orientation: Optional[np.ndarray] = None
    timestamp: float = 0.0
    priority: int = 0  # Higher numbers = higher priority
    source: str = "unknown"

class EndEffectorController:
    """Control robot end-effector position using inverse kinematics"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Initialize inverse kinematics solver
        self.ik_solver = InverseKinematics(config.get('kinematics', {}))
        
        # Control parameters
        self.control_frequency = config.get('control_frequency', 100)  # Hz
        self.position_tolerance = config.get('position_tolerance', 0.005)  # 5mm
        self.max_velocity = config.get('max_joint_velocity', 1.0)  # rad/s
        self.use_jacobian_ik = config.get('use_jacobian_ik', True)  # Faster for real-time
        
        # Current state
        self.current_target: Optional[EndEffectorTarget] = None
        self.last_joint_solution: Optional[np.ndarray] = None
        self.current_robot_state: Optional[RobotState] = None
        
        # Statistics
        self.ik_success_count = 0
        self.ik_failure_count = 0
        self.average_solve_time = 0.0
        self.last_solve_times = []
        self.max_solve_history = 50
        
        # Safety
        self.enable_safety_checks = config.get('enable_safety_checks', True)
        self.workspace_margin = config.get('workspace_margin', 0.05)  # 5cm margin
        
    def set_target_position(self, position: np.ndarray, 
                          orientation: Optional[np.ndarray] = None,
                          source: str = "external") -> bool:
        """
        Set target end-effector position
        
        Args:
            position: Target 3D position [x, y, z]
            orientation: Target quaternion [x, y, z, w] (optional)
            source: Source of the command
            
        Returns:
            success: Whether target was accepted
        """
        try:
            # Validate position
            if not self._validate_target_position(position):
                return False
            
            # Create target
            target = EndEffectorTarget(
                position=position.copy(),
                orientation=orientation.copy() if orientation is not None else None,
                timestamp=time.time(),
                source=source
            )
            
            self.current_target = target
            return True
            
        except Exception as e:
            print(f"Error setting end-effector target: {e}")
            return False
    
    def update_robot_state(self, robot_state: RobotState):
        """Update current robot state"""
        self.current_robot_state = robot_state
        
        # Update last joint solution from current state
        if robot_state.joint_state and robot_state.joint_state.positions is not None:
            self.last_joint_solution = robot_state.joint_state.positions.copy()
    
    def generate_control_command(self) -> Optional[ControlCommand]:
        """
        Generate control command to move towards target
        
        Returns:
            control_command: Joint command to execute, or None if no valid solution
        """
        if not self.current_target or not self.current_robot_state:
            return None
        
        try:
            start_time = time.time()
            
            # Get current joint positions
            if (not self.current_robot_state.joint_state or 
                self.current_robot_state.joint_state.positions is None):
                return None
            
            current_joints = self.current_robot_state.joint_state.positions
            target_position = self.current_target.position
            target_orientation = self.current_target.orientation
            
            # Check if we're already at target
            current_ee_pos, _ = self.ik_solver.forward_kinematics(current_joints)
            position_error = np.linalg.norm(current_ee_pos - target_position)
            
            if position_error < self.position_tolerance:
                # Already at target
                return None
            
            # Solve inverse kinematics
            joint_solution = None
            ik_success = False
            
            if self.use_jacobian_ik:
                # Use faster Jacobian-based IK for real-time control
                joint_solution, ik_success = self.ik_solver.jacobian_ik(
                    target_position,
                    current_joints,
                    max_iterations=20,  # Keep it fast
                    step_size=0.2
                )
            
            if not ik_success or joint_solution is None:
                # Fallback to optimization-based IK
                joint_solution, ik_success = self.ik_solver.inverse_kinematics(
                    target_position,
                    target_orientation,
                    initial_guess=current_joints
                )
            
            # Record statistics
            solve_time = time.time() - start_time
            self._update_solve_statistics(solve_time, ik_success)
            
            if not ik_success or joint_solution is None:
                self.ik_failure_count += 1
                return None
            
            # Safety checks
            if self.enable_safety_checks:
                if not self._validate_joint_solution(joint_solution, current_joints):
                    return None
            
            # Create joint command
            joint_names = [
                'shoulder_pan_joint',
                'shoulder_lift_joint',
                'elbow_joint',
                'wrist_1_joint',
                'wrist_2_joint',
                'wrist_3_joint'
            ]
            
            joint_command = JointCommand(
                joint_names=joint_names,
                positions=joint_solution.tolist(),
                velocities=[0.0] * 6,  # Position control
                efforts=[0.0] * 6
            )
            
            # Create control command
            command = ControlCommand(
                command_type=CommandType.JOINT,
                joint_command=joint_command
            )
            command.timestamp = time.time()
            command.source_module = 'EndEffectorController'
            
            # Store successful solution
            self.last_joint_solution = joint_solution
            self.ik_success_count += 1
            
            return command
            
        except Exception as e:
            print(f"Error generating end-effector control command: {e}")
            return None
    
    def _validate_target_position(self, position: np.ndarray) -> bool:
        """Validate target position is reachable"""
        try:
            # Check workspace limits with margin
            center = self.ik_solver.get_workspace_center()
            
            x_min, x_max = self.ik_solver.workspace_limits['x']
            y_min, y_max = self.ik_solver.workspace_limits['y']
            z_min, z_max = self.ik_solver.workspace_limits['z']
            
            # Apply margins
            margin = self.workspace_margin
            x_min += margin
            x_max -= margin
            y_min += margin
            y_max -= margin
            z_min += margin
            z_max -= margin
            
            x, y, z = position
            
            if not (x_min <= x <= x_max and 
                    y_min <= y <= y_max and 
                    z_min <= z <= z_max):
                print(f"Target position outside workspace: [{x:.3f}, {y:.3f}, {z:.3f}]")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating target position: {e}")
            return False
    
    def _validate_joint_solution(self, joint_solution: np.ndarray, 
                                current_joints: np.ndarray) -> bool:
        """Validate joint solution is safe"""
        try:
            # Check joint limits
            for i, (q, (q_min, q_max)) in enumerate(zip(joint_solution, self.ik_solver.joint_limits)):
                if q < q_min or q > q_max:
                    print(f"Joint {i} solution outside limits: {q:.3f} not in [{q_min:.3f}, {q_max:.3f}]")
                    return False
            
            # Check maximum joint velocity
            dt = 1.0 / self.control_frequency
            max_joint_change = self.max_velocity * dt
            
            joint_deltas = np.abs(joint_solution - current_joints)
            if np.any(joint_deltas > max_joint_change):
                max_delta = np.max(joint_deltas)
                print(f"Joint change too large: {max_delta:.3f} > {max_joint_change:.3f}")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating joint solution: {e}")
            return False
    
    def _update_solve_statistics(self, solve_time: float, success: bool):
        """Update solver performance statistics"""
        self.last_solve_times.append(solve_time)
        
        if len(self.last_solve_times) > self.max_solve_history:
            self.last_solve_times.pop(0)
        
        # Calculate average
        if self.last_solve_times:
            self.average_solve_time = sum(self.last_solve_times) / len(self.last_solve_times)
    
    def get_current_end_effector_position(self) -> Optional[np.ndarray]:
        """Get current end-effector position"""
        if not self.current_robot_state or not self.current_robot_state.joint_state:
            return None
        
        try:
            current_joints = self.current_robot_state.joint_state.positions
            position, _ = self.ik_solver.forward_kinematics(current_joints)
            return position
        except Exception as e:
            print(f"Error getting current end-effector position: {e}")
            return None
    
    def get_target_error(self) -> Optional[float]:
        """Get current position error to target"""
        if not self.current_target:
            return None
        
        current_pos = self.get_current_end_effector_position()
        if current_pos is None:
            return None
        
        return np.linalg.norm(current_pos - self.current_target.position)
    
    def get_status(self) -> Dict[str, Any]:
        """Get controller status"""
        current_pos = self.get_current_end_effector_position()
        target_error = self.get_target_error()
        
        total_attempts = self.ik_success_count + self.ik_failure_count
        success_rate = self.ik_success_count / total_attempts if total_attempts > 0 else 0
        
        return {
            'has_target': self.current_target is not None,
            'target_position': self.current_target.position.tolist() if self.current_target else None,
            'current_position': current_pos.tolist() if current_pos is not None else None,
            'position_error': target_error,
            'at_target': target_error is not None and target_error < self.position_tolerance,
            'ik_success_count': self.ik_success_count,
            'ik_failure_count': self.ik_failure_count,
            'ik_success_rate': success_rate,
            'average_solve_time': self.average_solve_time,
            'last_solve_time': self.last_solve_times[-1] if self.last_solve_times else 0
        }
    
    def reset_target(self):
        """Clear current target"""
        self.current_target = None
    
    def is_at_target(self) -> bool:
        """Check if robot is at target position"""
        error = self.get_target_error()
        return error is not None and error < self.position_tolerance