# Mouse End-Effector Control System

## Overview

This system provides **real-time inverse kinematics control** of the robot's end-effector using mouse input. Move the mouse to control X/Y position, use scroll wheel for Z-axis control.

## Features

🎮 **Intuitive Mouse Control**
- Mouse X/Y movement → End-effector X/Y position in workspace
- Mouse scroll wheel → End-effector Z position (up/down)
- Real-time visual feedback in MuJoCo viewer

🧮 **Advanced Inverse Kinematics**
- Fast Jacobian-based IK solver for real-time performance
- Optimization-based fallback for complex poses
- Workspace safety limits and collision avoidance

⚡ **Real-time Performance**
- 50-100Hz control update rate
- Sub-millisecond IK solving (Jacobian method)
- Smooth trajectory generation with filtering

🛡️ **Safety Features**
- Joint limit enforcement
- Workspace boundary checks
- Velocity limiting
- Emergency stop functionality

## Quick Start

### 1. Basic Testing
```bash
# Test inverse kinematics components
uv run test_mouse_endeffector_control.py

# Test full system integration
uv run test_mouse_ik_system.py
```

### 2. Run with MuJoCo Viewer
```bash
# Launch with visual feedback
./run_with_display.sh

# Or with monitoring
uv run test_with_viewer.py
```

### 3. Manual System Start
```bash
# Start system and control manually
uv run main.py
```

## Controls

### Mouse Controls
- **Mouse Movement**: End-effector X/Y positioning
  - Move mouse right → End-effector moves right (X+)
  - Move mouse left → End-effector moves left (X-)
  - Move mouse up → End-effector moves forward (Y+)
  - Move mouse down → End-effector moves backward (Y-)

- **Mouse Scroll**: End-effector Z positioning
  - Scroll up → End-effector moves up (Z+)
  - Scroll down → End-effector moves down (Z-)

### Keyboard Controls (Legacy)
- **W/A/S/D**: Joint-based movement
- **Q/E**: Up/Down movement
- **Arrow Keys**: Rotation
- **Space**: Gripper toggle
- **ESC**: Emergency stop

## Configuration

### Mouse Control Settings (`config.yaml`)
```yaml
input:
  # Enable mouse end-effector control
  enable_end_effector_control: true
  
  # Screen/workspace mapping
  screen_width: 1920
  screen_height: 1080
  workspace_width: 1.2    # meters
  workspace_height: 1.2   # meters
  workspace_center: [0.4, 0.0, 0.4]  # robot coordinates
  
  # Control sensitivity
  position_sensitivity: 1.0
  scroll_sensitivity: 0.02  # meters per scroll unit
  
  # Smoothing
  enable_smoothing: true
  smoothing_factor: 0.7
```

### Inverse Kinematics Settings
```yaml
act:
  # End-effector control parameters
  control_frequency: 100        # Hz
  position_tolerance: 0.005     # 5mm
  max_joint_velocity: 2.0       # rad/s
  use_jacobian_ik: true         # Fast IK method
  enable_safety_checks: true
  workspace_margin: 0.05        # 5cm safety margin
  
  # IK solver parameters
  kinematics:
    max_iterations: 100
    position_tolerance: 0.001   # 1mm
    orientation_tolerance: 0.01
```

## Technical Details

### Architecture
```
Mouse Input → MouseController → EndEffectorController → InverseKinematics
     ↓              ↓                    ↓                    ↓
Input Module → Memory → Act Module → Joint Commands → MuJoCo Adapter
     ↓              ↓         ↓              ↓              ↓
Visual Feedback ← Monitoring ← Robot State ← Sensor Reader ← MuJoCo Sim
```

### Coordinate Systems
- **Screen Coordinates**: 
  - Standard: Pixel coordinates (0,0) = top-left
  - MuJoCo Viewer: Centered coordinates (0,0) = center of viewer
  - System automatically detects and handles both coordinate systems
- **Workspace Coordinates**: Robot base frame (meters)
  - X: Forward/backward from robot base
  - Y: Left/right from robot base  
  - Z: Up/down from robot base

### Inverse Kinematics Methods

1. **Jacobian IK** (Primary - Fast)
   - Iterative gradient descent
   - ~20 iterations max
   - 0.1-1ms solve time
   - Best for real-time control

2. **Optimization IK** (Fallback - Robust)
   - Scipy optimization (L-BFGS-B)
   - Multiple initial guesses
   - 1-5ms solve time
   - Better for complex poses

## Performance Metrics

### Real-time Performance
- **Control Loop**: 100Hz
- **IK Solve Time**: <1ms (Jacobian), <5ms (Optimization)
- **End-to-End Latency**: ~10ms (mouse → robot)
- **Position Accuracy**: ±1mm

### Workspace Specifications
- **Reach**: ~1.2m radius from base
- **Precision**: 1mm positioning accuracy
- **Speed**: Up to 2 rad/s joint velocities
- **Safety**: Automatic limit enforcement

## Troubleshooting

### Common Issues

1. **No mouse response**
   - Check `enable_end_effector_control: true` in config
   - Verify display environment variables
   - Check mouse permissions

2. **IK failures**
   - Target may be outside workspace
   - Check joint limits in config
   - Reduce `max_joint_velocity` if moving too fast

3. **Jittery movement**
   - Increase `smoothing_factor` (0.7-0.9)
   - Reduce `position_sensitivity`
   - Lower control frequency

4. **System not starting**
   - Check dependencies: `uv install`
   - Verify MuJoCo installation
   - Check config file syntax

### Debug Commands
```bash
# Test IK solver independently
python -c "from modules.kinematics.inverse_kinematics import InverseKinematics; ik=InverseKinematics(); print('IK OK')"

# Test mouse controller
python -c "from modules.input.mouse_control import MouseEndEffectorController; print('Mouse OK')"

# Check system status
uv run debug_adapter.py

# Monitor system logs
tail -f system.log  # if logging to file
```

## Development

### Adding Custom IK Solvers
1. Extend `InverseKinematics` class
2. Implement `solve_ik()` method
3. Register in `EndEffectorController`

### Custom Mouse Mappings
1. Modify `MouseEndEffectorController`
2. Update workspace limits
3. Adjust sensitivity parameters

### Integration with Other Inputs
1. Add input handler in `input_module.py`
2. Create control mapping
3. Register with memory system

## Examples

### Simple Position Control
```python
from modules.input.mouse_control import MouseEndEffectorController
controller = MouseEndEffectorController()

# Set target from mouse position
target = controller.update_from_mouse(960, 540)  # Screen center
print(f"Target: {target}")  # Robot workspace coordinates
```

### Direct IK Usage
```python
from modules.kinematics.inverse_kinematics import InverseKinematics
ik = InverseKinematics()

# Solve for target position
target_pos = [0.5, 0.2, 0.4]  # meters
joints, success = ik.inverse_kinematics(target_pos)
print(f"Solution: {joints}, Success: {success}")
```

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Run the test suite to verify functionality
3. Check system logs for detailed error messages
4. Verify configuration settings match your setup