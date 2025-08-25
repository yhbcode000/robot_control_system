from abc import ABC, abstractmethod
import threading
import time
from collections import deque
from typing import Optional, Dict, Any
import numpy as np

from ..memory.memory_store import GlobalMemory
from ..logging.logger import get_module_logger
from .observer import Observer, Observable


class BaseModule(ABC):
    def __init__(self, name: str, config: Dict[str, Any], memory: Optional[GlobalMemory] = None):
        self.observers = []
        self.callbacks = []
        
        self.name = name
        self.config = config
        self.memory = memory or GlobalMemory.get_instance()
        self.logger = get_module_logger(name)
        
        # Threading attributes
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self._stop_event = threading.Event()
        
        # Health monitoring attributes
        self.last_heartbeat = time.time()
        self.heartbeat_interval = config.get('heartbeat_interval', 0.5)
        self.error_count = 0
        self.consecutive_errors = 0
        self.processing_times = deque(maxlen=100)
        self.message_count = 0
        
        # Module state
        self.enabled = config.get('enabled', True)
        self.initialized = False
        
    def initialize(self) -> bool:
        try:
            self.logger.info(f"Initializing {self.name} module")
            result = self._initialize()
            self.initialized = result
            if result:
                self.logger.info(f"{self.name} module initialized successfully")
            else:
                self.logger.error(f"{self.name} module initialization failed")
            return result
        except Exception as e:
            self.logger.error(f"Error initializing {self.name}: {e}")
            self.initialized = False
            return False
    
    @abstractmethod
    def _initialize(self) -> bool:
        pass
    
    def start(self):
        if not self.enabled:
            self.logger.info(f"{self.name} module is disabled")
            return
        
        if not self.initialized:
            if not self.initialize():
                self.logger.error(f"Cannot start {self.name} - initialization failed")
                return
        
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run_wrapper, name=f"{self.name}Thread")
        self.thread.daemon = True
        self.thread.start()
        self.logger.info(f"{self.name} module started")
    
    def stop(self):
        if self.running:
            self.logger.info(f"Stopping {self.name} module")
            self.running = False
            self._stop_event.set()
            
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5.0)
                if self.thread.is_alive():
                    self.logger.warning(f"{self.name} thread did not stop gracefully")
            
            self._cleanup()
            self.logger.info(f"{self.name} module stopped")
    
    def _run_wrapper(self):
        try:
            self.logger.debug(f"{self.name} thread started")
            
            while self.running and not self._stop_event.is_set():
                start_time = time.time()
                
                try:
                    # Send heartbeat
                    self._send_heartbeat()
                    
                    # Run module logic
                    self.run()
                    
                    # Record metrics
                    processing_time = time.time() - start_time
                    self.processing_times.append(processing_time)
                    self.message_count += 1
                    
                    # Reset consecutive error counter on success
                    self.consecutive_errors = 0
                    
                except Exception as e:
                    self.error_count += 1
                    self.consecutive_errors += 1
                    self.logger.error(f"Error in {self.name} run loop: {e}", exc_info=True)
                    self._report_error(e)
                    
                    # Backoff on consecutive errors
                    if self.consecutive_errors > 3:
                        time.sleep(min(self.consecutive_errors * 0.1, 1.0))
                
                # Sleep if needed to maintain update rate
                if hasattr(self.config, 'update_rate'):
                    sleep_time = (1.0 / self.config['update_rate']) - (time.time() - start_time)
                    if sleep_time > 0:
                        self._stop_event.wait(sleep_time)
                        
        except Exception as e:
            self.logger.critical(f"Critical error in {self.name} thread: {e}", exc_info=True)
            self._report_critical_error(e)
        finally:
            self.logger.debug(f"{self.name} thread stopped")
    
    @abstractmethod 
    def run(self):
        pass
    
    def _send_heartbeat(self):
        self.last_heartbeat = time.time()
        heartbeat_data = {
            'timestamp': self.last_heartbeat,
            'error_count': self.error_count,
            'avg_processing_time': np.mean(self.processing_times) if self.processing_times else 0,
            'message_count': self.message_count,
            'consecutive_errors': self.consecutive_errors
        }
        self.memory.update_module_heartbeat(self.name, heartbeat_data)
    
    def _report_error(self, error: Exception):
        error_data = {
            'module': self.name,
            'error': str(error),
            'timestamp': time.time(),
            'consecutive_errors': self.consecutive_errors
        }
        self.memory.update('system_status', f'{self.name}_error', error_data)
        self.notify('error', error_data)
    
    def _report_critical_error(self, error: Exception):
        error_data = {
            'module': self.name,
            'error': str(error),
            'timestamp': time.time(),
            'critical': True
        }
        self.memory.update('system_status', f'{self.name}_critical_error', error_data)
        self.notify('critical_error', error_data)
    
    def _cleanup(self):
        try:
            self.cleanup()
        except Exception as e:
            self.logger.error(f"Error during {self.name} cleanup: {e}")
    
    def cleanup(self):
        pass
    
    def get_status(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'enabled': self.enabled,
            'running': self.running,
            'initialized': self.initialized,
            'error_count': self.error_count,
            'message_count': self.message_count,
            'avg_processing_time': np.mean(self.processing_times) if self.processing_times else 0,
            'last_heartbeat': self.last_heartbeat,
            'consecutive_errors': self.consecutive_errors
        }
    
    def notify(self, event: str, data: Any = None):
        """Notify observers of an event"""
        for callback in self.callbacks:
            try:
                callback(event, data)
            except Exception as e:
                self.logger.error(f"Observer notification failed: {e}")
    
    def is_healthy(self) -> bool:
        if not self.running:
            return False
        if self.consecutive_errors > 5:
            return False
        if time.time() - self.last_heartbeat > self.heartbeat_interval * 10:
            return False
        return True