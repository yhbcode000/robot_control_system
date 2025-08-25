from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import time
from enum import Enum

from models.robot_state import RobotState, JointState, EndEffectorPose
from models.sensor_data import SensorBundle
from .models import AdapterStatus, ConnectionState


class AdapterType(Enum):
    SIMULATION = "simulation"
    MUJOCO = "mujoco"
    REAL_ROBOT = "real_robot"
    ROS = "ros"


class BaseAdapter(ABC):
    """Base class for all robot adapters"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.adapter_type = AdapterType.SIMULATION
        self.connection_state = ConnectionState.DISCONNECTED
        self.last_heartbeat = 0.0
        self.error_count = 0
        self.command_count = 0
        
        # Connection parameters
        self.timeout = config.get('timeout', 5.0)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.heartbeat_interval = config.get('heartbeat_interval', 1.0)
        
        # Performance tracking
        self.start_time = time.time()
        self.last_command_time = 0.0
        self.command_latencies = []
        
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the robot system"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the robot system"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to robot system"""
        pass
    
    @abstractmethod
    def read_sensors(self) -> Optional[SensorBundle]:
        """Read sensor data from robot"""
        pass
    
    @abstractmethod
    def get_robot_state(self) -> Optional[RobotState]:
        """Get current robot state"""
        pass
    
    @abstractmethod
    def send_joint_command(self, joint_names: List[str], positions: List[float], 
                          velocities: Optional[List[float]] = None) -> bool:
        """Send joint position command"""
        pass
    
    @abstractmethod
    def send_cartesian_command(self, position: List[float], orientation: List[float],
                              linear_velocity: Optional[List[float]] = None,
                              angular_velocity: Optional[List[float]] = None) -> bool:
        """Send Cartesian command"""
        pass
    
    @abstractmethod
    def send_gripper_command(self, position: float, force: float = 1.0) -> bool:
        """Send gripper command"""
        pass
    
    @abstractmethod
    def send_emergency_stop(self) -> bool:
        """Send emergency stop command"""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get adapter status"""
        uptime = time.time() - self.start_time
        avg_latency = np.mean(self.command_latencies) if self.command_latencies else 0
        
        return {
            'adapter_type': self.adapter_type.value,
            'connected': self.is_connected(),
            'connection_state': self.connection_state.value,
            'uptime': uptime,
            'error_count': self.error_count,
            'command_count': self.command_count,
            'last_heartbeat': self.last_heartbeat,
            'average_latency': avg_latency,
            'last_command_time': self.last_command_time
        }
    
    def send_heartbeat(self) -> bool:
        """Send heartbeat to maintain connection"""
        try:
            self.last_heartbeat = time.time()
            return True
        except Exception as e:
            print(f"Heartbeat failed: {e}")
            return False
    
    def record_command(self, success: bool, latency: float = 0.0):
        """Record command execution"""
        self.command_count += 1
        self.last_command_time = time.time()
        
        if latency > 0:
            self.command_latencies.append(latency)
            # Keep only recent latencies
            if len(self.command_latencies) > 100:
                self.command_latencies.pop(0)
        
        if not success:
            self.error_count += 1
    
    def reset_error_count(self):
        """Reset error counter"""
        self.error_count = 0
    
    def validate_joint_command(self, joint_names: List[str], positions: List[float]) -> bool:
        """Validate joint command parameters"""
        if len(joint_names) != len(positions):
            return False
        
        # Check for reasonable joint limits (simplified)
        for pos in positions:
            if abs(pos) > 6.28:  # ±2π radians
                return False
        
        return True
    
    def validate_cartesian_command(self, position: List[float], orientation: List[float]) -> bool:
        """Validate Cartesian command parameters"""
        if len(position) != 3 or len(orientation) != 4:
            return False
        
        # Check position bounds (simplified)
        for pos in position:
            if abs(pos) > 2.0:  # ±2 meters
                return False
        
        # Check quaternion normalization
        quat_norm = np.linalg.norm(orientation)
        if abs(quat_norm - 1.0) > 0.1:
            return False
        
        return True
    
    def validate_gripper_command(self, position: float, force: float) -> bool:
        """Validate gripper command parameters"""
        return 0.0 <= position <= 1.0 and 0.0 <= force <= 1.0
    
    def get_joint_limits(self) -> Dict[str, List[float]]:
        """Get joint limits for the robot"""
        # Default limits - should be overridden by specific adapters
        return {
            'min': [-3.14, -3.14, -3.14, -3.14, -3.14, -3.14],
            'max': [3.14, 3.14, 3.14, 3.14, 3.14, 3.14]
        }
    
    def get_workspace_bounds(self) -> Dict[str, List[float]]:
        """Get workspace bounds"""
        # Default workspace - should be overridden by specific adapters
        return {
            'min': [0.1, -0.5, 0.1],
            'max': [0.8, 0.5, 0.8]
        }
    
    def emergency_stop_active(self) -> bool:
        """Check if emergency stop is currently active"""
        # Default implementation - should be overridden
        return False
    
    def clear_emergency_stop(self) -> bool:
        """Clear emergency stop state"""
        # Default implementation - should be overridden
        return True
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Get adapter capabilities"""
        return {
            'joint_control': True,
            'cartesian_control': True,
            'gripper_control': True,
            'force_control': False,
            'impedance_control': False,
            'trajectory_following': True,
            'real_time_control': False
        }
    
    def configure(self, config: Dict[str, Any]) -> bool:
        """Configure adapter with new parameters"""
        try:
            self.config.update(config)
            return True
        except Exception as e:
            print(f"Configuration failed: {e}")
            return False
    
    def health_check(self) -> bool:
        """Perform health check"""
        try:
            if not self.is_connected():
                return False
            
            # Check if heartbeat is recent
            if time.time() - self.last_heartbeat > self.heartbeat_interval * 3:
                return False
            
            # Check error rate
            if self.command_count > 0:
                error_rate = self.error_count / self.command_count
                if error_rate > 0.1:  # More than 10% errors
                    return False
            
            return True
            
        except Exception:
            return False
    
    def get_diagnostics(self) -> Dict[str, Any]:
        """Get detailed diagnostics information"""
        status = self.get_status()
        
        diagnostics = {
            'basic_status': status,
            'health_check': self.health_check(),
            'capabilities': self.get_capabilities(),
            'joint_limits': self.get_joint_limits(),
            'workspace_bounds': self.get_workspace_bounds(),
            'emergency_stop_active': self.emergency_stop_active()
        }
        
        # Add performance metrics
        if self.command_latencies:
            diagnostics['performance'] = {
                'avg_latency': np.mean(self.command_latencies),
                'max_latency': np.max(self.command_latencies),
                'min_latency': np.min(self.command_latencies),
                'latency_std': np.std(self.command_latencies)
            }
        
        return diagnostics