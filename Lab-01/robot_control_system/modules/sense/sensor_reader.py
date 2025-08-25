"""Sensor reader for continuous robot state updates"""

import time
import threading
from typing import Optional, Any
from core.memory.memory_store import GlobalMemory
from models.robot_state import RobotState
from models.sensor_data import SensorBundle

class SensorReader:
    """Continuous sensor reading from adapter"""
    
    def __init__(self, adapter, memory: GlobalMemory, update_rate: float = 50.0):
        self.adapter = adapter
        self.memory = memory
        self.update_rate = update_rate
        
        self.running = False
        self.thread = None
        self.last_update_time = 0
        self.read_count = 0
        self.error_count = 0
        
    def start(self):
        """Start sensor reading thread"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._sensor_loop, daemon=True)
        self.thread.start()
        print("Sensor reader started")
    
    def stop(self):
        """Stop sensor reading thread"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
    
    def _sensor_loop(self):
        """Main sensor reading loop"""
        while self.running:
            try:
                current_time = time.time()
                
                # Read robot state from adapter
                if self.adapter and self.adapter.is_connected():
                    # Get robot state
                    robot_state = self.adapter.get_robot_state()
                    if robot_state:
                        # Update memory with fresh robot state
                        self.memory.update('sensor_state', 'robot_state', robot_state)
                        self.read_count += 1
                        
                        # Debug logging every 5 seconds
                        if current_time - self.last_update_time > 5.0:
                            print(f"Sensor reader: {self.read_count} updates, {self.error_count} errors")
                            if hasattr(robot_state.joint_state, 'positions'):
                                pos_str = ', '.join([f"{p:.3f}" for p in robot_state.joint_state.positions[:3]])
                                print(f"Joint positions (first 3): [{pos_str}]")
                            self.last_update_time = current_time
                    
                    # Read sensor bundle
                    try:
                        sensor_bundle = self.adapter.read_sensors()
                        if sensor_bundle:
                            self.memory.update('sensor_state', 'sensor_bundle', sensor_bundle)
                    except Exception as e:
                        print(f"Warning: Could not read sensor bundle: {e}")
                
                # Sleep based on update rate
                sleep_time = 1.0 / self.update_rate
                time.sleep(sleep_time)
                
            except Exception as e:
                self.error_count += 1
                print(f"Error in sensor loop: {e}")
                time.sleep(0.1)  # Short delay on error
    
    def get_stats(self):
        """Get sensor reader statistics"""
        return {
            'running': self.running,
            'read_count': self.read_count,
            'error_count': self.error_count,
            'update_rate': self.update_rate
        }