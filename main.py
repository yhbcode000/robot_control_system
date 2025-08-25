#!/usr/bin/env python3
"""
Robot Control System - Main Entry Point

A modular robot control system with shared memory architecture.
Each module operates in its own thread and communicates through a global singleton memory store.
"""

import hydra
from omegaconf import DictConfig, OmegaConf
import time
import signal
import sys
from typing import Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.memory.memory_store import GlobalMemory
from core.logging.logger import setup_logging, get_module_logger
from modules.watchdog.watchdog_module import WatchdogModule
from modules.input.input_module import InputModule
from modules.sense.sense_module import SenseModule
from modules.plan.plan_module import PlanModule
from modules.act.act_module import ActModule
from modules.output.output_module import OutputModule
from modules.robot.robot_module import RobotModule
from adapters import create_adapter


class RobotControlSystem:
    def __init__(self, config: DictConfig):
        self.config = config
        self.logger = get_module_logger('System')
        self.memory = GlobalMemory.get_instance()
        self.modules = {}
        self.watchdog = None
        self.adapter = None
        self.running = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def initialize(self) -> bool:
        """Initialize the robot control system"""
        try:
            self.logger.info("=" * 50)
            self.logger.info("ROBOT CONTROL SYSTEM STARTING")
            self.logger.info("=" * 50)
            
            # Initialize global memory
            self.logger.info("Initializing global memory...")
            
            # Initialize adapter
            self.logger.info("Initializing adapter...")
            # Convert DictConfig to regular dict to avoid Hydra-related hanging issues
            adapter_config = OmegaConf.to_container(self.config.adapter, resolve=True)
            self.adapter = create_adapter(adapter_config)
            if self.adapter.connect():
                self.logger.info("Adapter connected successfully")
            else:
                self.logger.error("Failed to connect adapter")
                return False
            
            # Initialize watchdog first (it monitors other modules)
            if self.config.modules.watchdog.enabled:
                self.logger.info("Initializing Watchdog module...")
                self.watchdog = WatchdogModule(self.config.modules.watchdog, self.memory)
                if self.watchdog.initialize():
                    self.watchdog.start()
                    self.logger.info("Watchdog module started successfully")
                else:
                    self.logger.error("Failed to initialize Watchdog module")
                    return False
            
            # Initialize other modules
            module_configs = {
                'input': (InputModule, self.config.modules.input),
                'sense': (SenseModule, self.config.modules.sense),
                'plan': (PlanModule, self.config.modules.plan),
                'act': (ActModule, self.config.modules.act),
                'robot': (RobotModule, self.config.modules.robot),
                'output': (OutputModule, self.config.modules.output),
            }
            
            for name, (module_class, module_config) in module_configs.items():
                if module_config.enabled:
                    self.logger.info(f"Initializing {name} module...")
                    
                    # Create module with adapter if needed
                    if name in ['input', 'plan', 'act', 'robot']:
                        module = module_class(module_config, self.memory)
                    elif name in ['sense', 'output']:
                        module = module_class(module_config, self.memory, self.adapter)
                    else:
                        module = module_class(module_config, self.memory)
                    
                    if module.initialize():
                        self.modules[name] = module
                        
                        # Register with watchdog
                        if self.watchdog:
                            self.watchdog.register_module(name, module)
                        
                        self.logger.info(f"{name} module initialized successfully")
                    else:
                        self.logger.error(f"Failed to initialize {name} module")
                        return False
            
            self.logger.info("All modules initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during system initialization: {e}")
            return False
    
    def start(self):
        """Start all modules"""
        try:
            self.logger.info("Starting all modules...")
            
            # Start all modules
            for name, module in self.modules.items():
                self.logger.info(f"Starting {name} module...")
                module.start()
            
            self.running = True
            self.logger.info("All modules started successfully")
            
            # Main system loop
            self._main_loop()
            
        except Exception as e:
            self.logger.error(f"Error during system startup: {e}")
            self.shutdown()
    
    def _main_loop(self):
        """Main system monitoring loop"""
        try:
            loop_count = 0
            last_status_time = 0
            
            while self.running:
                current_time = time.time()
                
                # Check for emergency stop
                if self._check_emergency_stop():
                    self.logger.critical("EMERGENCY STOP DETECTED!")
                    break
                
                # Display status periodically
                if (self.config.display.show_status and 
                    current_time - last_status_time > self.config.display.status_interval):
                    self._display_status()
                    last_status_time = current_time
                
                # System health check
                if self.watchdog:
                    health_score = self.watchdog.get_system_health_score()
                    if health_score < 50:
                        self.logger.warning(f"System health degraded: {health_score:.1f}%")
                
                loop_count += 1
                time.sleep(0.1)  # 10Hz main loop
                
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            self.shutdown()
    
    def _check_emergency_stop(self) -> bool:
        """Check if emergency stop is active"""
        emergency_status = self.memory.get('system_status', 'emergency_stop')
        if emergency_status and emergency_status.get('active', False):
            return True
        
        # Check input module for emergency stop
        for module in self.modules.values():
            if hasattr(module, 'is_emergency_stop_pressed') and module.is_emergency_stop_pressed():
                return True
        
        return False
    
    def _display_status(self):
        """Display system status"""
        try:
            health_data = self.memory.get_health_status()
            
            status_msg = "\n" + "="*60 + "\n"
            status_msg += f"ROBOT CONTROL SYSTEM STATUS\n"
            status_msg += "="*60 + "\n"
            
            # System health
            if self.watchdog:
                health_score = self.watchdog.get_system_health_score()
                status_msg += f"System Health: {health_score:.1f}%\n"
            
            # Module status
            status_msg += f"{'Module':<12} {'Status':<10} {'Heartbeat':<12} {'Errors':<8}\n"
            status_msg += "-"*60 + "\n"
            
            for name, module in self.modules.items():
                status = module.get_status()
                heartbeat_age = time.time() - status['last_heartbeat']
                
                status_str = "RUNNING" if status['running'] else "STOPPED"
                if not status['initialized']:
                    status_str = "NOT_INIT"
                
                status_msg += f"{name:<12} {status_str:<10} {heartbeat_age:<12.1f}s {status['error_count']:<8}\n"
            
            status_msg += "="*60
            
            self.logger.info(status_msg)
            
        except Exception as e:
            self.logger.error(f"Error displaying status: {e}")
    
    def shutdown(self):
        """Graceful system shutdown"""
        if not self.running:
            return
        
        self.logger.info("Shutting down Robot Control System...")
        self.running = False
        
        try:
            # Stop all modules
            for name, module in self.modules.items():
                self.logger.info(f"Stopping {name} module...")
                module.stop()
            
            # Stop watchdog last
            if self.watchdog:
                self.logger.info("Stopping Watchdog module...")
                self.watchdog.stop()
            
            # Disconnect adapter
            if self.adapter:
                self.logger.info("Disconnecting adapter...")
                self.adapter.disconnect()
            
            self.logger.info("System shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle system signals"""
        self.logger.info(f"Received signal {signum}")
        self.shutdown()
        sys.exit(0)


@hydra.main(version_base=None, config_path=".", config_name="config")
def main(cfg: DictConfig) -> None:
    """Main entry point"""
    
    # Setup logging
    setup_logging(cfg.logging)
    
    # Create and run system
    system = RobotControlSystem(cfg)
    
    if system.initialize():
        system.start()
    else:
        print("Failed to initialize system")
        sys.exit(1)


if __name__ == "__main__":
    main()