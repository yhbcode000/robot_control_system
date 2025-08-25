#!/usr/bin/env python3
"""Debug MuJoCo adapter directly"""

import time
import sys
import os
from pathlib import Path
import numpy as np

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from adapters.mujoco_adapter import MuJoCoAdapter

def debug_mujoco_adapter():
    """Debug MuJoCo adapter functionality"""
    print("MuJoCo Adapter Debug")
    print("="*50)
    
    # Create adapter configuration
    config = {
        'model_path': 'assets/robots/arm/ur5e.xml',
        'render': False,  # No rendering for debug
        'physics_timestep': 0.001,
        'control_timestep': 0.01,
        'joint_names': [
            'shoulder_pan_joint',
            'shoulder_lift_joint', 
            'elbow_joint',
            'wrist_1_joint',
            'wrist_2_joint',
            'wrist_3_joint'
        ],
        'actuator_names': [
            'shoulder_pan',
            'shoulder_lift',
            'elbow',
            'wrist_1',
            'wrist_2',
            'wrist_3'
        ],
        'end_effector_body': 'wrist_3_link',
        'gripper_joint': None
    }
    
    # Create and connect adapter
    print("1. Creating MuJoCo adapter...")
    adapter = MuJoCoAdapter(config)
    
    print("2. Connecting to MuJoCo...")
    if not adapter.connect():
        print("❌ Failed to connect to MuJoCo")
        return False
    
    print("✅ Connected successfully!")
    
    # Test robot state reading
    print("\n3. Testing robot state reading...")
    try:
        robot_state = adapter.get_robot_state()
        if robot_state:
            print("✅ Robot state retrieved")
            print(f"   Is moving: {robot_state.is_moving}")
            print(f"   Emergency stop: {robot_state.emergency_stop}")
            
            if robot_state.joint_state:
                print(f"   Joint count: {len(robot_state.joint_state.positions)}")
                print(f"   Joint positions: {robot_state.joint_state.positions[:3]}")
                print(f"   Joint velocities: {robot_state.joint_state.velocities[:3]}")
            
            if robot_state.end_effector_pose:
                print(f"   End effector position: {robot_state.end_effector_pose.position}")
        else:
            print("❌ No robot state returned")
            return False
            
    except Exception as e:
        print(f"❌ Error reading robot state: {e}")
        return False
    
    # Test sensor reading
    print("\n4. Testing sensor reading...")
    try:
        sensor_bundle = adapter.read_sensors()
        if sensor_bundle:
            print("✅ Sensor bundle retrieved")
            if hasattr(sensor_bundle, 'force_torque') and sensor_bundle.force_torque:
                print(f"   Force: {sensor_bundle.force_torque.force}")
                print(f"   Torque: {sensor_bundle.force_torque.torque}")
        else:
            print("⚠️  No sensor bundle (this may be normal)")
            
    except Exception as e:
        print(f"❌ Error reading sensors: {e}")
    
    # Test command sending
    print("\n5. Testing joint command...")
    try:
        initial_state = adapter.get_robot_state()
        initial_positions = initial_state.joint_state.positions.copy()
        print(f"   Initial positions: {initial_positions[:3]}")
        
        # Send a small movement command
        target_positions = initial_positions.copy()
        target_positions[0] += 0.01  # Move first joint by 0.01 radians
        
        joint_names = ['shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint', 
                      'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint']
        
        success = adapter.send_joint_command(joint_names, target_positions.tolist())
        if success:
            print("✅ Joint command sent")
            
            # Wait and check for changes
            time.sleep(0.5)
            
            updated_state = adapter.get_robot_state()
            if updated_state and updated_state.joint_state:
                new_positions = updated_state.joint_state.positions
                print(f"   New positions: {new_positions[:3]}")
                
                position_diff = np.linalg.norm(new_positions - initial_positions)
                print(f"   Position change: {position_diff:.6f}")
                
                if position_diff > 0.001:
                    print("✅ Robot moved successfully!")
                    result = True
                else:
                    print("⚠️  Robot may not have moved")
                    result = False
            else:
                print("❌ Could not read updated state")
                result = False
        else:
            print("❌ Failed to send joint command")
            result = False
            
    except Exception as e:
        print(f"❌ Error testing command: {e}")
        result = False
    
    # Disconnect
    print("\n6. Disconnecting...")
    adapter.disconnect()
    print("✅ Disconnected")
    
    return result

if __name__ == '__main__':
    success = debug_mujoco_adapter()
    
    print("\n" + "="*50)
    if success:
        print("🎉 MuJoCo adapter is working correctly!")
    else:
        print("❌ MuJoCo adapter has issues")
    print("="*50)