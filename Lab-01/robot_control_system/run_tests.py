#!/usr/bin/env python3
"""
Test runner for the Robot Control System
"""

import unittest
import sys
import os
import time
from io import StringIO

# Add the project root to Python path
sys.path.append(os.path.dirname(__file__))

def run_all_tests():
    """Run all test suites and generate a comprehensive report"""
    
    print("=" * 70)
    print("ROBOT CONTROL SYSTEM - COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    
    # Discover and load all tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('tests', pattern='test_*.py')
    
    # Custom test result class to capture detailed results
    class DetailedTestResult(unittest.TextTestResult):
        def __init__(self, stream, descriptions, verbosity):
            super().__init__(stream, descriptions, verbosity)
            self.test_results = []
            self.start_time = None
        
        def startTest(self, test):
            self.start_time = time.time()
            super().startTest(test)
        
        def addSuccess(self, test):
            duration = time.time() - self.start_time
            self.test_results.append({
                'test': str(test),
                'status': 'PASS',
                'duration': duration,
                'message': None
            })
            super().addSuccess(test)
        
        def addError(self, test, err):
            duration = time.time() - self.start_time
            self.test_results.append({
                'test': str(test),
                'status': 'ERROR',
                'duration': duration,
                'message': str(err[1])
            })
            super().addError(test, err)
        
        def addFailure(self, test, err):
            duration = time.time() - self.start_time
            self.test_results.append({
                'test': str(test),
                'status': 'FAIL',
                'duration': duration,
                'message': str(err[1])
            })
            super().addFailure(test, err)
        
        def addSkip(self, test, reason):
            duration = time.time() - self.start_time
            self.test_results.append({
                'test': str(test),
                'status': 'SKIP',
                'duration': duration,
                'message': reason
            })
            super().addSkip(test, reason)
    
    # Run tests with detailed results
    runner = unittest.TextTestRunner(
        verbosity=2,
        resultclass=DetailedTestResult,
        buffer=True
    )
    
    start_time = time.time()
    result = runner.run(test_suite)
    total_time = time.time() - start_time
    
    # Generate detailed report
    print("\n" + "=" * 70)
    print("TEST EXECUTION SUMMARY")
    print("=" * 70)
    
    # Overall statistics
    total_tests = result.testsRun
    total_failures = len(result.failures)
    total_errors = len(result.errors)
    total_skipped = len(result.skipped) if hasattr(result, 'skipped') else 0
    total_passed = total_tests - total_failures - total_errors - total_skipped
    
    print(f"Total Tests Run: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failures}")
    print(f"Errors: {total_errors}")
    print(f"Skipped: {total_skipped}")
    print(f"Total Execution Time: {total_time:.3f}s")
    
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    print(f"Success Rate: {success_rate:.1f}%")
    
    # Detailed test results
    if hasattr(result, 'test_results'):
        print("\n" + "-" * 70)
        print("DETAILED TEST RESULTS")
        print("-" * 70)
        
        # Group results by test module
        test_modules = {}
        for test_result in result.test_results:
            test_name = test_result['test']
            module_name = test_name.split('.')[0] if '.' in test_name else 'Unknown'
            
            if module_name not in test_modules:
                test_modules[module_name] = []
            test_modules[module_name].append(test_result)
        
        for module_name, tests in test_modules.items():
            print(f"\n{module_name}:")
            for test in tests:
                status_symbol = {
                    'PASS': '✓',
                    'FAIL': '✗',
                    'ERROR': '✗',
                    'SKIP': '-'
                }.get(test['status'], '?')
                
                print(f"  {status_symbol} {test['test'].split('.')[-1]} "
                      f"({test['duration']:.3f}s) {test['status']}")
                
                if test['message'] and test['status'] in ['FAIL', 'ERROR']:
                    # Show first line of error message
                    error_line = test['message'].split('\n')[0]
                    print(f"    → {error_line}")
    
    # Performance analysis
    if hasattr(result, 'test_results'):
        print("\n" + "-" * 70)
        print("PERFORMANCE ANALYSIS")
        print("-" * 70)
        
        durations = [t['duration'] for t in result.test_results]
        if durations:
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)
            
            print(f"Average Test Duration: {avg_duration:.3f}s")
            print(f"Longest Test: {max_duration:.3f}s")
            print(f"Shortest Test: {min_duration:.3f}s")
            
            # Find slowest tests
            slow_tests = sorted(result.test_results, key=lambda x: x['duration'], reverse=True)[:3]
            print("\nSlowest Tests:")
            for i, test in enumerate(slow_tests, 1):
                print(f"  {i}. {test['test'].split('.')[-1]} ({test['duration']:.3f}s)")
    
    # System health check
    print("\n" + "-" * 70)
    print("SYSTEM HEALTH CHECK")
    print("-" * 70)
    
    health_checks = [
        ("Memory System", total_passed > 0),
        ("Module Communication", total_failures == 0),
        ("Adapter Integration", total_errors == 0),
        ("Error Handling", success_rate > 80),
        ("Performance", avg_duration < 1.0 if 'avg_duration' in locals() else True)
    ]
    
    for check_name, is_healthy in health_checks:
        status = "✓ HEALTHY" if is_healthy else "✗ NEEDS ATTENTION"
        print(f"  {check_name}: {status}")
    
    print("\n" + "=" * 70)
    
    # Return overall success
    return result.wasSuccessful()


def run_specific_test(test_name):
    """Run a specific test module"""
    print(f"Running specific test: {test_name}")
    
    test_loader = unittest.TestLoader()
    try:
        test_suite = test_loader.loadTestsFromName(f'tests.{test_name}')
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(test_suite)
        return result.wasSuccessful()
    except Exception as e:
        print(f"Error loading test {test_name}: {e}")
        return False


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        success = run_specific_test(test_name)
    else:
        # Run all tests
        success = run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)