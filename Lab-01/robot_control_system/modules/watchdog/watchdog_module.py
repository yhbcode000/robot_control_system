import time
import threading
from typing import Dict, Optional, Any
from collections import deque

from core.base.module import BaseModule
from core.memory.memory_store import GlobalMemory
from core.memory.memory_types import ThreadHealth, ModuleMetrics, SystemMetrics
from .health_monitor import HealthMonitor
from .failure_handler import FailureHandler
from .metrics import SystemMetricsCollector
from .models import SystemHealthReport, ModuleHealth


class WatchdogModule(BaseModule):
    def __init__(self, config: Dict[str, Any], memory: Optional[GlobalMemory] = None):
        super().__init__('Watchdog', config, memory)
        
        # Sub-components
        self.health_monitor = HealthMonitor(config)
        self.failure_handler = FailureHandler(config)
        self.metrics_collector = SystemMetricsCollector()
        
        # Monitoring configuration
        self.check_interval = config.get('check_interval', 1.0)
        self.auto_restart = config.get('auto_restart', True)
        self.alert_console = config.get('alerts', {}).get('console', True)
        
        # Tracked modules
        self.monitored_modules: Dict[str, BaseModule] = {}
        self.module_health: Dict[str, ModuleHealth] = {}
        
        # System state
        self.system_start_time = time.time()
        self.total_recoveries = 0
        self.total_failures = 0
        
    def _initialize(self) -> bool:
        try:
            self.logger.info("Watchdog module initializing...")
            
            # Initialize health status in memory
            self.memory.update('health_status', 'data', {
                'thread_health': {},
                'module_metrics': {},
                'system_metrics': None,
                'health_score': 100.0
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Watchdog: {e}")
            return False
    
    def register_module(self, name: str, module: BaseModule):
        self.monitored_modules[name] = module
        self.health_monitor.register_module(name)
        self.logger.info(f"Registered module {name} for monitoring")
    
    def unregister_module(self, name: str):
        if name in self.monitored_modules:
            del self.monitored_modules[name]
            self.logger.info(f"Unregistered module {name}")
    
    def run(self):
        # Main monitoring loop iteration
        self._check_all_modules()
        self._update_system_metrics()
        self._update_health_report()
        
        # Sleep for check interval
        time.sleep(self.check_interval)
    
    def _check_all_modules(self):
        for name, module in self.monitored_modules.items():
            try:
                # Check module health
                health = self.health_monitor.check_module_health(name)
                self.module_health[name] = health
                
                # Special monitoring for robot module
                if name == 'robot':
                    self._monitor_robot_safety(module)
                
                # Detect failures
                failures = self.health_monitor.detect_failures(health)
                
                if failures and self.auto_restart:
                    self._handle_module_failure(module, failures)
                
                # Update thread health in memory
                thread_health = ThreadHealth(
                    module_name=name,
                    status=self.health_monitor.get_module_status(health),
                    last_heartbeat=health.last_heartbeat,
                    consecutive_misses=health.consecutive_errors,
                    cpu_usage=health.cpu_usage,
                    memory_usage=health.memory_usage,
                    response_time=health.processing_time,
                    error_count=health.consecutive_errors,
                    message_queue_size=health.queue_size
                )
                self.memory.update_thread_health(name, thread_health)
                
                # Update module metrics
                metrics = ModuleMetrics(
                    module_name=name,
                    last_heartbeat=health.last_heartbeat,
                    processing_time=health.processing_time,
                    error_count=health.consecutive_errors,
                    throughput=0,  # TODO: Calculate from module
                    queue_size=health.queue_size,
                    cpu_percent=health.cpu_usage,
                    memory_mb=health.memory_usage
                )
                self.memory.update_module_metrics(name, metrics)
                
            except Exception as e:
                self.logger.error(f"Error checking module {name}: {e}")
    
    def _handle_module_failure(self, module: BaseModule, failures: list):
        self.total_failures += 1
        
        # Determine recovery strategy
        strategy = self.failure_handler.determine_recovery_strategy(
            module.name, failures
        )
        
        if strategy.value != "none":
            self.logger.warning(f"Module {module.name} has failures: {failures}")
            self.logger.info(f"Attempting {strategy.value} recovery for {module.name}")
            
            # Execute recovery
            success = self.failure_handler.execute_recovery(module, strategy)
            
            if success:
                self.total_recoveries += 1
                self.logger.info(f"Recovery successful for {module.name}")
                
                # Reset failure counter after successful recovery
                if module.is_healthy():
                    self.failure_handler.reset_attempts(module.name)
            else:
                self.logger.error(f"Recovery failed for {module.name}")
            
            # Alert if configured
            if self.alert_console:
                self._send_alert(module.name, failures, strategy, success)
    
    def _update_system_metrics(self):
        try:
            # Collect system metrics
            sys_metrics = self.metrics_collector.collect_system_metrics()
            
            # Calculate FPS (messages per second)
            total_messages = sum(
                self.module_health.get(name, ModuleHealth(
                    module_name=name, is_healthy=False, last_heartbeat=0,
                    heartbeat_age=0, error_rate=0, cpu_usage=0, memory_usage=0,
                    queue_size=0, processing_time=0, consecutive_errors=0,
                    health_score=0
                )).queue_size 
                for name in self.monitored_modules
            )
            
            metrics = SystemMetrics(
                cpu_usage=sys_metrics.get('system_cpu_percent', 0),
                memory_usage=sys_metrics.get('system_memory_percent', 0),
                message_queue_size=total_messages,
                latency=0,  # TODO: Calculate system latency
                uptime=time.time() - self.system_start_time,
                total_messages=total_messages,
                fps=0  # TODO: Calculate actual FPS
            )
            
            self.memory.update_system_metrics(metrics)
            
        except Exception as e:
            self.logger.error(f"Error updating system metrics: {e}")
    
    def _update_health_report(self):
        try:
            # Calculate overall health score
            health_scores = [h.health_score for h in self.module_health.values()]
            overall_score = sum(health_scores) / len(health_scores) if health_scores else 100.0
            
            # Create health report
            report = SystemHealthReport(
                overall_health_score=overall_score,
                module_health=self.module_health,
                active_failures=self.failure_handler.get_failure_history()[-10:],
                cpu_usage=self.metrics_collector.collect_system_metrics().get('system_cpu_percent', 0),
                memory_usage=self.metrics_collector.collect_system_metrics().get('system_memory_percent', 0),
                uptime=time.time() - self.system_start_time,
                total_errors=self.total_failures,
                total_recoveries=self.total_recoveries
            )
            
            # Update memory
            self.memory.update('system_status', 'health_report', report)
            
        except Exception as e:
            self.logger.error(f"Error updating health report: {e}")
    
    def _send_alert(self, module_name: str, failures: list, strategy: Any, success: bool):
        alert_msg = f"\n{'='*50}\n"
        alert_msg += f"WATCHDOG ALERT - {module_name}\n"
        alert_msg += f"Failures: {[f.value for f in failures]}\n"
        alert_msg += f"Recovery: {strategy.value} - {'SUCCESS' if success else 'FAILED'}\n"
        alert_msg += f"{'='*50}"
        
        if success:
            self.logger.warning(alert_msg)
        else:
            self.logger.error(alert_msg)
    
    def get_system_health_score(self) -> float:
        health_scores = [h.health_score for h in self.module_health.values()]
        return sum(health_scores) / len(health_scores) if health_scores else 100.0
    
    def get_module_status(self, module_name: str) -> Optional[ModuleHealth]:
        return self.module_health.get(module_name)
    
    def force_recovery(self, module_name: str, strategy: str = "restart"):
        if module_name in self.monitored_modules:
            module = self.monitored_modules[module_name]
            from .models import RecoveryStrategy
            
            strategy_enum = RecoveryStrategy(strategy)
            success = self.failure_handler.execute_recovery(module, strategy_enum)
            
            return success
        return False
    
    def _monitor_robot_safety(self, robot_module):
        """Special monitoring for robot module safety"""
        try:
            # Get robot state summary
            robot_summary = robot_module.get_state_summary()
            
            # Check for safety issues
            if not robot_summary.get('is_safe', True):
                self.logger.warning("Robot safety violation detected!")
                safety_violations = robot_summary.get('safety_violations', [])
                for violation in safety_violations:
                    self.logger.warning(f"Safety violation: {violation}")
                
                # Update memory with safety alert
                self.memory.update('system_status', 'safety_alert', {
                    'active': True,
                    'violations': safety_violations,
                    'timestamp': time.time()
                })
            
            # Check emergency stop
            if robot_summary.get('emergency_stop', False):
                self.logger.critical("EMERGENCY STOP ACTIVE")
                
                # Update system status
                self.memory.update('system_status', 'emergency_stop', {
                    'active': True,
                    'timestamp': time.time(),
                    'triggered_by': 'robot_module'
                })
            
            # Check collision detection
            if robot_summary.get('collision_detected', False):
                self.logger.error("COLLISION DETECTED")
                
                # Update memory with collision alert
                self.memory.update('system_status', 'collision_alert', {
                    'active': True,
                    'timestamp': time.time()
                })
            
            # Monitor command frequency
            cmd_freq = robot_summary.get('command_frequency', 0)
            if cmd_freq > 0:
                self.logger.debug(f"Robot command frequency: {cmd_freq:.1f} Hz")
                
                # Update robot metrics
                self.memory.update('robot', 'command_frequency', cmd_freq)
            
        except Exception as e:
            self.logger.error(f"Error monitoring robot safety: {e}")
    
    def cleanup(self):
        self.logger.info("Watchdog cleanup started")
        # Any cleanup needed