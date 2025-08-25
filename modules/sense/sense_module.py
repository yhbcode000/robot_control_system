import time
from typing import Dict, Any, Optional, List
import threading
import numpy as np

from core.base.module import BaseModule
from core.memory.memory_store import GlobalMemory
from modules.input.models import InputBuffer, ParsedCommand, CommandType
from models.robot_state import RobotState, JointState, EndEffectorPose
from models.sensor_data import SensorBundle
from models.planning_data import PlanRequest
from .parser import InputParser
from .models import SenseState, InterpretedInput
from .sensor_reader import SensorReader


class SenseModule(BaseModule):
    def __init__(self, config: Dict[str, Any], memory: Optional[GlobalMemory] = None, adapter=None):
        super().__init__('Sense', config, memory)
        
        # Store adapter reference for sensor readings
        self.adapter = adapter
        
        # Initialize input parser
        self.input_parser = InputParser(config)
        
        # Initialize sensor reader for continuous updates
        if self.adapter:
            sensor_update_rate = config.get('sensor_update_rate', 50.0)  # Hz
            self.sensor_reader = SensorReader(self.adapter, self.memory, sensor_update_rate)
        else:
            self.sensor_reader = None
        
        # State tracking
        self.current_robot_state = RobotState()
        self.sense_state = SenseState()
        self.last_input_update = 0.0
        
        # Configuration
        self.update_rate = config.get('update_rate', 50)  # Hz
        self.input_timeout = config.get('input_timeout', 1.0)  # seconds
        self.filter_noise = config.get('filter_noise', True)
        
        # Input processing
        self.active_inputs: Dict[str, ParsedCommand] = {}
        self.input_history = []
        self.max_history = 100
        
        # Robot state tracking
        self.joint_names = config.get('joint_names', [
            'shoulder_pan_joint',
            'shoulder_lift_joint', 
            'elbow_joint',
            'wrist_1_joint',
            'wrist_2_joint',
            'wrist_3_joint'
        ])
        
        # Subscribe to input buffer changes
        self.memory.subscribe_to_namespace('input_buffer', self._on_input_buffer_change)
    
    def _initialize(self) -> bool:
        try:
            self.logger.info("Initializing Sense module...")
            
            # Initialize sense state in memory
            self.memory.update('sensor_state', 'current', self.sense_state)
            
            # Initialize robot state with default values
            self._initialize_robot_state()
            
            # Start sensor reader if available
            if self.sensor_reader:
                self.sensor_reader.start()
                self.logger.info("Sensor reader started for continuous updates")
            
            self.logger.info("Sense module initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Sense module: {e}")
            return False
    
    def _initialize_robot_state(self):
        """Initialize robot state with default values"""
        try:
            # Create default joint state
            joint_state = JointState(
                joint_names=self.joint_names,
                positions=np.zeros(len(self.joint_names)),
                velocities=np.zeros(len(self.joint_names)),
                efforts=np.zeros(len(self.joint_names))
            )
            
            # Create default end-effector pose
            end_effector_pose = EndEffectorPose(
                position=np.array([0.5, 0.0, 0.5]),  # Default position
                orientation=np.array([0, 0, 0, 1])   # Default orientation (quaternion)
            )
            
            # Update robot state
            self.current_robot_state = RobotState(
                joint_state=joint_state,
                end_effector_pose=end_effector_pose,
                gripper_state=0.0,
                is_moving=False,
                is_collision_detected=False,
                emergency_stop=False
            )
            
            # Store in memory
            self.memory.update('sensor_state', 'robot_state', self.current_robot_state)
            
        except Exception as e:
            self.logger.error(f"Error initializing robot state: {e}")
    
    def run(self):
        """Main sense processing loop"""
        try:
            # Get current input buffer
            input_buffer = self.memory.get('input_buffer', 'current')
            
            if input_buffer and isinstance(input_buffer, InputBuffer):
                # Check if input has been updated
                if input_buffer.last_update > self.last_input_update:
                    self._process_input_buffer(input_buffer)
                    self.last_input_update = input_buffer.last_update
            
            # Update sensor readings (from adapter if available)
            self._update_sensor_readings()
            
            # Process interpreted inputs into plan requests
            self._generate_plan_requests()
            
            # Update memory with current state
            self.memory.update('sensor_state', 'current', self.sense_state)
            self.memory.update('sensor_state', 'robot_state', self.current_robot_state)
            
            # Sleep based on update rate
            if self.update_rate > 0:
                time.sleep(1.0 / self.update_rate)
            
        except Exception as e:
            self.logger.error(f"Error in sense processing: {e}")
            raise
    
    def _on_input_buffer_change(self, key: str, value: Any):
        """Handle input buffer changes"""
        try:
            if key == 'current' and isinstance(value, InputBuffer):
                # Input buffer was updated
                self.logger.debug("Input buffer updated, will process in next cycle")
        except Exception as e:
            self.logger.error(f"Error handling input buffer change: {e}")
    
    def _process_input_buffer(self, input_buffer: InputBuffer):
        """Process current input buffer"""
        try:
            # Update active inputs
            self.active_inputs = input_buffer.active_commands.copy()
            
            # Parse inputs to interpreted commands
            interpreted_inputs = []
            
            for input_key, parsed_command in self.active_inputs.items():
                interpreted = self.input_parser.parse_command(parsed_command)
                if interpreted:
                    interpreted_inputs.append(interpreted)
            
            # Update sense state
            self.sense_state.active_interpreted_inputs = interpreted_inputs
            self.sense_state.has_active_input = len(interpreted_inputs) > 0
            self.sense_state.last_input_time = time.time()
            
            # Log active commands (periodically)
            if hasattr(self, '_last_input_log'):
                if time.time() - self._last_input_log > 2.0:  # Log every 2 seconds
                    if interpreted_inputs:
                        input_types = [inp.movement_type for inp in interpreted_inputs if inp.movement_type]
                        self.logger.debug(f"Active interpreted inputs: {set(input_types)}")
                    self._last_input_log = time.time()
            else:
                self._last_input_log = time.time()
            
            # Add to history
            self.input_history.append({
                'timestamp': time.time(),
                'interpreted_inputs': interpreted_inputs.copy()
            })
            
            # Limit history size
            if len(self.input_history) > self.max_history:
                self.input_history.pop(0)
            
        except Exception as e:
            self.logger.error(f"Error processing input buffer: {e}")
    
    def _update_sensor_readings(self):
        """Update sensor readings from adapter or sensor reader"""
        try:
            # If we have a sensor reader, get the latest robot state from memory
            if self.sensor_reader and self.sensor_reader.running:
                # Get the latest robot state from memory (updated by sensor reader)
                latest_robot_state = self.memory.get('sensor_state', 'robot_state')
                if latest_robot_state:
                    self.current_robot_state = latest_robot_state
                    
                # Also check for sensor bundle
                sensor_bundle = self.memory.get('sensor_state', 'sensor_bundle')
                if sensor_bundle:
                    # Process sensor bundle if needed
                    self.logger.debug("Got sensor bundle from memory")
            
            elif self.adapter and self.adapter.is_connected():
                # Fallback to direct adapter reading if sensor reader not available
                try:
                    # Get robot state from adapter
                    adapter_robot_state = self.adapter.get_robot_state()
                    if adapter_robot_state:
                        # Update current robot state with adapter data
                        self.current_robot_state = adapter_robot_state
                        self.logger.debug("Updated robot state from adapter directly")
                    
                    # Read sensor bundle from adapter
                    sensor_bundle = self.adapter.read_sensors()
                    if sensor_bundle:
                        # Store sensor data in memory
                        self.memory.update('sensor_state', 'sensor_bundle', sensor_bundle)
                        
                except Exception as e:
                    self.logger.warning(f"Error reading from adapter: {e}")
                    # Fall back to simulation
                    self._simulate_sensor_readings()
            else:
                # Adapter not available - simulate sensor readings
                self._simulate_sensor_readings()
                
        except Exception as e:
            self.logger.error(f"Error updating sensor readings: {e}")
    
    def _simulate_sensor_readings(self):
        """Simulate sensor readings when adapter is not available"""
        try:
            # Update robot state based on any movement commands
            if self.sense_state.has_active_input:
                self.current_robot_state.is_moving = True
                
                # Update last movement time
                if not hasattr(self.current_robot_state, 'last_movement_time'):
                    self.current_robot_state.last_movement_time = time.time()
                else:
                    self.current_robot_state.last_movement_time = time.time()
            else:
                # Check if we should stop moving
                if (hasattr(self.current_robot_state, 'last_movement_time') and 
                    time.time() - self.current_robot_state.last_movement_time > 0.5):
                    self.current_robot_state.is_moving = False
            
            # Check for emergency stop
            emergency_inputs = [inp for inp in self.sense_state.active_interpreted_inputs 
                              if inp.is_emergency_stop]
            if emergency_inputs:
                self.current_robot_state.emergency_stop = True
                self.memory.update('system_status', 'emergency_stop', {
                    'active': True,
                    'triggered_by': 'user_input',
                    'timestamp': time.time()
                })
                self.logger.warning("Emergency stop activated by user input")
            else:
                # Reset emergency stop if no active emergency commands
                if self.current_robot_state.emergency_stop:
                    self.current_robot_state.emergency_stop = False
                    self.memory.update('system_status', 'emergency_stop', {
                        'active': False,
                        'timestamp': time.time()
                    })
                    self.logger.info("Emergency stop deactivated")
            
        except Exception as e:
            self.logger.error(f"Error updating sensor readings: {e}")
    
    def _generate_plan_requests(self):
        """Generate plan requests based on interpreted inputs"""
        try:
            if not self.sense_state.active_interpreted_inputs:
                return
            
            # Group inputs by movement type
            movement_inputs = {}
            special_commands = []
            
            for interpreted in self.sense_state.active_interpreted_inputs:
                if interpreted.movement_type:
                    if interpreted.movement_type not in movement_inputs:
                        movement_inputs[interpreted.movement_type] = []
                    movement_inputs[interpreted.movement_type].append(interpreted)
                
                if interpreted.is_special_command:
                    special_commands.append(interpreted)
                
                if interpreted.is_emergency_stop:
                    # Emergency stop takes precedence
                    self.logger.warning("Emergency stop detected - clearing all plan requests")
                    self.memory.update('planned_trajectory', 'pending_requests', [])
                    return
            
            # Generate plan requests for movements
            plan_requests = []
            
            # Handle linear movements (translation)
            linear_movements = movement_inputs.get('linear', [])
            if linear_movements:
                # Combine all linear movement directions
                total_direction = np.zeros(3)
                for inp in linear_movements:
                    if inp.direction_vector is not None:
                        total_direction += inp.direction_vector * inp.magnitude
                
                # Normalize if needed
                magnitude = np.linalg.norm(total_direction)
                if magnitude > 0:
                    if magnitude > 1.0:
                        total_direction /= magnitude
                    
                    # Create plan request for linear movement
                    current_pos = self.current_robot_state.end_effector_pose.position
                    step_size = 0.01  # 1cm per step
                    target_pos = current_pos + total_direction * step_size
                    
                    plan_request = PlanRequest(
                        target_position=target_pos,
                        target_orientation=self.current_robot_state.end_effector_pose.orientation,
                        constraints={'movement_type': 'linear', 'continuous': True},
                        planning_algorithm='simple',
                        max_planning_time=0.1
                    )
                    plan_requests.append(plan_request)
            
            # Handle angular movements (rotation)
            angular_movements = movement_inputs.get('angular', [])
            if angular_movements:
                # Create plan request for rotation
                for inp in angular_movements:
                    if inp.rotation_axis is not None and inp.rotation_angle != 0:
                        plan_request = PlanRequest(
                            target_position=self.current_robot_state.end_effector_pose.position,
                            constraints={
                                'movement_type': 'angular',
                                'rotation_axis': inp.rotation_axis,
                                'rotation_angle': inp.rotation_angle * 0.1,  # Small increments
                                'continuous': True
                            },
                            planning_algorithm='simple',
                            max_planning_time=0.1
                        )
                        plan_requests.append(plan_request)
            
            # Handle gripper commands
            gripper_movements = movement_inputs.get('gripper', [])
            if gripper_movements:
                for inp in gripper_movements:
                    plan_request = PlanRequest(
                        constraints={
                            'movement_type': 'gripper',
                            'gripper_action': inp.gripper_action,
                            'gripper_target': inp.gripper_target
                        },
                        planning_algorithm='direct',
                        max_planning_time=0.05
                    )
                    plan_requests.append(plan_request)
            
            # Handle special commands
            for special in special_commands:
                if special.special_command:
                    plan_request = PlanRequest(
                        constraints={
                            'movement_type': 'special',
                            'special_command': special.special_command
                        },
                        planning_algorithm='direct',
                        max_planning_time=1.0
                    )
                    plan_requests.append(plan_request)
            
            # Send plan requests to memory if any were generated
            if plan_requests:
                current_requests = self.memory.get('planned_trajectory', 'pending_requests', [])
                # Add new requests (replace for continuous control)
                self.memory.update('planned_trajectory', 'pending_requests', plan_requests)
                
                if len(plan_requests) > 0:
                    self.logger.debug(f"Generated {len(plan_requests)} plan requests")
            
        except Exception as e:
            self.logger.error(f"Error generating plan requests: {e}")
    
    def get_current_state(self) -> SenseState:
        """Get current sense state"""
        return self.sense_state
    
    def get_robot_state(self) -> RobotState:
        """Get current robot state"""
        return self.current_robot_state
    
    def get_active_inputs(self) -> List[InterpretedInput]:
        """Get currently active interpreted inputs"""
        return self.sense_state.active_interpreted_inputs
    
    def is_emergency_stop_active(self) -> bool:
        """Check if emergency stop is active"""
        return self.current_robot_state.emergency_stop
    
    def cleanup(self):
        """Cleanup sense module"""
        try:
            self.logger.info("Cleaning up Sense module...")
            
            # Stop sensor reader
            if self.sensor_reader:
                self.sensor_reader.stop()
                self.logger.info("Sensor reader stopped")
            
            # Clear any pending plan requests
            self.memory.update('planned_trajectory', 'pending_requests', [])
            
            self.logger.info("Sense module cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Sense module cleanup: {e}")