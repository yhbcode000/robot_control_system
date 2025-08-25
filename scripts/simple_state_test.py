#!/usr/bin/env python3
"""Simple test to check if robot state is updating from MuJoCo"""

import time
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from core.memory.memory_store import GlobalMemory
from modules.act.direct_control import DirectControlHandler
from modules.input.models import ParsedCommand, CommandType
from modules.sense.models import InterpretedInput
import numpy as np

def quick_robot_state_test():
    """Quick test to see if robot state updates"""
    memory = GlobalMemory.get_instance()
    
    print("Quick Robot State Test")
    print("="*40)
    
    # Wait a moment for any existing system to initialize
    time.sleep(1)
    
    # Check if robot state exists in memory
    print("1. Checking for robot state in memory...")
    robot_state = memory.get('sensor_state', 'robot_state')
    
    if robot_state:
        print("✅ Robot state found in memory")
        if hasattr(robot_state, 'joint_state') and robot_state.joint_state:
            positions = robot_state.joint_state.positions
            print(f"   Joint positions: {positions[:3]}")  # Show first 3 joints
        else:
            print("   No joint state data")
    else:
        print("❌ No robot state found in memory")
        return False
    
    # Check adapter status
    print("\n2. Checking if sensor readings are active...")
    sensor_bundle = memory.get('sensor_state', 'sensor_bundle')
    if sensor_bundle:
        print("✅ Sensor bundle found in memory")
    else:
        print("⚠️  No sensor bundle in memory")
    
    # Generate a command and see if robot state changes
    print("\n3. Generating control command...")
    handler = DirectControlHandler({'linear_speed': 0.02})
    
    # Create interpreted input for movement
    parsed_cmd = ParsedCommand(CommandType.MOVEMENT, 'forward')
    interpreted = InterpretedInput(parsed_cmd)
    interpreted.movement_type = 'linear'
    interpreted.direction_vector = np.array([1, 0, 0])
    interpreted.magnitude = 1.0
    
    # Generate control command
    commands = handler.process_interpreted_inputs([interpreted])
    if commands:
        print(f"   Generated {len(commands)} control commands")
        cmd = commands[0]
        if cmd.joint_command:
            print(f"   Target positions: {cmd.joint_command.positions[:3]}")
            
            # Send command to memory
            memory.update('action_commands', 'pending_commands', commands)
            print("   Command sent to system")
    
    # Check for position updates over time
    print("\n4. Monitoring robot state for 5 seconds...")
    initial_positions = None
    position_changes = 0
    
    for i in range(50):  # 5 seconds at 10Hz
        robot_state = memory.get('sensor_state', 'robot_state')
        
        if robot_state and hasattr(robot_state, 'joint_state') and robot_state.joint_state:
            current_positions = robot_state.joint_state.positions
            
            if initial_positions is None:
                initial_positions = current_positions.copy()
            else:
                # Check for changes
                diff = np.linalg.norm(current_positions - initial_positions)
                if diff > 0.001:  # 1mm threshold
                    position_changes += 1
                    if position_changes == 1:  # First change
                        print(f"   Position change detected! Diff: {diff:.6f}")
                        print(f"   Joint 0: {initial_positions[0]:.6f} → {current_positions[0]:.6f}")
        
        time.sleep(0.1)
    
    print(f"\n5. Results:")
    print(f"   Position changes detected: {position_changes}")
    
    if position_changes > 0:
        print("✅ Robot state is updating properly!")
        return True
    else:
        print("⚠️  No position changes detected")
        print("   This could mean:")
        print("   - MuJoCo simulation is not running")
        print("   - Commands are not reaching the adapter")
        print("   - Robot state is not being read from adapter")
        return False

if __name__ == '__main__':
    success = quick_robot_state_test()
    
    print("\n" + "="*40)
    if success:
        print("🎉 PASSED: Robot state is updating!")
    else:
        print("❌ FAILED: Robot state not updating properly")
    print("="*40)