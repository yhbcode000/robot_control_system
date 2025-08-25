#!/usr/bin/env python3
"""
Integration tests for the complete robot control system
"""

import unittest
import threading
import time
import sys
import os
import yaml
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.memory.memory_store import GlobalMemory
from adapters.mujoco_adapter import MuJoCoAdapter
from modules.input.models import ParsedCommand, CommandType
from modules.watchdog.watchdog_module import WatchdogModule


class TestSystemIntegration(unittest.TestCase):
    """Test cases for complete system integration"""
    
    def setUp(self):
        """Set up test environment"""
        GlobalMemory._instance = None
        GlobalMemory._lock = threading.Lock()
        
        # Load test configuration
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
    
    def test_complete_command_flow(self):
        """Test complete command flow from input to adapter"""
        memory = GlobalMemory.get_instance()
        
        # Initialize adapter
        adapter = MuJoCoAdapter(self.config['adapter'])
        self.assertTrue(adapter.connect(), "Adapter should connect successfully")
        
        try:
            # Simulate input command
            command = ParsedCommand(
                command_type=CommandType.MOVEMENT,
                direction='forward',
                magnitude=0.5,
                is_continuous=False
            )
            
            # Store in input buffer (simulating Input module)
            active_commands = memory.get('input_buffer', 'active_commands', {})
            active_commands['test_command'] = command
            memory.update('input_buffer', 'active_commands', active_commands)
            
            # Verify command storage
            retrieved_commands = memory.get('input_buffer', 'active_commands', {})
            self.assertIn('test_command', retrieved_commands)
            
            # Simulate Sense module processing
            processed_command = retrieved_commands['test_command']
            memory.update('sense_buffer', 'parsed_commands', [processed_command])
            
            # Simulate Plan module generating trajectory
            trajectory = {
                'joint_names': self.config['adapter']['joint_names'],
                'positions': [0.1, -0.1, 0.1, -0.1, -0.1, 0.1],
                'velocities': [0.0] * 6,
                'timestamp': time.time()
            }
            memory.update('plan_buffer', 'current_trajectory', trajectory)
            
            # Simulate Act module executing command
            current_trajectory = memory.get('plan_buffer', 'current_trajectory')
            if current_trajectory:
                result = adapter.send_joint_command(
                    current_trajectory['joint_names'],
                    current_trajectory['positions']
                )
                self.assertTrue(result, "Joint command execution should succeed")
            
            # Simulate Output module formatting response
            output_data = {
                'status': 'success',
                'joint_positions': current_trajectory['positions'],
                'timestamp': time.time()
            }
            memory.update('output_buffer', 'last_output', output_data)
            
            # Verify complete flow
            final_output = memory.get('output_buffer', 'last_output')
            self.assertEqual(final_output['status'], 'success')
            self.assertEqual(len(final_output['joint_positions']), 6)
            
        finally:
            adapter.disconnect()
    
    def test_watchdog_monitoring(self):
        """Test watchdog monitoring of system health"""
        memory = GlobalMemory.get_instance()
        
        # Configure watchdog with fast intervals for testing
        watchdog_config = {
            'enabled': True,
            'check_interval': 0.1,
            'heartbeat_timeout': 0.5,
            'heartbeat_warning': 0.3,
            'auto_restart': False,  # Disable auto-restart for testing
            'max_restart_attempts': 3,
            'recovery_strategy': 'restart',
            'recovery_cooldown': 1.0,
            'alerts': {'console': False, 'sound': False}  # Quiet for testing
        }
        
        watchdog = WatchdogModule(watchdog_config)
        
        # Simulate healthy module
        memory.update_module_status('TestModule', 'running', 'Module operational')
        heartbeat_data = {
            'timestamp': time.time(),
            'error_count': 0,
            'avg_processing_time': 0.01
        }
        memory.update_module_heartbeat('TestModule', heartbeat_data)
        
        # Start watchdog briefly
        watchdog.start()
        time.sleep(0.2)  # Let it run a few cycles
        watchdog.stop()
        
        # Verify watchdog recorded its own health
        watchdog_health = memory.get_module_health('Watchdog')
        self.assertIsNotNone(watchdog_health)
        self.assertIn('heartbeat', watchdog_health)
    
    def test_concurrent_module_operations(self):
        """Test concurrent module operations"""
        memory = GlobalMemory.get_instance()
        results = []
        
        def simulate_module(module_name, operation_count):
            """Simulate a module performing operations"""
            for i in range(operation_count):
                # Simulate processing
                time.sleep(0.001)
                
                # Update heartbeat
                heartbeat_data = {
                    'timestamp': time.time(),
                    'error_count': 0,
                    'avg_processing_time': 0.001
                }
                memory.update_module_heartbeat(module_name, heartbeat_data)
                
                # Store some data
                memory.update(f'{module_name}_buffer', f'data_{i}', f'value_{i}')
                
                results.append((module_name, i))
        
        # Start multiple simulated modules
        modules = ['Input', 'Sense', 'Plan', 'Act', 'Output']
        threads = []
        
        for module_name in modules:
            thread = threading.Thread(
                target=simulate_module,
                args=(module_name, 10)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all modules to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations completed
        self.assertEqual(len(results), 50)  # 5 modules * 10 operations each
        
        # Verify health data for all modules
        for module_name in modules:
            health = memory.get_module_health(module_name)
            self.assertIsNotNone(health)
            self.assertIn('heartbeat', health)
    
    def test_error_recovery_flow(self):
        """Test error detection and recovery flow"""
        memory = GlobalMemory.get_instance()
        
        # Simulate module error
        memory.update_module_status('TestModule', 'error', 'Simulated failure')
        
        # Verify error status
        health = memory.get_module_health('TestModule')
        self.assertEqual(health['status'], 'error')
        
        # Simulate recovery process
        memory.update_module_status('TestModule', 'restarting', 'Attempting recovery')
        time.sleep(0.1)
        
        memory.update_module_status('TestModule', 'running', 'Successfully recovered')
        heartbeat_data = {
            'timestamp': time.time(),
            'error_count': 1,  # Incremented due to previous error
            'avg_processing_time': 0.01
        }
        memory.update_module_heartbeat('TestModule', heartbeat_data)
        
        # Verify recovery
        final_health = memory.get_module_health('TestModule')
        self.assertEqual(final_health['status'], 'running')
        self.assertEqual(final_health['message'], 'Successfully recovered')
        self.assertEqual(final_health['heartbeat']['error_count'], 1)
    
    def test_performance_metrics(self):
        """Test performance metrics collection"""
        memory = GlobalMemory.get_instance()
        
        # Simulate modules with different performance characteristics
        modules_data = [
            ('FastModule', 0.001, 0),
            ('SlowModule', 0.1, 0),
            ('ErrorProneModule', 0.01, 5)
        ]
        
        for module_name, avg_time, error_count in modules_data:
            heartbeat_data = {
                'timestamp': time.time(),
                'error_count': error_count,
                'avg_processing_time': avg_time
            }
            memory.update_module_heartbeat(module_name, heartbeat_data)
        
        # Verify metrics collection
        for module_name, expected_time, expected_errors in modules_data:
            health = memory.get_module_health(module_name)
            self.assertEqual(health['heartbeat']['avg_processing_time'], expected_time)
            self.assertEqual(health['heartbeat']['error_count'], expected_errors)


if __name__ == '__main__':
    unittest.main()