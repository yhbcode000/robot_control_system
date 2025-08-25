#!/usr/bin/env python3
"""Test full system integration with real-time robot state updates"""

import time
import sys
import os
import threading
from pathlib import Path
from pynput import keyboard
import signal

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from core.memory.memory_store import GlobalMemory

class SystemIntegrationTest:
    """Test full system with keyboard control and robot state monitoring"""
    
    def __init__(self):
        self.memory = GlobalMemory.get_instance()
        self.running = False
        self.system = None
        
        # Statistics
        self.robot_updates = 0
        self.commands_sent = 0
        self.position_changes = 0
        self.last_positions = None
        
        # Setup signal handler
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
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
            
            print("Starting Robot Control System...")
            
            # Initialize Hydra
            if not GlobalHydra().is_initialized():
                initialize(config_path=".", version_base=None)
            
            # Load config
            cfg = compose(config_name="config")
            
            # Create system
            self.system = RobotControlSystem(cfg)
            
            def run_system():
                try:
                    if self.system.initialize():
                        print("✅ System initialized successfully")
                        self.system.start()
                    else:
                        print("❌ Failed to initialize system")
                except Exception as e:
                    print(f"System error: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Start system in background
            self.system_thread = threading.Thread(target=run_system, daemon=True)
            self.system_thread.start()
            
            # Wait for system to start
            time.sleep(3)
            return True
            
        except Exception as e:
            print(f"Error starting system: {e}")
            return False
    
    def monitor_robot_state(self):
        """Monitor robot state updates"""
        last_print_time = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Get robot state
                robot_state = self.memory.get('sensor_state', 'robot_state')
                
                if robot_state:
                    self.robot_updates += 1
                    
                    # Check for position changes
                    if hasattr(robot_state, 'joint_state') and robot_state.joint_state:
                        current_positions = robot_state.joint_state.positions
                        
                        if self.last_positions is not None:
                            import numpy as np
                            diff = np.linalg.norm(current_positions - self.last_positions)
                            if diff > 0.001:  # 1mm threshold
                                self.position_changes += 1
                        
                        self.last_positions = current_positions.copy()
                    
                    # Print status every 3 seconds
                    if current_time - last_print_time > 3.0:
                        self._print_status(robot_state)
                        last_print_time = current_time
                
                time.sleep(0.1)  # 10Hz monitoring
                
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(1.0)
    
    def _print_status(self, robot_state):
        """Print current status"""
        print(f"\n{'='*50}")
        print(f"SYSTEM STATUS - Updates: {self.robot_updates}, Changes: {self.position_changes}")
        print(f"{'='*50}")
        
        if hasattr(robot_state, 'joint_state') and robot_state.joint_state:
            pos = robot_state.joint_state.positions
            vel = robot_state.joint_state.velocities
            print(f"Joint 0: pos={pos[0]:+.4f}, vel={vel[0]:+.4f}")
            print(f"Joint 1: pos={pos[1]:+.4f}, vel={vel[1]:+.4f}")
            print(f"Joint 2: pos={pos[2]:+.4f}, vel={vel[2]:+.4f}")
        
        if hasattr(robot_state, 'is_moving'):
            print(f"Is Moving: {robot_state.is_moving}")
            
        if hasattr(robot_state, 'emergency_stop') and robot_state.emergency_stop:
            print("🚨 EMERGENCY STOP ACTIVE")
        
        # Check command activity
        pending_commands = self.memory.get('action_commands', 'pending_commands', [])
        if pending_commands:
            print(f"Commands in queue: {len(pending_commands)}")
        
        print(f"{'='*50}")
    
    def simulate_keyboard_input(self):
        """Simulate keyboard input for testing"""
        print("\nStarting keyboard input simulation...")
        print("Will simulate: W (forward) → D (right) → S (backward) → A (left)")
        
        time.sleep(2)  # Wait for system to be ready
        
        # Create keyboard controller
        kb = keyboard.Controller()
        
        # Sequence of keys to press
        key_sequence = [
            ('w', 'forward', 2.0),
            ('d', 'right', 2.0), 
            ('s', 'backward', 2.0),
            ('a', 'left', 2.0),
            ('q', 'up', 1.5),
            ('e', 'down', 1.5),
            ('space', 'gripper', 0.5)
        ]
        
        for key, description, duration in key_sequence:
            if not self.running:
                break
                
            print(f"\nSimulating '{key}' ({description}) for {duration}s")
            
            # Press key
            if key == 'space':
                kb.press(keyboard.Key.space)
                time.sleep(0.1)
                kb.release(keyboard.Key.space)
            else:
                kb.press(key)
                time.sleep(duration)
                kb.release(key)
                
            self.commands_sent += 1
            
            # Short pause between commands
            time.sleep(0.5)
        
        print("\nKeyboard simulation complete!")
    
    def run_test(self, duration=20):
        """Run the full integration test"""
        print("="*60)
        print("ROBOT CONTROL SYSTEM INTEGRATION TEST")
        print("="*60)
        print("This test will:")
        print("• Start the complete robot control system")
        print("• Monitor robot state updates in real-time")
        print("• Simulate keyboard control commands")  
        print("• Verify MuJoCo responds to commands")
        print("="*60)
        
        # Start system
        if not self.start_system():
            return False
        
        self.running = True
        
        try:
            # Start monitoring in background
            monitor_thread = threading.Thread(target=self.monitor_robot_state, daemon=True)
            monitor_thread.start()
            
            # Start keyboard simulation in background
            keyboard_thread = threading.Thread(target=self.simulate_keyboard_input, daemon=True)
            keyboard_thread.start()
            
            # Wait for test duration
            print(f"\nRunning test for {duration} seconds...")
            print("Press Ctrl+C to stop early\n")
            
            time.sleep(duration)
            
        except KeyboardInterrupt:
            print("\nTest interrupted by user")
        
        finally:
            self.stop()
        
        return self._evaluate_results()
    
    def _evaluate_results(self):
        """Evaluate test results"""
        print("\n" + "="*60)
        print("TEST RESULTS")
        print("="*60)
        print(f"Robot state updates: {self.robot_updates}")
        print(f"Position changes detected: {self.position_changes}")
        print(f"Commands simulated: {self.commands_sent}")
        
        # Evaluate success
        success = True
        issues = []
        
        if self.robot_updates < 50:  # Should have many updates
            issues.append("Too few robot state updates")
            success = False
            
        if self.position_changes == 0:
            issues.append("No robot movement detected")
            success = False
            
        if self.commands_sent == 0:
            issues.append("No commands were sent")
            success = False
        
        if success:
            print("\n🎉 TEST PASSED!")
            print("✅ Robot state updates are working correctly")
            print("✅ MuJoCo simulation is responding to commands")
            print("✅ Real-time control is functional")
        else:
            print(f"\n❌ TEST FAILED!")
            for issue in issues:
                print(f"   • {issue}")
        
        print("="*60)
        return success
    
    def stop(self):
        """Stop the test"""
        self.running = False
        
        if self.system:
            try:
                self.system.shutdown()
            except:
                pass

def main():
    """Main test function"""
    test = SystemIntegrationTest()
    
    try:
        success = test.run_test(duration=15)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()