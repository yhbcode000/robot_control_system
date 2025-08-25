"""Direct control handler for teleoperation"""

import numpy as np
import time
from typing import Dict, Any, Optional, List
from models.control_commands import ControlCommand, JointCommand, CartesianCommand, GripperCommand, CommandType, ControlMode
from modules.input.models import CommandType as InputCommandType

class DirectControlHandler:
    """Handles direct teleoperation commands from keyboard/mouse input"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Control parameters
        self.linear_speed = config.get('linear_speed', 0.01)  # m/step
        self.angular_speed = config.get('angular_speed', 0.05)  # rad/step
        self.gripper_speed = config.get('gripper_speed', 0.1)  # units/step
        
        # Current state
        self.current_position = np.array([0.5, 0.0, 0.5])
        self.current_orientation = np.array([0, 0, 0, 1])
        self.current_gripper = 0.0
        
        # Joint limits (simplified)
        self.joint_limits = config.get('joint_limits', [
            (-3.14, 3.14),  # Joint 0
            (-3.14, 3.14),  # Joint 1
            (-3.14, 3.14),  # Joint 2
            (-3.14, 3.14),  # Joint 3
            (-3.14, 3.14),  # Joint 4
            (-3.14, 3.14),  # Joint 5
        ])
        
        # Current joint positions
        self.current_joints = np.zeros(6)
        
    def process_interpreted_inputs(self, interpreted_inputs: List[Any]) -> List[ControlCommand]:
        """Process interpreted inputs and generate control commands"""
        commands = []
        
        # Combine all movement inputs
        total_linear = np.zeros(3)
        total_angular = np.zeros(3)
        gripper_action = None
        
        for inp in interpreted_inputs:
            if hasattr(inp, 'movement_type'):
                if inp.movement_type == 'linear' and inp.direction_vector is not None:
                    total_linear += inp.direction_vector * inp.magnitude
                elif inp.movement_type == 'angular' and inp.rotation_axis is not None:
                    total_angular += inp.rotation_axis * inp.rotation_angle
            
            if hasattr(inp, 'is_gripper_command') and inp.is_gripper_command:
                gripper_action = inp.gripper_action
        
        # Generate joint command based on movement
        if np.any(total_linear != 0) or np.any(total_angular != 0):
            # Simple differential control for demonstration
            # In reality, you'd use inverse kinematics here
            
            # Map linear movements to joint velocities (simplified)
            joint_deltas = np.zeros(6)
            
            # X movement -> Joint 0 (base rotation)
            if total_linear[0] != 0:
                joint_deltas[0] = total_linear[0] * self.linear_speed
            
            # Y movement -> Joint 1 (shoulder)
            if total_linear[1] != 0:
                joint_deltas[1] = total_linear[1] * self.linear_speed
                
            # Z movement -> Joint 2 (elbow)
            if total_linear[2] != 0:
                joint_deltas[2] = -total_linear[2] * self.linear_speed
            
            # Angular movements
            if total_angular[0] != 0:  # Roll
                joint_deltas[3] = total_angular[0] * self.angular_speed
            if total_angular[1] != 0:  # Pitch
                joint_deltas[4] = total_angular[1] * self.angular_speed
            if total_angular[2] != 0:  # Yaw
                joint_deltas[5] = total_angular[2] * self.angular_speed
            
            # Update joint positions
            self.current_joints += joint_deltas
            
            # Apply joint limits
            for i, (min_val, max_val) in enumerate(self.joint_limits):
                self.current_joints[i] = np.clip(self.current_joints[i], min_val, max_val)
            
            # Create joint command
            joint_command = JointCommand(
                joint_names=['joint_' + str(i) for i in range(6)],
                positions=self.current_joints.copy(),
                velocities=np.zeros(6),
                efforts=np.zeros(6)
            )
            
            command = ControlCommand(
                command_type=CommandType.JOINT,
                joint_command=joint_command
            )
            command.timestamp = time.time()
            command.source_module = 'Act'
            commands.append(command)
        
        # Handle gripper commands
        if gripper_action:
            if gripper_action == 'open':
                self.current_gripper = min(1.0, self.current_gripper + self.gripper_speed)
            elif gripper_action == 'close':
                self.current_gripper = max(0.0, self.current_gripper - self.gripper_speed)
            elif gripper_action == 'toggle':
                self.current_gripper = 1.0 if self.current_gripper < 0.5 else 0.0
            
            gripper_command = GripperCommand(
                position=self.current_gripper,
                force=1.0
            )
            
            command = ControlCommand(
                command_type=CommandType.GRIPPER,
                gripper_command=gripper_command
            )
            command.timestamp = time.time()
            command.source_module = 'Act'
            commands.append(command)
        
        return commands
    
    def reset(self):
        """Reset to home position"""
        self.current_joints = np.zeros(6)
        self.current_position = np.array([0.5, 0.0, 0.5])
        self.current_orientation = np.array([0, 0, 0, 1])
        self.current_gripper = 0.0