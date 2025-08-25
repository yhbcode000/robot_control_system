import time
from typing import Dict, Any, Optional, List
import threading
import json

from core.base.module import BaseModule
from core.memory.memory_store import GlobalMemory
from models.control_commands import ControlCommand
from .signal_formatter import SignalFormatter
from .models import OutputState, SignalFormat, OutputStats


class OutputModule(BaseModule):
    def __init__(self, config: Dict[str, Any], memory: Optional[GlobalMemory] = None, adapter=None):
        super().__init__('Output', config, memory)
        
        # Store adapter reference
        self.adapter = adapter
        
        # Initialize signal formatter
        self.signal_formatter = SignalFormatter(config)
        
        # Configuration
        self.update_rate = config.get('update_rate', 100)  # Hz
        self.output_format = config.get('format', 'json')
        self.enable_logging = config.get('enable_logging', False)
        self.log_file = config.get('log_file', 'output.log')
        
        # State
        self.output_state = OutputState()
        self.output_stats = OutputStats()
        
        # Command queue
        self.command_queue = []
        self.queue_lock = threading.Lock()
        
        # Last sent commands (for avoiding duplicates)
        self.last_commands = {}
        self.command_timeout = 0.1  # Don't send same command within 100ms
        
        # Emergency handling
        self.emergency_active = False
        self.last_emergency_time = 0.0
        
        # Subscribe to action commands
        self.memory.subscribe_to_namespace('action_commands', self._on_action_commands_change)
        
        # File handle for logging
        self.log_file_handle = None
        if self.enable_logging:
            try:
                self.log_file_handle = open(self.log_file, 'a')
            except Exception as e:
                self.logger.warning(f"Could not open log file {self.log_file}: {e}")
    
    def _initialize(self) -> bool:
        try:
            self.logger.info("Initializing Output module...")
            
            # Initialize output state in memory
            self.memory.update('output_signals', 'current_state', self.output_state)
            
            # Test adapter connection if available
            if self.adapter:
                try:
                    adapter_status = self.adapter.get_status()
                    self.output_state.adapter_connected = adapter_status.get('connected', False)
                    self.logger.info(f"Adapter connection status: {self.output_state.adapter_connected}")
                except Exception as e:
                    self.logger.warning(f"Could not check adapter status: {e}")
                    self.output_state.adapter_connected = False
            else:
                self.logger.info("No adapter provided - running in simulation mode")
                self.output_state.adapter_connected = False
            
            self.logger.info("Output module initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Output module: {e}")
            return False
    
    def run(self):
        """Main output processing loop"""
        try:
            # Process command queue
            self._process_command_queue()
            
            # Check for new action commands
            self._check_for_new_commands()
            
            # Handle emergency commands with priority
            self._handle_emergency_commands()
            
            # Send commands to adapter
            self._send_commands_to_adapter()
            
            # Update output state
            self._update_output_state()
            
            # Update memory
            self.memory.update('output_signals', 'current_state', self.output_state)
            self.memory.update('output_signals', 'stats', self.output_stats)
            
            # Sleep based on update rate
            if self.update_rate > 0:
                time.sleep(1.0 / self.update_rate)
            
        except Exception as e:
            self.logger.error(f"Error in output processing: {e}")
            raise
    
    def _on_action_commands_change(self, key: str, value: Any):
        """Handle changes to action commands namespace"""
        try:
            if key == 'pending_commands' and isinstance(value, list):
                # New commands available
                with self.queue_lock:
                    self.command_queue.extend(value)
                self.logger.debug(f"Received {len(value)} new commands")
                
            elif key == 'emergency_command' and value:
                # Emergency command
                self._handle_emergency_command(value)
                
            elif key == 'trajectory_complete' and value:
                # Trajectory completion notification
                self.output_state.last_trajectory_completion = value.get('timestamp', time.time())
                self.logger.debug("Trajectory completion received")
                
        except Exception as e:
            self.logger.error(f"Error handling action commands change: {e}")
    
    def _check_for_new_commands(self):
        """Check memory for new action commands"""
        try:
            # Get pending commands
            pending_commands = self.memory.get('action_commands', 'pending_commands', [])
            
            if pending_commands:
                with self.queue_lock:
                    self.command_queue.extend(pending_commands)
                
                # Clear from memory to prevent reprocessing
                self.memory.update('action_commands', 'pending_commands', [])
                
                self.logger.debug(f"Retrieved {len(pending_commands)} commands from memory")
            
        except Exception as e:
            self.logger.error(f"Error checking for new commands: {e}")
    
    def _process_command_queue(self):
        """Process commands in the queue"""
        try:
            commands_to_process = []
            
            with self.queue_lock:
                # Get all commands from queue
                commands_to_process = self.command_queue.copy()
                self.command_queue.clear()
            
            if not commands_to_process:
                return
            
            # Filter out duplicate/stale commands
            filtered_commands = self._filter_commands(commands_to_process)
            
            # Format commands for output
            formatted_signals = []
            for command in filtered_commands:
                try:
                    signal = self.signal_formatter.format_command(command, self.output_format)
                    if signal:
                        formatted_signals.append(signal)
                except Exception as e:
                    self.logger.error(f"Error formatting command: {e}")
                    self.output_stats.formatting_errors += 1
            
            # Store formatted signals
            self.output_state.pending_signals = formatted_signals
            self.output_state.signals_in_queue = len(formatted_signals)
            
            # Log commands if enabled
            if self.enable_logging and self.log_file_handle:
                self._log_commands(filtered_commands)
            
            # Update stats
            self.output_stats.total_commands_processed += len(commands_to_process)
            self.output_stats.commands_sent_to_adapter += len(filtered_commands)
            
        except Exception as e:
            self.logger.error(f"Error processing command queue: {e}")
    
    def _filter_commands(self, commands: List[ControlCommand]) -> List[ControlCommand]:
        """Filter out duplicate or stale commands"""
        try:
            filtered = []
            current_time = time.time()
            
            for command in commands:
                # Check if command is too old
                if hasattr(command, 'timestamp'):
                    command_age = current_time - command.timestamp
                    if command_age > 1.0:  # Commands older than 1 second are stale
                        self.logger.debug("Skipping stale command")
                        self.output_stats.stale_commands += 1
                        continue
                
                # Check for duplicates (simplified)
                command_key = self._get_command_key(command)
                last_sent = self.last_commands.get(command_key, 0)
                
                if current_time - last_sent > self.command_timeout:
                    filtered.append(command)
                    self.last_commands[command_key] = current_time
                else:
                    self.logger.debug("Skipping duplicate command")
                    self.output_stats.duplicate_commands += 1
            
            return filtered
            
        except Exception as e:
            self.logger.error(f"Error filtering commands: {e}")
            return commands
    
    def _get_command_key(self, command: ControlCommand) -> str:
        """Get unique key for command deduplication"""
        try:
            key_parts = [command.command_type.value]
            
            if command.joint_command:
                key_parts.append("joint")
                if hasattr(command.joint_command, 'positions'):
                    # Use position values (simplified)
                    key_parts.append(str(hash(tuple(command.joint_command.positions))))
                    
            elif command.cartesian_command:
                key_parts.append("cartesian")
                if hasattr(command.cartesian_command, 'position'):
                    # Use position values (simplified)
                    key_parts.append(str(hash(tuple(command.cartesian_command.position))))
                    
            elif command.gripper_command:
                key_parts.append("gripper")
                key_parts.append(str(command.gripper_command.position))
            
            return "_".join(key_parts)
            
        except Exception as e:
            self.logger.error(f"Error generating command key: {e}")
            return "unknown"
    
    def _handle_emergency_commands(self):
        """Handle emergency commands with high priority"""
        try:
            emergency_command = self.memory.get('action_commands', 'emergency_command')
            
            if emergency_command and not self.emergency_active:
                self._handle_emergency_command(emergency_command)
                
            elif not emergency_command and self.emergency_active:
                # Emergency cleared
                self._clear_emergency()
                
        except Exception as e:
            self.logger.error(f"Error handling emergency commands: {e}")
    
    def _handle_emergency_command(self, command):
        """Handle individual emergency command"""
        try:
            self.logger.warning("Emergency command received - immediate processing")
            
            self.emergency_active = True
            self.last_emergency_time = time.time()
            self.output_state.emergency_active = True
            
            # Format emergency command
            if isinstance(command, ControlCommand):
                signal = self.signal_formatter.format_command(command, self.output_format)
                
                # Send immediately to adapter if available
                if self.adapter and signal:
                    try:
                        self.adapter.send_emergency_stop()
                        self.logger.warning("Emergency stop sent to adapter")
                        self.output_stats.emergency_commands_sent += 1
                    except Exception as e:
                        self.logger.error(f"Failed to send emergency stop to adapter: {e}")
                        self.output_stats.adapter_errors += 1
                
                # Store as high priority signal
                self.output_state.emergency_signal = signal
            
        except Exception as e:
            self.logger.error(f"Error handling emergency command: {e}")
    
    def _clear_emergency(self):
        """Clear emergency state"""
        try:
            self.logger.info("Emergency state cleared")
            self.emergency_active = False
            self.output_state.emergency_active = False
            self.output_state.emergency_signal = None
            
        except Exception as e:
            self.logger.error(f"Error clearing emergency state: {e}")
    
    def _send_commands_to_adapter(self):
        """Send formatted signals to the adapter"""
        try:
            if not self.adapter:
                # No adapter - just update stats for simulation
                signals_count = len(self.output_state.pending_signals)
                if signals_count > 0:
                    self.output_stats.successful_sends += signals_count
                    self.output_state.pending_signals = []
                    self.output_state.signals_in_queue = 0
                    self.output_state.last_send_time = time.time()
                return
            
            # Check adapter status
            try:
                adapter_status = self.adapter.get_status()
                self.output_state.adapter_connected = adapter_status.get('connected', False)
            except Exception as e:
                self.logger.warning(f"Could not check adapter status: {e}")
                self.output_state.adapter_connected = False
            
            if not self.output_state.adapter_connected:
                self.logger.warning("Adapter not connected - commands queued")
                return
            
            # Send pending signals
            if self.output_state.pending_signals:
                try:
                    for signal in self.output_state.pending_signals:
                        self._send_signal_to_adapter(signal)
                        self.output_stats.successful_sends += 1
                    
                    # Clear sent signals
                    self.output_state.pending_signals = []
                    self.output_state.signals_in_queue = 0
                    self.output_state.last_send_time = time.time()
                    
                except Exception as e:
                    self.logger.error(f"Error sending signals to adapter: {e}")
                    self.output_stats.adapter_errors += 1
            
        except Exception as e:
            self.logger.error(f"Error in send_commands_to_adapter: {e}")
    
    def _send_signal_to_adapter(self, signal: Dict[str, Any]):
        """Send individual signal to adapter"""
        try:
            if not self.adapter:
                return
            
            # Extract command type and data
            command_type = signal.get('type', 'unknown')
            command_data = signal.get('data', {})
            
            if command_type == 'joint':
                # Send joint command
                joint_names = command_data.get('joint_names', [])
                positions = command_data.get('positions', [])
                velocities = command_data.get('velocities', [])
                
                self.adapter.send_joint_command(joint_names, positions, velocities)
                
            elif command_type == 'cartesian':
                # Send Cartesian command
                position = command_data.get('position', [0, 0, 0])
                orientation = command_data.get('orientation', [0, 0, 0, 1])
                linear_vel = command_data.get('linear_velocity', [0, 0, 0])
                angular_vel = command_data.get('angular_velocity', [0, 0, 0])
                
                self.adapter.send_cartesian_command(position, orientation, linear_vel, angular_vel)
                
            elif command_type == 'gripper':
                # Send gripper command
                position = command_data.get('position', 0.0)
                force = command_data.get('force', 1.0)
                
                self.adapter.send_gripper_command(position, force)
                
            elif command_type == 'emergency_stop':
                # Send emergency stop
                self.adapter.send_emergency_stop()
                
            else:
                self.logger.warning(f"Unknown command type for adapter: {command_type}")
            
        except Exception as e:
            self.logger.error(f"Error sending signal to adapter: {e}")
            self.output_stats.adapter_errors += 1
    
    def _update_output_state(self):
        """Update output module state"""
        try:
            current_time = time.time()
            self.output_state.last_update_time = current_time
            
            # Update connection status
            if self.adapter:
                try:
                    adapter_status = self.adapter.get_status()
                    self.output_state.adapter_connected = adapter_status.get('connected', False)
                    self.output_state.adapter_info = adapter_status
                except Exception:
                    self.output_state.adapter_connected = False
            
            # Check if we're sending commands regularly
            time_since_last_send = current_time - self.output_state.last_send_time
            self.output_state.is_active = time_since_last_send < 1.0
            
            # Update performance stats
            total_attempts = self.output_stats.successful_sends + self.output_stats.adapter_errors
            if total_attempts > 0:
                self.output_stats.success_rate = self.output_stats.successful_sends / total_attempts
            
        except Exception as e:
            self.logger.error(f"Error updating output state: {e}")
    
    def _log_commands(self, commands: List[ControlCommand]):
        """Log commands to file"""
        try:
            if not self.log_file_handle:
                return
            
            timestamp = time.time()
            for command in commands:
                log_entry = {
                    'timestamp': timestamp,
                    'command_type': command.command_type.value,
                    'source_module': getattr(command, 'source_module', 'unknown')
                }
                
                # Add command-specific details
                if command.joint_command:
                    log_entry['joint_positions'] = command.joint_command.positions.tolist() if hasattr(command.joint_command.positions, 'tolist') else list(command.joint_command.positions)
                elif command.cartesian_command:
                    if hasattr(command.cartesian_command, 'position'):
                        log_entry['position'] = command.cartesian_command.position.tolist() if hasattr(command.cartesian_command.position, 'tolist') else list(command.cartesian_command.position)
                elif command.gripper_command:
                    log_entry['gripper_position'] = command.gripper_command.position
                
                # Write to log
                json.dump(log_entry, self.log_file_handle)
                self.log_file_handle.write('\n')
            
            self.log_file_handle.flush()
            
        except Exception as e:
            self.logger.error(f"Error logging commands: {e}")
    
    def get_output_state(self) -> OutputState:
        """Get current output state"""
        return self.output_state
    
    def get_output_stats(self) -> OutputStats:
        """Get output statistics"""
        return self.output_stats
    
    def force_send_signal(self, signal: Dict[str, Any]) -> bool:
        """Force send a signal immediately (for testing/debugging)"""
        try:
            if self.adapter and self.output_state.adapter_connected:
                self._send_signal_to_adapter(signal)
                return True
            else:
                self.logger.warning("Cannot force send signal - adapter not available")
                return False
                
        except Exception as e:
            self.logger.error(f"Error force sending signal: {e}")
            return False
    
    def cleanup(self):
        """Cleanup output module"""
        try:
            self.logger.info("Cleaning up Output module...")
            
            # Send any remaining commands
            if self.output_state.pending_signals:
                self.logger.info(f"Sending {len(self.output_state.pending_signals)} remaining commands")
                self._send_commands_to_adapter()
            
            # Close log file
            if self.log_file_handle:
                self.log_file_handle.close()
                self.log_file_handle = None
            
            # Clear command queue
            with self.queue_lock:
                self.command_queue.clear()
            
            self.logger.info("Output module cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Output module cleanup: {e}")