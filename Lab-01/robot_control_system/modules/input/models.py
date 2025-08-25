from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum
import time


class InputType(Enum):
    KEYBOARD = "keyboard"
    MOUSE = "mouse"


class CommandType(Enum):
    MOVEMENT = "movement"
    ROTATION = "rotation"
    GRIPPER = "gripper"
    EMERGENCY_STOP = "emergency_stop"
    CAMERA = "camera"
    SPECIAL = "special"


@dataclass
class ParsedCommand:
    command_type: CommandType
    direction: Optional[str] = None  # forward, backward, left, right, up, down
    magnitude: float = 1.0  # 0.0 to 1.0
    is_continuous: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class InputBuffer:
    keyboard_state: Dict[str, bool] = field(default_factory=dict)
    mouse_position: tuple = (0, 0)
    mouse_buttons: Dict[str, bool] = field(default_factory=dict)
    active_commands: Dict[str, ParsedCommand] = field(default_factory=dict)
    mouse_inputs: list = field(default_factory=list)  # Store recent mouse inputs with metadata
    last_update: float = field(default_factory=time.time)