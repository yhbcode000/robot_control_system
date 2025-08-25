import time
from typing import Dict, Any, Optional, List
import threading
import numpy as np

from core.base.module import BaseModule
from core.memory.memory_store import GlobalMemory
from models.planning_data import PlanRequest, PlanResponse, Trajectory, Waypoint, MotionPlan, PlanningStatus
from models.robot_state import RobotState
from models.control_commands import JointCommand, CartesianCommand, ControlMode
from .trajectory import TrajectoryGenerator
from .models import PlannerConfig, PlanningContext


class PlanModule(BaseModule):
    def __init__(self, config: Dict[str, Any], memory: Optional[GlobalMemory] = None):
        super().__init__('Plan', config, memory)
        
        # Initialize trajectory generator
        self.trajectory_generator = TrajectoryGenerator(config)
        
        # Configuration
        self.planning_algorithm = config.get('algorithm', 'simple')
        self.update_rate = config.get('update_rate', 20)  # Hz
        self.max_planning_time = config.get('max_planning_time', 0.5)  # seconds
        
        # State
        self.current_motion_plan = MotionPlan()
        self.pending_requests: List[PlanRequest] = []
        self.planning_context = PlanningContext()
        self.is_planning = False
        self.planning_thread: Optional[threading.Thread] = None
        
        # Performance tracking
        self.planning_times = []
        self.success_count = 0
        self.failure_count = 0
        
        # Subscribe to planned trajectory namespace changes
        self.memory.subscribe_to_namespace('planned_trajectory', self._on_trajectory_change)
        
        # Subscribe to sensor state changes for robot state updates
        self.memory.subscribe_to_namespace('sensor_state', self._on_sensor_state_change)
    
    def _initialize(self) -> bool:
        try:
            self.logger.info("Initializing Plan module...")
            
            # Initialize motion plan in memory
            self.memory.update('planned_trajectory', 'current_plan', self.current_motion_plan)
            
            # Set up planning context
            self._initialize_planning_context()
            
            self.logger.info("Plan module initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Plan module: {e}")
            return False
    
    def _initialize_planning_context(self):
        """Initialize planning context with default values"""
        try:
            # Get current robot state
            robot_state = self.memory.get('sensor_state', 'robot_state')
            
            if robot_state and isinstance(robot_state, RobotState):
                if robot_state.end_effector_pose:
                    self.planning_context.current_position = robot_state.end_effector_pose.position.copy()
                    self.planning_context.current_orientation = robot_state.end_effector_pose.orientation.copy()
                
                if robot_state.joint_state:
                    self.planning_context.current_joint_positions = robot_state.joint_state.positions.copy()
                
                self.planning_context.gripper_state = robot_state.gripper_state
                self.planning_context.is_moving = robot_state.is_moving
            else:
                # Set default values
                self.planning_context.current_position = np.array([0.5, 0.0, 0.5])
                self.planning_context.current_orientation = np.array([0, 0, 0, 1])
                self.planning_context.current_joint_positions = np.zeros(6)
                self.planning_context.gripper_state = 0.0
                self.planning_context.is_moving = False
            
            # Set workspace bounds
            self.planning_context.workspace_min = np.array([0.1, -0.5, 0.1])
            self.planning_context.workspace_max = np.array([0.8, 0.5, 0.8])
            
        except Exception as e:
            self.logger.error(f"Error initializing planning context: {e}")
    
    def run(self):
        """Main planning loop"""
        try:
            # Check for new plan requests
            self._check_for_new_requests()
            
            # Process pending requests
            self._process_pending_requests()
            
            # Update current motion plan status
            self._update_motion_plan_status()
            
            # Update memory with current state
            self.memory.update('planned_trajectory', 'current_plan', self.current_motion_plan)
            
            # Sleep based on update rate
            if self.update_rate > 0:
                time.sleep(1.0 / self.update_rate)
            
        except Exception as e:
            self.logger.error(f"Error in planning loop: {e}")
            raise
    
    def _on_trajectory_change(self, key: str, value: Any):
        """Handle changes to planned trajectory namespace"""
        try:
            if key == 'pending_requests' and isinstance(value, list):
                # New plan requests arrived
                self.pending_requests.extend(value)
                self.logger.debug(f"Received {len(value)} new plan requests")
                
        except Exception as e:
            self.logger.error(f"Error handling trajectory change: {e}")
    
    def _on_sensor_state_change(self, key: str, value: Any):
        """Handle sensor state changes"""
        try:
            if key == 'robot_state' and isinstance(value, RobotState):
                # Update planning context with new robot state
                self._update_planning_context(value)
                
        except Exception as e:
            self.logger.error(f"Error handling sensor state change: {e}")
    
    def _update_planning_context(self, robot_state: RobotState):
        """Update planning context with new robot state"""
        try:
            if robot_state.end_effector_pose:
                self.planning_context.current_position = robot_state.end_effector_pose.position.copy()
                self.planning_context.current_orientation = robot_state.end_effector_pose.orientation.copy()
            
            if robot_state.joint_state:
                self.planning_context.current_joint_positions = robot_state.joint_state.positions.copy()
            
            self.planning_context.gripper_state = robot_state.gripper_state
            self.planning_context.is_moving = robot_state.is_moving
            self.planning_context.emergency_stop = robot_state.emergency_stop
            
        except Exception as e:
            self.logger.error(f"Error updating planning context: {e}")
    
    def _check_for_new_requests(self):
        """Check memory for new plan requests"""
        try:
            # Get pending requests from memory
            pending_from_memory = self.memory.get('planned_trajectory', 'pending_requests', [])
            
            if pending_from_memory:
                # Add to our pending list
                self.pending_requests.extend(pending_from_memory)
                
                # Clear from memory to prevent reprocessing
                self.memory.update('planned_trajectory', 'pending_requests', [])
                
                self.logger.debug(f"Retrieved {len(pending_from_memory)} requests from memory")
            
        except Exception as e:
            self.logger.error(f"Error checking for new requests: {e}")
    
    def _process_pending_requests(self):
        """Process all pending plan requests"""
        try:
            if not self.pending_requests:
                return
            
            # Check for emergency stop
            if self.planning_context.emergency_stop:
                self.logger.warning("Emergency stop active - clearing all pending requests")
                self.pending_requests.clear()
                self.current_motion_plan.status = PlanningStatus.FAILED
                return
            
            # Process requests one by one
            processed_requests = []
            
            for request in self.pending_requests:
                try:
                    # Check if request is still valid
                    if self._is_request_expired(request):
                        self.logger.debug("Skipping expired request")
                        processed_requests.append(request)
                        continue
                    
                    # Plan for this request
                    start_time = time.time()
                    response = self._plan_for_request(request)
                    planning_time = time.time() - start_time
                    
                    # Update statistics
                    self.planning_times.append(planning_time)
                    if len(self.planning_times) > 100:  # Keep last 100 times
                        self.planning_times.pop(0)
                    
                    if response and response.success:
                        self.success_count += 1
                        self._update_current_trajectory(response.trajectory)
                        self.logger.debug(f"Successfully planned trajectory in {planning_time:.3f}s")
                    else:
                        self.failure_count += 1
                        self.logger.warning(f"Planning failed for request: {response.error_message if response else 'No response'}")
                    
                    processed_requests.append(request)
                    
                except Exception as e:
                    self.logger.error(f"Error processing request: {e}")
                    processed_requests.append(request)
                    self.failure_count += 1
            
            # Remove processed requests
            for req in processed_requests:
                if req in self.pending_requests:
                    self.pending_requests.remove(req)
            
        except Exception as e:
            self.logger.error(f"Error processing pending requests: {e}")
    
    def _is_request_expired(self, request: PlanRequest, max_age: float = 2.0) -> bool:
        """Check if a plan request has expired"""
        return request.age() > max_age
    
    def _plan_for_request(self, request: PlanRequest) -> Optional[PlanResponse]:
        """Plan a trajectory for a specific request"""
        try:
            response = PlanResponse()
            response.request_id = str(id(request))  # Simple ID generation
            
            planning_start = time.time()
            
            # Choose planning algorithm
            if self.planning_algorithm == 'simple':
                trajectory = self._simple_planning(request)
            elif self.planning_algorithm == 'advanced':
                trajectory = self._advanced_planning(request)
            else:
                trajectory = self._simple_planning(request)  # Default fallback
            
            planning_time = time.time() - planning_start
            
            if trajectory:
                response.trajectory = trajectory
                response.success = True
                response.planning_time = planning_time
                self.logger.debug(f"Generated trajectory with {len(trajectory.waypoints)} waypoints")
            else:
                response.success = False
                response.error_message = "Failed to generate trajectory"
                response.planning_time = planning_time
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error during planning: {e}")
            response = PlanResponse()
            response.success = False
            response.error_message = str(e)
            return response
    
    def _simple_planning(self, request: PlanRequest) -> Optional[Trajectory]:
        """Simple trajectory planning algorithm"""
        try:
            trajectory = Trajectory()
            
            # Handle different types of movements
            movement_type = request.constraints.get('movement_type', 'linear')
            
            if movement_type == 'linear':
                return self._plan_linear_movement(request)
            elif movement_type == 'angular':
                return self._plan_angular_movement(request)
            elif movement_type == 'gripper':
                return self._plan_gripper_movement(request)
            elif movement_type == 'special':
                return self._plan_special_movement(request)
            else:
                # Default linear movement
                return self._plan_linear_movement(request)
            
        except Exception as e:
            self.logger.error(f"Error in simple planning: {e}")
            return None
    
    def _plan_linear_movement(self, request: PlanRequest) -> Optional[Trajectory]:
        """Plan linear movement trajectory"""
        try:
            current_pos = self.planning_context.current_position
            current_ori = self.planning_context.current_orientation
            
            if request.target_position is not None:
                target_pos = request.target_position
            else:
                # No target specified, can't plan
                return None
            
            target_ori = request.target_orientation if request.target_orientation is not None else current_ori
            
            # Check workspace bounds
            if not self._is_position_safe(target_pos):
                self.logger.warning("Target position is outside safe workspace")
                return None
            
            # Generate simple linear trajectory
            trajectory = self.trajectory_generator.generate_linear_trajectory(
                start_position=current_pos,
                end_position=target_pos,
                start_orientation=current_ori,
                end_orientation=target_ori,
                duration=0.1,  # Fast for continuous control
                steps=2
            )
            
            return trajectory
            
        except Exception as e:
            self.logger.error(f"Error planning linear movement: {e}")
            return None
    
    def _plan_angular_movement(self, request: PlanRequest) -> Optional[Trajectory]:
        """Plan angular movement trajectory"""
        try:
            current_pos = self.planning_context.current_position
            current_ori = self.planning_context.current_orientation
            
            # Extract rotation information from constraints
            rotation_axis = request.constraints.get('rotation_axis')
            rotation_angle = request.constraints.get('rotation_angle', 0.0)
            
            if rotation_axis is None or rotation_angle == 0:
                return None
            
            # Calculate target orientation
            target_ori = self._apply_rotation(current_ori, rotation_axis, rotation_angle)
            
            # Generate rotation trajectory
            trajectory = self.trajectory_generator.generate_rotation_trajectory(
                position=current_pos,
                start_orientation=current_ori,
                end_orientation=target_ori,
                duration=0.1,
                steps=2
            )
            
            return trajectory
            
        except Exception as e:
            self.logger.error(f"Error planning angular movement: {e}")
            return None
    
    def _plan_gripper_movement(self, request: PlanRequest) -> Optional[Trajectory]:
        """Plan gripper movement"""
        try:
            gripper_action = request.constraints.get('gripper_action', 'toggle')
            gripper_target = request.constraints.get('gripper_target')
            
            # Determine target gripper position
            if gripper_target is not None:
                target_gripper = gripper_target
            elif gripper_action == 'toggle':
                # Toggle between open and closed
                target_gripper = 1.0 if self.planning_context.gripper_state < 0.5 else 0.0
            elif gripper_action == 'open':
                target_gripper = 1.0
            elif gripper_action == 'close':
                target_gripper = 0.0
            else:
                return None
            
            # Create simple gripper trajectory
            trajectory = Trajectory()
            trajectory.status = PlanningStatus.READY
            
            # Add gripper command
            from models.control_commands import GripperCommand
            gripper_command = GripperCommand(
                position=target_gripper,
                force=1.0
            )
            
            # Store in trajectory metadata for now
            trajectory.metadata = {
                'gripper_command': gripper_command,
                'movement_type': 'gripper'
            }
            
            return trajectory
            
        except Exception as e:
            self.logger.error(f"Error planning gripper movement: {e}")
            return None
    
    def _plan_special_movement(self, request: PlanRequest) -> Optional[Trajectory]:
        """Plan special movement (home, reset, presets)"""
        try:
            special_command = request.constraints.get('special_command')
            
            if special_command == 'home':
                # Move to home position
                home_position = np.array([0.5, 0.0, 0.5])
                home_orientation = np.array([0, 0, 0, 1])
                
                trajectory = self.trajectory_generator.generate_linear_trajectory(
                    start_position=self.planning_context.current_position,
                    end_position=home_position,
                    start_orientation=self.planning_context.current_orientation,
                    end_orientation=home_orientation,
                    duration=2.0,  # Slower for safety
                    steps=10
                )
                
                return trajectory
                
            elif special_command == 'reset':
                # Stop all movement
                trajectory = Trajectory()
                trajectory.status = PlanningStatus.READY
                trajectory.metadata = {
                    'special_command': 'reset',
                    'movement_type': 'special'
                }
                return trajectory
                
            elif special_command.startswith('preset_'):
                # Handle preset positions
                preset_positions = {
                    'preset_1': (np.array([0.6, 0.2, 0.4]), np.array([0, 0, 0, 1])),
                    'preset_2': (np.array([0.6, -0.2, 0.4]), np.array([0, 0, 0, 1])),
                    'preset_3': (np.array([0.4, 0.0, 0.6]), np.array([0, 0, 0, 1]))
                }
                
                if special_command in preset_positions:
                    target_pos, target_ori = preset_positions[special_command]
                    
                    trajectory = self.trajectory_generator.generate_linear_trajectory(
                        start_position=self.planning_context.current_position,
                        end_position=target_pos,
                        start_orientation=self.planning_context.current_orientation,
                        end_orientation=target_ori,
                        duration=1.5,
                        steps=8
                    )
                    
                    return trajectory
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error planning special movement: {e}")
            return None
    
    def _advanced_planning(self, request: PlanRequest) -> Optional[Trajectory]:
        """Advanced trajectory planning (placeholder for future implementation)"""
        self.logger.debug("Advanced planning not implemented, falling back to simple planning")
        return self._simple_planning(request)
    
    def _is_position_safe(self, position: np.ndarray) -> bool:
        """Check if position is within safe workspace bounds"""
        try:
            if len(position) != 3:
                return False
            
            within_bounds = np.all(position >= self.planning_context.workspace_min) and \
                           np.all(position <= self.planning_context.workspace_max)
            
            return within_bounds
            
        except Exception as e:
            self.logger.error(f"Error checking position safety: {e}")
            return False
    
    def _apply_rotation(self, current_orientation: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
        """Apply rotation to current orientation (simplified)"""
        # This is a simplified implementation
        # In practice, you'd want proper quaternion rotation
        try:
            # For now, just return the current orientation with small modification
            # This should be replaced with proper quaternion math
            result = current_orientation.copy()
            
            # Simple approximation - modify quaternion slightly based on axis and angle
            if len(axis) == 3:
                # Convert to small quaternion rotation and combine
                # This is a placeholder - real implementation would use proper quaternion operations
                small_rotation = np.array([axis[0] * angle * 0.1, 
                                         axis[1] * angle * 0.1, 
                                         axis[2] * angle * 0.1, 
                                         1.0])
                small_rotation = small_rotation / np.linalg.norm(small_rotation)
                
                # Simple quaternion "multiplication" (this is not mathematically correct)
                # Replace with proper quaternion multiplication in real implementation
                result = result * 0.9 + small_rotation * 0.1
                result = result / np.linalg.norm(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error applying rotation: {e}")
            return current_orientation
    
    def _update_current_trajectory(self, trajectory: Trajectory):
        """Update current motion plan with new trajectory"""
        try:
            self.current_motion_plan.current_trajectory = trajectory
            self.current_motion_plan.status = PlanningStatus.READY
            self.current_motion_plan.execution_progress = 0.0
            
        except Exception as e:
            self.logger.error(f"Error updating current trajectory: {e}")
    
    def _update_motion_plan_status(self):
        """Update motion plan execution status"""
        try:
            # This would be updated based on feedback from the Act module
            # For now, just manage basic status
            
            if self.current_motion_plan.current_trajectory:
                if self.current_motion_plan.status == PlanningStatus.READY:
                    # Check if trajectory should be marked as executing
                    pass
                elif self.current_motion_plan.status == PlanningStatus.EXECUTING:
                    # Check if trajectory is complete
                    pass
            
        except Exception as e:
            self.logger.error(f"Error updating motion plan status: {e}")
    
    def get_current_plan(self) -> MotionPlan:
        """Get current motion plan"""
        return self.current_motion_plan
    
    def get_planning_stats(self) -> Dict[str, Any]:
        """Get planning performance statistics"""
        avg_time = np.mean(self.planning_times) if self.planning_times else 0
        total_requests = self.success_count + self.failure_count
        success_rate = self.success_count / total_requests if total_requests > 0 else 0
        
        return {
            'total_requests': total_requests,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'success_rate': success_rate,
            'avg_planning_time': avg_time,
            'pending_requests': len(self.pending_requests)
        }
    
    def cleanup(self):
        """Cleanup plan module"""
        try:
            self.logger.info("Cleaning up Plan module...")
            
            # Clear pending requests
            self.pending_requests.clear()
            
            # Stop any active planning
            self.is_planning = False
            
            self.logger.info("Plan module cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Plan module cleanup: {e}")