import time
from typing import Dict, Any, Optional, List
import threading
import numpy as np

from core.base.module import BaseModule
from core.memory.memory_store import GlobalMemory
from models.planning_data import Trajectory, MotionPlan, PlanningStatus
from models.control_commands import ControlCommand, JointCommand, CartesianCommand, GripperCommand, CommandType, ControlMode
from models.robot_state import RobotState
from .command_generator import CommandGenerator
from .models import ActionState, ExecutionContext, CommandBuffer
from .direct_control import DirectControlHandler
from .end_effector_control import EndEffectorController


class ActModule(BaseModule):
    def __init__(self, config: Dict[str, Any], memory: Optional[GlobalMemory] = None):
        super().__init__('Act', config, memory)
        
        # Initialize command generator
        self.command_generator = CommandGenerator(config)
        
        # Initialize direct control handler for teleoperation
        self.direct_control_handler = DirectControlHandler(config)
        
        # Initialize end-effector controller for IK-based control
        self.end_effector_controller = EndEffectorController(config)
        
        # Configuration
        self.update_rate = config.get('update_rate', 100)  # Hz
        self.control_mode = config.get('control_mode', 'position')
        self.max_command_age = config.get('max_command_age', 0.1)  # seconds
        
        # State
        self.action_state = ActionState()
        self.execution_context = ExecutionContext()
        self.command_buffer = CommandBuffer()
        
        # Current execution
        self.current_trajectory: Optional[Trajectory] = None
        self.trajectory_start_time: float = 0.0
        self.trajectory_progress: float = 0.0
        
        # Performance tracking
        self.commands_generated = 0
        self.execution_errors = 0
        self.successful_executions = 0
        
        # Threading for smooth trajectory execution
        self.trajectory_executor_thread: Optional[threading.Thread] = None
        self.executing_trajectory = False
        
        # Subscribe to planned trajectory changes
        self.memory.subscribe_to_namespace('planned_trajectory', self._on_trajectory_change)
        
        # Subscribe to robot state changes
        self.memory.subscribe_to_namespace('sensor_state', self._on_robot_state_change)
    
    def _initialize(self) -> bool:
        try:
            self.logger.info("Initializing Act module...")
            
            # Initialize action state in memory
            self.memory.update('action_commands', 'current_state', self.action_state)
            
            # Set up execution context
            self._initialize_execution_context()
            
            self.logger.info("Act module initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Act module: {e}")
            return False
    
    def _initialize_execution_context(self):
        """Initialize execution context with default values"""
        try:
            # Get current robot state
            robot_state = self.memory.get('sensor_state', 'robot_state')
            
            if robot_state and isinstance(robot_state, RobotState):
                self.execution_context.current_robot_state = robot_state
            
            # Set control parameters
            self.execution_context.control_frequency = self.update_rate
            self.execution_context.position_tolerance = 0.001  # 1mm
            self.execution_context.orientation_tolerance = 0.01  # ~0.57 degrees
            
        except Exception as e:
            self.logger.error(f"Error initializing execution context: {e}")
    
    def run(self):
        """Main action processing loop"""
        try:
            # Check for new trajectories to execute
            self._check_for_new_trajectories()
            
            # Execute current trajectory if active
            if self.current_trajectory and not self.executing_trajectory:
                self._execute_current_trajectory()
            
            # Process any direct commands
            self._process_direct_commands()
            
            # Update action state
            self._update_action_state()
            
            # Generate and send control commands
            self._generate_control_commands()
            
            # Update memory with current state
            self.memory.update('action_commands', 'current_state', self.action_state)
            
            # Sleep based on update rate
            if self.update_rate > 0:
                time.sleep(1.0 / self.update_rate)
            
        except Exception as e:
            self.logger.error(f"Error in action processing: {e}")
            raise
    
    def _on_trajectory_change(self, key: str, value: Any):
        """Handle changes to planned trajectory namespace"""
        try:
            if key == 'current_plan' and isinstance(value, MotionPlan):
                # New motion plan available
                if (value.current_trajectory and 
                    value.status == PlanningStatus.READY and
                    value.current_trajectory != self.current_trajectory):
                    
                    self.logger.debug("New trajectory received for execution")
                    self._set_new_trajectory(value.current_trajectory)
                    
        except Exception as e:
            self.logger.error(f"Error handling trajectory change: {e}")
    
    def _on_robot_state_change(self, key: str, value: Any):
        """Handle robot state changes"""
        try:
            if key == 'robot_state' and isinstance(value, RobotState):
                self.execution_context.current_robot_state = value
                
                # Check for emergency stop
                if value.emergency_stop and not self.action_state.emergency_stop_active:
                    self._handle_emergency_stop()
                elif not value.emergency_stop and self.action_state.emergency_stop_active:
                    self._clear_emergency_stop()
                    
        except Exception as e:
            self.logger.error(f"Error handling robot state change: {e}")
    
    def _check_for_new_trajectories(self):
        """Check for new trajectories from planning module"""
        try:
            # Get current motion plan
            motion_plan = self.memory.get('planned_trajectory', 'current_plan')
            
            if motion_plan and isinstance(motion_plan, MotionPlan):
                if (motion_plan.current_trajectory and 
                    motion_plan.status == PlanningStatus.READY and
                    motion_plan.current_trajectory != self.current_trajectory):
                    
                    self._set_new_trajectory(motion_plan.current_trajectory)
                    
        except Exception as e:
            self.logger.error(f"Error checking for new trajectories: {e}")
    
    def _set_new_trajectory(self, trajectory: Trajectory):
        """Set a new trajectory for execution"""
        try:
            # Stop current trajectory execution if active
            if self.executing_trajectory:
                self.executing_trajectory = False
                if self.trajectory_executor_thread and self.trajectory_executor_thread.is_alive():
                    self.trajectory_executor_thread.join(timeout=0.1)
            
            # Set new trajectory
            self.current_trajectory = trajectory
            self.trajectory_start_time = time.time()
            self.trajectory_progress = 0.0
            
            # Update action state
            self.action_state.has_active_trajectory = True
            self.action_state.trajectory_start_time = self.trajectory_start_time
            self.action_state.execution_progress = 0.0
            
            self.logger.debug(f"Set new trajectory with {len(trajectory.waypoints)} waypoints")
            
        except Exception as e:
            self.logger.error(f"Error setting new trajectory: {e}")
    
    def _execute_current_trajectory(self):
        """Execute the current trajectory"""
        try:
            if not self.current_trajectory:
                return
            
            # Start trajectory execution thread
            if not self.executing_trajectory:
                self.executing_trajectory = True
                self.trajectory_executor_thread = threading.Thread(
                    target=self._trajectory_execution_thread,
                    daemon=True
                )
                self.trajectory_executor_thread.start()
                
        except Exception as e:
            self.logger.error(f"Error starting trajectory execution: {e}")
    
    def _trajectory_execution_thread(self):
        """Thread for smooth trajectory execution"""
        try:
            self.logger.debug("Starting trajectory execution thread")
            
            while (self.executing_trajectory and 
                   self.current_trajectory and 
                   self.running):
                
                current_time = time.time()
                elapsed_time = current_time - self.trajectory_start_time
                
                # Check if trajectory is complete
                if elapsed_time >= self.current_trajectory.total_duration:
                    self._finish_trajectory_execution()
                    break
                
                # Calculate progress
                self.trajectory_progress = elapsed_time / self.current_trajectory.total_duration
                self.action_state.execution_progress = self.trajectory_progress
                
                # Generate command for current time
                command = self._generate_trajectory_command(elapsed_time)
                
                if command:
                    # Add to command buffer
                    self.command_buffer.add_command(command)
                    self.commands_generated += 1
                
                # Sleep for control frequency
                time.sleep(1.0 / self.execution_context.control_frequency)
            
        except Exception as e:
            self.logger.error(f"Error in trajectory execution thread: {e}")
            self.executing_trajectory = False
        finally:
            self.logger.debug("Trajectory execution thread finished")
    
    def _generate_trajectory_command(self, elapsed_time: float) -> Optional[ControlCommand]:
        """Generate control command for current trajectory position"""
        try:
            if not self.current_trajectory:
                return None
            
            # Check trajectory type and generate appropriate command
            if self.current_trajectory.cartesian_trajectory:
                return self._generate_cartesian_command(elapsed_time)
            elif self.current_trajectory.joint_trajectory:
                return self._generate_joint_command(elapsed_time)
            elif self.current_trajectory.waypoints:
                return self._generate_waypoint_command(elapsed_time)
            elif hasattr(self.current_trajectory, 'metadata'):
                return self._generate_metadata_command()
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error generating trajectory command: {e}")
            return None
    
    def _generate_cartesian_command(self, elapsed_time: float) -> Optional[ControlCommand]:
        """Generate Cartesian command from trajectory"""
        try:
            cartesian_traj = self.current_trajectory.cartesian_trajectory
            if not cartesian_traj:
                return None
            
            # Find appropriate command based on time
            target_cmd = None
            for cmd in cartesian_traj:
                cmd_time = cmd.timestamp - self.trajectory_start_time
                if cmd_time <= elapsed_time:
                    target_cmd = cmd
                else:
                    break
            
            if not target_cmd:
                target_cmd = cartesian_traj[0]  # Use first command as fallback
            
            # Create control command
            control_cmd = ControlCommand(
                command_type=CommandType.CARTESIAN,
                cartesian_command=target_cmd
            )
            control_cmd.source_module = self.name
            
            return control_cmd
            
        except Exception as e:
            self.logger.error(f"Error generating Cartesian command: {e}")
            return None
    
    def _generate_joint_command(self, elapsed_time: float) -> Optional[ControlCommand]:
        """Generate joint command from trajectory"""
        try:
            joint_traj = self.current_trajectory.joint_trajectory
            if not joint_traj:
                return None
            
            # Find appropriate command based on time
            target_cmd = None
            for cmd in joint_traj:
                cmd_time = cmd.timestamp - self.trajectory_start_time
                if cmd_time <= elapsed_time:
                    target_cmd = cmd
                else:
                    break
            
            if not target_cmd:
                target_cmd = joint_traj[0]  # Use first command as fallback
            
            # Create control command
            control_cmd = ControlCommand(
                command_type=CommandType.JOINT,
                joint_command=target_cmd
            )
            control_cmd.source_module = self.name
            
            return control_cmd
            
        except Exception as e:
            self.logger.error(f"Error generating joint command: {e}")
            return None
    
    def _generate_waypoint_command(self, elapsed_time: float) -> Optional[ControlCommand]:
        """Generate command from waypoints"""
        try:
            waypoints = self.current_trajectory.waypoints
            if not waypoints:
                return None
            
            # Interpolate between waypoints
            target_waypoint = None
            for waypoint in waypoints:
                if waypoint.timestamp_offset <= elapsed_time:
                    target_waypoint = waypoint
                else:
                    break
            
            if not target_waypoint:
                target_waypoint = waypoints[0]  # Use first waypoint as fallback
            
            # Create Cartesian command from waypoint
            cartesian_cmd = CartesianCommand(
                position=target_waypoint.position,
                orientation=target_waypoint.orientation,
                control_mode=ControlMode.POSITION
            )
            
            control_cmd = ControlCommand(
                command_type=CommandType.CARTESIAN,
                cartesian_command=cartesian_cmd
            )
            control_cmd.source_module = self.name
            
            return control_cmd
            
        except Exception as e:
            self.logger.error(f"Error generating waypoint command: {e}")
            return None
    
    def _generate_metadata_command(self) -> Optional[ControlCommand]:
        """Generate command from trajectory metadata"""
        try:
            metadata = self.current_trajectory.metadata
            if not metadata:
                return None
            
            movement_type = metadata.get('movement_type')
            
            if movement_type == 'gripper':
                gripper_cmd = metadata.get('gripper_command')
                if gripper_cmd:
                    control_cmd = ControlCommand(
                        command_type=CommandType.GRIPPER,
                        gripper_command=gripper_cmd
                    )
                    control_cmd.source_module = self.name
                    return control_cmd
            
            elif movement_type == 'special':
                special_command = metadata.get('special_command')
                if special_command:
                    # Handle special commands
                    if special_command == 'reset':
                        # Generate stop command
                        cartesian_cmd = CartesianCommand(
                            linear_velocity=np.zeros(3),
                            angular_velocity=np.zeros(3),
                            control_mode=ControlMode.VELOCITY
                        )
                        control_cmd = ControlCommand(
                            command_type=CommandType.CARTESIAN,
                            cartesian_command=cartesian_cmd
                        )
                        control_cmd.source_module = self.name
                        return control_cmd
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error generating metadata command: {e}")
            return None
    
    def _finish_trajectory_execution(self):
        """Finish trajectory execution"""
        try:
            self.executing_trajectory = False
            self.action_state.has_active_trajectory = False
            self.action_state.execution_progress = 1.0
            self.trajectory_progress = 1.0
            
            self.successful_executions += 1
            self.logger.debug("Trajectory execution completed successfully")
            
            # Clear current trajectory
            self.current_trajectory = None
            
            # Update memory to indicate completion
            self.memory.update('action_commands', 'trajectory_complete', {
                'timestamp': time.time(),
                'success': True
            })
            
        except Exception as e:
            self.logger.error(f"Error finishing trajectory execution: {e}")
    
    def _process_direct_commands(self):
        """Process any direct commands that bypass trajectory planning"""
        try:
            # Check for direct commands in memory
            direct_commands = self.memory.get('action_commands', 'direct_commands', [])
            
            if direct_commands:
                for cmd in direct_commands:
                    if isinstance(cmd, ControlCommand):
                        self.command_buffer.add_command(cmd)
                        self.commands_generated += 1
                
                # Clear direct commands after processing
                self.memory.update('action_commands', 'direct_commands', [])
            
            # Check for interpreted inputs from Sense module for teleoperation
            sense_state = self.memory.get('sensor_state', 'current')
            if sense_state and hasattr(sense_state, 'active_interpreted_inputs'):
                if sense_state.active_interpreted_inputs:
                    # Generate direct control commands from interpreted inputs
                    control_commands = self.direct_control_handler.process_interpreted_inputs(
                        sense_state.active_interpreted_inputs
                    )
                    
                    for cmd in control_commands:
                        self.command_buffer.add_command(cmd)
                        self.commands_generated += 1
                    
                    if control_commands:
                        self.logger.debug(f"Generated {len(control_commands)} direct control commands")
            
            # Check for end-effector control targets from mouse input
            self._process_end_effector_control()
                
        except Exception as e:
            self.logger.error(f"Error processing direct commands: {e}")
    
    def _process_end_effector_control(self):
        """Process end-effector control from mouse input"""
        try:
            # Update robot state in end-effector controller
            robot_state = self.memory.get('sensor_state', 'robot_state')
            if robot_state:
                self.end_effector_controller.update_robot_state(robot_state)
            
            # Check for end-effector targets from input buffer
            input_buffer = self.memory.get('input_buffer', 'current')
            if input_buffer and hasattr(input_buffer, 'mouse_inputs'):
                for mouse_input in input_buffer.mouse_inputs:
                    if (hasattr(mouse_input, 'metadata') and 
                        mouse_input.metadata and
                        'end_effector_target' in mouse_input.metadata):
                        
                        # Get target position from mouse
                        target_pos = mouse_input.metadata['end_effector_target']
                        
                        # Set target in end-effector controller
                        success = self.end_effector_controller.set_target_position(
                            target_pos, source='mouse'
                        )
                        
                        if success:
                            self.logger.debug(f"Set end-effector target: {target_pos}")
            
            # Generate control command for current target
            ee_command = self.end_effector_controller.generate_control_command()
            if ee_command:
                self.command_buffer.add_command(ee_command)
                self.commands_generated += 1
                self.logger.debug("Generated end-effector control command")
                
        except Exception as e:
            self.logger.error(f"Error processing end-effector control: {e}")
    
    def _update_action_state(self):
        """Update action state"""
        try:
            self.action_state.is_executing = self.executing_trajectory
            self.action_state.commands_in_buffer = self.command_buffer.size()
            self.action_state.total_commands_generated = self.commands_generated
            self.action_state.execution_errors = self.execution_errors
            self.action_state.successful_executions = self.successful_executions
            self.action_state.last_update_time = time.time()
            
        except Exception as e:
            self.logger.error(f"Error updating action state: {e}")
    
    def _generate_control_commands(self):
        """Generate control commands and send to output"""
        try:
            # Get commands from buffer
            commands = self.command_buffer.get_commands(max_age=self.max_command_age)
            
            if commands:
                # Send commands to memory for output module
                self.memory.update('action_commands', 'pending_commands', commands)
                
                self.logger.debug(f"Generated {len(commands)} control commands")
            
        except Exception as e:
            self.logger.error(f"Error generating control commands: {e}")
    
    def _handle_emergency_stop(self):
        """Handle emergency stop activation"""
        try:
            self.logger.warning("Emergency stop activated - halting all action")
            
            # Stop trajectory execution
            self.executing_trajectory = False
            self.current_trajectory = None
            
            # Clear command buffer
            self.command_buffer.clear()
            
            # Set emergency stop state
            self.action_state.emergency_stop_active = True
            
            # Generate emergency stop command
            from models.control_commands import EmergencyStopCommand
            emergency_cmd = EmergencyStopCommand(reason="Emergency stop from user input")
            
            control_cmd = ControlCommand(
                command_type=CommandType.EMERGENCY_STOP,
                emergency_stop=emergency_cmd
            )
            control_cmd.source_module = self.name
            
            # Send immediately
            self.memory.update('action_commands', 'emergency_command', control_cmd)
            
        except Exception as e:
            self.logger.error(f"Error handling emergency stop: {e}")
    
    def _clear_emergency_stop(self):
        """Clear emergency stop state"""
        try:
            self.logger.info("Emergency stop cleared - resuming normal operation")
            self.action_state.emergency_stop_active = False
            
            # Clear emergency command
            self.memory.update('action_commands', 'emergency_command', None)
            
        except Exception as e:
            self.logger.error(f"Error clearing emergency stop: {e}")
    
    def get_action_state(self) -> ActionState:
        """Get current action state"""
        return self.action_state
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        total_commands = self.commands_generated
        error_rate = self.execution_errors / total_commands if total_commands > 0 else 0
        success_rate = self.successful_executions / (self.successful_executions + self.execution_errors) if (self.successful_executions + self.execution_errors) > 0 else 0
        
        return {
            'total_commands_generated': self.commands_generated,
            'execution_errors': self.execution_errors,
            'successful_executions': self.successful_executions,
            'error_rate': error_rate,
            'success_rate': success_rate,
            'is_executing': self.executing_trajectory,
            'trajectory_progress': self.trajectory_progress
        }
    
    def cleanup(self):
        """Cleanup act module"""
        try:
            self.logger.info("Cleaning up Act module...")
            
            # Stop trajectory execution
            self.executing_trajectory = False
            if self.trajectory_executor_thread and self.trajectory_executor_thread.is_alive():
                self.trajectory_executor_thread.join(timeout=1.0)
            
            # Clear command buffer
            self.command_buffer.clear()
            
            self.logger.info("Act module cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Act module cleanup: {e}")