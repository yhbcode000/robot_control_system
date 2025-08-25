# API Reference

Complete API documentation for the Robot Control System.

## 🏗️ Core Components

### [Memory System](./memory.md)
Thread-safe singleton memory system with namespace isolation.

```python
from core.memory import MemoryStore

memory = MemoryStore()
memory.write("robot", "position", [0.0, 0.0, 0.0])
position = memory.read("robot", "position")
```

### [Base Classes](./base.md)
Foundation classes for all system modules.

```python
from core.base import BaseModule

class CustomModule(BaseModule):
    def process(self, data):
        # Custom processing logic
        pass
```

## 🔧 Modules

### [Watchdog Module](./watchdog.md)
Health monitoring and system diagnostics.

```python
from modules.watchdog import WatchdogModule

watchdog = WatchdogModule()
health_score = watchdog.get_health_score()
```

### [Input Module](./input.md)
Keyboard and mouse input handling.

```python
from modules.input import InputModule

input_module = InputModule()
commands = input_module.get_commands()
```

### [Sense Module](./sense.md)
Input parsing and command validation.

```python
from modules.sense import SenseModule

sense = SenseModule()
parsed_command = sense.parse_input(raw_input)
```

### [Plan Module](./plan.md)
Trajectory planning and motion generation.

```python
from modules.plan import PlanModule

planner = PlanModule()
trajectory = planner.plan_motion(start, goal)
```

### [Act Module](./act.md)
Command execution and robot control.

```python
from modules.act import ActModule

actor = ActModule()
control_signals = actor.execute_command(command)
```

### [Output Module](./output.md)
Signal formatting and adapter communication.

```python
from modules.output import OutputModule

output = OutputModule()
formatted_signals = output.format_signals(raw_signals)
```

## 🤖 Adapters

### [MuJoCo Adapter](./mujoco.md)
Physics simulation interface for robot control.

```python
from adapters.mujoco_adapter import MujocoAdapter

adapter = MujocoAdapter()
adapter.load_model("assets/robots/arm/ur5e.xml")
adapter.set_joint_positions([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
```

## 📊 Data Models

### [Robot State](./models.md#robot-state)
Current robot configuration and status.

```python
from models.robot_state import RobotState

state = RobotState(
    joint_positions=[0.0] * 6,
    joint_velocities=[0.0] * 6,
    timestamp=time.time()
)
```

### [Control Commands](./models.md#control-commands)
Commands for robot movement and actions.

```python
from models.control_commands import MovementCommand

command = MovementCommand(
    direction="forward",
    magnitude=0.5,
    duration=1.0
)
```

### [Sensor Data](./models.md#sensor-data)
Sensor readings and measurements.

```python
from models.sensor_data import SensorData

sensor_data = SensorData(
    joint_positions=current_positions,
    joint_velocities=current_velocities,
    forces=current_forces
)
```

## 🔧 Utilities

### [Configuration](./config.md)
System configuration management with Hydra.

```python
from hydra import compose, initialize
from omegaconf import OmegaConf

with initialize(config_path="../"):
    cfg = compose(config_name="config")
```

### [Logging](./logging.md)
Structured logging with color support.

```python
from core.logging import get_logger

logger = get_logger(__name__)
logger.info("System started successfully")
```

## 🎯 Quick Reference

### Common Patterns

#### Module Communication
```python
# Write to memory
memory.write("input", "commands", commands)

# Read from memory
commands = memory.read("input", "commands")

# Subscribe to changes
memory.subscribe("input", "commands", callback_function)
```

#### Error Handling
```python
try:
    result = module.process(data)
except ModuleException as e:
    logger.error(f"Module processing failed: {e}")
    # Handle error gracefully
```

#### Configuration Access
```python
@hydra.main(config_path=".", config_name="config")
def main(cfg: DictConfig) -> None:
    update_rate = cfg.system.update_rate
    enable_gui = cfg.system.enable_gui
```

## 📚 Additional Resources

- [System Architecture Overview](../guides/architecture.md)
- [Configuration Guide](../guides/configuration.md)
- [Performance Tuning](../guides/performance.md)
- [Troubleshooting](../guides/troubleshooting.md)