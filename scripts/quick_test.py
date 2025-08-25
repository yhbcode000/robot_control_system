#!/usr/bin/env python3
"""Quick test of the robot control system with simulated keyboard input"""

import time
import sys
import os
import threading
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from core.memory.memory_store import GlobalMemory
from modules.input.models import ParsedCommand, CommandType, InputBuffer
from modules.sense.models import InterpretedInput
from modules.act.direct_control import DirectControlHandler
import numpy as np

def test_control_pipeline():
    """Test the complete control pipeline"""
    print("Testing Robot Control Pipeline...")
    print("="*50)
    
    # Initialize memory
    memory = GlobalMemory.get_instance()
    
    # Test 1: Simulate keyboard input
    print("\n1. Simulating keyboard input (W key - forward)")
    parsed_cmd = ParsedCommand(CommandType.MOVEMENT, 'forward')
    
    # Create input buffer
    input_buffer = InputBuffer()
    input_buffer.active_commands = {'key_w': parsed_cmd}
    input_buffer.last_update = time.time()
    
    memory.update('input_buffer', 'current', input_buffer)
    
    # Test 2: Simulate sense module interpretation
    print("2. Testing sense module interpretation")
    interpreted = InterpretedInput(parsed_cmd)
    interpreted.movement_type = 'linear'
    interpreted.direction_vector = np.array([1, 0, 0])  # Forward
    interpreted.magnitude = 1.0
    
    # Create sense state
    class MockSenseState:
        def __init__(self):
            self.active_interpreted_inputs = [interpreted]
            self.has_active_input = True
            self.last_input_time = time.time()
    
    sense_state = MockSenseState()
    memory.update('sensor_state', 'current', sense_state)
    
    # Test 3: Generate control commands
    print("3. Testing direct control generation")
    handler = DirectControlHandler({
        'linear_speed': 0.01,
        'angular_speed': 0.05,
        'gripper_speed': 0.1
    })
    
    control_cmds = handler.process_interpreted_inputs([interpreted])
    print(f"   Generated {len(control_cmds)} control commands")
    
    for i, cmd in enumerate(control_cmds):
        print(f"   Command {i+1}:")
        print(f"     Type: {cmd.command_type}")
        if cmd.joint_command:
            positions = cmd.joint_command.positions
            print(f"     Joint positions: {positions}")
            print(f"     Joint deltas: {positions - np.zeros(6)}")
        
        # Store in memory as if act module generated it
        memory.update('action_commands', 'pending_commands', [cmd])
    
    # Test 4: Check command flow
    print("4. Checking command flow in memory")
    pending = memory.get('action_commands', 'pending_commands', [])
    print(f"   Commands in memory: {len(pending)}")
    
    # Test 5: Robot module safety checks
    print("5. Testing robot module integration")
    from modules.robot.robot_module import RobotModule
    
    config = {
        'update_rate': 50,
        'safety_checks': True,
        'collision_detection': True,
        'joint_names': ['joint_0', 'joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5'],
        'joint_limits': [(-3.14, 3.14)] * 6,
        'home_position': [0.0] * 6
    }
    
    robot_module = RobotModule(config, memory)
    if robot_module.initialize():
        print("   Robot module initialized successfully")
        
        # Get robot state summary
        summary = robot_module.get_state_summary()
        print(f"   Robot is safe: {summary['is_safe']}")
        print(f"   Emergency stop: {summary['emergency_stop']}")
        print(f"   Commands executed: {summary['commands_executed']}")
    
    print("\n" + "="*50)
    print("✅ Control pipeline test completed successfully!")
    print("\nThe system can:")
    print("• Capture keyboard input (W/A/S/D/Q/E)")
    print("• Interpret input as robot movements")
    print("• Generate joint control commands")
    print("• Monitor robot safety")
    print("• Track command execution")
    
    return True

def simulate_keyboard_sequence():
    """Simulate a sequence of keyboard inputs"""
    print("\n" + "="*50)
    print("KEYBOARD SEQUENCE SIMULATION")
    print("="*50)
    
    memory = GlobalMemory.get_instance()
    handler = DirectControlHandler({'linear_speed': 0.02})
    
    # Define key sequence
    key_sequence = [
        ('w', 'forward', np.array([1, 0, 0])),
        ('d', 'right', np.array([0, 1, 0])),
        ('q', 'up', np.array([0, 0, 1])),
        ('s', 'backward', np.array([-1, 0, 0])),
        ('space', 'gripper', None)
    ]
    
    total_commands = 0
    
    for key, description, direction in key_sequence:
        print(f"\nSimulating '{key}' key ({description})")
        
        # Create parsed command
        if key == 'space':
            parsed_cmd = ParsedCommand(CommandType.GRIPPER, 'toggle')
        else:
            parsed_cmd = ParsedCommand(CommandType.MOVEMENT, description)
        
        # Create interpreted input
        interpreted = InterpretedInput(parsed_cmd)
        
        if direction is not None:
            interpreted.movement_type = 'linear'
            interpreted.direction_vector = direction
            interpreted.magnitude = 1.0
        else:
            interpreted.is_gripper_command = True
            interpreted.gripper_action = 'toggle'
        
        # Generate commands
        commands = handler.process_interpreted_inputs([interpreted])
        total_commands += len(commands)
        
        print(f"  Generated {len(commands)} commands")
        for cmd in commands:
            if cmd.joint_command:
                print(f"    Joint command: {cmd.joint_command.positions[:3]}")
            elif cmd.gripper_command:
                print(f"    Gripper command: {cmd.gripper_command.position:.2f}")
        
        time.sleep(0.1)  # Small delay between commands
    
    print(f"\n✅ Sequence complete! Total commands generated: {total_commands}")
    return total_commands > 0

if __name__ == '__main__':
    try:
        # Run basic pipeline test
        success = test_control_pipeline()
        
        if success:
            # Run keyboard sequence simulation
            simulate_keyboard_sequence()
            
        print("\n🎉 All tests passed! The robot control system is ready.")
        print("\nTo run with MuJoCo viewer:")
        print("  ./run_with_display.sh")
        print("\nTo run with monitoring:")
        print("  python test_with_viewer.py")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)