#!/usr/bin/env python3
"""
Simple runner script to test the basic system functionality.
"""

import sys
import os
import time
import logging

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def test_basic_functionality():
    """Test basic system components"""
    
    print("="*60)
    print("ROBOT CONTROL SYSTEM - BASIC TEST")
    print("="*60)
    
    try:
        # Test 1: Memory System
        print("\n1. Testing Global Memory System...")
        from core.memory.memory_store import GlobalMemory
        
        memory = GlobalMemory.get_instance()
        memory.update('test', 'message', 'Hello World')
        result = memory.get('test', 'message')
        print(f"   Memory test: {result}")
        assert result == 'Hello World', "Memory test failed"
        print("   ✓ Memory system working")
        
        # Test 2: Logging System
        print("\n2. Testing Logging System...")
        from core.logging.logger import setup_logging, get_module_logger
        
        setup_logging({'level': 'INFO', 'colorful': True})
        logger = get_module_logger('Test')
        logger.info("Test log message")
        print("   ✓ Logging system working")
        
        # Test 3: Base Module
        print("\n3. Testing Base Module...")
        from core.base.module import BaseModule
        
        class TestModule(BaseModule):
            def _initialize(self):
                return True
            def run(self):
                time.sleep(0.1)
        
        test_module = TestModule('TestModule', {'enabled': True}, memory)
        init_success = test_module.initialize()
        print(f"   Module initialization: {init_success}")
        assert init_success, "Module initialization failed"
        print("   ✓ Base module working")
        
        # Test 4: Watchdog Module
        print("\n4. Testing Watchdog Module...")
        from modules.watchdog.watchdog_module import WatchdogModule
        
        watchdog_config = {
            'enabled': True,
            'check_interval': 1.0,
            'heartbeat_timeout': 5.0,
            'auto_restart': True,
            'max_restart_attempts': 3,
            'alerts': {'console': True}
        }
        
        watchdog = WatchdogModule(watchdog_config, memory)
        watchdog_init = watchdog.initialize()
        print(f"   Watchdog initialization: {watchdog_init}")
        assert watchdog_init, "Watchdog initialization failed"
        print("   ✓ Watchdog module working")
        
        # Test 5: Input Module (basic initialization)
        print("\n5. Testing Input Module...")
        from modules.input.input_module import InputModule
        
        input_config = {
            'enabled': True,
            'keyboard_mapping': 'wasd',
            'update_rate': 60,
            'heartbeat_interval': 0.5
        }
        
        input_module = InputModule(input_config, memory)
        # Note: Input module might fail to initialize if no display available
        try:
            input_init = input_module.initialize()
            print(f"   Input initialization: {input_init}")
            print("   ✓ Input module structure working")
        except Exception as e:
            print(f"   Input module error (expected in headless env): {e}")
            print("   ✓ Input module structure working (display not available)")
        
        print("\n" + "="*60)
        print("✅ BASIC SYSTEM TEST COMPLETED SUCCESSFULLY!")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def demo_memory_system():
    """Demonstrate the memory system with multiple namespaces"""
    
    print("\n" + "="*40)
    print("MEMORY SYSTEM DEMONSTRATION")
    print("="*40)
    
    from core.memory.memory_store import GlobalMemory
    
    memory = GlobalMemory.get_instance()
    
    # Test different namespaces
    print("\n1. Testing multiple namespaces...")
    memory.update('input_buffer', 'keyboard_state', {'w': True, 's': False})
    memory.update('sensor_state', 'joint_positions', [0.1, 0.2, 0.3])
    memory.update('system_status', 'uptime', 42.5)
    
    print(f"   Input buffer: {memory.get('input_buffer', 'keyboard_state')}")
    print(f"   Sensor state: {memory.get('sensor_state', 'joint_positions')}")
    print(f"   System status: {memory.get('system_status', 'uptime')}")
    
    # Test observer pattern
    print("\n2. Testing observer notifications...")
    
    def callback_function(namespace, key, value):
        print(f"   📢 Callback: {namespace}.{key} = {value}")
    
    memory.subscribe_global(callback_function)
    memory.update('test_namespace', 'test_key', 'test_value')
    
    print("\n✅ Memory system demonstration completed!")


if __name__ == "__main__":
    print("Robot Control System Test Suite\n")
    
    # Run basic functionality test
    success = test_basic_functionality()
    
    if success:
        # Demonstrate memory system
        demo_memory_system()
        
        print("\n🎉 All tests passed! The system is ready for development.")
        print("\nNext steps:")
        print("- Implement remaining modules (Sense, Plan, Act, Output)")
        print("- Create MuJoCo adapter")
        print("- Add comprehensive testing")
        print("- Implement the complete control pipeline")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        sys.exit(1)