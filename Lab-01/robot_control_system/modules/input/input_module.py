import time
from typing import Dict, Any, Optional
import threading

from core.base.module import BaseModule
from core.memory.memory_store import GlobalMemory
from models.sensor_data import KeyboardInput, MouseInput
from .keyboard_handler import KeyboardHandler
from .mouse_handler import MouseHandler
from .models import InputBuffer, ParsedCommand


class InputModule(BaseModule):
    def __init__(self, config: Dict[str, Any], memory: Optional[GlobalMemory] = None):
        super().__init__('Input', config, memory)
        
        # Input handlers
        self.keyboard_handler = KeyboardHandler(config)
        self.mouse_handler = MouseHandler(config)
        
        # Input buffer
        self.input_buffer = InputBuffer()
        
        # Configuration
        self.update_rate = config.get('update_rate', 60)  # Hz
        self.buffer_size = config.get('buffer_size', 100)
        
        # State tracking
        self.last_keyboard_input = None
        self.last_mouse_input = None
        
    def _initialize(self) -> bool:
        try:
            self.logger.info("Initializing Input module...")
            
            # Setup callbacks
            self.keyboard_handler.add_callback(self._on_keyboard_input)
            self.mouse_handler.add_callback(self._on_mouse_input)
            
            # Start input handlers
            keyboard_ok = self.keyboard_handler.start()
            mouse_ok = self.mouse_handler.start()
            
            if not keyboard_ok:
                self.logger.warning("Failed to start keyboard handler")
            else:
                self.logger.info("Keyboard handler started successfully")
                
            if not mouse_ok:
                self.logger.warning("Failed to start mouse handler")
            else:
                self.logger.info("Mouse handler started successfully")
                if self.mouse_handler.enable_end_effector_control:
                    self.logger.info("End-effector control is ENABLED")
            
            # Initialize input buffer in memory
            self.memory.update('input_buffer', 'current', self.input_buffer)
            
            self.logger.info("Input module initialized successfully")
            return keyboard_ok or mouse_ok  # At least one should work
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Input module: {e}")
            return False
    
    def run(self):
        """Main input processing loop"""
        try:
            # Update input buffer state
            self._update_input_buffer()
            
            # Process active commands
            self._process_active_commands()
            
            # Update memory with current state
            self.memory.update('input_buffer', 'current', self.input_buffer)
            
            # Sleep based on update rate
            if self.update_rate > 0:
                time.sleep(1.0 / self.update_rate)
            
        except Exception as e:
            self.logger.error(f"Error in input processing: {e}")
            raise
    
    def _on_keyboard_input(self, input_msg: KeyboardInput):
        """Handle keyboard input callback"""
        try:
            self.last_keyboard_input = input_msg
            
            # Update keyboard state in buffer
            self.input_buffer.keyboard_state[input_msg.key] = input_msg.is_pressed
            
            # Get parsed command if available
            parsed_command = self.keyboard_handler.get_parsed_command(input_msg.key)
            
            if parsed_command:
                if input_msg.is_pressed:
                    # Add to active commands
                    self.input_buffer.active_commands[f"key_{input_msg.key}"] = parsed_command
                    self.logger.debug(f"Activated command: {parsed_command.command_type.value} - {parsed_command.direction}")
                else:
                    # Remove from active commands
                    cmd_key = f"key_{input_msg.key}"
                    if cmd_key in self.input_buffer.active_commands:
                        del self.input_buffer.active_commands[cmd_key]
                        self.logger.debug(f"Deactivated command for key: {input_msg.key}")
            
            # Update last update time
            self.input_buffer.last_update = time.time()
            
            # Store raw input in memory for other modules
            self.memory.update('input_buffer', 'last_keyboard', input_msg)
            
        except Exception as e:
            self.logger.error(f"Error processing keyboard input: {e}")
    
    def _on_mouse_input(self, input_msg: MouseInput):
        """Handle mouse input callback"""
        try:
            self.last_mouse_input = input_msg
            
            
            # Update mouse state in buffer
            self.input_buffer.mouse_position = (input_msg.x, input_msg.y)
            
            if input_msg.button:
                self.input_buffer.mouse_buttons[input_msg.button] = input_msg.is_pressed
            
            # Get parsed command if available
            if input_msg.button:
                parsed_command = self.mouse_handler.get_parsed_command(input_msg.button)
                
                if parsed_command:
                    if input_msg.is_pressed:
                        # Add to active commands
                        self.input_buffer.active_commands[f"mouse_{input_msg.button}"] = parsed_command
                        self.logger.debug(f"Activated mouse command: {parsed_command.command_type.value}")
                    else:
                        # Remove from active commands
                        cmd_key = f"mouse_{input_msg.button}"
                        if cmd_key in self.input_buffer.active_commands:
                            del self.input_buffer.active_commands[cmd_key]
                            self.logger.debug(f"Deactivated mouse command: {input_msg.button}")
            
            # Handle scroll commands
            if input_msg.scroll_delta != 0:
                scroll_dir = 'scroll_up' if input_msg.scroll_delta > 0 else 'scroll_down'
                parsed_command = self.mouse_handler.get_parsed_command(scroll_dir)
                
                if parsed_command:
                    # Scroll commands are momentary
                    cmd_key = f"scroll_{time.time()}"
                    self.input_buffer.active_commands[cmd_key] = parsed_command
                    self.logger.debug(f"Activated scroll command: {scroll_dir}")
            
            # Store mouse input with metadata for end-effector control
            self.input_buffer.mouse_inputs.append(input_msg)
            
            # Keep only recent mouse inputs (last 10)
            if len(self.input_buffer.mouse_inputs) > 10:
                self.input_buffer.mouse_inputs.pop(0)
            
            # Update last update time
            self.input_buffer.last_update = time.time()
            
            # Store raw input in memory for other modules
            self.memory.update('input_buffer', 'last_mouse', input_msg)
            
        except Exception as e:
            self.logger.error(f"Error processing mouse input: {e}")
    
    def _update_input_buffer(self):
        """Update input buffer with current state"""
        try:
            # Update keyboard state
            active_keys = self.keyboard_handler.get_active_keys()
            for key in list(self.input_buffer.keyboard_state.keys()):
                if key not in active_keys:
                    self.input_buffer.keyboard_state[key] = False
            
            # Update mouse buttons
            active_buttons = self.mouse_handler.get_pressed_buttons()
            for button in list(self.input_buffer.mouse_buttons.keys()):
                if button not in active_buttons:
                    self.input_buffer.mouse_buttons[button] = False
            
            # Update mouse position
            self.input_buffer.mouse_position = self.mouse_handler.get_current_position()
            
            # Clean up old scroll commands (they should be momentary)
            current_time = time.time()
            to_remove = []
            for cmd_key in self.input_buffer.active_commands:
                if cmd_key.startswith('scroll_'):
                    cmd_time = float(cmd_key.split('_')[1])
                    if current_time - cmd_time > 0.1:  # 100ms timeout for scroll
                        to_remove.append(cmd_key)
            
            for cmd_key in to_remove:
                del self.input_buffer.active_commands[cmd_key]
            
        except Exception as e:
            self.logger.error(f"Error updating input buffer: {e}")
    
    def _process_active_commands(self):
        """Process currently active commands"""
        try:
            if not self.input_buffer.active_commands:
                return
            
            # Log active commands periodically
            if hasattr(self, '_last_command_log'):
                if time.time() - self._last_command_log > 1.0:  # Log every second
                    active_types = [cmd.command_type.value for cmd in self.input_buffer.active_commands.values()]
                    if active_types:
                        self.logger.debug(f"Active commands: {set(active_types)}")
                    self._last_command_log = time.time()
            else:
                self._last_command_log = time.time()
            
        except Exception as e:
            self.logger.error(f"Error processing active commands: {e}")
    
    def cleanup(self):
        """Cleanup input handlers"""
        try:
            self.logger.info("Cleaning up Input module...")
            
            self.keyboard_handler.stop()
            self.mouse_handler.stop()
            
            self.logger.info("Input module cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Input module cleanup: {e}")
    
    def get_current_commands(self) -> Dict[str, ParsedCommand]:
        """Get currently active commands"""
        return self.input_buffer.active_commands.copy()
    
    def get_input_state(self) -> InputBuffer:
        """Get current input state"""
        return self.input_buffer
    
    def is_emergency_stop_pressed(self) -> bool:
        """Check if emergency stop is pressed"""
        for cmd in self.input_buffer.active_commands.values():
            if cmd.command_type.value == 'emergency_stop':
                return True
        return False