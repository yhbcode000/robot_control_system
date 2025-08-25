# Modular Robot Control System - Development Guide

## Project Overview
A modular robot control system with shared memory architecture. Each module operates in its own thread and communicates through a global singleton memory store. The system controls a robot arm in MuJoCo simulator using keyboard and mouse inputs.

## Key Architecture Principles
- **Thread-safe singleton memory**: Global memory store with observable pattern
- **Modular design**: Each module runs in its own thread with heartbeat mechanism
- **Watchdog monitoring**: Critical module that monitors all other modules' health
- **Event-driven communication**: Modules react to memory changes
- **Graceful degradation**: System can operate at reduced capacity when modules fail

## Module Priority Order
1. **Watchdog Module** - MUST be implemented first (monitors all other modules)
2. Core Infrastructure (memory, logging, base classes)
3. Input Module
4. Sense Module
5. Plan Module
6. Act Module
7. Output Module

## Critical Implementation Details

### Testing Requirements
- ALWAYS check for existing test commands before running tests
- Look for test scripts in package.json, Makefile, or pyproject.toml
- Never assume pytest or specific test frameworks without checking

### Code Style Requirements
- NO comments unless explicitly requested
- Follow existing code conventions in the codebase
- Check existing imports and dependencies before adding new ones
- Use type hints for all function parameters and returns
- Keep module responsibilities clearly separated

### Thread Safety Requirements
- All memory writes must use locks
- Memory reads should be lock-free when possible
- Each module must send heartbeats at configured intervals
- Modules must handle shutdown signals gracefully

## Watchdog Module - Critical Component

### Health Monitoring Implementation
```python
class ThreadHealth:
    thread_id: str
    status: Enum  # HEALTHY, DEGRADED, FROZEN, DEAD
    last_heartbeat: float
    consecutive_misses: int
    cpu_usage: float
    memory_usage: float
    response_time: float
```

### Recovery Strategies
- **RESTART**: Kill and restart thread
- **RESET**: Reset module state, keep thread
- **DEGRADE**: Reduce functionality
- **ISOLATE**: Disconnect from system
- **EMERGENCY_STOP**: Stop entire system

### Failure Detection Rules
- No heartbeat for > timeout → FROZEN
- Exception in thread → DEAD
- Processing time > threshold → DEGRADED
- Memory usage increasing → MEMORY_LEAK
- Queue size > limit → OVERLOADED

## Memory Structure
```
GlobalMemory
├── input_buffer      # Raw keyboard/mouse inputs
├── sensor_state      # Current robot state
├── planned_trajectory # Motion planning output
├── action_commands   # Control commands
├── output_signals    # Formatted signals for adapter
├── system_status     # Overall system state
└── health_status     # Module health metrics
    ├── thread_health
    ├── module_metrics
    └── system_metrics
```

## Development Commands

### Project Setup
```bash
# Initialize project with uv
uv init robot_control_system
cd robot_control_system

# Add all required dependencies
uv add mujoco pygame pynput hydra-core omegaconf colorlog dataclasses-json pydantic typing-extensions numpy
```

### Running the System
```bash
# Default configuration
uv run python main.py

# Override configurations
uv run python main.py modules.plan.algorithm=advanced adapter.render=false

# Disable specific modules
uv run python main.py modules.bridge.enabled=false
```

### Testing
```bash
# Run all tests
uv run pytest tests/

# Run specific test module
uv run pytest tests/test_watchdog/

# Run with coverage
uv run pytest --cov=robot_control_system tests/
```

## File Structure Requirements

### Each Module Directory Must Contain:
1. `__init__.py` - Package initialization
2. `{module}_module.py` - Main module implementation
3. `models.py` - Module-specific data models
4. Additional support files as needed

### Base Module Class Pattern
Every module MUST inherit from BaseModule and implement:
- `run()` method for main logic
- Heartbeat sending
- Error handling and reporting
- Clean shutdown handling

## Configuration Management

### Hydra Configuration Structure
- System-level settings (update rates, memory size)
- Module-specific settings (each with enable flag and heartbeat_interval)
- Adapter configuration (type, model path, render settings)
- Logging configuration (level, formatting)

### Configuration Override Priority
1. Command-line arguments (highest priority)
2. Environment variables
3. config.yaml file (lowest priority)

## Error Handling Guidelines

### Module Failures
- Log error with full traceback
- Update error_count in memory
- Send error report to watchdog
- Attempt recovery based on strategy
- Graceful degradation if recovery fails

### System-wide Failures
- Emergency stop capability
- State preservation before shutdown
- Clear error reporting to user
- Automatic restart attempts (configurable)

## Performance Requirements

### Threading
- Each module runs in dedicated thread
- Non-blocking operations preferred
- Message queues for inter-module communication
- Configurable update rates per module

### Memory Management
- Circular buffers for time-series data
- Automatic old data pruning
- Memory leak detection by watchdog
- Resource usage monitoring

## Robot Control Mappings

### Keyboard Controls
- **W/S**: Forward/backward movement
- **A/D**: Left/right movement
- **Q/E**: Up/down movement
- **Arrow Keys**: End-effector rotation
- **Space**: Gripper control
- **ESC**: Emergency stop

### Mouse Controls
- **Left Click + Drag**: Direct positioning
- **Right Click + Drag**: Camera control
- **Scroll**: Zoom control

## Testing Strategy

### Unit Tests Required
- Memory singleton thread safety
- Module heartbeat mechanism
- Watchdog failure detection
- Recovery strategy execution
- Message passing between modules

### Integration Tests Required
- Full pipeline data flow
- Multi-module failure scenarios
- System degradation modes
- Performance under load
- Resource leak detection

## Common Pitfalls to Avoid
1. Don't assume test frameworks - always check first
2. Don't create modules without heartbeat mechanism
3. Don't skip watchdog implementation - it's critical
4. Don't use blocking operations in module run loops
5. Don't forget thread cleanup on shutdown

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Project setup with uv
- [ ] Global singleton memory implementation
- [ ] Thread-safe logging system
- [ ] Base module class with heartbeat
- [ ] Basic configuration with Hydra

### Phase 2: Watchdog System
- [ ] Health monitoring implementation
- [ ] Failure detection logic
- [ ] Recovery strategy execution
- [ ] Metrics collection
- [ ] System health scoring

### Phase 3: Module Pipeline
- [ ] Input module (keyboard/mouse)
- [ ] Sense module (data parsing)
- [ ] Plan module (trajectory generation)
- [ ] Act module (command generation)
- [ ] Output module (signal formatting)

### Phase 4: Integration
- [ ] MuJoCo adapter
- [ ] Module registration with watchdog
- [ ] Full system testing
- [ ] Performance optimization
- [ ] Documentation

## Debug Mode Features
When `debug: true` in config:
- Verbose logging for all modules
- Memory state dumping
- Thread state visualization
- Performance profiling
- Simulated failure injection

## Extension Points
1. New modules: Inherit from BaseModule
2. New adapters: Implement BaseAdapter interface
3. New algorithms: Add to module strategies
4. New data models: Extend base message classes
5. External integrations: Use adapter pattern

## Code Review Checklist
Before committing any module:
- [ ] Inherits from BaseModule
- [ ] Implements heartbeat mechanism
- [ ] Has proper error handling
- [ ] Includes unit tests
- [ ] Thread-safe memory operations
- [ ] Graceful shutdown handling
- [ ] Logging at appropriate levels
- [ ] Type hints on all methods
- [ ] No hardcoded values (use config)
- [ ] Documentation in docstrings