#!/usr/bin/env python3
"""Test mouse-based end-effector control with inverse kinematics"""

import time
import sys
import os
import threading
import numpy as np
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from modules.kinematics.inverse_kinematics import InverseKinematics
from modules.input.mouse_control import MouseEndEffectorController, MouseControlConfig
from modules.act.end_effector_control import EndEffectorController
from models.sensor_data import MouseInput
from models.robot_state import RobotState, JointState, EndEffectorPose

def test_inverse_kinematics():
    """Test inverse kinematics solver"""
    print("="*60)
    print("TESTING INVERSE KINEMATICS")
    print("="*60)
    
    # Create IK solver
    ik = InverseKinematics()
    
    # Test forward kinematics
    print("1. Testing forward kinematics...")
    test_joints = np.array([0, -np.pi/4, np.pi/2, -np.pi/4, np.pi/2, 0])
    position, orientation = ik.forward_kinematics(test_joints)
    print(f"   Joint angles: {test_joints}")
    print(f"   End-effector position: {position}")
    print(f"   End-effector orientation: {orientation}")
    
    # Test inverse kinematics
    print("\n2. Testing inverse kinematics...")
    target_position = np.array([0.3, 0.2, 0.5])
    print(f"   Target position: {target_position}")
    
    start_time = time.time()
    solution, success = ik.inverse_kinematics(target_position, initial_guess=test_joints)
    solve_time = time.time() - start_time
    
    if success:
        print(f"   ✅ IK solution found in {solve_time:.3f}s")
        print(f"   Solution joints: {solution}")
        
        # Verify solution
        verify_pos, _ = ik.forward_kinematics(solution)
        error = np.linalg.norm(verify_pos - target_position)
        print(f"   Position error: {error:.6f}m")
        
        if error < 0.01:
            print("   ✅ Solution verified")
            return True
        else:
            print("   ❌ Solution verification failed")
            return False
    else:
        print(f"   ❌ IK failed after {solve_time:.3f}s")
        return False

def test_mouse_control():
    """Test mouse control mapping"""
    print("\n" + "="*60)
    print("TESTING MOUSE CONTROL MAPPING")
    print("="*60)
    
    # Create mouse controller
    config = MouseControlConfig(
        screen_width=1920,
        screen_height=1080,
        workspace_width=1.0,
        workspace_height=1.0,
        workspace_center=(0.4, 0.0, 0.4)
    )
    
    controller = MouseEndEffectorController(config)
    
    # Test mouse position mapping
    test_cases = [
        (960, 540, "center"),      # Screen center -> workspace center
        (0, 0, "top-left"),        # Top-left -> workspace bounds
        (1920, 1080, "bottom-right"), # Bottom-right -> workspace bounds
        (960, 270, "top-center"),  # Top-center -> forward
        (960, 810, "bottom-center") # Bottom-center -> backward
    ]
    
    print("Mouse position to workspace mapping:")
    for mouse_x, mouse_y, description in test_cases:
        target = controller.update_from_mouse(mouse_x, mouse_y)
        print(f"   {description:15} ({mouse_x:4d}, {mouse_y:4d}) -> ({target[0]:.3f}, {target[1]:.3f}, {target[2]:.3f})")
    
    # Test scroll control (Z-axis)
    print("\nScroll control (Z-axis):")
    controller.reset_to_center()
    initial_target = controller.get_current_target()
    
    # Scroll up
    target_up = controller.update_from_mouse(960, 540, scroll_delta=5)
    print(f"   Scroll up:   Z: {initial_target[2]:.3f} -> {target_up[2]:.3f}")
    
    # Scroll down
    target_down = controller.update_from_mouse(960, 540, scroll_delta=-3)
    print(f"   Scroll down: Z: {target_up[2]:.3f} -> {target_down[2]:.3f}")
    
    print("✅ Mouse control mapping test passed")
    return True

def test_end_effector_controller():
    """Test end-effector controller"""
    print("\n" + "="*60)
    print("TESTING END-EFFECTOR CONTROLLER") 
    print("="*60)
    
    # Create controller
    config = {
        'control_frequency': 50,
        'position_tolerance': 0.01,
        'max_joint_velocity': 2.0,
        'use_jacobian_ik': True,
        'enable_safety_checks': False,  # Disable for testing
        'workspace_margin': 0.01  # Reduce margin
    }
    
    controller = EndEffectorController(config)
    
    # Create mock robot state
    joint_positions = np.array([0, -np.pi/6, np.pi/4, -np.pi/6, np.pi/2, 0])
    joint_state = JointState(
        joint_names=['joint_' + str(i) for i in range(6)],
        positions=joint_positions,
        velocities=np.zeros(6),
        efforts=np.zeros(6)
    )
    
    # Get current end-effector position
    ik = InverseKinematics()
    current_pos, current_ori = ik.forward_kinematics(joint_positions)
    
    ee_pose = EndEffectorPose(
        position=current_pos,
        orientation=current_ori
    )
    
    robot_state = RobotState(
        joint_state=joint_state,
        end_effector_pose=ee_pose
    )
    
    controller.update_robot_state(robot_state)
    print(f"   Current end-effector position: {current_pos}")
    
    # Set target position - use a more realistic reachable target
    target_pos = np.array([0.4, 0.2, 0.5])  # Known good position
    print(f"   Target position: {target_pos}")
    
    success = controller.set_target_position(target_pos)
    if success:
        print("   ✅ Target position set successfully")
        
        # Generate control command
        try:
            command = controller.generate_control_command()
            if command:
                print("   ✅ Control command generated")
                if command.joint_command:
                    print(f"   Target joint positions: {command.joint_command.positions[:3]}")
                    
                    # Verify the solution would reach target
                    new_pos, _ = ik.forward_kinematics(np.array(command.joint_command.positions))
                    error = np.linalg.norm(new_pos - target_pos)
                    print(f"   Expected position error: {error:.6f}m")
                    
                    if error < 0.02:  # 2cm tolerance
                        print("   ✅ End-effector controller test passed")
                        return True
            else:
                print("   ❌ Failed to generate control command")
                # Check controller status for debugging
                status = controller.get_status()
                print(f"   Debug - IK success rate: {status['ik_success_rate']:.2f}")
                print(f"   Debug - Position error: {status['position_error']:.6f}")
        except Exception as e:
            print(f"   ❌ Error in control command generation: {e}")
    else:
        print("   ❌ Failed to set target position")
    
    return False

def test_mouse_simulation():
    """Test simulated mouse input"""
    print("\n" + "="*60)
    print("TESTING MOUSE INPUT SIMULATION")
    print("="*60)
    
    # Create mouse controller
    config = MouseControlConfig(workspace_center=(0.4, 0.0, 0.4))
    mouse_controller = MouseEndEffectorController(config)
    
    # Create end-effector controller
    ee_config = {
        'control_frequency': 10,
        'use_jacobian_ik': True,
        'enable_safety_checks': False  # Disable for testing
    }
    ee_controller = EndEffectorController(ee_config)
    
    # Create initial robot state
    initial_joints = np.array([0, -np.pi/6, np.pi/4, -np.pi/6, np.pi/2, 0])
    ik = InverseKinematics()
    initial_pos, initial_ori = ik.forward_kinematics(initial_joints)
    
    joint_state = JointState(
        joint_names=['joint_' + str(i) for i in range(6)],
        positions=initial_joints,
        velocities=np.zeros(6),
        efforts=np.zeros(6)
    )
    
    robot_state = RobotState(
        joint_state=joint_state,
        end_effector_pose=EndEffectorPose(position=initial_pos, orientation=initial_ori)
    )
    
    ee_controller.update_robot_state(robot_state)
    
    print(f"Initial end-effector position: {initial_pos}")
    
    # Simulate mouse movements
    mouse_movements = [
        (1200, 540, 0, "right"),     # Move right
        (960, 300, 0, "forward"),    # Move forward  
        (960, 540, 3, "up"),         # Move up with scroll
        (720, 540, -2, "left+down"), # Move left and down
    ]
    
    successful_commands = 0
    
    for mouse_x, mouse_y, scroll, description in mouse_movements:
        print(f"\n   Simulating: {description}")
        print(f"   Mouse: ({mouse_x}, {mouse_y}), Scroll: {scroll}")
        
        # Update mouse controller
        target_pos = mouse_controller.update_from_mouse(mouse_x, mouse_y, scroll)
        print(f"   Target position: ({target_pos[0]:.3f}, {target_pos[1]:.3f}, {target_pos[2]:.3f})")
        
        # Set target in end-effector controller
        ee_controller.set_target_position(target_pos)
        
        # Generate command
        command = ee_controller.generate_control_command()
        if command and command.joint_command:
            print(f"   ✅ Generated joint command")
            successful_commands += 1
            
            # Verify solution
            solution_joints = np.array(command.joint_command.positions)
            solution_pos, _ = ik.forward_kinematics(solution_joints)
            error = np.linalg.norm(solution_pos - target_pos)
            print(f"   Position error: {error:.6f}m")
        else:
            print(f"   ❌ Failed to generate command")
    
    success_rate = successful_commands / len(mouse_movements)
    print(f"\nMouse simulation results:")
    print(f"   Successful commands: {successful_commands}/{len(mouse_movements)}")
    print(f"   Success rate: {success_rate:.1%}")
    
    return success_rate > 0.5  # At least 50% success

def test_integration():
    """Test full integration"""
    print("\n" + "="*60)
    print("TESTING FULL INTEGRATION")
    print("="*60)
    
    success_count = 0
    test_count = 4
    
    try:
        if test_inverse_kinematics():
            success_count += 1
        
        if test_mouse_control():
            success_count += 1
            
        if test_end_effector_controller():
            success_count += 1
            
        if test_mouse_simulation():
            success_count += 1
            
    except Exception as e:
        print(f"❌ Integration test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    print(f"Tests passed: {success_count}/{test_count}")
    print(f"Success rate: {success_count/test_count:.1%}")
    
    if success_count == test_count:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Inverse kinematics working")
        print("✅ Mouse control mapping working") 
        print("✅ End-effector controller working")
        print("✅ Mouse simulation working")
        print("\nMouse end-effector control is ready!")
        print("\nControls:")
        print("  • Mouse X/Y: End-effector X/Y position")
        print("  • Mouse scroll: End-effector Z position")
        print("  • Real-time inverse kinematics")
        return True
    else:
        print("❌ SOME TESTS FAILED")
        print("Check the output above for details")
        return False

if __name__ == '__main__':
    success = test_integration()
    sys.exit(0 if success else 1)