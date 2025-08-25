#!/usr/bin/env python3
"""
Full Robot Control System Demo - All modules running
"""

import time
import threading
import signal
import sys
import os
import yaml
from collections import defaultdict
sys.path.append(os.path.dirname(__file__))

from core.memory.memory_store import GlobalMemory
from core.logging.logger import get_module_logger
from modules.input.models import ParsedCommand, CommandType
from modules.watchdog.watchdog_module import WatchdogModule


class MockAdapter:
    """Mock adapter for demonstration without MuJoCo"""
    
    def __init__(self, config):
        self.config = config
        self.connected = False
        self.joint_positions = [0.0] * 6
        self.logger = get_module_logger("MockAdapter")
    
    def connect(self):
        self.logger.info("Mock adapter connecting...")
        time.sleep(0.5)  # Simulate connection time
        self.connected = True
        self.logger.info("Mock adapter connected successfully")
        return True
    
    def disconnect(self):
        self.connected = False
        self.logger.info("Mock adapter disconnected")
    
    def send_joint_command(self, joint_names, positions, velocities=None):
        if not self.connected:
            return False
        
        self.joint_positions = positions[:len(self.joint_positions)]
        self.logger.debug(f"Joint command: {[f'{p:.3f}' for p in self.joint_positions]}")
        return True
    
    def send_cartesian_command(self, position, orientation):
        if not self.connected:
            return False
        
        self.logger.debug(f"Cartesian command: pos={position}, rot={orientation}")
        return True
    
    def step_simulation(self):
        if not self.connected:
            return False
        
        # Simulate some physics
        time.sleep(0.001)
        return True
    
    def get_joint_positions(self):
        return self.joint_positions.copy()


class SystemDemo:
    """Full system demonstration"""
    
    def __init__(self):
        self.logger = get_module_logger("System")
        self.memory = GlobalMemory.get_instance()
        self.running = False
        self.modules = {}
        self.adapter = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        self.logger.info("Shutdown signal received")
        self.stop()
    
    def initialize(self):
        """Initialize all system components"""
        self.logger.info("=" * 50)
        self.logger.info("ROBOT CONTROL SYSTEM STARTING")
        self.logger.info("=" * 50)
        
        # Initialize global memory
        self.logger.info("Initializing global memory...")
        
        # Initialize mock adapter
        self.logger.info("Initializing mock adapter...")
        config = {
            'joint_names': ['shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint', 
                          'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint'],
            'render': False
        }
        self.adapter = MockAdapter(config)
        
        if not self.adapter.connect():
            self.logger.error("Failed to connect adapter")
            return False
        
        # Initialize watchdog
        self.logger.info("Initializing watchdog...")
        watchdog_config = {
            'enabled': True,
            'check_interval': 2.0,
            'heartbeat_timeout': 10.0,
            'heartbeat_warning': 5.0,
            'auto_restart': False,
            'max_restart_attempts': 3,
            'recovery_strategy': 'restart',
            'recovery_cooldown': 2.0,
            'alerts': {'console': True, 'sound': False}
        }
        
        self.modules['watchdog'] = WatchdogModule(watchdog_config)
        
        self.logger.info("=" * 50)
        self.logger.info("SYSTEM INITIALIZATION COMPLETE")
        self.logger.info("=" * 50)
        
        return True
    
    def start_modules(self):
        """Start all system modules"""
        self.logger.info("Starting system modules...")
        
        # Start watchdog
        self.modules['watchdog'].start()
        self.logger.info("✅ Watchdog module started")
        
        # Start demo threads
        self.running = True
        
        # Input simulation thread
        input_thread = threading.Thread(target=self._simulate_input, daemon=True)
        input_thread.start()
        self.logger.info("✅ Input simulation started")
        
        # Processing threads
        sense_thread = threading.Thread(target=self._simulate_sense, daemon=True)
        sense_thread.start()
        self.logger.info("✅ Sense module started")
        
        plan_thread = threading.Thread(target=self._simulate_plan, daemon=True)
        plan_thread.start()
        self.logger.info("✅ Plan module started")
        
        act_thread = threading.Thread(target=self._simulate_act, daemon=True)
        act_thread.start()
        self.logger.info("✅ Act module started")
        
        output_thread = threading.Thread(target=self._simulate_output, daemon=True)
        output_thread.start()
        self.logger.info("✅ Output module started")
        
        self.logger.info("🚀 ALL MODULES OPERATIONAL")
    
    def _simulate_input(self):
        """Simulate input module"""
        logger = get_module_logger("Input")
        logger.info("Input module running...")
        
        commands = [
            ('w', 'forward'),
            ('a', 'left'),
            ('s', 'backward'),
            ('d', 'right'),
            ('space', 'gripper')
        ]
        
        cmd_index = 0
        
        while self.running:
            try:
                # Send heartbeat
                heartbeat_data = {
                    'timestamp': time.time(),
                    'error_count': 0,
                    'avg_processing_time': 0.001
                }
                self.memory.update_module_heartbeat('Input', heartbeat_data)
                
                # Simulate input every 3 seconds
                if cmd_index % 15 == 0:  # Every 3 seconds (200ms * 15)
                    key, direction = commands[(cmd_index // 15) % len(commands)]
                    
                    command = ParsedCommand(
                        command_type=CommandType.MOVEMENT if key != 'space' else CommandType.GRIPPER,
                        direction=direction,
                        magnitude=0.8,
                        is_continuous=False
                    )
                    
                    active_commands = self.memory.get('input_buffer', 'active_commands', {})
                    active_commands[f'input_{time.time()}'] = command
                    self.memory.update('input_buffer', 'active_commands', active_commands)
                    
                    logger.info(f"📥 Input command: {direction}")
                
                cmd_index += 1
                time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Input error: {e}")
                time.sleep(1)
    
    def _simulate_sense(self):
        """Simulate sense module"""
        logger = get_module_logger("Sense")
        logger.info("Sense module running...")
        
        while self.running:
            try:
                # Send heartbeat
                heartbeat_data = {
                    'timestamp': time.time(),
                    'error_count': 0,
                    'avg_processing_time': 0.002
                }
                self.memory.update_module_heartbeat('Sense', heartbeat_data)
                
                # Process input commands
                active_commands = self.memory.get('input_buffer', 'active_commands', {})
                if active_commands:
                    # Parse commands
                    parsed_commands = list(active_commands.values())
                    self.memory.update('sense_buffer', 'parsed_commands', parsed_commands)
                    logger.debug(f"🔍 Processed {len(parsed_commands)} commands")
                
                time.sleep(0.02)  # 50Hz
                
            except Exception as e:
                logger.error(f"Sense error: {e}")
                time.sleep(1)
    
    def _simulate_plan(self):
        """Simulate plan module"""
        logger = get_module_logger("Plan")
        logger.info("Plan module running...")
        
        while self.running:
            try:
                # Send heartbeat
                heartbeat_data = {
                    'timestamp': time.time(),
                    'error_count': 0,
                    'avg_processing_time': 0.005
                }
                self.memory.update_module_heartbeat('Plan', heartbeat_data)
                
                # Generate trajectories from commands
                parsed_commands = self.memory.get('sense_buffer', 'parsed_commands', [])
                if parsed_commands:
                    # Generate trajectory for latest command
                    latest_command = parsed_commands[-1]
                    
                    # Simple trajectory generation
                    direction_map = {
                        'forward': [0.1, 0.0, 0.0, 0.0, 0.0, 0.0],
                        'backward': [-0.1, 0.0, 0.0, 0.0, 0.0, 0.0],
                        'left': [0.0, 0.1, 0.0, 0.0, 0.0, 0.0],
                        'right': [0.0, -0.1, 0.0, 0.0, 0.0, 0.0],
                        'gripper': [0.0, 0.0, 0.0, 0.0, 0.0, 0.1]
                    }
                    
                    delta = direction_map.get(latest_command.direction, [0.0] * 6)
                    current_pos = self.adapter.get_joint_positions()
                    new_positions = [p + d * latest_command.magnitude for p, d in zip(current_pos, delta)]
                    
                    trajectory = {
                        'joint_names': ['shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint',
                                      'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint'],
                        'positions': new_positions,
                        'velocities': [0.0] * 6,
                        'timestamp': time.time()
                    }
                    
                    self.memory.update('plan_buffer', 'current_trajectory', trajectory)
                    logger.info(f"📍 Planned trajectory: {latest_command.direction}")
                
                time.sleep(0.033)  # 30Hz
                
            except Exception as e:
                logger.error(f"Plan error: {e}")
                time.sleep(1)
    
    def _simulate_act(self):
        """Simulate act module"""
        logger = get_module_logger("Act")
        logger.info("Act module running...")
        
        while self.running:
            try:
                # Send heartbeat
                heartbeat_data = {
                    'timestamp': time.time(),
                    'error_count': 0,
                    'avg_processing_time': 0.003
                }
                self.memory.update_module_heartbeat('Act', heartbeat_data)
                
                # Execute trajectories
                trajectory = self.memory.get('plan_buffer', 'current_trajectory')
                if trajectory and trajectory['timestamp'] > time.time() - 1.0:  # Fresh trajectory
                    # Send to adapter
                    success = self.adapter.send_joint_command(
                        trajectory['joint_names'],
                        trajectory['positions']
                    )
                    
                    if success:
                        self.adapter.step_simulation()
                        logger.debug(f"⚡ Executed joint command")
                
                time.sleep(0.01)  # 100Hz
                
            except Exception as e:
                logger.error(f"Act error: {e}")
                time.sleep(1)
    
    def _simulate_output(self):
        """Simulate output module"""
        logger = get_module_logger("Output")
        logger.info("Output module running...")
        
        while self.running:
            try:
                # Send heartbeat
                heartbeat_data = {
                    'timestamp': time.time(),
                    'error_count': 0,
                    'avg_processing_time': 0.001
                }
                self.memory.update_module_heartbeat('Output', heartbeat_data)
                
                # Format output signals
                current_positions = self.adapter.get_joint_positions()
                output_data = {
                    'joint_positions': current_positions,
                    'timestamp': time.time(),
                    'status': 'operational'
                }
                
                self.memory.update('output_buffer', 'current_state', output_data)
                
                time.sleep(0.01)  # 100Hz
                
            except Exception as e:
                logger.error(f"Output error: {e}")
                time.sleep(1)
    
    def run(self):
        """Run the main system loop"""
        if not self.initialize():
            return False
        
        self.start_modules()
        
        try:
            self.logger.info("🎮 System running - Press Ctrl+C to stop")
            self.logger.info("🤖 Watch the modules communicate in real-time!")
            
            # Main status loop
            cycle = 0
            while self.running:
                cycle += 1
                
                if cycle % 25 == 0:  # Every 5 seconds
                    self._print_status()
                
                time.sleep(0.2)
                
        except KeyboardInterrupt:
            self.logger.info("⏹️  Keyboard interrupt received")
        
        self.stop()
        return True
    
    def _print_status(self):
        """Print system status"""
        self.logger.info("📊 System Status Report:")
        
        # Module health
        modules = ['Input', 'Sense', 'Plan', 'Act', 'Output', 'Watchdog']
        healthy_count = 0
        
        for module_name in modules:
            heartbeat = self.memory.get_module_heartbeat(module_name)
            if heartbeat and heartbeat.age < 5.0:
                healthy_count += 1
                status = "✅"
            else:
                status = "❌"
            self.logger.info(f"  {status} {module_name}")
        
        # Memory usage
        active_commands = len(self.memory.get('input_buffer', 'active_commands', {}))
        trajectory = self.memory.get('plan_buffer', 'current_trajectory')
        current_state = self.memory.get('output_buffer', 'current_state')
        
        self.logger.info(f"  📥 Active commands: {active_commands}")
        self.logger.info(f"  📍 Trajectory: {'✅' if trajectory else '❌'}")
        self.logger.info(f"  📤 Output state: {'✅' if current_state else '❌'}")
        self.logger.info(f"  🔋 System health: {healthy_count}/{len(modules)} modules")
    
    def stop(self):
        """Stop the system"""
        self.logger.info("🛑 Stopping system...")
        self.running = False
        
        # Stop modules
        if 'watchdog' in self.modules:
            self.modules['watchdog'].stop()
            self.logger.info("✅ Watchdog stopped")
        
        # Disconnect adapter
        if self.adapter:
            self.adapter.disconnect()
            self.logger.info("✅ Adapter disconnected")
        
        self.logger.info("✅ System shutdown complete")


if __name__ == '__main__':
    demo = SystemDemo()
    success = demo.run()
    sys.exit(0 if success else 1)