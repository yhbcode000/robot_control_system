#!/usr/bin/env python3
"""
Tests for system modules
"""

import unittest
import threading
import time
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.memory.memory_store import GlobalMemory
from modules.input.models import ParsedCommand, CommandType
from modules.watchdog.watchdog_module import WatchdogModule


class TestModuleBase(unittest.TestCase):
    """Test cases for base module functionality"""
    
    def setUp(self):
        """Reset memory instance before each test"""
        GlobalMemory._instance = None
        GlobalMemory._lock = threading.Lock()
    
    def test_watchdog_initialization(self):
        """Test watchdog module initialization"""
        config = {
            'enabled': True,
            'check_interval': 0.1,
            'heartbeat_timeout': 1.0,
            'heartbeat_warning': 0.5,
            'auto_restart': True,
            'max_restart_attempts': 3,
            'recovery_strategy': 'restart',
            'recovery_cooldown': 1.0,
            'alerts': {'console': True, 'sound': False}
        }
        
        watchdog = WatchdogModule(config)
        self.assertEqual(watchdog.name, 'Watchdog')
        self.assertTrue(watchdog.enabled)
        self.assertEqual(watchdog.config['check_interval'], 0.1)
    
    def test_command_models(self):
        """Test command data models"""
        # Test movement command
        movement_cmd = ParsedCommand(
            command_type=CommandType.MOVEMENT,
            direction='forward',
            magnitude=1.0,
            is_continuous=True
        )
        
        self.assertEqual(movement_cmd.command_type, CommandType.MOVEMENT)
        self.assertEqual(movement_cmd.direction, 'forward')
        self.assertEqual(movement_cmd.magnitude, 1.0)
        self.assertTrue(movement_cmd.is_continuous)
        
        # Test gripper command
        gripper_cmd = ParsedCommand(
            command_type=CommandType.GRIPPER,
            direction='toggle',
            magnitude=1.0,
            is_continuous=False
        )
        
        self.assertEqual(gripper_cmd.command_type, CommandType.GRIPPER)
        self.assertEqual(gripper_cmd.direction, 'toggle')
        self.assertFalse(gripper_cmd.is_continuous)
    
    def test_module_heartbeat(self):
        """Test module heartbeat mechanism"""
        config = {
            'enabled': True,
            'check_interval': 0.1,
            'heartbeat_timeout': 1.0,
            'heartbeat_warning': 0.5,
            'auto_restart': True,
            'max_restart_attempts': 3,
            'recovery_strategy': 'restart',
            'recovery_cooldown': 1.0,
            'alerts': {'console': True, 'sound': False}
        }
        
        memory = GlobalMemory.get_instance()
        watchdog = WatchdogModule(config)
        
        # Start watchdog briefly to test heartbeat
        watchdog.start()
        time.sleep(0.2)  # Let it run briefly
        watchdog.stop()
        
        # Check if heartbeat was recorded
        health = memory.get_module_health('Watchdog')
        self.assertIsNotNone(health)
        self.assertIn('heartbeat', health)


class TestSystemIntegration(unittest.TestCase):
    """Test cases for system integration"""
    
    def setUp(self):
        """Reset memory instance before each test"""
        GlobalMemory._instance = None
        GlobalMemory._lock = threading.Lock()
    
    def test_memory_module_communication(self):
        """Test communication between modules via memory"""
        memory = GlobalMemory.get_instance()
        
        # Simulate input module writing commands
        test_command = ParsedCommand(
            command_type=CommandType.MOVEMENT,
            direction='left',
            magnitude=0.8,
            is_continuous=True
        )
        
        # Store command in input buffer
        active_commands = memory.get('input_buffer', 'active_commands', {})
        active_commands['test_key'] = test_command
        memory.update('input_buffer', 'active_commands', active_commands)
        
        # Simulate sense module reading commands
        retrieved_commands = memory.get('input_buffer', 'active_commands', {})
        self.assertIn('test_key', retrieved_commands)
        
        retrieved_command = retrieved_commands['test_key']
        self.assertEqual(retrieved_command.command_type, CommandType.MOVEMENT)
        self.assertEqual(retrieved_command.direction, 'left')
        self.assertEqual(retrieved_command.magnitude, 0.8)
    
    def test_module_health_monitoring(self):
        """Test health monitoring system"""
        memory = GlobalMemory.get_instance()
        
        # Simulate module health updates
        modules = ['Input', 'Sense', 'Plan', 'Act', 'Output']
        
        for module_name in modules:
            # Simulate healthy heartbeat
            heartbeat_data = {
                'timestamp': time.time(),
                'error_count': 0,
                'avg_processing_time': 0.01
            }
            memory.update_module_heartbeat(module_name, heartbeat_data)
            
            # Update status
            memory.update_module_status(module_name, 'running', 'Module operational')
            
            # Verify health data
            health = memory.get_module_health(module_name)
            self.assertEqual(health['status'], 'running')
            self.assertEqual(health['message'], 'Module operational')
            self.assertIn('heartbeat', health)
    
    def test_error_handling(self):
        """Test error handling and recovery"""
        memory = GlobalMemory.get_instance()
        
        # Simulate module error
        memory.update_module_status('TestModule', 'error', 'Simulated error condition')
        
        health = memory.get_module_health('TestModule')
        self.assertEqual(health['status'], 'error')
        self.assertEqual(health['message'], 'Simulated error condition')
        
        # Simulate recovery
        memory.update_module_status('TestModule', 'running', 'Recovered successfully')
        
        health = memory.get_module_health('TestModule')
        self.assertEqual(health['status'], 'running')
        self.assertEqual(health['message'], 'Recovered successfully')


if __name__ == '__main__':
    unittest.main()