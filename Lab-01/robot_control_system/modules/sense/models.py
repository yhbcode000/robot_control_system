from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import numpy as np
import time
from enum import Enum

from modules.input.models import ParsedCommand


class InterpretationType(Enum):
    LINEAR_MOVEMENT = "linear_movement"
    ANGULAR_MOVEMENT = "angular_movement"
    GRIPPER_CONTROL = "gripper_control"
    CAMERA_CONTROL = "camera_control"
    EMERGENCY_STOP = "emergency_stop"
    SPECIAL_COMMAND = "special_command"


@dataclass
class InterpretedInput:
    """Represents an interpreted input command with semantic meaning"""
    original_command: ParsedCommand
    movement_type: str = ""  # linear, angular, gripper, camera, special, emergency
    
    # Linear movement properties
    direction_vector: Optional[np.ndarray] = None  # 3D direction vector
    
    # Angular movement properties  
    rotation_axis: Optional[np.ndarray] = None     # 3D axis of rotation
    rotation_angle: float = 0.0                    # Rotation angle in radians
    
    # Gripper properties
    gripper_action: Optional[str] = None           # open, close, toggle
    gripper_target: Optional[float] = None         # 0.0 = closed, 1.0 = open
    
    # Camera properties
    camera_action: Optional[str] = None            # zoom_in, zoom_out, rotate, etc.
    
    # Special command properties
    special_command: Optional[str] = None          # reset, home, preset_1, etc.
    is_special_command: bool = False
    
    # General properties
    magnitude: float = 1.0                         # Command strength (0.0 - 1.0)
    is_continuous: bool = False                    # Whether command should repeat
    is_emergency_stop: bool = False                # Emergency stop flag
    confidence: float = 1.0                        # Confidence in interpretation (0.0 - 1.0)
    priority: str = "normal"                       # normal, high, critical
    
    # Metadata
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
        """Check if the interpreted input is valid"""
        if self.confidence <= 0:
            return False
        if self.magnitude < 0:
            return False
        if self.movement_type not in ['linear', 'angular', 'gripper', 'camera', 'special', 'emergency']:
            return False
        return True
    
    def age(self) -> float:
        """Get age of the input in seconds"""
        return time.time() - self.timestamp
    
    def is_expired(self, max_age: float = 1.0) -> bool:
        """Check if input has expired"""
        return self.age() > max_age


@dataclass
class SenseState:
    """Current state of the sense module"""
    active_interpreted_inputs: List[InterpretedInput] = field(default_factory=list)
    has_active_input: bool = False
    last_input_time: float = 0.0
    
    # Input processing statistics
    total_inputs_processed: int = 0
    successful_interpretations: int = 0
    failed_interpretations: int = 0
    
    # Current context
    current_mode: str = "normal"                   # normal, emergency, degraded
    input_sensitivity: float = 1.0                # Global input sensitivity multiplier
    
    # State flags
    is_emergency_active: bool = False
    is_input_timeout: bool = False
    last_update_time: float = field(default_factory=time.time)
    
    def update_stats(self, success: bool):
        """Update processing statistics"""
        self.total_inputs_processed += 1
        if success:
            self.successful_interpretations += 1
        else:
            self.failed_interpretations += 1
    
    def get_success_rate(self) -> float:
        """Get input interpretation success rate"""
        if self.total_inputs_processed == 0:
            return 1.0
        return self.successful_interpretations / self.total_inputs_processed
    
    def get_active_movements(self) -> List[str]:
        """Get list of active movement types"""
        return [inp.movement_type for inp in self.active_interpreted_inputs if inp.movement_type]
    
    def has_emergency_input(self) -> bool:
        """Check if any active input is emergency stop"""
        return any(inp.is_emergency_stop for inp in self.active_interpreted_inputs)
    
    def has_movement_input(self) -> bool:
        """Check if any active input is movement-related"""
        movement_types = ['linear', 'angular']
        return any(inp.movement_type in movement_types for inp in self.active_interpreted_inputs)
    
    def get_combined_direction(self) -> Optional[np.ndarray]:
        """Get combined direction vector from all linear movements"""
        linear_inputs = [inp for inp in self.active_interpreted_inputs 
                        if inp.movement_type == 'linear' and inp.direction_vector is not None]
        
        if not linear_inputs:
            return None
        
        combined = np.zeros(3)
        for inp in linear_inputs:
            combined += inp.direction_vector * inp.magnitude
        
        # Normalize if needed
        magnitude = np.linalg.norm(combined)
        if magnitude > 0:
            return combined / magnitude
        return None


@dataclass
class SensorInterpretation:
    """Interpretation of sensor data"""
    sensor_type: str                               # force, proximity, camera, etc.
    raw_data: Any                                 # Raw sensor reading
    interpreted_data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    alerts: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    
    def add_alert(self, alert: str):
        """Add an alert for this sensor interpretation"""
        if alert not in self.alerts:
            self.alerts.append(alert)


@dataclass
class ContextualState:
    """Contextual information for better input interpretation"""
    robot_is_moving: bool = False
    current_task: Optional[str] = None
    obstacle_detected: bool = False
    gripper_state: float = 0.0                    # 0.0 = closed, 1.0 = open
    
    # Environmental context
    workspace_bounds: Optional[Dict[str, float]] = None
    safety_zones: List[Dict[str, Any]] = field(default_factory=list)
    
    # User context
    user_skill_level: str = "beginner"            # beginner, intermediate, expert
    control_mode: str = "position"                # position, velocity, force
    
    def is_safe_to_move(self, direction: np.ndarray) -> bool:
        """Check if movement in given direction is safe"""
        # Implement safety checking logic
        if self.obstacle_detected:
            return False
        
        # Check workspace bounds if available
        if self.workspace_bounds:
            # This would need current position to properly check
            # For now, just return True
            pass
        
        return True
    
    def get_scaled_magnitude(self, base_magnitude: float) -> float:
        """Get scaled magnitude based on user skill level"""
        skill_scales = {
            "beginner": 0.3,
            "intermediate": 0.7,
            "expert": 1.0
        }
        return base_magnitude * skill_scales.get(self.user_skill_level, 0.5)


@dataclass
class InputHistory:
    """Historical record of input interpretations"""
    inputs: List[InterpretedInput] = field(default_factory=list)
    max_size: int = 100
    
    def add_input(self, input_data: InterpretedInput):
        """Add input to history"""
        self.inputs.append(input_data)
        
        # Limit size
        if len(self.inputs) > self.max_size:
            self.inputs.pop(0)
    
    def get_recent_inputs(self, time_window: float = 5.0) -> List[InterpretedInput]:
        """Get inputs from recent time window"""
        current_time = time.time()
        return [inp for inp in self.inputs 
                if current_time - inp.timestamp <= time_window]
    
    def get_movement_pattern(self) -> Dict[str, int]:
        """Analyze recent movement patterns"""
        recent = self.get_recent_inputs()
        pattern = {}
        
        for inp in recent:
            movement_type = inp.movement_type
            if movement_type in pattern:
                pattern[movement_type] += 1
            else:
                pattern[movement_type] = 1
        
        return pattern
    
    def clear_old_entries(self, max_age: float = 60.0):
        """Clear old entries beyond max_age"""
        current_time = time.time()
        self.inputs = [inp for inp in self.inputs 
                      if current_time - inp.timestamp <= max_age]