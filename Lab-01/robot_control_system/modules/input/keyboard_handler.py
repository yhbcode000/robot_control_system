import threading
from typing import Dict, Callable, Optional
from pynput import keyboard
import time

from models.sensor_data import KeyboardInput
from .models import ParsedCommand, CommandType


class KeyboardHandler:
    def __init__(self, config: Dict):
        self.config = config
        self.key_mappings = self._setup_key_mappings()
        self.pressed_keys = set()
        self.listener: Optional[keyboard.Listener] = None
        self.callbacks: list = []
        self._lock = threading.Lock()
        
    def _setup_key_mappings(self) -> Dict[str, ParsedCommand]:
        """Setup keyboard mappings based on config"""
        mapping_style = self.config.get('keyboard_mapping', 'wasd')
        
        if mapping_style == 'wasd':
            return {
                'w': ParsedCommand(CommandType.MOVEMENT, 'forward'),
                's': ParsedCommand(CommandType.MOVEMENT, 'backward'),
                'a': ParsedCommand(CommandType.MOVEMENT, 'left'),
                'd': ParsedCommand(CommandType.MOVEMENT, 'right'),
                'q': ParsedCommand(CommandType.MOVEMENT, 'up'),
                'e': ParsedCommand(CommandType.MOVEMENT, 'down'),
                'space': ParsedCommand(CommandType.GRIPPER, 'toggle'),
                'esc': ParsedCommand(CommandType.EMERGENCY_STOP, None),
                # Arrow keys for rotation
                'up': ParsedCommand(CommandType.ROTATION, 'pitch_up'),
                'down': ParsedCommand(CommandType.ROTATION, 'pitch_down'),
                'left': ParsedCommand(CommandType.ROTATION, 'yaw_left'),
                'right': ParsedCommand(CommandType.ROTATION, 'yaw_right'),
                # Additional controls
                'r': ParsedCommand(CommandType.SPECIAL, 'reset'),
                'h': ParsedCommand(CommandType.SPECIAL, 'home'),
                '1': ParsedCommand(CommandType.SPECIAL, 'preset_1'),
                '2': ParsedCommand(CommandType.SPECIAL, 'preset_2'),
                '3': ParsedCommand(CommandType.SPECIAL, 'preset_3'),
            }
        elif mapping_style == 'arrows':
            return {
                'up': ParsedCommand(CommandType.MOVEMENT, 'forward'),
                'down': ParsedCommand(CommandType.MOVEMENT, 'backward'),
                'left': ParsedCommand(CommandType.MOVEMENT, 'left'),
                'right': ParsedCommand(CommandType.MOVEMENT, 'right'),
                'space': ParsedCommand(CommandType.GRIPPER, 'toggle'),
                'esc': ParsedCommand(CommandType.EMERGENCY_STOP, None),
            }
        else:
            # Default WASD
            return self._setup_key_mappings()
    
    def start(self):
        """Start keyboard listener"""
        try:
            self.listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self.listener.start()
            return True
        except Exception as e:
            print(f"Failed to start keyboard listener: {e}")
            return False
    
    def stop(self):
        """Stop keyboard listener"""
        if self.listener:
            self.listener.stop()
            self.listener = None
    
    def _on_key_press(self, key):
        """Handle key press events"""
        try:
            key_str = self._key_to_string(key)
            
            with self._lock:
                if key_str not in self.pressed_keys:
                    self.pressed_keys.add(key_str)
                    
                    # Create keyboard input message
                    input_msg = KeyboardInput(
                        key=key_str,
                        is_pressed=True,
                        modifiers=self._get_current_modifiers()
                    )
                    
                    # Notify callbacks
                    self._notify_callbacks(input_msg)
                    
        except Exception as e:
            print(f"Error handling key press: {e}")
    
    def _on_key_release(self, key):
        """Handle key release events"""
        try:
            key_str = self._key_to_string(key)
            
            with self._lock:
                if key_str in self.pressed_keys:
                    self.pressed_keys.remove(key_str)
                    
                    # Create keyboard input message
                    input_msg = KeyboardInput(
                        key=key_str,
                        is_pressed=False,
                        modifiers=self._get_current_modifiers()
                    )
                    
                    # Notify callbacks
                    self._notify_callbacks(input_msg)
                    
        except Exception as e:
            print(f"Error handling key release: {e}")
    
    def _key_to_string(self, key) -> str:
        """Convert pynput key to string"""
        try:
            if hasattr(key, 'char') and key.char is not None:
                return key.char.lower()
            elif hasattr(key, 'name'):
                return key.name.lower()
            else:
                return str(key).lower()
        except:
            return 'unknown'
    
    def _get_current_modifiers(self) -> list:
        """Get currently pressed modifier keys"""
        modifiers = []
        
        # Check for common modifier keys in pressed_keys
        if 'ctrl' in self.pressed_keys or 'ctrl_l' in self.pressed_keys or 'ctrl_r' in self.pressed_keys:
            modifiers.append('ctrl')
        if 'alt' in self.pressed_keys or 'alt_l' in self.pressed_keys or 'alt_r' in self.pressed_keys:
            modifiers.append('alt')
        if 'shift' in self.pressed_keys or 'shift_l' in self.pressed_keys or 'shift_r' in self.pressed_keys:
            modifiers.append('shift')
        
        return modifiers
    
    def add_callback(self, callback: Callable):
        """Add callback for keyboard events"""
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        """Remove callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def _notify_callbacks(self, input_msg: KeyboardInput):
        """Notify all registered callbacks"""
        for callback in self.callbacks:
            try:
                callback(input_msg)
            except Exception as e:
                print(f"Error in keyboard callback: {e}")
    
    def get_parsed_command(self, key: str) -> Optional[ParsedCommand]:
        """Get parsed command for a key"""
        return self.key_mappings.get(key.lower())
    
    def get_active_keys(self) -> set:
        """Get currently pressed keys"""
        with self._lock:
            return self.pressed_keys.copy()
    
    def is_key_pressed(self, key: str) -> bool:
        """Check if a key is currently pressed"""
        with self._lock:
            return key.lower() in self.pressed_keys