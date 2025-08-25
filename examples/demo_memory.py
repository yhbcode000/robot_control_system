#!/usr/bin/env python3
"""
Live demo of the Robot Control System memory and modules
"""

import time
import threading
import sys
import os
sys.path.append(os.path.dirname(__file__))

from core.memory.memory_store import GlobalMemory
from modules.input.models import ParsedCommand, CommandType
from modules.watchdog.watchdog_module import WatchdogModule

def demo_system():
    """Demonstrate the system running without MuJoCo"""
    
    print("=" * 60)
    print("🤖 ROBOT CONTROL SYSTEM - LIVE DEMO")
    print("=" * 60)
    
    # Initialize memory
    print("Initializing global memory...")
    memory = GlobalMemory.get_instance()
    
    # Initialize watchdog
    print("Starting watchdog module...")
    watchdog_config = {
        'enabled': True,
        'check_interval': 1.0,
        'heartbeat_timeout': 5.0,
        'heartbeat_warning': 2.0,
        'auto_restart': True,
        'max_restart_attempts': 3,
        'recovery_strategy': 'restart',
        'recovery_cooldown': 1.0,
        'alerts': {'console': True, 'sound': False}
    }
    
    watchdog = WatchdogModule(watchdog_config)
    watchdog.start()
    
    print("✅ System components initialized!")
    print("\n" + "=" * 60)
    print("📊 SYSTEM ACTIVITY MONITOR")
    print("=" * 60)
    
    try:
        # Simulate system activity
        for i in range(10):
            print(f"\n--- Cycle {i+1}/10 ---")
            
            # Simulate input commands
            if i % 3 == 0:
                command = ParsedCommand(
                    command_type=CommandType.MOVEMENT,
                    direction='forward',
                    magnitude=0.8,
                    is_continuous=False
                )
                active_commands = memory.get('input_buffer', 'active_commands', {})
                active_commands[f'demo_cmd_{i}'] = command
                memory.update('input_buffer', 'active_commands', active_commands)
                print(f"📥 Input: Added {command.direction} command")
            
            # Simulate module heartbeats
            modules = ['Input', 'Sense', 'Plan', 'Act', 'Output']
            for module_name in modules:
                heartbeat_data = {
                    'timestamp': time.time(),
                    'error_count': 0,
                    'avg_processing_time': 0.001 + (i * 0.0001)  # Slight increase over time
                }
                memory.update_module_heartbeat(module_name, heartbeat_data)
            
            print(f"💓 Heartbeats: Updated {len(modules)} modules")
            
            # Simulate trajectory planning
            if i % 2 == 0:
                trajectory = {
                    'joint_names': ['shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint'],
                    'positions': [0.1 * i, -0.1 * i, 0.05 * i],
                    'velocities': [0.0, 0.0, 0.0],
                    'timestamp': time.time()
                }
                memory.update('plan_buffer', 'current_trajectory', trajectory)
                print(f"📍 Trajectory: Planning joint positions")
            
            # Show memory usage
            active_commands = memory.get('input_buffer', 'active_commands', {})
            current_trajectory = memory.get('plan_buffer', 'current_trajectory')
            
            print(f"🧠 Memory: {len(active_commands)} active commands")
            if current_trajectory:
                print(f"🎯 Target: Joints at {current_trajectory['positions']}")
            
            # Show watchdog status
            watchdog_health = memory.get_module_heartbeat('Watchdog')
            if watchdog_health:
                print(f"🐕 Watchdog: Monitoring (errors: {watchdog_health.error_count})")
            
            time.sleep(1)
        
        print("\n" + "=" * 60)
        print("🎉 DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        # Show final system stats
        print("\n📊 Final System Statistics:")
        
        # Module heartbeat status
        modules = ['Input', 'Sense', 'Plan', 'Act', 'Output', 'Watchdog']
        healthy_modules = 0
        
        for module_name in modules:
            heartbeat = memory.get_module_heartbeat(module_name)
            if heartbeat and heartbeat.age < 5.0:  # Healthy if updated within 5 seconds
                healthy_modules += 1
                status = "✅ HEALTHY"
                age = f"{heartbeat.age:.1f}s ago"
            else:
                status = "❌ STALE"
                age = "No recent heartbeat"
            
            print(f"  {module_name:12} : {status} ({age})")
        
        print(f"\nSystem Health: {healthy_modules}/{len(modules)} modules healthy")
        
        # Memory usage
        total_namespaces = len(memory._namespaces)
        print(f"Memory Usage: {total_namespaces} active namespaces")
        
        return healthy_modules == len(modules)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user")
        return True
        
    finally:
        print("\n🛑 Shutting down system...")
        watchdog.stop()
        print("✅ Watchdog stopped")
        print("✅ Memory system active")
        print("✅ Demo complete")

if __name__ == '__main__':
    try:
        success = demo_system()
        print(f"\n{'🎉 SUCCESS' if success else '❌ ISSUES DETECTED'}")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n💥 Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)