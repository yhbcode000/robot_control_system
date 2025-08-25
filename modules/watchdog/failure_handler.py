import time
import threading
from typing import Dict, Optional, Any
from collections import deque
import logging

from .models import RecoveryStrategy, FailureType, FailureEvent
from core.base.module import BaseModule


class FailureHandler:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger('FailureHandler')
        self.recovery_attempts: Dict[str, int] = {}
        self.failure_history: deque = deque(maxlen=100)
        self.max_restart_attempts = config.get('max_restart_attempts', 3)
        self.recovery_cooldown = config.get('recovery_cooldown', 5.0)
        self.last_recovery_time: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def determine_recovery_strategy(self, module_name: str, 
                                   failures: list) -> RecoveryStrategy:
        with self._lock:
            # Check if we're in cooldown
            if self._in_cooldown(module_name):
                return RecoveryStrategy.NONE
            
            # Get attempt count
            attempts = self.recovery_attempts.get(module_name, 0)
            
            # If too many attempts, give up or escalate
            if attempts >= self.max_restart_attempts:
                self.logger.warning(f"Module {module_name} exceeded max recovery attempts")
                return RecoveryStrategy.ISOLATE
            
            # Determine strategy based on failure types
            if FailureType.CRITICAL_ERROR in failures:
                return RecoveryStrategy.EMERGENCY_STOP
            
            if FailureType.FROZEN_THREAD in failures:
                return RecoveryStrategy.RESTART
            
            if FailureType.HEARTBEAT_TIMEOUT in failures:
                if attempts == 0:
                    return RecoveryStrategy.RESET
                else:
                    return RecoveryStrategy.RESTART
            
            if FailureType.HIGH_ERROR_RATE in failures:
                return RecoveryStrategy.RESET
            
            if FailureType.MEMORY_LEAK in failures:
                return RecoveryStrategy.RESTART
            
            if FailureType.CPU_OVERLOAD in failures:
                return RecoveryStrategy.DEGRADE
            
            if FailureType.PERFORMANCE_DEGRADATION in failures:
                return RecoveryStrategy.DEGRADE
            
            if FailureType.QUEUE_OVERFLOW in failures:
                return RecoveryStrategy.RESET
            
            return RecoveryStrategy.NONE
    
    def execute_recovery(self, module: BaseModule, strategy: RecoveryStrategy) -> bool:
        module_name = module.name
        
        with self._lock:
            # Record the attempt
            self.recovery_attempts[module_name] = self.recovery_attempts.get(module_name, 0) + 1
            self.last_recovery_time[module_name] = time.time()
            
            # Create failure event
            event = FailureEvent(
                module_name=module_name,
                failure_type=FailureType.HIGH_ERROR_RATE,  # Should be passed in
                recovery_strategy=strategy,
                recovery_attempted=True
            )
        
        try:
            self.logger.info(f"Executing {strategy.value} recovery for {module_name}")
            
            if strategy == RecoveryStrategy.RESTART:
                return self._restart_module(module)
            
            elif strategy == RecoveryStrategy.RESET:
                return self._reset_module(module)
            
            elif strategy == RecoveryStrategy.DEGRADE:
                return self._degrade_module(module)
            
            elif strategy == RecoveryStrategy.ISOLATE:
                return self._isolate_module(module)
            
            elif strategy == RecoveryStrategy.EMERGENCY_STOP:
                return self._emergency_stop(module)
            
            else:
                return True
            
        except Exception as e:
            self.logger.error(f"Recovery failed for {module_name}: {e}")
            event.recovery_successful = False
            return False
        
        finally:
            with self._lock:
                event.recovery_successful = True
                self.failure_history.append(event)
    
    def _restart_module(self, module: BaseModule) -> bool:
        try:
            self.logger.info(f"Restarting module {module.name}")
            
            # Stop the module
            module.stop()
            
            # Wait a moment
            time.sleep(0.5)
            
            # Restart the module
            module.start()
            
            # Verify it started
            time.sleep(0.5)
            if module.running:
                self.logger.info(f"Module {module.name} restarted successfully")
                return True
            else:
                self.logger.error(f"Module {module.name} failed to restart")
                return False
                
        except Exception as e:
            self.logger.error(f"Error restarting module {module.name}: {e}")
            return False
    
    def _reset_module(self, module: BaseModule) -> bool:
        try:
            self.logger.info(f"Resetting module {module.name}")
            
            # Clear module error counts
            module.error_count = 0
            module.consecutive_errors = 0
            
            # Clear any module-specific state
            if hasattr(module, 'reset'):
                module.reset()
            
            # Clear memory namespace for this module if it exists
            module.memory.clear_namespace(f"{module.name}_buffer")
            
            self.logger.info(f"Module {module.name} reset successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error resetting module {module.name}: {e}")
            return False
    
    def _degrade_module(self, module: BaseModule) -> bool:
        try:
            self.logger.info(f"Degrading module {module.name}")
            
            # Reduce update rate if possible
            if 'update_rate' in module.config:
                original_rate = module.config['update_rate']
                module.config['update_rate'] = max(1, original_rate // 2)
                self.logger.info(f"Reduced {module.name} update rate from {original_rate} to {module.config['update_rate']}")
            
            # Set degraded flag
            if hasattr(module, 'degraded'):
                module.degraded = True
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error degrading module {module.name}: {e}")
            return False
    
    def _isolate_module(self, module: BaseModule) -> bool:
        try:
            self.logger.warning(f"Isolating module {module.name}")
            
            # Stop the module
            module.stop()
            
            # Mark as isolated
            module.enabled = False
            
            self.logger.warning(f"Module {module.name} isolated from system")
            return True
            
        except Exception as e:
            self.logger.error(f"Error isolating module {module.name}: {e}")
            return False
    
    def _emergency_stop(self, module: BaseModule) -> bool:
        self.logger.critical(f"EMERGENCY STOP triggered by {module.name}")
        
        # This should trigger system-wide emergency stop
        # For now, just stop the problematic module
        module.stop()
        
        # Set emergency flag in memory
        module.memory.update('system_status', 'emergency_stop', {
            'triggered_by': module.name,
            'timestamp': time.time(),
            'active': True
        })
        
        return True
    
    def _in_cooldown(self, module_name: str) -> bool:
        last_time = self.last_recovery_time.get(module_name, 0)
        return (time.time() - last_time) < self.recovery_cooldown
    
    def reset_attempts(self, module_name: str):
        with self._lock:
            self.recovery_attempts[module_name] = 0
    
    def get_failure_history(self) -> list:
        with self._lock:
            return list(self.failure_history)