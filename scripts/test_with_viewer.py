#!/usr/bin/env python3
"""Test robot control system with MuJoCo viewer and monitoring"""

import sys
import os
import time
import threading
import signal
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from core.memory.memory_store import GlobalMemory
from tools.mujoco_viewer import MuJoCoViewerTool

class RobotSystemTester:
    """Test the robot control system with visual feedback"""
    
    def __init__(self):
        self.system_process = None
        self.viewer_tool = None
        self.memory = GlobalMemory.get_instance()
        self.running = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def start_system(self):
        """Start the robot control system in background"""
        try:
            print("Starting robot control system...")
            
            # Import and setup system
            from main import RobotControlSystem
            from omegaconf import DictConfig, OmegaConf
            import hydra
            from hydra import initialize, compose
            from hydra.core.global_hydra import GlobalHydra
            
            # Initialize Hydra
            if not GlobalHydra().is_initialized():
                initialize(config_path=".", version_base=None)
            
            # Load config
            cfg = compose(config_name="config")
            
            # Create system
            self.system = RobotControlSystem(cfg)
            
            # Start system in background thread
            def run_system():
                try:
                    if self.system.initialize():
                        self.running = True
                        print("Robot control system started successfully")
                        self.system.start()
                    else:
                        print("Failed to initialize robot control system")
                except Exception as e:
                    print(f"Error running system: {e}")
                    import traceback
                    traceback.print_exc()
            
            self.system_thread = threading.Thread(target=run_system, daemon=True)
            self.system_thread.start()
            
            # Wait for system to start
            time.sleep(2)
            
            return True
            
        except Exception as e:
            print(f"Error starting system: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def start_viewer(self, auto_screenshot=True):
        """Start the MuJoCo viewer with monitoring"""
        try:
            print("Starting MuJoCo viewer...")
            
            # Create viewer tool
            config = {
                'model_path': 'assets/robots/arm/ur5e.xml'
            }
            
            self.viewer_tool = MuJoCoViewerTool(config)
            
            if not self.viewer_tool.initialize():
                print("Failed to initialize MuJoCo viewer")
                return False
            
            print("\n" + "="*60)
            print("ROBOT CONTROL SYSTEM TEST")
            print("="*60)
            print("Keyboard Controls (in terminal where system is running):")
            print("  W/S: Forward/Backward movement")
            print("  A/D: Left/Right movement")
            print("  Q/E: Up/Down movement")
            print("  Arrow Keys: Rotation")
            print("  Space: Toggle Gripper")
            print("  ESC: Emergency Stop")
            print("\nMuJoCo Viewer Controls:")
            print("  Mouse: Rotate view")
            print("  Scroll: Zoom")
            print("  S: Take screenshot")
            print("  A: Toggle auto screenshots")
            print("  R: Reset robot")
            print("  Q: Quit viewer")
            print("="*60)
            
            # Start viewer (this will block)
            success = self.viewer_tool.launch_viewer(
                auto_screenshot=auto_screenshot,
                screenshot_interval=3.0
            )
            
            return success
            
        except Exception as e:
            print(f"Error starting viewer: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def monitor_system(self):
        """Monitor system status and provide feedback"""
        last_status_time = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                if current_time - last_status_time > 5.0:
                    # Print system status
                    self._print_system_status()
                    last_status_time = current_time
                
                time.sleep(1.0)
                
            except Exception as e:
                print(f"Error monitoring system: {e}")
                time.sleep(2.0)
    
    def _print_system_status(self):
        """Print current system status"""
        try:
            print("\n" + "-"*40)
            print("SYSTEM STATUS")
            print("-"*40)
            
            # Robot state
            robot_state = self.memory.get('robot', 'current_state')
            if robot_state:
                print(f"Robot Moving: {getattr(robot_state, 'is_moving', 'Unknown')}")
                print(f"Emergency Stop: {getattr(robot_state, 'emergency_stop', 'Unknown')}")
                print(f"Collision Detected: {getattr(robot_state, 'is_collision_detected', 'Unknown')}")
            
            # Command metrics
            robot_metrics = self.memory.get('robot', 'metrics', {})
            if robot_metrics:
                print(f"Commands Executed: {robot_metrics.get('commands_executed', 0)}")
                print(f"Command Frequency: {robot_metrics.get('command_frequency', 0):.1f} Hz")
            
            # Input status
            input_buffer = self.memory.get('input_buffer', 'current')
            if input_buffer and hasattr(input_buffer, 'active_commands'):
                active_count = len(input_buffer.active_commands)
                if active_count > 0:
                    print(f"Active Input Commands: {active_count}")
                    for key, cmd in list(input_buffer.active_commands.items())[:3]:
                        print(f"  {key}: {cmd.command_type.value if hasattr(cmd, 'command_type') else 'unknown'}")
            
            # Safety status
            safety_alert = self.memory.get('system_status', 'safety_alert')
            if safety_alert and safety_alert.get('active', False):
                print("⚠️  SAFETY VIOLATIONS DETECTED:")
                for violation in safety_alert.get('violations', []):
                    print(f"   - {violation}")
            
            # Health status
            health_data = self.memory.get_health_status()
            if health_data:
                health_score = health_data.get('health_score', 0)
                print(f"System Health: {health_score:.1f}%")
            
            print("-"*40)
            
        except Exception as e:
            print(f"Error printing status: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle system signals"""
        print(f"\nReceived signal {signum} - shutting down...")
        self.stop()
    
    def stop(self):
        """Stop the system"""
        print("Stopping robot control system...")
        self.running = False
        
        if hasattr(self, 'system'):
            try:
                self.system.shutdown()
            except:
                pass
        
        if self.viewer_tool:
            self.viewer_tool.viewer_running = False
        
        print("System stopped")

def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Robot Control System with Viewer')
    parser.add_argument('--no-viewer', action='store_true', help='Run without MuJoCo viewer')
    parser.add_argument('--no-auto-screenshot', action='store_true', help='Disable automatic screenshots')
    parser.add_argument('--monitor-only', action='store_true', help='Only monitor, don\'t start system')
    
    args = parser.parse_args()
    
    # Create tester
    tester = RobotSystemTester()
    
    try:
        if not args.monitor_only:
            # Start the robot control system
            if not tester.start_system():
                print("Failed to start robot control system")
                sys.exit(1)
        
        if not args.no_viewer:
            # Start MuJoCo viewer with monitoring
            print("Press Ctrl+C to stop the system")
            
            # Start monitoring in background
            monitor_thread = threading.Thread(target=tester.monitor_system, daemon=True)
            monitor_thread.start()
            
            # Start viewer (this will block until viewer is closed)
            tester.start_viewer(auto_screenshot=not args.no_auto_screenshot)
        else:
            # Run without viewer - just monitor
            print("Running in monitor-only mode. Press Ctrl+C to stop.")
            tester.monitor_system()
            
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Error in main: {e}")
        import traceback
        traceback.print_exc()
    finally:
        tester.stop()
        print("Test completed")

if __name__ == '__main__':
    main()