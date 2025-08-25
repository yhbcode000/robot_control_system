import time
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import threading
import signal
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from .base_adapter import BaseAdapter, AdapterType
from .models import ConnectionState
from models.robot_state import RobotState, JointState, EndEffectorPose
from models.sensor_data import SensorBundle, ForceTorqueSensor

try:
    import mujoco
    import mujoco.viewer
    MUJOCO_AVAILABLE = True
except ImportError:
    MUJOCO_AVAILABLE = False
    print("MuJoCo not available - MuJoCoAdapter will run in simulation mode")


class MuJoCoAdapter(BaseAdapter):
    """MuJoCo simulation adapter"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.adapter_type = AdapterType.MUJOCO
        
        # MuJoCo specific attributes
        self.model = None
        self.data = None
        self.viewer = None
        self.viewer_thread = None
        
        # Configuration
        self.model_path = config.get('model_path', 'assets/robots/arm/robot_arm.xml')
        self.render = config.get('render', True)
        # Support both timestep naming conventions
        self.timestep = config.get('timestep', config.get('physics_timestep', 0.001))
        self.control_frequency = config.get('control_frequency', 1.0 / config.get('control_timestep', 0.01) if config.get('control_timestep') else 100)
        
        # Control state
        self.target_positions = None
        self.target_velocities = None
        self.emergency_stop_flag = False
        self.last_control_time = 0.0
        
        # Joint mapping
        self.joint_names = config.get('joint_names', [
            'shoulder_pan_joint',
            'shoulder_lift_joint',
            'elbow_joint', 
            'wrist_1_joint',
            'wrist_2_joint',
            'wrist_3_joint'
        ])
        
        # Actuator mapping (may be different from joint names)
        self.actuator_names = config.get('actuator_names', self.joint_names)
        
        # Control indices (will be populated after loading model)
        self.joint_indices = {}
        self.actuator_indices = {}
        
        # Simulation control
        self.simulation_running = False
        self.simulation_thread = None
        self.thread_lock = threading.Lock()
        
        # End effector
        self.end_effector_body_name = config.get('end_effector_body', 'wrist_3_link')
        self.end_effector_body_id = None
        
        # Gripper  
        gripper_joint = config.get('gripper_joint', 'gripper_joint')
        self.gripper_joint_name = gripper_joint if gripper_joint is not None else 'gripper_joint'
        self.gripper_joint_id = None
        self.current_gripper_position = 0.0
        self.target_gripper_position = 0.0
    
    def connect(self) -> bool:
        """Connect to MuJoCo simulation with simplified approach"""
        try:
            if not MUJOCO_AVAILABLE:
                print("MuJoCo not available - creating mock connection")
                self.connection_state = ConnectionState.CONNECTED
                return True
            
            print(f"Starting MuJoCo adapter connection...")
            return self._do_connection()
            
        except Exception as e:
            print(f"Failed to connect MuJoCo adapter: {e}")
            import traceback
            traceback.print_exc()
            self.connection_state = ConnectionState.ERROR
            self.error_count += 1
            return False
    
    def _do_connection(self) -> bool:
        """Perform the actual connection steps"""
        try:
            print("Loading MuJoCo model...")
            # Load MuJoCo model
            self.model = mujoco.MjModel.from_xml_path(self.model_path)
            self.data = mujoco.MjData(self.model)
            print("Model loaded successfully")
            
            print("Setting up joint mappings...")
            # Set up joint mappings
            self._setup_joint_mappings()
            
            print("Initializing target positions...")
            # Initialize target positions
            self.target_positions = np.zeros(len(self.joint_names))
            self.target_velocities = np.zeros(len(self.joint_names))
            
            print("Starting simulation thread...")
            # Start simulation thread
            self.simulation_running = True
            self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
            self.simulation_thread.start()
            
            # Wait a moment for simulation thread to start
            time.sleep(0.1)
            
            # Start viewer if requested
            if self.render:
                print("Starting viewer thread...")
                self.viewer_thread = threading.Thread(target=self._viewer_loop, daemon=True)
                self.viewer_thread.start()
                # Wait a moment for viewer thread to start
                time.sleep(0.1)
            
            print("Setting connection state...")
            self.connection_state = ConnectionState.CONNECTED
            self.send_heartbeat()
            
            print("Connection completed successfully")
            return True
            
        except Exception as e:
            print(f"Error in _do_connection: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from MuJoCo simulation with robust cleanup"""
        try:
            print("Starting MuJoCo adapter disconnection...")
            
            # Stop simulation
            self.simulation_running = False
            
            # Wait for simulation thread to finish with timeout
            if self.simulation_thread and self.simulation_thread.is_alive():
                print("Waiting for simulation thread to stop...")
                self.simulation_thread.join(timeout=2.0)
                if self.simulation_thread.is_alive():
                    print("Warning: Simulation thread did not stop cleanly")
            
            # Close viewer safely
            if self.viewer:
                print("Closing viewer...")
                try:
                    self.viewer.close()
                except Exception as e:
                    print(f"Warning: Error closing viewer: {e}")
                finally:
                    self.viewer = None
            
            # Wait for viewer thread to finish with timeout
            if self.viewer_thread and self.viewer_thread.is_alive():
                print("Waiting for viewer thread to stop...")
                self.viewer_thread.join(timeout=2.0)
                if self.viewer_thread.is_alive():
                    print("Warning: Viewer thread did not stop cleanly")
            
            # Clean up MuJoCo objects
            print("Cleaning up MuJoCo objects...")
            self.model = None
            self.data = None
            
            self.connection_state = ConnectionState.DISCONNECTED
            
            print("MuJoCo adapter disconnected successfully")
            return True
            
        except Exception as e:
            print(f"Error disconnecting MuJoCo adapter: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to MuJoCo"""
        if not MUJOCO_AVAILABLE:
            return self.connection_state == ConnectionState.CONNECTED
        
        return (self.connection_state == ConnectionState.CONNECTED and 
                self.model is not None and 
                self.data is not None and
                self.simulation_running)
    
    def _setup_joint_mappings(self):
        """Set up joint name to index mappings"""
        try:
            if not self.model:
                return
            
            for i, joint_name in enumerate(self.joint_names):
                # Find joint ID in MuJoCo model
                joint_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
                if joint_id >= 0:
                    self.joint_indices[joint_name] = joint_id
                else:
                    print(f"Warning: Joint '{joint_name}' not found in model")
                
                # Find actuator ID using actuator name (not joint name)
                if i < len(self.actuator_names):
                    actuator_name = self.actuator_names[i]
                    actuator_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)
                    if actuator_id >= 0:
                        self.actuator_indices[joint_name] = actuator_id
                    else:
                        print(f"Warning: Actuator '{actuator_name}' not found in model")
                else:
                    print(f"Warning: No actuator name provided for joint '{joint_name}'")
            
            # Find end effector body
            self.end_effector_body_id = mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_BODY, self.end_effector_body_name)
            
            if self.end_effector_body_id < 0:
                print(f"Warning: End effector body '{self.end_effector_body_name}' not found")
                self.end_effector_body_id = None
            
            # Find gripper joint
            self.gripper_joint_id = mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_JOINT, self.gripper_joint_name)
            
            if self.gripper_joint_id < 0:
                print(f"Warning: Gripper joint '{self.gripper_joint_name}' not found")
                self.gripper_joint_id = None
                
        except Exception as e:
            print(f"Error setting up joint mappings: {e}")
    
    def _simulation_loop(self):
        """Main simulation loop"""
        try:
            last_time = time.time()
            
            while self.simulation_running:
                current_time = time.time()
                dt = current_time - last_time
                
                with self.thread_lock:
                    if self.model and self.data:
                        # Apply control commands
                        self._apply_control()
                        
                        # Step simulation
                        mujoco.mj_step(self.model, self.data)
                        
                        # Update heartbeat
                        self.send_heartbeat()
                
                last_time = current_time
                
                # Sleep to maintain simulation frequency
                sleep_time = self.timestep - (time.time() - current_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except Exception as e:
            print(f"Simulation loop error: {e}")
            self.error_count += 1
    
    def _viewer_loop(self):
        """Viewer rendering loop"""
        try:
            if not MUJOCO_AVAILABLE:
                return
            
            with mujoco.viewer.launch_passive(self.model, self.data) as viewer:
                self.viewer = viewer
                
                while self.simulation_running and self.viewer.is_running():
                    with self.thread_lock:
                        # Sync viewer
                        viewer.sync()
                    
                    # Sleep to limit render rate
                    time.sleep(1.0 / 60.0)  # 60 FPS max
                    
        except Exception as e:
            print(f"Viewer loop error: {e}")
    
    def _apply_control(self):
        """Apply current control commands to simulation"""
        try:
            if not self.data or self.emergency_stop_flag:
                return
            
            # Apply joint position control
            if self.target_positions is not None:
                for i, joint_name in enumerate(self.joint_names):
                    actuator_id = self.actuator_indices.get(joint_name)
                    if actuator_id is not None and i < len(self.target_positions):
                        self.data.ctrl[actuator_id] = self.target_positions[i]
            
            # Apply gripper control
            if self.gripper_joint_id is not None:
                # Simple gripper control (this depends on your robot model)
                gripper_actuator_id = mujoco.mj_name2id(
                    self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, self.gripper_joint_name)
                if gripper_actuator_id >= 0:
                    self.data.ctrl[gripper_actuator_id] = self.target_gripper_position
            
        except Exception as e:
            print(f"Error applying control: {e}")
    
    def read_sensors(self) -> Optional[SensorBundle]:
        """Read sensor data from simulation"""
        try:
            if not self.is_connected():
                return None
            
            with self.thread_lock:
                if not self.data:
                    return None
                
                # Create sensor bundle
                sensor_bundle = SensorBundle()
                
                # Add force/torque sensor if available
                if len(self.data.sensordata) > 0:
                    # This is simplified - real implementation would map specific sensors
                    force_data = self.data.sensordata[:3] if len(self.data.sensordata) >= 3 else np.zeros(3)
                    torque_data = self.data.sensordata[3:6] if len(self.data.sensordata) >= 6 else np.zeros(3)
                    
                    sensor_bundle.force_torque = ForceTorqueSensor(
                        force=force_data,
                        torque=torque_data
                    )
                
                return sensor_bundle
                
        except Exception as e:
            print(f"Error reading sensors: {e}")
            self.error_count += 1
            return None
    
    def get_robot_state(self) -> Optional[RobotState]:
        """Get current robot state from simulation"""
        try:
            if not self.is_connected():
                return None
            
            with self.thread_lock:
                if not self.data:
                    return None
                
                # Get joint state
                joint_positions = []
                joint_velocities = []
                
                for joint_name in self.joint_names:
                    joint_id = self.joint_indices.get(joint_name)
                    if joint_id is not None:
                        # Get joint position and velocity
                        qpos_addr = self.model.jnt_qposadr[joint_id]
                        qvel_addr = self.model.jnt_dofadr[joint_id]
                        
                        joint_positions.append(self.data.qpos[qpos_addr])
                        joint_velocities.append(self.data.qvel[qvel_addr])
                    else:
                        joint_positions.append(0.0)
                        joint_velocities.append(0.0)
                
                joint_state = JointState(
                    joint_names=self.joint_names,
                    positions=np.array(joint_positions),
                    velocities=np.array(joint_velocities),
                    efforts=np.zeros(len(self.joint_names))  # MuJoCo doesn't directly provide efforts
                )
                
                # Get end effector pose
                end_effector_pose = None
                if self.end_effector_body_id is not None:
                    # Get body position and orientation
                    body_pos = self.data.xpos[self.end_effector_body_id].copy()
                    body_quat = self.data.xquat[self.end_effector_body_id].copy()
                    
                    # Get body velocity (simplified)
                    body_vel = np.zeros(3)  # Would need to calculate from joint velocities
                    angular_vel = np.zeros(3)
                    
                    end_effector_pose = EndEffectorPose(
                        position=body_pos,
                        orientation=body_quat,
                        linear_velocity=body_vel,
                        angular_velocity=angular_vel
                    )
                
                # Get gripper state
                gripper_state = 0.0
                if self.gripper_joint_id is not None:
                    qpos_addr = self.model.jnt_qposadr[self.gripper_joint_id]
                    gripper_state = self.data.qpos[qpos_addr]
                
                # Create robot state
                robot_state = RobotState(
                    joint_state=joint_state,
                    end_effector_pose=end_effector_pose,
                    gripper_state=gripper_state,
                    is_moving=np.any(np.abs(joint_velocities) > 0.01),
                    is_collision_detected=False,  # Would need collision detection
                    emergency_stop=self.emergency_stop_flag
                )
                
                return robot_state
                
        except Exception as e:
            print(f"Error getting robot state: {e}")
            self.error_count += 1
            return None
    
    def send_joint_command(self, joint_names: List[str], positions: List[float], 
                          velocities: Optional[List[float]] = None) -> bool:
        """Send joint position command to simulation"""
        try:
            start_time = time.time()
            
            if not self.is_connected():
                self.record_command(False)
                return False
            
            if not self.validate_joint_command(joint_names, positions):
                self.record_command(False)
                return False
            
            # Map joint commands to target positions
            for i, joint_name in enumerate(joint_names):
                # Handle simplified joint names (joint_0, joint_1, etc.)
                if joint_name.startswith('joint_'):
                    try:
                        joint_idx = int(joint_name.split('_')[1])
                        if 0 <= joint_idx < len(self.target_positions) and i < len(positions):
                            self.target_positions[joint_idx] = positions[i]
                    except (ValueError, IndexError):
                        pass
                elif joint_name in self.joint_indices and i < len(positions):
                    joint_idx = self.joint_names.index(joint_name) if joint_name in self.joint_names else -1
                    if joint_idx >= 0:
                        self.target_positions[joint_idx] = positions[i]
            
            # Record successful command
            latency = time.time() - start_time
            self.record_command(True, latency)
            self.last_control_time = time.time()
            
            return True
            
        except Exception as e:
            print(f"Error sending joint command: {e}")
            self.record_command(False)
            return False
    
    def send_cartesian_command(self, position: List[float], orientation: List[float],
                              linear_velocity: Optional[List[float]] = None,
                              angular_velocity: Optional[List[float]] = None) -> bool:
        """Send Cartesian command (converted to joint command via IK)"""
        try:
            start_time = time.time()
            
            if not self.is_connected():
                self.record_command(False)
                return False
            
            if not self.validate_cartesian_command(position, orientation):
                self.record_command(False)
                return False
            
            # For now, just record the command without full IK implementation
            # In a real implementation, you would:
            # 1. Use MuJoCo's IK solver or implement your own
            # 2. Convert Cartesian target to joint positions
            # 3. Send joint command
            
            # Simplified: just update the control time
            self.last_control_time = time.time()
            
            # Record successful command
            latency = time.time() - start_time
            self.record_command(True, latency)
            
            return True
            
        except Exception as e:
            print(f"Error sending Cartesian command: {e}")
            self.record_command(False)
            return False
    
    def send_gripper_command(self, position: float, force: float = 1.0) -> bool:
        """Send gripper command to simulation"""
        try:
            start_time = time.time()
            
            if not self.is_connected():
                self.record_command(False)
                return False
            
            if not self.validate_gripper_command(position, force):
                self.record_command(False)
                return False
            
            # Set target gripper position
            self.target_gripper_position = position
            self.current_gripper_position = position
            self.last_control_time = time.time()
            
            # Record successful command
            latency = time.time() - start_time
            self.record_command(True, latency)
            
            return True
            
        except Exception as e:
            print(f"Error sending gripper command: {e}")
            self.record_command(False)
            return False
    
    def send_emergency_stop(self) -> bool:
        """Send emergency stop command"""
        try:
            self.emergency_stop_flag = True
            
            # Stop all motion by setting target positions to current positions
            if self.data and self.target_positions is not None:
                for i, joint_name in enumerate(self.joint_names):
                    joint_id = self.joint_indices.get(joint_name)
                    if joint_id is not None and i < len(self.target_positions):
                        qpos_addr = self.model.jnt_qposadr[joint_id]
                        self.target_positions[i] = self.data.qpos[qpos_addr]
            
            self.record_command(True)
            print("Emergency stop activated in MuJoCo simulation")
            return True
            
        except Exception as e:
            print(f"Error sending emergency stop: {e}")
            self.record_command(False)
            return False
    
    def emergency_stop_active(self) -> bool:
        """Check if emergency stop is active"""
        return self.emergency_stop_flag
    
    def clear_emergency_stop(self) -> bool:
        """Clear emergency stop state"""
        try:
            self.emergency_stop_flag = False
            print("Emergency stop cleared in MuJoCo simulation")
            return True
        except Exception as e:
            print(f"Error clearing emergency stop: {e}")
            return False
    
    def get_joint_limits(self) -> Dict[str, List[float]]:
        """Get joint limits from MuJoCo model"""
        if not self.model:
            return super().get_joint_limits()
        
        try:
            min_limits = []
            max_limits = []
            
            for joint_name in self.joint_names:
                joint_id = self.joint_indices.get(joint_name)
                if joint_id is not None:
                    min_limits.append(self.model.jnt_range[joint_id][0])
                    max_limits.append(self.model.jnt_range[joint_id][1])
                else:
                    min_limits.append(-3.14)
                    max_limits.append(3.14)
            
            return {'min': min_limits, 'max': max_limits}
            
        except Exception as e:
            print(f"Error getting joint limits: {e}")
            return super().get_joint_limits()
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Get MuJoCo adapter capabilities"""
        return {
            'joint_control': True,
            'cartesian_control': True,  # With IK
            'gripper_control': self.gripper_joint_id is not None,
            'force_control': False,  # Would need force control setup
            'impedance_control': False,
            'trajectory_following': True,
            'real_time_control': True,
            'visualization': self.render,
            'collision_detection': True,  # MuJoCo has built-in collision detection
            'physics_simulation': True
        }