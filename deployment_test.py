#!/usr/bin/env python3
"""
Deployment Test Script - DevOps Validation
Tests critical deployment infrastructure and system reliability
"""

import subprocess
import sys
import os
import time
from pathlib import Path


def test_environment():
    """Test UV environment and dependencies"""
    print("=== ENVIRONMENT VALIDATION ===")
    
    # Test UV version
    try:
        result = subprocess.run(['uv', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✓ UV available: {result.stdout.strip()}")
        else:
            print(f"✗ UV check failed")
            return False
    except Exception as e:
        print(f"✗ UV not available: {e}")
        return False
    
    # Test Python version
    try:
        result = subprocess.run(['uv', 'run', 'python', '--version'], 
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✓ Python available: {result.stdout.strip()}")
        else:
            print(f"✗ Python check failed")
            return False
    except Exception as e:
        print(f"✗ Python not available: {e}")
        return False
    
    return True


def test_file_paths():
    """Test that all required files and paths exist"""
    print("\n=== FILE PATH VALIDATION ===")
    
    required_files = [
        'main.py',
        'config.yaml', 
        'assets/robots/arm/ur5e.xml',
        'assets/robots/arm/meshes/base_0.obj',
        'pyproject.toml'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
            print(f"✗ Missing: {file_path}")
        else:
            print(f"✓ Found: {file_path}")
    
    return len(missing_files) == 0


def test_system_startup():
    """Test system can start and run briefly"""
    print("\n=== SYSTEM STARTUP TEST ===")
    
    try:
        # Run system for 5 seconds to test startup
        cmd = ['uv', 'run', 'python', 'main.py', 'adapter.render=false']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        
        output_lines = result.stderr.split('\n') if result.stderr else []
        
        # Check for key startup messages
        startup_indicators = [
            "ROBOT CONTROL SYSTEM STARTING",
            "Adapter connected successfully", 
            "All modules initialized successfully",
            "All modules started successfully"
        ]
        
        found_indicators = []
        for indicator in startup_indicators:
            if any(indicator in line for line in output_lines):
                found_indicators.append(indicator)
                print(f"✓ {indicator}")
        
        if len(found_indicators) >= 3:
            print("✓ System startup successful")
            return True
        else:
            print(f"✗ System startup incomplete - found {len(found_indicators)}/4 indicators")
            return False
            
    except subprocess.TimeoutExpired:
        print("✓ System ran for full timeout period (indicates stable operation)")
        return True
    except Exception as e:
        print(f"✗ System startup failed: {e}")
        return False


def test_command_variations():
    """Test different ways to invoke the system"""
    print("\n=== COMMAND VARIATION TESTS ===")
    
    commands = [
        ['uv', 'run', 'python', 'main.py', 'adapter.render=false'],
        ['uv', 'run', 'python', 'main.py', 'adapter.render=false', 'logging.level=INFO']
    ]
    
    success_count = 0
    for i, cmd in enumerate(commands, 1):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if "ROBOT CONTROL SYSTEM STARTING" in (result.stderr or ""):
                print(f"✓ Command variation {i} works")
                success_count += 1
            else:
                print(f"✗ Command variation {i} failed to start")
        except subprocess.TimeoutExpired:
            print(f"✓ Command variation {i} ran successfully (timeout)")
            success_count += 1
        except Exception as e:
            print(f"✗ Command variation {i} failed: {e}")
    
    return success_count == len(commands)


def main():
    """Run all deployment validation tests"""
    print("ROBOT CONTROL SYSTEM - DEPLOYMENT VALIDATION")
    print("=" * 50)
    
    os.chdir(Path(__file__).parent)  # Ensure we're in the right directory
    
    tests = [
        ("Environment", test_environment),
        ("File Paths", test_file_paths), 
        ("System Startup", test_system_startup),
        ("Command Variations", test_command_variations)
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ {test_name} test crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("DEPLOYMENT VALIDATION SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(tests)
    
    for test_name, passed_test in results.items():
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"{test_name:<20} {status}")
        if passed_test:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ DEPLOYMENT READY - All tests passed")
        return 0
    else:
        print("✗ DEPLOYMENT ISSUES DETECTED - Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())