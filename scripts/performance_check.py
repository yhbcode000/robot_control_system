#!/usr/bin/env python3
"""
Performance analysis and optimization for Robot Control System
"""

import time
import psutil
import threading
import sys
import os
import yaml
sys.path.append(os.path.dirname(__file__))

from core.memory.memory_store import GlobalMemory
from adapters.mujoco_adapter import MuJoCoAdapter


def measure_memory_performance():
    """Measure memory system performance"""
    print("Testing memory system performance...")
    
    memory = GlobalMemory.get_instance()
    
    # Test basic operations speed
    start_time = time.time()
    for i in range(1000):
        memory.update('perf_test', f'key_{i}', f'value_{i}')
    write_time = time.time() - start_time
    
    start_time = time.time()
    for i in range(1000):
        memory.get('perf_test', f'key_{i}')
    read_time = time.time() - start_time
    
    print(f"  Memory writes (1000 ops): {write_time:.3f}s ({1000/write_time:.0f} ops/sec)")
    print(f"  Memory reads (1000 ops): {read_time:.3f}s ({1000/read_time:.0f} ops/sec)")
    
    return {
        'write_ops_per_sec': 1000 / write_time,
        'read_ops_per_sec': 1000 / read_time,
        'total_time': write_time + read_time
    }


def measure_adapter_performance():
    """Measure adapter initialization and command performance"""
    print("Testing adapter performance...")
    
    # Load config
    with open('robot_control_system/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    adapter_config = config['adapter'].copy()
    adapter_config['render'] = False  # Disable rendering for performance testing
    
    # Test adapter initialization time
    start_time = time.time()
    adapter = MuJoCoAdapter(adapter_config)
    connect_result = adapter.connect()
    init_time = time.time() - start_time
    
    if not connect_result:
        print("  ❌ Adapter connection failed")
        return None
    
    print(f"  Adapter initialization: {init_time:.3f}s")
    
    try:
        # Test joint command performance
        joint_names = adapter_config['joint_names']
        test_positions = [0.0] * len(joint_names)
        
        start_time = time.time()
        for _ in range(100):
            adapter.send_joint_command(joint_names, test_positions)
        command_time = time.time() - start_time
        
        print(f"  Joint commands (100 ops): {command_time:.3f}s ({100/command_time:.0f} ops/sec)")
        
        # Test simulation step performance
        start_time = time.time()
        for _ in range(100):
            adapter.step_simulation()
        step_time = time.time() - start_time
        
        print(f"  Simulation steps (100 ops): {step_time:.3f}s ({100/step_time:.0f} Hz)")
        
        return {
            'init_time': init_time,
            'command_ops_per_sec': 100 / command_time,
            'simulation_hz': 100 / step_time
        }
        
    finally:
        adapter.disconnect()


def measure_threading_performance():
    """Measure multi-threading performance"""
    print("Testing threading performance...")
    
    memory = GlobalMemory.get_instance()
    results = []
    
    def worker_thread(worker_id, operations):
        start_time = time.time()
        for i in range(operations):
            memory.update(f'thread_test_{worker_id}', f'key_{i}', f'value_{i}')
            memory.get(f'thread_test_{worker_id}', f'key_{i}')
        duration = time.time() - start_time
        results.append((worker_id, duration, operations))
    
    # Test with multiple threads
    num_threads = 4
    operations_per_thread = 250
    
    start_time = time.time()
    threads = []
    for i in range(num_threads):
        thread = threading.Thread(target=worker_thread, args=(i, operations_per_thread))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    total_time = time.time() - start_time
    total_operations = num_threads * operations_per_thread * 2  # read + write
    
    print(f"  Concurrent operations ({num_threads} threads): {total_time:.3f}s")
    print(f"  Total throughput: {total_operations/total_time:.0f} ops/sec")
    
    return {
        'concurrent_ops_per_sec': total_operations / total_time,
        'thread_count': num_threads,
        'total_time': total_time
    }


def measure_system_resources():
    """Measure system resource usage"""
    print("Measuring system resources...")
    
    process = psutil.Process()
    
    # Get current resource usage
    cpu_percent = process.cpu_percent()
    memory_info = process.memory_info()
    memory_percent = process.memory_percent()
    
    print(f"  CPU usage: {cpu_percent:.1f}%")
    print(f"  Memory usage: {memory_info.rss / 1024 / 1024:.1f} MB ({memory_percent:.1f}%)")
    print(f"  Thread count: {process.num_threads()}")
    
    return {
        'cpu_percent': cpu_percent,
        'memory_mb': memory_info.rss / 1024 / 1024,
        'memory_percent': memory_percent,
        'thread_count': process.num_threads()
    }


def analyze_performance():
    """Run comprehensive performance analysis"""
    print("=" * 70)
    print("ROBOT CONTROL SYSTEM - PERFORMANCE ANALYSIS")
    print("=" * 70)
    
    # Measure baseline system resources
    baseline_resources = measure_system_resources()
    
    print("\n" + "-" * 50)
    print("PERFORMANCE BENCHMARKS")
    print("-" * 50)
    
    # Run performance tests
    memory_perf = measure_memory_performance()
    threading_perf = measure_threading_performance()
    adapter_perf = measure_adapter_performance()
    
    # Final resource check
    print("\n" + "-" * 50)
    print("FINAL RESOURCE USAGE")
    print("-" * 50)
    final_resources = measure_system_resources()
    
    # Performance analysis
    print("\n" + "-" * 50)
    print("PERFORMANCE ANALYSIS")
    print("-" * 50)
    
    issues = []
    recommendations = []
    
    # Analyze memory performance
    if memory_perf['write_ops_per_sec'] < 10000:
        issues.append("Memory write performance below target (10k ops/sec)")
        recommendations.append("Consider optimizing memory locking strategy")
    
    if memory_perf['read_ops_per_sec'] < 50000:
        issues.append("Memory read performance below target (50k ops/sec)")
        recommendations.append("Consider read-optimized data structures")
    
    # Analyze adapter performance
    if adapter_perf and adapter_perf['init_time'] > 2.0:
        issues.append("Adapter initialization slow (>2s)")
        recommendations.append("Consider lazy loading of mesh assets")
    
    if adapter_perf and adapter_perf['simulation_hz'] < 100:
        issues.append("Simulation frequency below target (100 Hz)")
        recommendations.append("Optimize physics timestep or disable rendering")
    
    # Analyze resource usage
    if final_resources['memory_mb'] > 500:
        issues.append("High memory usage (>500 MB)")
        recommendations.append("Profile memory usage and optimize data structures")
    
    if final_resources['thread_count'] > 20:
        issues.append("High thread count")
        recommendations.append("Review thread pooling and lifecycle management")
    
    # Print results
    if issues:
        print("⚠️  PERFORMANCE ISSUES DETECTED:")
        for issue in issues:
            print(f"  • {issue}")
        
        print("\n💡 RECOMMENDATIONS:")
        for rec in recommendations:
            print(f"  • {rec}")
    else:
        print("✅ NO PERFORMANCE ISSUES DETECTED")
        print("System performance is within acceptable limits.")
    
    # Performance score
    score = 100
    score -= len(issues) * 10
    score = max(0, score)
    
    print(f"\n📊 PERFORMANCE SCORE: {score}/100")
    
    if score >= 80:
        print("🟢 EXCELLENT: System performance is optimal")
    elif score >= 60:
        print("🟡 GOOD: Minor optimizations recommended")
    elif score >= 40:
        print("🟠 FAIR: Some performance issues need attention")
    else:
        print("🔴 POOR: Significant performance optimization required")
    
    print("=" * 70)
    
    return score >= 60


if __name__ == '__main__':
    success = analyze_performance()
    sys.exit(0 if success else 1)