#!/usr/bin/env python3
"""
Tests for the global memory system
"""

import unittest
import threading
import time
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.memory.memory_store import GlobalMemory


class TestGlobalMemory(unittest.TestCase):
    """Test cases for GlobalMemory singleton"""
    
    def setUp(self):
        """Reset memory instance before each test"""
        # Clear the singleton instance for clean testing
        GlobalMemory._instance = None
        GlobalMemory._lock = threading.Lock()
    
    def test_singleton_behavior(self):
        """Test that GlobalMemory maintains singleton pattern"""
        memory1 = GlobalMemory.get_instance()
        memory2 = GlobalMemory.get_instance()
        
        self.assertIs(memory1, memory2, "GlobalMemory should return same instance")
    
    def test_thread_safety(self):
        """Test thread-safe access to memory"""
        instances = []
        
        def get_instance():
            instances.append(GlobalMemory.get_instance())
        
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=get_instance)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All instances should be the same
        first_instance = instances[0]
        for instance in instances:
            self.assertIs(instance, first_instance)
    
    def test_namespace_operations(self):
        """Test namespace-based data storage and retrieval"""
        memory = GlobalMemory.get_instance()
        
        # Test setting and getting data
        memory.update('test_ns', 'key1', 'value1')
        self.assertEqual(memory.get('test_ns', 'key1'), 'value1')
        
        # Test default values
        self.assertEqual(memory.get('test_ns', 'nonexistent', 'default'), 'default')
        
        # Test complex data structures
        test_data = {'nested': {'data': [1, 2, 3]}}
        memory.update('test_ns', 'complex', test_data)
        retrieved = memory.get('test_ns', 'complex')
        self.assertEqual(retrieved, test_data)
    
    def test_observer_pattern(self):
        """Test observer notifications"""
        memory = GlobalMemory.get_instance()
        notifications = []
        
        def observer(key, value):
            notifications.append((key, value))
        
        # Subscribe to namespace-level notifications
        namespace_obj = memory._namespaces.get('test_ns')
        if not namespace_obj:
            from core.memory.memory_types import MemoryNamespace
            memory._namespaces['test_ns'] = MemoryNamespace()
        
        memory._namespaces['test_ns'].subscribe(observer)
        
        # Update data and check notifications
        memory.update('test_ns', 'observed_key', 'observed_value')
        
        # Should receive notification
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0], ('observed_key', 'observed_value'))
    
    def test_health_tracking(self):
        """Test health status tracking for modules"""
        memory = GlobalMemory.get_instance()
        
        # Test heartbeat updates
        heartbeat_data = {
            'timestamp': time.time(),
            'error_count': 0,
            'avg_processing_time': 0.01
        }
        
        memory.update_module_heartbeat('test_module', heartbeat_data)
        
        # Use the correct method to get heartbeat data
        heartbeat = memory.get_module_heartbeat('test_module')
        self.assertIsNotNone(heartbeat)
        # HeartbeatInfo is a dataclass, access attributes directly
        self.assertEqual(heartbeat.timestamp, heartbeat_data['timestamp'])
        self.assertEqual(heartbeat.error_count, heartbeat_data['error_count'])
    
    def test_module_status_updates(self):
        """Test module status updates"""
        memory = GlobalMemory.get_instance()
        
        # Test metrics updates with correct parameters
        from core.memory.memory_types import ModuleMetrics
        
        metrics = ModuleMetrics(
            module_name='test_module',
            last_heartbeat=time.time(),
            processing_time=0.01,
            error_count=0,
            throughput=10.0,
            queue_size=5
        )
        
        memory.update_module_metrics('test_module', metrics)
        
        # Verify metrics were stored
        health_data = memory.get('health_status', 'data', {})
        self.assertIn('module_metrics', health_data)
        self.assertIn('test_module', health_data['module_metrics'])
        
        stored_metrics = health_data['module_metrics']['test_module']
        self.assertEqual(stored_metrics.module_name, 'test_module')
        self.assertEqual(stored_metrics.error_count, 0)
    
    def test_concurrent_access(self):
        """Test concurrent read/write operations"""
        memory = GlobalMemory.get_instance()
        results = []
        
        def worker(worker_id):
            for i in range(100):
                memory.update('concurrent_test', f'worker_{worker_id}_key_{i}', f'value_{i}')
                value = memory.get('concurrent_test', f'worker_{worker_id}_key_{i}')
                results.append((worker_id, i, value))
        
        threads = []
        for worker_id in range(5):
            thread = threading.Thread(target=worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all operations completed successfully
        self.assertEqual(len(results), 500)  # 5 workers * 100 operations each
        
        # Verify data integrity
        for worker_id, i, value in results:
            self.assertEqual(value, f'value_{i}')


if __name__ == '__main__':
    unittest.main()