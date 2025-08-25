#!/usr/bin/env python3
"""Complete test of mouse end-effector control system with MuJoCo"""

import time
import sys
import os
import threading
import signal
import numpy as np
from pathlib import Path

# Add project root to path  
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from core.memory.memory_store import GlobalMemory

class MouseEndEffectorTest:
    """Test mouse-based end-effector control with full system"""
    
    def __init__(self):
        self.system = None
        self.running = False
        self.memory = GlobalMemory.get_instance()
        
        # Test statistics
        self.commands_generated = 0
        self.successful_ik = 0
        self.position_updates = 0
        
        # Setup signal handler
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C"""
        print("\n\nStopping test...")
        self.stop()
        sys.exit(0)
    
    def start_system(self):
        """Start the robot control system"""
        try:
            from main import RobotControlSystem
            from omegaconf import DictConfig, OmegaConf
            from hydra import initialize, compose
            from hydra.core.global_hydra import GlobalHydra
            
            print("Starting Robot Control System with Mouse End-Effector Control...")
            
            # Initialize Hydra
            if not GlobalHydra().is_initialized():
                initialize(config_path=".", version_base=None)
            
            # Load config
            cfg = compose(config_name="config")
            
            # Create and start system
            self.system = RobotControlSystem(cfg)
            
            def run_system():
                try:
                    if self.system.initialize():
                        print("✅ System initialized with mouse end-effector control")
                        self.system.start()
                    else:
                        print("❌ Failed to initialize system")
                except Exception as e:
                    print(f"System error: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Start system in background
            system_thread = threading.Thread(target=run_system, daemon=True)
            system_thread.start()
            
            # Wait for system to initialize
            time.sleep(4)
            return True
            
        except Exception as e:
            print(f"Error starting system: {e}")
            return False
    
    def simulate_mouse_movements(self):
        """Simulate mouse movements for end-effector control"""
        print("\n" + "="*60)
        print("SIMULATING MOUSE END-EFFECTOR CONTROL")
        print("="*60)
        print("Simulating mouse movements to control robot end-effector...")
        
        # Import mouse simulation
        from pynput.mouse import Button, Listener
        from pynput import mouse
        
        # Mouse positions to test (x, y, scroll)
        test_positions = [
            (1200, 540, 0, "Move right (X+)"),
            (960, 400, 0, "Move forward (Y+)"),
            (960, 540, 3, "Move up (Z+) with scroll"),
            (720, 540, 0, "Move left (X-)"),
            (960, 680, 0, "Move backward (Y-)"),
            (960, 540, -2, "Move down (Z-) with scroll"),
            (1100, 460, 1, "Diagonal movement + up"),
        ]
        
        # Create mouse controller for simulation
        kb = mouse.Controller()
        
        print("\nExecuting mouse control sequence:")
        
        for i, (x, y, scroll, description) in enumerate(test_positions):
            if not self.running:
                break
                
            print(f"\n{i+1}. {description}")
            print(f"   Mouse: ({x}, {y}), Scroll: {scroll}")
            
            # Move mouse to position
            kb.position = (x, y)
            time.sleep(0.1)
            
            # Apply scroll if needed
            if scroll != 0:
                kb.scroll(0, scroll)
                time.sleep(0.1)
            
            # Wait to see effect
            time.sleep(2.0)
            
            # Check results
            self._check_command_results()
        
        print("\n✅ Mouse simulation sequence completed!")
    
    def monitor_system(self):
        """Monitor system performance and end-effector position"""
        last_status_time = 0
        last_position = None
        
        while self.running:
            try:
                current_time = time.time()
                
                # Monitor robot state
                robot_state = self.memory.get('sensor_state', 'robot_state')
                if robot_state and hasattr(robot_state, 'end_effector_pose'):
                    if robot_state.end_effector_pose:
                        current_pos = robot_state.end_effector_pose.position
                        
                        # Check for position changes
                        if last_position is not None:
                            distance = np.linalg.norm(current_pos - last_position)
                            if distance > 0.001:  # 1mm threshold
                                self.position_updates += 1
                        
                        last_position = current_pos.copy()
                
                # Monitor commands
                pending_commands = self.memory.get('action_commands', 'pending_commands', [])
                if pending_commands:
                    for cmd in pending_commands:
                        if (hasattr(cmd, 'source_module') and 
                            cmd.source_module == 'EndEffectorController'):
                            self.successful_ik += 1
                    self.commands_generated += len(pending_commands)
                
                # Periodic status
                if current_time - last_status_time > 4.0:
                    self._print_detailed_status(robot_state)
                    last_status_time = current_time
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(1.0)
    
    def _print_detailed_status(self, robot_state):
        """Print detailed system status"""
        try:
            print("\n" + "─"*50)
            print("MOUSE END-EFFECTOR CONTROL STATUS")
            print("─"*50)
            
            # Current end-effector position
            if robot_state and hasattr(robot_state, 'end_effector_pose'):
                if robot_state.end_effector_pose:
                    pos = robot_state.end_effector_pose.position
                    print(f"End-effector position: [{pos[0]:+.3f}, {pos[1]:+.3f}, {pos[2]:+.3f}]")
            
            # Mouse target
            input_buffer = self.memory.get('input_buffer', 'current')
            if input_buffer and hasattr(input_buffer, 'mouse_inputs'):
                if input_buffer.mouse_inputs:
                    last_mouse = input_buffer.mouse_inputs[-1]
                    if (hasattr(last_mouse, 'metadata') and last_mouse.metadata and
                        'end_effector_target' in last_mouse.metadata):
                        target = last_mouse.metadata['end_effector_target']
                        print(f"Mouse target position: [{target[0]:+.3f}, {target[1]:+.3f}, {target[2]:+.3f}]")
                        
                        # Calculate error
                        if robot_state and robot_state.end_effector_pose:
                            current_pos = robot_state.end_effector_pose.position
                            error = np.linalg.norm(current_pos - target)
                            print(f"Position error: {error:.4f}m")
            
            # Statistics
            print(f"IK commands generated: {self.successful_ik}")
            print(f"Position updates: {self.position_updates}")
            
            # Control mode
            if input_buffer and hasattr(input_buffer, 'mouse_inputs'):
                if input_buffer.mouse_inputs:
                    last_mouse = input_buffer.mouse_inputs[-1]
                    if hasattr(last_mouse, 'metadata') and last_mouse.metadata:
                        if 'control_mode' in last_mouse.metadata:
                            mode = last_mouse.metadata['control_mode']
                            print(f"Control mode: {mode}")
            
            print("─"*50)
            
        except Exception as e:
            print(f"Error in detailed status: {e}")
    
    def _check_command_results(self):
        """Check results of last command"""
        try:
            # Look for recent IK commands
            commands = self.memory.get('action_commands', 'pending_commands', [])
            ik_commands = [cmd for cmd in commands 
                          if hasattr(cmd, 'source_module') and 
                          cmd.source_module == 'EndEffectorController']
            
            if ik_commands:
                print(f"   ✅ Generated {len(ik_commands)} IK commands")
            else:
                print(f"   ⚠️  No IK commands generated")
            
            # Check robot state
            robot_state = self.memory.get('sensor_state', 'robot_state')
            if robot_state and robot_state.is_moving:
                print(f"   ✅ Robot is moving")
            
        except Exception as e:
            print(f"   Error checking results: {e}")
    
    def run_test(self, duration=30):
        """Run the complete mouse end-effector control test"""
        print("="*70)
        print("ROBOT MOUSE END-EFFECTOR CONTROL TEST")
        print("="*70)
        print("This test demonstrates:")
        print("• Real-time inverse kinematics")
        print("• Mouse position → End-effector X/Y control")
        print("• Mouse scroll → End-effector Z control")
        print("• Integration with MuJoCo simulation")
        print("="*70)
        
        # Start system
        if not self.start_system():
            return False
        
        self.running = True
        
        try:
            # Start monitoring in background
            monitor_thread = threading.Thread(target=self.monitor_system, daemon=True)
            monitor_thread.start()
            
            # Wait a moment for system to stabilize
            print("\nWaiting for system to stabilize...")
            time.sleep(3)
            
            # Run mouse simulation
            sim_thread = threading.Thread(target=self.simulate_mouse_movements, daemon=True)
            sim_thread.start()
            
            # Run for specified duration
            print(f"\nRunning test for {duration} seconds...")
            print("Press Ctrl+C to stop early")
            
            time.sleep(duration)
            
        except KeyboardInterrupt:
            print("\nTest interrupted by user")
        
        finally:
            self.running = False
            if self.system:
                try:
                    self.system.shutdown()
                except:
                    pass
        
        return self._evaluate_results()
    
    def _evaluate_results(self):
        """Evaluate test results"""
        print("\n" + "="*70)
        print("TEST RESULTS")
        print("="*70)
        print(f"IK commands generated: {self.successful_ik}")
        print(f"Position updates: {self.position_updates}")
        print(f"Total commands: {self.commands_generated}")
        
        # Evaluate success
        success = (self.successful_ik > 0 and 
                  self.position_updates > 0 and 
                  self.commands_generated > 0)
        
        if success:
            print("\n🎉 TEST SUCCESSFUL!")
            print("✅ Mouse end-effector control is working")
            print("✅ Inverse kinematics is functional")
            print("✅ Real-time control achieved")
            print("\n🎮 CONTROLS AVAILABLE:")
            print("   • Mouse X/Y movement → End-effector X/Y position")
            print("   • Mouse scroll wheel → End-effector Z position")
            print("   • Real-time inverse kinematics solving")
            print("   • Workspace safety limits")
        else:
            print("\n❌ TEST FAILED!")
            print("Check system logs for details")
        
        print("="*70)
        return success
    
    def stop(self):
        """Stop the test"""
        self.running = False

def main():
    """Main test function"""
    test = MouseEndEffectorTest()
    
    try:
        success = test.run_test(duration=25)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()