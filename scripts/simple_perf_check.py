#!/usr/bin/env python3
"""
Simple performance check for Robot Control System core components
"""

import time
import threading
import sys
import os
sys.path.append(os.path.dirname(__file__))

from core.memory.memory_store import GlobalMemory


def test_memory_performance():
    """Test memory system performance"""
    print("Testing memory system performance...")
    
    memory = GlobalMemory.get_instance()
    
    # Test write performance
    start_time = time.time()
    for i in range(1000):
        memory.update('perf_test', f'key_{i}', f'value_{i}')
    write_time = time.time() - start_time
    
    # Test read performance  
    start_time = time.time()
    for i in range(1000):
        memory.get('perf_test', f'key_{i}')
    read_time = time.time() - start_time
    
    write_ops_per_sec = 1000 / write_time
    read_ops_per_sec = 1000 / read_time
    
    print(f"  ✓ Memory writes: {write_ops_per_sec:.0f} ops/sec")
    print(f"  ✓ Memory reads: {read_ops_per_sec:.0f} ops/sec")
    
    return write_ops_per_sec > 10000 and read_ops_per_sec > 50000


def test_threading_performance():
    """Test concurrent access performance"""
    print("Testing threading performance...")
    
    memory = GlobalMemory.get_instance()
    success_count = 0
    
    def worker(worker_id):
        nonlocal success_count
        try:
            for i in range(100):
                memory.update(f'thread_test_{worker_id}', f'key_{i}', f'value_{i}')
                memory.get(f'thread_test_{worker_id}', f'key_{i}')
            success_count += 1
        except Exception as e:
            print(f"    Thread {worker_id} error: {e}")
    
    start_time = time.time()
    threads = []
    for i in range(4):
        thread = threading.Thread(target=worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    total_time = time.time() - start_time
    total_ops = 4 * 100 * 2  # 4 threads, 100 ops each, read+write
    throughput = total_ops / total_time
    
    print(f"  ✓ Concurrent throughput: {throughput:.0f} ops/sec")
    print(f"  ✓ Thread success rate: {success_count}/4")
    
    return success_count == 4 and throughput > 1000


def test_heartbeat_performance():
    """Test heartbeat system performance"""
    print("Testing heartbeat performance...")
    
    memory = GlobalMemory.get_instance()
    
    start_time = time.time()
    for i in range(100):
        heartbeat_data = {
            'timestamp': time.time(),
            'error_count': 0,
            'avg_processing_time': 0.001
        }
        memory.update_module_heartbeat(f'test_module_{i}', heartbeat_data)
    heartbeat_time = time.time() - start_time
    
    start_time = time.time()
    for i in range(100):
        memory.get_module_heartbeat(f'test_module_{i}')
    retrieve_time = time.time() - start_time
    
    heartbeat_ops_per_sec = 100 / heartbeat_time
    retrieve_ops_per_sec = 100 / retrieve_time
    
    print(f"  ✓ Heartbeat updates: {heartbeat_ops_per_sec:.0f} ops/sec")
    print(f"  ✓ Heartbeat retrieval: {retrieve_ops_per_sec:.0f} ops/sec")
    
    return heartbeat_ops_per_sec > 1000 and retrieve_ops_per_sec > 5000


def run_performance_check():
    """Run all performance checks"""
    print("=" * 60)
    print("ROBOT CONTROL SYSTEM - PERFORMANCE CHECK")
    print("=" * 60)
    
    results = []
    
    # Test memory system
    results.append(test_memory_performance())
    
    # Test threading
    results.append(test_threading_performance())
    
    # Test heartbeat system
    results.append(test_heartbeat_performance())
    
    print("\n" + "=" * 60)
    print("PERFORMANCE RESULTS")
    print("=" * 60)
    
    test_names = [
        "Memory System Performance",
        "Threading Performance", 
        "Heartbeat System Performance"
    ]
    
    passed_tests = 0
    for i, (test_name, passed) in enumerate(zip(test_names, results)):
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:30} : {status}")
        if passed:
            passed_tests += 1
    
    success_rate = (passed_tests / len(results)) * 100
    
    print("-" * 60)
    print(f"Performance Tests Passed: {passed_tests}/{len(results)} ({success_rate:.1f}%)")
    
    if success_rate == 100:
        print("\n🎉 EXCELLENT: All performance tests passed!")
        print("System is running at optimal performance.")
    elif success_rate >= 75:
        print("\n✅ GOOD: Most performance tests passed.")
        print("System performance is acceptable with minor issues.")
    elif success_rate >= 50:
        print("\n⚠️  FAIR: Some performance issues detected.")
        print("Consider optimization to improve system performance.")
    else:
        print("\n❌ POOR: Multiple performance issues detected.")
        print("System requires performance optimization.")
    
    print("=" * 60)
    
    return success_rate >= 75


if __name__ == '__main__':
    success = run_performance_check()
    sys.exit(0 if success else 1)