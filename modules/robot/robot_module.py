"""Robot Module - Central robot state and control management"""

import time
import threading
import numpy as np
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from core.base.module import BaseModule
from core.memory.memory_store import GlobalMemory
from models.robot_state import RobotState, JointState, EndEffectorPose
from models.control_commands import ControlCommand, CommandType
from models.sensor_data import SensorBundle

@dataclass
class RobotConfig:
    """Robot configuration parameters"""
    joint_names: List[str]
    joint_limits: List[tuple]
    max_velocities: List[float]
    max_accelerations: List[float]
    workspace_limits: Dict[str, tuple]
    home_position: List[float]
    
class RobotModule(BaseModule):
    """Central robot module that manages robot state and control"""
    
    def __init__(self, config: Dict[str, Any], memory: Optional[GlobalMemory] = None):
        super().__init__('Robot', config, memory)
        
        # Robot configuration
        self.robot_config = self._load_robot_config(config)
        
        # State tracking
        self.current_state = RobotState()
        self.target_state = RobotState()
        self.state_history = []
        self.max_history = config.get('history_size', 100)
        
        # Control parameters
        self.control_mode = config.get('control_mode', 'position')
        self.safety_checks_enabled = config.get('safety_checks', True)
        self.collision_detection_enabled = config.get('collision_detection', True)
        
        # Performance metrics
        self.total_commands_executed = 0
        self.total_errors = 0
        self.last_command_time = 0
        self.command_frequency = 0
        
        # Safety state
        self.is_safe = True
        self.safety_violations = []
        self.emergency_stop_active = False
        
        # Update rate
        self.update_rate = config.get('update_rate', 100)  # Hz
        
        # Thread safety
        self.state_lock = threading.Lock()
        
    def _load_robot_config(self, config: Dict[str, Any]) -> RobotConfig:
        """Load robot configuration"""
        return RobotConfig(
            joint_names=config.get('joint_names', [
                'shoulder_pan_joint',
                'shoulder_lift_joint',
                'elbow_joint',
                'wrist_1_joint',
                'wrist_2_joint',
                'wrist_3_joint'
            ]),
            joint_limits=config.get('joint_limits', [
                (-3.14, 3.14),
                (-3.14, 3.14),
                (-3.14, 3.14),
                (-3.14, 3.14),
                (-3.14, 3.14),
                (-3.14, 3.14)
            ]),
            max_velocities=config.get('max_velocities', [1.0] * 6),
            max_accelerations=config.get('max_accelerations', [2.0] * 6),
            workspace_limits=config.get('workspace_limits', {
                'x': (-1.0, 1.0),
                'y': (-1.0, 1.0),
                'z': (0.0, 2.0)
            }),
            home_position=config.get('home_position', [0.0] * 6)
        )
    
    def _initialize(self) -> bool:
        """Initialize robot module"""
        try:
            self.logger.info("Initializing Robot module...")
            
            # Initialize robot state
            self._initialize_robot_state()
            
            # Register with memory
            self.memory.update('robot', 'current_state', self.current_state)
            self.memory.update('robot', 'config', self.robot_config)
            
            # Subscribe to relevant namespaces
            self.memory.subscribe_to_namespace('sensor_state', self._on_sensor_update)
            self.memory.subscribe_to_namespace('action_commands', self._on_command_update)
            self.memory.subscribe_to_namespace('system_status', self._on_system_status_update)
            
            self.logger.info("Robot module initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Robot module: {e}")
            return False
    
    def _initialize_robot_state(self):
        """Initialize robot state with default values"""
        try:
            # Create joint state at home position
            joint_state = JointState(
                joint_names=self.robot_config.joint_names,
                positions=np.array(self.robot_config.home_position),
                velocities=np.zeros(len(self.robot_config.joint_names)),
                efforts=np.zeros(len(self.robot_config.joint_names))
            )
            
            # Create default end-effector pose
            end_effector_pose = EndEffectorPose(
                position=np.array([0.5, 0.0, 0.5]),
                orientation=np.array([0, 0, 0, 1]),
                linear_velocity=np.zeros(3),
                angular_velocity=np.zeros(3)
            )
            
            # Set current state
            self.current_state = RobotState(
                joint_state=joint_state,
                end_effector_pose=end_effector_pose,
                gripper_state=0.0,
                is_moving=False,
                is_collision_detected=False,
                emergency_stop=False
            )
            
            # Set target state to match current
            self.target_state = RobotState(
                joint_state=joint_state,
                end_effector_pose=end_effector_pose,
                gripper_state=0.0,
                is_moving=False,
                is_collision_detected=False,
                emergency_stop=False
            )
            
        except Exception as e:
            self.logger.error(f"Error initializing robot state: {e}")
    
    def run(self):
        """Main robot module loop"""
        try:
            # Update robot state from adapter
            self._update_current_state()
            
            # Perform safety checks
            if self.safety_checks_enabled:
                self._perform_safety_checks()
            
            # Check for collision
            if self.collision_detection_enabled:
                self._check_collision()
            
            # Update state history
            self._update_state_history()
            
            # Calculate performance metrics
            self._update_metrics()
            
            # Update memory with current state
            with self.state_lock:
                self.memory.update('robot', 'current_state', self.current_state)
                self.memory.update('robot', 'target_state', self.target_state)
                self.memory.update('robot', 'is_safe', self.is_safe)
                self.memory.update('robot', 'metrics', {
                    'commands_executed': self.total_commands_executed,
                    'errors': self.total_errors,
                    'command_frequency': self.command_frequency
                })
            
            # Sleep based on update rate
            if self.update_rate > 0:
                time.sleep(1.0 / self.update_rate)
                
        except Exception as e:
            self.logger.error(f"Error in robot module loop: {e}")
            raise
    
    def _update_current_state(self):
        """Update current robot state from adapter"""
        try:
            # Get robot state from sensor data
            robot_state = self.memory.get('sensor_state', 'robot_state')
            
            if robot_state and isinstance(robot_state, RobotState):
                with self.state_lock:
                    self.current_state = robot_state
                    
                    # Check if robot is at target
                    if self._is_at_target():
                        self.current_state.is_moving = False
                    
        except Exception as e:
            self.logger.error(f"Error updating current state: {e}")
    
    def _perform_safety_checks(self):
        """Perform safety checks on robot state"""
        try:
            violations = []
            
            with self.state_lock:
                # Check joint limits
                if self.current_state.joint_state:
                    for i, (pos, (min_limit, max_limit)) in enumerate(
                        zip(self.current_state.joint_state.positions, self.robot_config.joint_limits)
                    ):
                        if pos < min_limit or pos > max_limit:
                            violations.append(f"Joint {i} out of limits: {pos:.3f}")
                
                # Check workspace limits
                if self.current_state.end_effector_pose:
                    pos = self.current_state.end_effector_pose.position
                    for axis, (min_limit, max_limit) in self.robot_config.workspace_limits.items():
                        idx = {'x': 0, 'y': 1, 'z': 2}[axis]
                        if pos[idx] < min_limit or pos[idx] > max_limit:
                            violations.append(f"End effector {axis} out of workspace: {pos[idx]:.3f}")
                
                # Check velocity limits
                if self.current_state.joint_state:
                    for i, (vel, max_vel) in enumerate(
                        zip(self.current_state.joint_state.velocities, self.robot_config.max_velocities)
                    ):
                        if abs(vel) > max_vel:
                            violations.append(f"Joint {i} velocity exceeds limit: {vel:.3f}")
                
                # Update safety state
                self.safety_violations = violations
                self.is_safe = len(violations) == 0
                
                if not self.is_safe:
                    self.logger.warning(f"Safety violations detected: {violations}")
                    
        except Exception as e:
            self.logger.error(f"Error performing safety checks: {e}")
    
    def _check_collision(self):
        """Check for collision detection"""
        try:
            # Simple collision detection based on sensor data
            sensor_bundle = self.memory.get('sensor_state', 'sensor_bundle')
            
            if sensor_bundle and isinstance(sensor_bundle, SensorBundle):
                if sensor_bundle.force_torque:
                    # Check for unexpected forces
                    force_magnitude = np.linalg.norm(sensor_bundle.force_torque.force)
                    if force_magnitude > 50.0:  # Threshold in Newtons
                        with self.state_lock:
                            self.current_state.is_collision_detected = True
                            self.logger.warning(f"Possible collision detected: force={force_magnitude:.1f}N")
                else:
                    with self.state_lock:
                        self.current_state.is_collision_detected = False
                        
        except Exception as e:
            self.logger.error(f"Error checking collision: {e}")
    
    def _is_at_target(self) -> bool:
        """Check if robot is at target position"""
        try:
            if not self.target_state.joint_state or not self.current_state.joint_state:
                return True
            
            # Check joint positions
            position_error = np.linalg.norm(
                self.target_state.joint_state.positions - 
                self.current_state.joint_state.positions
            )
            
            return position_error < 0.01  # 0.01 radians tolerance
            
        except Exception as e:
            self.logger.error(f"Error checking if at target: {e}")
            return False
    
    def _update_state_history(self):
        """Update state history for analysis"""
        try:
            with self.state_lock:
                history_entry = {
                    'timestamp': time.time(),
                    'state': self.current_state,
                    'is_safe': self.is_safe
                }
                
                self.state_history.append(history_entry)
                
                # Limit history size
                if len(self.state_history) > self.max_history:
                    self.state_history.pop(0)
                    
        except Exception as e:
            self.logger.error(f"Error updating state history: {e}")
    
    def _update_metrics(self):
        """Update performance metrics"""
        try:
            current_time = time.time()
            
            # Calculate command frequency
            if self.last_command_time > 0:
                time_diff = current_time - self.last_command_time
                if time_diff > 0:
                    self.command_frequency = 1.0 / time_diff
            
        except Exception as e:
            self.logger.error(f"Error updating metrics: {e}")
    
    def _on_sensor_update(self, key: str, value: Any):
        """Handle sensor state updates"""
        try:
            if key == 'robot_state' and isinstance(value, RobotState):
                with self.state_lock:
                    self.current_state = value
                    
        except Exception as e:
            self.logger.error(f"Error handling sensor update: {e}")
    
    def _on_command_update(self, key: str, value: Any):
        """Handle command updates"""
        try:
            if key == 'pending_commands' and isinstance(value, list):
                # Track command execution
                self.total_commands_executed += len(value)
                self.last_command_time = time.time()
                
            elif key == 'emergency_command' and value:
                self.emergency_stop_active = True
                self.logger.warning("Emergency stop activated in robot module")
                
        except Exception as e:
            self.logger.error(f"Error handling command update: {e}")
    
    def _on_system_status_update(self, key: str, value: Any):
        """Handle system status updates"""
        try:
            if key == 'emergency_stop' and isinstance(value, dict):
                self.emergency_stop_active = value.get('active', False)
                
        except Exception as e:
            self.logger.error(f"Error handling system status update: {e}")
    
    def move_to_home(self):
        """Move robot to home position"""
        try:
            self.logger.info("Moving robot to home position")
            
            with self.state_lock:
                # Set target to home position
                self.target_state.joint_state.positions = np.array(self.robot_config.home_position)
                
            # Generate command
            from models.control_commands import JointCommand
            joint_cmd = JointCommand(
                joint_names=self.robot_config.joint_names,
                positions=self.robot_config.home_position,
                velocities=[0.0] * len(self.robot_config.joint_names),
                efforts=[0.0] * len(self.robot_config.joint_names)
            )
            
            cmd = ControlCommand(
                command_type=CommandType.JOINT,
                joint_command=joint_cmd
            )
            
            # Send to memory
            self.memory.update('action_commands', 'direct_commands', [cmd])
            
        except Exception as e:
            self.logger.error(f"Error moving to home: {e}")
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of robot state"""
        with self.state_lock:
            return {
                'is_safe': self.is_safe,
                'is_moving': self.current_state.is_moving,
                'emergency_stop': self.emergency_stop_active,
                'collision_detected': self.current_state.is_collision_detected,
                'safety_violations': self.safety_violations,
                'commands_executed': self.total_commands_executed,
                'command_frequency': self.command_frequency
            }
    
    def cleanup(self):
        """Cleanup robot module"""
        try:
            self.logger.info("Cleaning up Robot module...")
            
            # Clear state history
            self.state_history.clear()
            
            self.logger.info("Robot module cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Robot module cleanup: {e}")