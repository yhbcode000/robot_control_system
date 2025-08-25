import json
import time
from typing import Dict, Any, Optional
import numpy as np

from models.control_commands import ControlCommand, CommandType


class SignalFormatter:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.default_format = config.get('default_format', 'json')
        self.precision = config.get('precision', 6)  # Decimal places for floats
        
    def format_command(self, command: ControlCommand, output_format: str = None) -> Optional[Dict[str, Any]]:
        """Format a control command for output"""
        try:
            if not command:
                return None
            
            format_type = output_format or self.default_format
            
            # Create base signal structure
            signal = {
                'timestamp': time.time(),
                'type': command.command_type.value,
                'source': getattr(command, 'source_module', 'unknown'),
                'priority': command.priority.value if hasattr(command, 'priority') else 'normal'
            }
            
            # Add command-specific data
            if command.command_type == CommandType.JOINT:
                signal['data'] = self._format_joint_command(command.joint_command)
            elif command.command_type == CommandType.CARTESIAN:
                signal['data'] = self._format_cartesian_command(command.cartesian_command)
            elif command.command_type == CommandType.GRIPPER:
                signal['data'] = self._format_gripper_command(command.gripper_command)
            elif command.command_type == CommandType.EMERGENCY_STOP:
                signal['data'] = self._format_emergency_command(command.emergency_stop)
            else:
                signal['data'] = {}
            
            # Apply format-specific processing
            if format_type == 'json':
                return self._format_as_json(signal)
            elif format_type == 'binary':
                return self._format_as_binary(signal)
            elif format_type == 'ros':
                return self._format_as_ros(signal)
            else:
                return signal  # Return raw format
                
        except Exception as e:
            print(f"Error formatting command: {e}")
            return None
    
    def _format_joint_command(self, joint_command) -> Dict[str, Any]:
        """Format joint command data"""
        if not joint_command:
            return {}
        
        data = {
            'joint_names': joint_command.joint_names,
            'control_mode': joint_command.control_mode.value
        }
        
        if joint_command.positions is not None:
            data['positions'] = self._format_array(joint_command.positions)
        
        if joint_command.velocities is not None:
            data['velocities'] = self._format_array(joint_command.velocities)
        
        if joint_command.efforts is not None:
            data['efforts'] = self._format_array(joint_command.efforts)
        
        return data
    
    def _format_cartesian_command(self, cartesian_command) -> Dict[str, Any]:
        """Format Cartesian command data"""
        if not cartesian_command:
            return {}
        
        data = {
            'control_mode': cartesian_command.control_mode.value
        }
        
        if cartesian_command.position is not None:
            data['position'] = self._format_array(cartesian_command.position)
        
        if cartesian_command.orientation is not None:
            data['orientation'] = self._format_array(cartesian_command.orientation)
        
        if cartesian_command.linear_velocity is not None:
            data['linear_velocity'] = self._format_array(cartesian_command.linear_velocity)
        
        if cartesian_command.angular_velocity is not None:
            data['angular_velocity'] = self._format_array(cartesian_command.angular_velocity)
        
        return data
    
    def _format_gripper_command(self, gripper_command) -> Dict[str, Any]:
        """Format gripper command data"""
        if not gripper_command:
            return {}
        
        return {
            'position': round(gripper_command.position, self.precision),
            'force': round(gripper_command.force, self.precision)
        }
    
    def _format_emergency_command(self, emergency_command) -> Dict[str, Any]:
        """Format emergency stop command data"""
        if not emergency_command:
            return {'reason': 'unknown'}
        
        return {
            'reason': emergency_command.reason,
            'active': True
        }
    
    def _format_array(self, array) -> list:
        """Format numpy array or list to rounded list"""
        try:
            if isinstance(array, np.ndarray):
                return [round(float(x), self.precision) for x in array]
            elif isinstance(array, (list, tuple)):
                return [round(float(x), self.precision) for x in array]
            else:
                return [float(array)] if array is not None else []
        except Exception as e:
            print(f"Error formatting array: {e}")
            return []
    
    def _format_as_json(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Format signal as JSON-compatible structure"""
        try:
            # Ensure all values are JSON serializable
            def make_serializable(obj):
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, dict):
                    return {k: make_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [make_serializable(item) for item in obj]
                else:
                    return obj
            
            return make_serializable(signal)
            
        except Exception as e:
            print(f"Error formatting as JSON: {e}")
            return signal
    
    def _format_as_binary(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Format signal as binary-compatible structure"""
        # For binary format, we might pack arrays more efficiently
        # For now, just return the regular format with a binary flag
        signal['format'] = 'binary'
        return signal
    
    def _format_as_ros(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Format signal as ROS-compatible message"""
        try:
            # Convert to ROS message format
            ros_signal = {
                'header': {
                    'stamp': {
                        'sec': int(signal['timestamp']),
                        'nsec': int((signal['timestamp'] % 1) * 1e9)
                    },
                    'frame_id': 'base_link'  # Default frame
                },
                'command_type': signal['type'],
                'source': signal['source'],
                'priority': signal['priority']
            }
            
            # Add ROS-specific data formatting
            data = signal.get('data', {})
            
            if signal['type'] == 'joint':
                ros_signal['joint_state'] = {
                    'name': data.get('joint_names', []),
                    'position': data.get('positions', []),
                    'velocity': data.get('velocities', []),
                    'effort': data.get('efforts', [])
                }
            
            elif signal['type'] == 'cartesian':
                ros_signal['pose'] = {
                    'position': {
                        'x': data.get('position', [0, 0, 0])[0] if data.get('position') else 0,
                        'y': data.get('position', [0, 0, 0])[1] if data.get('position') else 0,
                        'z': data.get('position', [0, 0, 0])[2] if data.get('position') else 0
                    },
                    'orientation': {
                        'x': data.get('orientation', [0, 0, 0, 1])[0] if data.get('orientation') else 0,
                        'y': data.get('orientation', [0, 0, 0, 1])[1] if data.get('orientation') else 0,
                        'z': data.get('orientation', [0, 0, 0, 1])[2] if data.get('orientation') else 0,
                        'w': data.get('orientation', [0, 0, 0, 1])[3] if data.get('orientation') else 1
                    }
                }
                
                if 'linear_velocity' in data or 'angular_velocity' in data:
                    ros_signal['twist'] = {
                        'linear': {
                            'x': data.get('linear_velocity', [0, 0, 0])[0] if data.get('linear_velocity') else 0,
                            'y': data.get('linear_velocity', [0, 0, 0])[1] if data.get('linear_velocity') else 0,
                            'z': data.get('linear_velocity', [0, 0, 0])[2] if data.get('linear_velocity') else 0
                        },
                        'angular': {
                            'x': data.get('angular_velocity', [0, 0, 0])[0] if data.get('angular_velocity') else 0,
                            'y': data.get('angular_velocity', [0, 0, 0])[1] if data.get('angular_velocity') else 0,
                            'z': data.get('angular_velocity', [0, 0, 0])[2] if data.get('angular_velocity') else 0
                        }
                    }
            
            elif signal['type'] == 'gripper':
                ros_signal['gripper_command'] = {
                    'position': data.get('position', 0.0),
                    'max_effort': data.get('force', 1.0)
                }
            
            ros_signal['format'] = 'ros'
            return ros_signal
            
        except Exception as e:
            print(f"Error formatting as ROS: {e}")
            signal['format'] = 'ros'
            return signal
    
    def format_status_message(self, module_name: str, status: Dict[str, Any]) -> Dict[str, Any]:
        """Format a status message"""
        try:
            return {
                'timestamp': time.time(),
                'type': 'status',
                'source': module_name,
                'data': status
            }
        except Exception as e:
            print(f"Error formatting status message: {e}")
            return {}
    
    def format_error_message(self, module_name: str, error: str, error_code: int = 0) -> Dict[str, Any]:
        """Format an error message"""
        try:
            return {
                'timestamp': time.time(),
                'type': 'error',
                'source': module_name,
                'data': {
                    'error_message': error,
                    'error_code': error_code
                }
            }
        except Exception as e:
            print(f"Error formatting error message: {e}")
            return {}
    
    def validate_signal(self, signal: Dict[str, Any]) -> bool:
        """Validate a formatted signal"""
        try:
            # Check required fields
            required_fields = ['timestamp', 'type', 'source', 'data']
            
            for field in required_fields:
                if field not in signal:
                    return False
            
            # Check timestamp is reasonable
            current_time = time.time()
            signal_time = signal['timestamp']
            
            if abs(signal_time - current_time) > 10.0:  # More than 10 seconds difference
                return False
            
            # Check type is valid
            valid_types = ['joint', 'cartesian', 'gripper', 'emergency_stop', 'status', 'error']
            if signal['type'] not in valid_types:
                return False
            
            # Type-specific validation
            data = signal['data']
            
            if signal['type'] == 'joint':
                if 'joint_names' not in data or 'positions' not in data:
                    return False
                if len(data['joint_names']) != len(data['positions']):
                    return False
            
            elif signal['type'] == 'cartesian':
                if 'position' in data and len(data['position']) != 3:
                    return False
                if 'orientation' in data and len(data['orientation']) != 4:
                    return False
            
            elif signal['type'] == 'gripper':
                if 'position' not in data:
                    return False
                if not (0.0 <= data['position'] <= 1.0):
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error validating signal: {e}")
            return False
    
    def serialize_signal(self, signal: Dict[str, Any], format_type: str = 'json') -> str:
        """Serialize signal to string"""
        try:
            if format_type == 'json':
                return json.dumps(signal, indent=2)
            else:
                return str(signal)
                
        except Exception as e:
            print(f"Error serializing signal: {e}")
            return "{}"
    
    def deserialize_signal(self, signal_string: str, format_type: str = 'json') -> Optional[Dict[str, Any]]:
        """Deserialize signal from string"""
        try:
            if format_type == 'json':
                return json.loads(signal_string)
            else:
                # For other formats, would need specific parsing logic
                return None
                
        except Exception as e:
            print(f"Error deserializing signal: {e}")
            return None