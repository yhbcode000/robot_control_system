import numpy as np
import time
from typing import Dict, Any, Optional, List
from models.control_commands import (
    ControlCommand, JointCommand, CartesianCommand, GripperCommand,
    VelocityCommand, CommandType, ControlMode
)
from models.robot_state import RobotState
from models.planning_data import Waypoint


class CommandGenerator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Control parameters
        self.position_scale = config.get('position_scale', 1.0)
        self.velocity_scale = config.get('velocity_scale', 1.0)
        self.max_linear_velocity = config.get('max_linear_velocity', 0.1)  # m/s
        self.max_angular_velocity = config.get('max_angular_velocity', 0.5)  # rad/s
        
        # Safety limits
        self.max_position_change = config.get('max_position_change', 0.01)  # 1cm per command
        self.max_orientation_change = config.get('max_orientation_change', 0.1)  # radians
        
        # Joint limits (simplified - should be robot-specific)
        self.joint_limits = config.get('joint_limits', {
            'min': np.array([-3.14, -3.14, -3.14, -3.14, -3.14, -3.14]),
            'max': np.array([3.14, 3.14, 3.14, 3.14, 3.14, 3.14])
        })
        
        # Default joint names
        self.joint_names = config.get('joint_names', [
            'shoulder_pan_joint',
            'shoulder_lift_joint', 
            'elbow_joint',
            'wrist_1_joint',
            'wrist_2_joint',
            'wrist_3_joint'
        ])
    
    def generate_cartesian_command(self, target_position: np.ndarray, 
                                 target_orientation: np.ndarray,
                                 current_state: Optional[RobotState] = None,
                                 control_mode: ControlMode = ControlMode.POSITION) -> CartesianCommand:
        """Generate Cartesian space command"""
        try:
            # Apply safety limits
            safe_position = self._apply_position_limits(target_position, current_state)
            safe_orientation = self._apply_orientation_limits(target_orientation, current_state)
            
            # Create command
            command = CartesianCommand(
                position=safe_position,
                orientation=safe_orientation,
                control_mode=control_mode
            )
            command.source_module = 'Act'
            
            return command
            
        except Exception as e:
            print(f"Error generating Cartesian command: {e}")
            # Return safe default command
            return CartesianCommand(
                position=np.array([0.5, 0.0, 0.5]),
                orientation=np.array([0, 0, 0, 1]),
                control_mode=control_mode
            )
    
    def generate_velocity_command(self, linear_velocity: np.ndarray,
                                angular_velocity: np.ndarray,
                                current_state: Optional[RobotState] = None) -> VelocityCommand:
        """Generate velocity command"""
        try:
            # Apply velocity limits
            safe_linear_vel = self._limit_linear_velocity(linear_velocity)
            safe_angular_vel = self._limit_angular_velocity(angular_velocity)
            
            # Create command
            command = VelocityCommand(
                linear=safe_linear_vel,
                angular=safe_angular_vel
            )
            command.source_module = 'Act'
            
            return command
            
        except Exception as e:
            print(f"Error generating velocity command: {e}")
            # Return stop command
            return VelocityCommand(
                linear=np.zeros(3),
                angular=np.zeros(3)
            )
    
    def generate_joint_command(self, joint_positions: np.ndarray,
                             joint_velocities: Optional[np.ndarray] = None,
                             control_mode: ControlMode = ControlMode.POSITION,
                             current_state: Optional[RobotState] = None) -> JointCommand:
        """Generate joint space command"""
        try:
            # Apply joint limits
            safe_positions = self._apply_joint_limits(joint_positions)
            
            # Create command
            command = JointCommand(
                joint_names=self.joint_names[:len(safe_positions)],
                positions=safe_positions,
                velocities=joint_velocities,
                control_mode=control_mode
            )
            command.source_module = 'Act'
            
            return command
            
        except Exception as e:
            print(f"Error generating joint command: {e}")
            # Return safe default command
            return JointCommand(
                joint_names=self.joint_names,
                positions=np.zeros(len(self.joint_names)),
                control_mode=control_mode
            )
    
    def generate_gripper_command(self, target_position: float,
                               force: float = 1.0) -> GripperCommand:
        """Generate gripper command"""
        try:
            # Clamp gripper position
            safe_position = max(0.0, min(1.0, target_position))
            safe_force = max(0.1, min(1.0, force))
            
            command = GripperCommand(
                position=safe_position,
                force=safe_force
            )
            command.source_module = 'Act'
            
            return command
            
        except Exception as e:
            print(f"Error generating gripper command: {e}")
            return GripperCommand(position=0.0, force=0.5)
    
    def waypoint_to_cartesian_command(self, waypoint: Waypoint,
                                    current_state: Optional[RobotState] = None) -> CartesianCommand:
        """Convert waypoint to Cartesian command"""
        return self.generate_cartesian_command(
            target_position=waypoint.position,
            target_orientation=waypoint.orientation,
            current_state=current_state,
            control_mode=ControlMode.POSITION
        )
    
    def interpolate_trajectory_command(self, start_waypoint: Waypoint,
                                     end_waypoint: Waypoint,
                                     t: float) -> CartesianCommand:
        """Interpolate between two waypoints at parameter t (0 to 1)"""
        try:
            if not (0 <= t <= 1):
                t = max(0, min(1, t))
            
            # Linear interpolation for position
            position = start_waypoint.position + t * (end_waypoint.position - start_waypoint.position)
            
            # Simple linear interpolation for orientation (should use SLERP for quaternions)
            orientation = start_waypoint.orientation + t * (end_waypoint.orientation - start_waypoint.orientation)
            
            # Normalize quaternion if it's a 4D vector
            if len(orientation) == 4:
                norm = np.linalg.norm(orientation)
                if norm > 0:
                    orientation = orientation / norm
            
            return self.generate_cartesian_command(position, orientation)
            
        except Exception as e:
            print(f"Error interpolating trajectory command: {e}")
            return self.waypoint_to_cartesian_command(start_waypoint)
    
    def _apply_position_limits(self, target_position: np.ndarray, 
                              current_state: Optional[RobotState] = None) -> np.ndarray:
        """Apply position safety limits"""
        try:
            safe_position = target_position.copy()
            
            if current_state and current_state.end_effector_pose:
                current_pos = current_state.end_effector_pose.position
                
                # Limit maximum change per command
                position_change = safe_position - current_pos
                change_magnitude = np.linalg.norm(position_change)
                
                if change_magnitude > self.max_position_change:
                    # Scale down the change to stay within limits
                    position_change = position_change * (self.max_position_change / change_magnitude)
                    safe_position = current_pos + position_change
            
            # Apply workspace bounds (basic)
            workspace_min = np.array([0.1, -0.6, 0.1])
            workspace_max = np.array([0.8, 0.6, 0.8])
            
            safe_position = np.maximum(safe_position, workspace_min)
            safe_position = np.minimum(safe_position, workspace_max)
            
            return safe_position
            
        except Exception as e:
            print(f"Error applying position limits: {e}")
            return target_position
    
    def _apply_orientation_limits(self, target_orientation: np.ndarray,
                                current_state: Optional[RobotState] = None) -> np.ndarray:
        """Apply orientation safety limits"""
        try:
            safe_orientation = target_orientation.copy()
            
            # Normalize quaternion if it's 4D
            if len(safe_orientation) == 4:
                norm = np.linalg.norm(safe_orientation)
                if norm > 0:
                    safe_orientation = safe_orientation / norm
                else:
                    safe_orientation = np.array([0, 0, 0, 1])  # Default quaternion
            
            # TODO: Add orientation change limits similar to position
            
            return safe_orientation
            
        except Exception as e:
            print(f"Error applying orientation limits: {e}")
            return target_orientation
    
    def _apply_joint_limits(self, joint_positions: np.ndarray) -> np.ndarray:
        """Apply joint position limits"""
        try:
            safe_positions = joint_positions.copy()
            
            # Apply joint limits
            joint_min = self.joint_limits['min'][:len(safe_positions)]
            joint_max = self.joint_limits['max'][:len(safe_positions)]
            
            safe_positions = np.maximum(safe_positions, joint_min)
            safe_positions = np.minimum(safe_positions, joint_max)
            
            return safe_positions
            
        except Exception as e:
            print(f"Error applying joint limits: {e}")
            return joint_positions
    
    def _limit_linear_velocity(self, velocity: np.ndarray) -> np.ndarray:
        """Limit linear velocity magnitude"""
        try:
            velocity_magnitude = np.linalg.norm(velocity)
            
            if velocity_magnitude > self.max_linear_velocity:
                # Scale down velocity to stay within limits
                return velocity * (self.max_linear_velocity / velocity_magnitude)
            
            return velocity
            
        except Exception as e:
            print(f"Error limiting linear velocity: {e}")
            return np.zeros(3)
    
    def _limit_angular_velocity(self, velocity: np.ndarray) -> np.ndarray:
        """Limit angular velocity magnitude"""
        try:
            velocity_magnitude = np.linalg.norm(velocity)
            
            if velocity_magnitude > self.max_angular_velocity:
                # Scale down velocity to stay within limits
                return velocity * (self.max_angular_velocity / velocity_magnitude)
            
            return velocity
            
        except Exception as e:
            print(f"Error limiting angular velocity: {e}")
            return np.zeros(3)
    
    def create_stop_command(self, control_mode: ControlMode = ControlMode.VELOCITY) -> ControlCommand:
        """Create a stop command"""
        try:
            if control_mode == ControlMode.VELOCITY:
                velocity_cmd = VelocityCommand(
                    linear=np.zeros(3),
                    angular=np.zeros(3)
                )
                
                control_cmd = ControlCommand(
                    command_type=CommandType.CARTESIAN,
                    cartesian_command=CartesianCommand(
                        linear_velocity=np.zeros(3),
                        angular_velocity=np.zeros(3),
                        control_mode=ControlMode.VELOCITY
                    )
                )
            else:
                # Position hold command would maintain current position
                control_cmd = ControlCommand(
                    command_type=CommandType.CARTESIAN,
                    cartesian_command=CartesianCommand(
                        control_mode=ControlMode.POSITION
                    )
                )
            
            control_cmd.source_module = 'Act'
            return control_cmd
            
        except Exception as e:
            print(f"Error creating stop command: {e}")
            return ControlCommand()
    
    def validate_command(self, command: ControlCommand) -> bool:
        """Validate a control command for safety"""
        try:
            if command.command_type == CommandType.CARTESIAN:
                return self._validate_cartesian_command(command.cartesian_command)
            elif command.command_type == CommandType.JOINT:
                return self._validate_joint_command(command.joint_command)
            elif command.command_type == CommandType.GRIPPER:
                return self._validate_gripper_command(command.gripper_command)
            else:
                return True  # Default to valid
                
        except Exception as e:
            print(f"Error validating command: {e}")
            return False
    
    def _validate_cartesian_command(self, command: Optional[CartesianCommand]) -> bool:
        """Validate Cartesian command"""
        if not command:
            return False
        
        # Check position bounds if provided
        if command.position is not None:
            if len(command.position) != 3:
                return False
            
            # Check reasonable position values
            if np.any(np.abs(command.position) > 2.0):  # 2m is reasonable max
                return False
        
        # Check orientation if provided
        if command.orientation is not None:
            if len(command.orientation) == 4:
                # Check quaternion normalization
                norm = np.linalg.norm(command.orientation)
                if abs(norm - 1.0) > 0.1:  # Allow some tolerance
                    return False
        
        return True
    
    def _validate_joint_command(self, command: Optional[JointCommand]) -> bool:
        """Validate joint command"""
        if not command:
            return False
        
        if command.positions is not None:
            # Check joint limits
            if len(command.positions) > len(self.joint_limits['min']):
                return False
            
            joint_min = self.joint_limits['min'][:len(command.positions)]
            joint_max = self.joint_limits['max'][:len(command.positions)]
            
            if np.any(command.positions < joint_min) or np.any(command.positions > joint_max):
                return False
        
        return True
    
    def _validate_gripper_command(self, command: Optional[GripperCommand]) -> bool:
        """Validate gripper command"""
        if not command:
            return False
        
        # Check gripper position bounds
        if not (0.0 <= command.position <= 1.0):
            return False
        
        # Check force bounds
        if not (0.0 <= command.force <= 1.0):
            return False
        
        return True