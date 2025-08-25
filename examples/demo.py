#!/usr/bin/env python3
"""
Simple demo script to test the Robot Control System
"""

import time
import threading
from core.memory.memory_store import GlobalMemory
from modules.input.models import ParsedCommand, CommandType

def demo_input_simulation():
    """Simulate some input commands"""
    memory = GlobalMemory.get_instance()
    
    print("Starting input simulation...")
    time.sleep(2)  # Wait for system to start
    
    # Simulate some keyboard inputs
    commands = [
        ('w', 'forward movement'),
        ('a', 'left movement'), 
        ('s', 'backward movement'),
        ('d', 'right movement'),
        ('space', 'gripper toggle'),
    ]
    
    for key, description in commands:
        print(f"Simulating {description} (key: {key})")
        
        # Create a parsed command
        command = ParsedCommand(
            command_type=CommandType.MOVEMENT if key != 'space' else CommandType.GRIPPER,
            direction={'w': 'forward', 'a': 'left', 's': 'backward', 'd': 'right'}.get(key, 'toggle'),
            magnitude=1.0,
            is_continuous=False
        )
        
        # Simulate adding to input buffer
        active_commands = memory.get('input_buffer', 'active_commands', {})
        active_commands[f'demo_{key}'] = command
        memory.update('input_buffer', 'active_commands', active_commands)
        
        time.sleep(1)
        
        # Clear the command
        active_commands = memory.get('input_buffer', 'active_commands', {})
        if f'demo_{key}' in active_commands:
            del active_commands[f'demo_{key}']
        memory.update('input_buffer', 'active_commands', active_commands)
        
        time.sleep(0.5)
    
    print("Input simulation completed")

if __name__ == "__main__":
    # Start input simulation in background
    input_thread = threading.Thread(target=demo_input_simulation, daemon=True)
    input_thread.start()
    
    print("Demo commands will be injected into the system...")
    print("Watch the system logs for processing!")
    print("Press Ctrl+C to exit")