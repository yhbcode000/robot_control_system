#!/usr/bin/env python3
"""MuJoCo Viewer and Screenshot Tool"""

import numpy as np
import time
import threading
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

try:
    import mujoco
    import mujoco.viewer
    MUJOCO_AVAILABLE = True
except ImportError:
    MUJOCO_AVAILABLE = False
    print("MuJoCo not available")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("PIL not available - screenshots will be disabled")

from core.memory.memory_store import GlobalMemory
from models.control_commands import ControlCommand, CommandType

class MuJoCoViewerTool:
    """Tool for capturing MuJoCo viewer screenshots and monitoring control"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.model_path = self.config.get('model_path', 'assets/robots/arm/ur5e.xml')
        
        # MuJoCo objects
        self.model = None
        self.data = None
        self.viewer = None
        
        # Screenshot settings
        self.screenshot_dir = Path('screenshots')
        self.screenshot_dir.mkdir(exist_ok=True)
        self.screenshot_counter = 0
        
        # Control monitoring
        self.memory = GlobalMemory.get_instance()
        self.last_command_time = 0
        self.command_count = 0
        
        # Viewer state
        self.viewer_running = False
        self.auto_screenshot = False
        self.screenshot_interval = 2.0  # seconds
        
    def initialize(self):
        """Initialize MuJoCo model and data"""
        if not MUJOCO_AVAILABLE:
            print("Cannot initialize - MuJoCo not available")
            return False
            
        try:
            print(f"Loading MuJoCo model: {self.model_path}")
            self.model = mujoco.MjModel.from_xml_path(self.model_path)
            self.data = mujoco.MjData(self.model)
            
            print(f"Model loaded successfully:")
            print(f"  Joints: {self.model.njnt}")
            print(f"  Actuators: {self.model.nu}")
            print(f"  Bodies: {self.model.nbody}")
            
            return True
            
        except Exception as e:
            print(f"Failed to initialize MuJoCo: {e}")
            return False
    
    def launch_viewer(self, auto_screenshot=False, screenshot_interval=2.0):
        """Launch MuJoCo viewer with monitoring"""
        if not MUJOCO_AVAILABLE or not self.model or not self.data:
            print("Cannot launch viewer - MuJoCo not initialized")
            return False
            
        self.auto_screenshot = auto_screenshot
        self.screenshot_interval = screenshot_interval
        
        try:
            print("Launching MuJoCo viewer...")
            print("\nViewer Controls:")
            print("  Mouse: Rotate view")
            print("  Scroll: Zoom")
            print("  S: Take screenshot")
            print("  A: Toggle auto screenshots")
            print("  R: Reset robot to home")
            print("  ESC/Q: Quit")
            
            with mujoco.viewer.launch_passive(self.model, self.data) as viewer:
                self.viewer = viewer
                self.viewer_running = True
                
                # Start monitoring thread
                monitor_thread = threading.Thread(target=self._monitor_commands, daemon=True)
                monitor_thread.start()
                
                # Start auto screenshot thread if enabled
                if auto_screenshot:
                    screenshot_thread = threading.Thread(target=self._auto_screenshot, daemon=True)
                    screenshot_thread.start()
                
                last_screenshot_time = 0
                
                while self.viewer_running and viewer.is_running():
                    # Step simulation
                    mujoco.mj_step(self.model, self.data)
                    
                    # Sync viewer
                    viewer.sync()
                    
                    # Check for keyboard input
                    if hasattr(viewer, 'key_pressed'):
                        if viewer.key_pressed('s'):
                            self.take_screenshot()
                        elif viewer.key_pressed('a'):
                            self.auto_screenshot = not self.auto_screenshot
                            print(f"Auto screenshot: {'ON' if self.auto_screenshot else 'OFF'}")
                        elif viewer.key_pressed('r'):
                            self._reset_robot()
                        elif viewer.key_pressed('q'):
                            break
                    
                    # Manual screenshot check
                    current_time = time.time()
                    if (current_time - last_screenshot_time > 1.0 and 
                        self.command_count > 0):
                        # Take screenshot when robot is moving
                        if self.auto_screenshot:
                            last_screenshot_time = current_time
                    
                    # Small delay
                    time.sleep(0.01)
                    
                print("Viewer closed")
                
        except Exception as e:
            print(f"Error in viewer: {e}")
            return False
        finally:
            self.viewer_running = False
            self.viewer = None
            
        return True
    
    def take_screenshot(self, filename=None):
        """Take a screenshot of the MuJoCo viewer"""
        if not PIL_AVAILABLE:
            print("Cannot take screenshot - PIL not available")
            return None
            
        if not self.viewer:
            print("Cannot take screenshot - viewer not running")
            return None
            
        try:
            # Get viewport dimensions
            viewport = self.viewer.viewport
            width, height = viewport.width, viewport.height
            
            # Create RGB buffer
            rgb_buffer = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Render scene to buffer
            mujoco.mjr_render(viewport, self.viewer.scn, self.viewer.ctx)
            mujoco.mjr_readPixels(rgb_buffer, None, viewport, self.viewer.ctx)
            
            # Flip image vertically (OpenGL convention)
            rgb_buffer = np.flipud(rgb_buffer)
            
            # Create PIL image
            image = Image.fromarray(rgb_buffer)
            
            # Save screenshot
            if filename is None:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"mujoco_screenshot_{timestamp}_{self.screenshot_counter:04d}.png"
                self.screenshot_counter += 1
            
            filepath = self.screenshot_dir / filename
            image.save(filepath)
            
            print(f"Screenshot saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            return None
    
    def _monitor_commands(self):
        """Monitor control commands from the robot system"""
        last_command_count = 0
        last_status_time = 0
        
        while self.viewer_running:
            try:
                current_time = time.time()
                
                # Check for pending commands
                pending_commands = self.memory.get('action_commands', 'pending_commands', [])
                
                if pending_commands:
                    self.command_count += len(pending_commands)
                    self.last_command_time = current_time
                    
                    # Log command activity
                    if self.command_count != last_command_count:
                        print(f"Commands processed: {self.command_count} (+" +
                              f"{self.command_count - last_command_count})")
                        last_command_count = self.command_count
                        
                        # Show command details
                        for cmd in pending_commands[-2:]:  # Show last 2 commands
                            if hasattr(cmd, 'command_type'):
                                if cmd.command_type == CommandType.JOINT:
                                    if cmd.joint_command:
                                        positions = cmd.joint_command.positions
                                        print(f"  Joint command: {positions[:3]}")
                                        
                                        # Check if this is from end-effector control
                                        if hasattr(cmd, 'source_module') and cmd.source_module == 'EndEffectorController':
                                            print(f"    (End-effector control)")
                                elif cmd.command_type == CommandType.GRIPPER:
                                    if cmd.gripper_command:
                                        print(f"  Gripper: {cmd.gripper_command.position:.2f}")
                                elif cmd.command_type == CommandType.EMERGENCY_STOP:
                                    print("  EMERGENCY STOP")
                
                # Periodic status display (every 3 seconds)
                if current_time - last_status_time > 3.0:
                    self._display_status()
                    last_status_time = current_time
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error monitoring commands: {e}")
                time.sleep(1.0)
    
    def _display_status(self):
        """Display comprehensive system status"""
        try:
            print("\n" + "="*60)
            print("ROBOT CONTROL SYSTEM STATUS")
            print("="*60)
            
            # Robot state from sensor
            robot_state = self.memory.get('sensor_state', 'robot_state')
            if robot_state and hasattr(robot_state, 'joint_state') and robot_state.joint_state:
                positions = robot_state.joint_state.positions
                print(f"Joint positions: [{positions[0]:+.3f}, {positions[1]:+.3f}, {positions[2]:+.3f}, ...]")
                
                if hasattr(robot_state, 'end_effector_pose') and robot_state.end_effector_pose:
                    ee_pos = robot_state.end_effector_pose.position
                    print(f"End-effector:    [{ee_pos[0]:+.3f}, {ee_pos[1]:+.3f}, {ee_pos[2]:+.3f}]")
            
            # End-effector target from mouse
            input_buffer = self.memory.get('input_buffer', 'current')
            if input_buffer and hasattr(input_buffer, 'mouse_inputs'):
                recent_mouse = input_buffer.mouse_inputs[-1:] if input_buffer.mouse_inputs else []
                for mouse_input in recent_mouse:
                    if (hasattr(mouse_input, 'metadata') and mouse_input.metadata and 
                        'end_effector_target' in mouse_input.metadata):
                        target = mouse_input.metadata['end_effector_target']
                        print(f"Mouse target:    [{target[0]:+.3f}, {target[1]:+.3f}, {target[2]:+.3f}]")
                        
                        if 'z_control' in mouse_input.metadata:
                            direction = mouse_input.metadata.get('scroll_direction', 'unknown')
                            print(f"                 (Z-control: {direction})")
            
            # Control status
            if hasattr(robot_state, 'is_moving') and robot_state.is_moving:
                print("Status: MOVING")
            else:
                print("Status: IDLE")
            
            if hasattr(robot_state, 'emergency_stop') and robot_state.emergency_stop:
                print("⚠️  EMERGENCY STOP ACTIVE")
            
            # Command statistics
            print(f"Commands processed: {self.command_count}")
            
            print("="*60)
            
        except Exception as e:
            print(f"Error displaying status: {e}")
    
    def _auto_screenshot(self):
        """Automatically take screenshots at intervals"""
        last_screenshot = 0
        
        while self.viewer_running:
            try:
                if self.auto_screenshot:
                    current_time = time.time()
                    if current_time - last_screenshot >= self.screenshot_interval:
                        if self.command_count > 0:  # Only screenshot if there's activity
                            self.take_screenshot()
                            last_screenshot = current_time
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error in auto screenshot: {e}")
                time.sleep(1.0)
    
    def _reset_robot(self):
        """Reset robot to home position"""
        try:
            print("Resetting robot to home position...")
            
            # Send reset command to memory
            self.memory.update('robot_commands', 'reset_requested', {
                'timestamp': time.time(),
                'requester': 'mujoco_viewer_tool'
            })
            
            # Reset simulation state
            mujoco.mj_resetData(self.model, self.data)
            
        except Exception as e:
            print(f"Error resetting robot: {e}")

def main():
    """Main function for running the viewer tool"""
    import argparse
    
    parser = argparse.ArgumentParser(description='MuJoCo Viewer and Screenshot Tool')
    parser.add_argument('--model', default='assets/robots/arm/ur5e.xml', help='Path to MuJoCo model')
    parser.add_argument('--auto-screenshot', action='store_true', help='Enable automatic screenshots')
    parser.add_argument('--screenshot-interval', type=float, default=2.0, help='Screenshot interval in seconds')
    parser.add_argument('--screenshot-only', action='store_true', help='Take single screenshot and exit')
    
    args = parser.parse_args()
    
    # Create viewer tool
    config = {
        'model_path': args.model
    }
    
    tool = MuJoCoViewerTool(config)
    
    if not tool.initialize():
        sys.exit(1)
    
    if args.screenshot_only:
        # Take a single screenshot without viewer
        print("Taking screenshot without viewer...")
        # This would require a headless render setup
        print("Screenshot-only mode not implemented - use viewer mode")
        sys.exit(1)
    else:
        # Launch interactive viewer
        success = tool.launch_viewer(
            auto_screenshot=args.auto_screenshot,
            screenshot_interval=args.screenshot_interval
        )
        
        if not success:
            sys.exit(1)

if __name__ == '__main__':
    main()