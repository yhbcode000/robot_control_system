import numpy as np
from typing import Dict, Optional, Any
import time

from modules.input.models import ParsedCommand, CommandType
from .models import InterpretedInput


class InputParser:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Movement scaling factors
        self.linear_scale = config.get('linear_scale', 1.0)
        self.angular_scale = config.get('angular_scale', 1.0)
        self.gripper_scale = config.get('gripper_scale', 1.0)
        
        # Movement mappings
        self.direction_mappings = {
            'forward': np.array([1.0, 0.0, 0.0]),    # +X
            'backward': np.array([-1.0, 0.0, 0.0]),  # -X
            'left': np.array([0.0, 1.0, 0.0]),       # +Y
            'right': np.array([0.0, -1.0, 0.0]),     # -Y
            'up': np.array([0.0, 0.0, 1.0]),         # +Z
            'down': np.array([0.0, 0.0, -1.0])       # -Z
        }
        
        self.rotation_mappings = {
            'pitch_up': ('pitch', np.pi/36),      # 5 degrees
            'pitch_down': ('pitch', -np.pi/36),   # -5 degrees
            'yaw_left': ('yaw', np.pi/36),        # 5 degrees
            'yaw_right': ('yaw', -np.pi/36),      # -5 degrees
            'roll_left': ('roll', np.pi/36),      # 5 degrees
            'roll_right': ('roll', -np.pi/36)     # -5 degrees
        }
    
    def parse_command(self, parsed_command: ParsedCommand) -> Optional[InterpretedInput]:
        """Parse a ParsedCommand into an InterpretedInput"""
        try:
            if parsed_command.command_type == CommandType.MOVEMENT:
                return self._parse_movement_command(parsed_command)
            
            elif parsed_command.command_type == CommandType.ROTATION:
                return self._parse_rotation_command(parsed_command)
            
            elif parsed_command.command_type == CommandType.GRIPPER:
                return self._parse_gripper_command(parsed_command)
            
            elif parsed_command.command_type == CommandType.EMERGENCY_STOP:
                return self._parse_emergency_stop(parsed_command)
            
            elif parsed_command.command_type == CommandType.CAMERA:
                return self._parse_camera_command(parsed_command)
            
            elif parsed_command.command_type == CommandType.SPECIAL:
                return self._parse_special_command(parsed_command)
            
            else:
                # Unknown command type
                return None
                
        except Exception as e:
            print(f"Error parsing command: {e}")
            return None
    
    def _parse_movement_command(self, cmd: ParsedCommand) -> Optional[InterpretedInput]:
        """Parse movement command"""
        if cmd.direction not in self.direction_mappings:
            return None
        
        direction_vector = self.direction_mappings[cmd.direction] * cmd.magnitude * self.linear_scale
        
        return InterpretedInput(
            original_command=cmd,
            movement_type='linear',
            direction_vector=direction_vector,
            magnitude=cmd.magnitude * self.linear_scale,
            is_continuous=cmd.is_continuous,
            confidence=1.0,
            timestamp=time.time()
        )
    
    def _parse_rotation_command(self, cmd: ParsedCommand) -> Optional[InterpretedInput]:
        """Parse rotation command"""
        if cmd.direction not in self.rotation_mappings:
            return None
        
        axis, angle = self.rotation_mappings[cmd.direction]
        scaled_angle = angle * cmd.magnitude * self.angular_scale
        
        # Convert axis name to vector
        axis_vectors = {
            'pitch': np.array([0, 1, 0]),  # Rotation around Y-axis
            'yaw': np.array([0, 0, 1]),    # Rotation around Z-axis  
            'roll': np.array([1, 0, 0])    # Rotation around X-axis
        }
        
        return InterpretedInput(
            original_command=cmd,
            movement_type='angular',
            rotation_axis=axis_vectors.get(axis, np.array([0, 0, 1])),
            rotation_angle=scaled_angle,
            magnitude=abs(scaled_angle),
            is_continuous=cmd.is_continuous,
            confidence=1.0,
            timestamp=time.time()
        )
    
    def _parse_gripper_command(self, cmd: ParsedCommand) -> Optional[InterpretedInput]:
        """Parse gripper command"""
        gripper_action = cmd.direction if cmd.direction else 'toggle'
        
        # Determine target based on action
        if gripper_action == 'toggle':
            gripper_target = None  # Will be determined by the planner
        elif gripper_action == 'open':
            gripper_target = 1.0
        elif gripper_action == 'close':
            gripper_target = 0.0
        else:
            gripper_target = None
        
        return InterpretedInput(
            original_command=cmd,
            movement_type='gripper',
            gripper_action=gripper_action,
            gripper_target=gripper_target,
            magnitude=cmd.magnitude * self.gripper_scale,
            is_continuous=cmd.is_continuous,
            confidence=1.0,
            timestamp=time.time()
        )
    
    def _parse_emergency_stop(self, cmd: ParsedCommand) -> InterpretedInput:
        """Parse emergency stop command"""
        return InterpretedInput(
            original_command=cmd,
            movement_type='emergency',
            is_emergency_stop=True,
            magnitude=1.0,
            is_continuous=False,
            confidence=1.0,
            priority='critical',
            timestamp=time.time()
        )
    
    def _parse_camera_command(self, cmd: ParsedCommand) -> Optional[InterpretedInput]:
        """Parse camera command"""
        # Camera commands are not directly robot movements,
        # but could affect the planning context
        camera_action = cmd.direction if cmd.direction else 'unknown'
        
        return InterpretedInput(
            original_command=cmd,
            movement_type='camera',
            camera_action=camera_action,
            magnitude=cmd.magnitude,
            is_continuous=cmd.is_continuous,
            confidence=0.8,  # Lower confidence as it's not direct robot control
            timestamp=time.time()
        )
    
    def _parse_special_command(self, cmd: ParsedCommand) -> Optional[InterpretedInput]:
        """Parse special command"""
        special_action = cmd.direction if cmd.direction else 'unknown'
        
        return InterpretedInput(
            original_command=cmd,
            movement_type='special',
            special_command=special_action,
            is_special_command=True,
            magnitude=cmd.magnitude,
            is_continuous=cmd.is_continuous,
            confidence=1.0,
            timestamp=time.time()
        )
    
    def combine_inputs(self, inputs: list) -> Optional[InterpretedInput]:
        """Combine multiple inputs into a single interpreted input"""
        if not inputs:
            return None
        
        if len(inputs) == 1:
            return inputs[0]
        
        try:
            # Group inputs by movement type
            linear_inputs = [inp for inp in inputs if inp.movement_type == 'linear']
            angular_inputs = [inp for inp in inputs if inp.movement_type == 'angular']
            
            # Combine linear movements
            combined_linear = None
            if linear_inputs:
                total_direction = np.zeros(3)
                total_magnitude = 0.0
                
                for inp in linear_inputs:
                    if inp.direction_vector is not None:
                        total_direction += inp.direction_vector
                        total_magnitude += inp.magnitude
                
                # Normalize direction
                direction_magnitude = np.linalg.norm(total_direction)
                if direction_magnitude > 0:
                    total_direction = total_direction / direction_magnitude
                
                combined_linear = InterpretedInput(
                    original_command=linear_inputs[0].original_command,
                    movement_type='linear',
                    direction_vector=total_direction,
                    magnitude=min(total_magnitude, 1.0),  # Cap at 1.0
                    is_continuous=any(inp.is_continuous for inp in linear_inputs),
                    confidence=min(inp.confidence for inp in linear_inputs),
                    timestamp=time.time()
                )
            
            # For now, return the combined linear movement
            # More sophisticated combination logic can be added later
            return combined_linear
            
        except Exception as e:
            print(f"Error combining inputs: {e}")
            return inputs[0]  # Return first input as fallback
    
    def validate_input(self, interpreted: InterpretedInput) -> bool:
        """Validate an interpreted input"""
        try:
            # Basic validation
            if interpreted.magnitude < 0:
                return False
            
            if interpreted.magnitude > 10.0:  # Reasonable upper bound
                return False
            
            if interpreted.confidence < 0 or interpreted.confidence > 1.0:
                return False
            
            # Movement-specific validation
            if interpreted.movement_type == 'linear':
                if interpreted.direction_vector is not None:
                    # Check if direction vector is reasonable
                    magnitude = np.linalg.norm(interpreted.direction_vector)
                    if magnitude > 2.0:  # Reasonable upper bound
                        return False
            
            elif interpreted.movement_type == 'angular':
                if interpreted.rotation_angle is not None:
                    # Check if rotation angle is reasonable
                    if abs(interpreted.rotation_angle) > np.pi:  # Max 180 degrees
                        return False
            
            elif interpreted.movement_type == 'gripper':
                if interpreted.gripper_target is not None:
                    if interpreted.gripper_target < 0 or interpreted.gripper_target > 1.0:
                        return False
            
            return True
            
        except Exception as e:
            print(f"Error validating input: {e}")
            return False