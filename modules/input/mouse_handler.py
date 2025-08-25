import threading
from typing import Dict, Callable, Optional, Tuple
from pynput import mouse
import time

from models.sensor_data import MouseInput
from .models import ParsedCommand, CommandType
from .mouse_control import MouseEndEffectorController, MouseControlConfig, MouseTracker


class MouseHandler:
    def __init__(self, config: Dict):
        self.config = config
        self.mouse_mappings = self._setup_mouse_mappings()
        self.current_position = (0, 0)
        self.last_position = (0, 0)
        self.pressed_buttons = set()
        self.listener: Optional[mouse.Listener] = None
        self.callbacks: list = []
        self.drag_start_pos: Optional[Tuple[int, int]] = None
        self.is_dragging = False
        self._lock = threading.Lock()
        
        # Mouse sensitivity settings
        self.sensitivity = config.get('mouse_sensitivity', 1.0)
        self.deadzone = config.get('mouse_deadzone', 5)  # pixels
        
        # End-effector control
        self.enable_end_effector_control = config.get('enable_end_effector_control', True)
        
        if self.enable_end_effector_control:
            # Setup mouse control configuration
            mouse_config = MouseControlConfig(
                screen_width=config.get('screen_width', 1920),
                screen_height=config.get('screen_height', 1080),
                workspace_width=config.get('workspace_width', 1.2),
                workspace_height=config.get('workspace_height', 1.2),
                workspace_center=config.get('workspace_center', (0.4, 0.0, 0.4)),
                position_sensitivity=config.get('position_sensitivity', 1.0),
                scroll_sensitivity=config.get('scroll_sensitivity', 0.01),
                enable_smoothing=config.get('enable_smoothing', True),
                smoothing_factor=config.get('smoothing_factor', 0.8)
            )
            
            self.end_effector_controller = MouseEndEffectorController(mouse_config)
            self.mouse_tracker = MouseTracker()
        else:
            self.end_effector_controller = None
            self.mouse_tracker = None
        
    def _setup_mouse_mappings(self) -> Dict[str, ParsedCommand]:
        """Setup mouse button mappings"""
        return {
            'left': ParsedCommand(CommandType.MOVEMENT, 'direct_control'),
            'right': ParsedCommand(CommandType.CAMERA, 'rotate'),
            'middle': ParsedCommand(CommandType.GRIPPER, 'toggle'),
            'scroll_up': ParsedCommand(CommandType.CAMERA, 'zoom_in'),
            'scroll_down': ParsedCommand(CommandType.CAMERA, 'zoom_out'),
        }
    
    def start(self):
        """Start mouse listener"""
        try:
            # Start mouse listener
            self.listener = mouse.Listener(
                on_move=self._on_mouse_move,
                on_click=self._on_mouse_click,
                on_scroll=self._on_mouse_scroll
            )
            self.listener.start()
            
            return True
        except Exception as e:
            print(f"Failed to start mouse listener: {e}")
            return False
    
    def stop(self):
        """Stop mouse listener"""
        if self.listener:
            self.listener.stop()
            self.listener = None
    
    def _on_mouse_move(self, x, y):
        """Handle mouse movement"""
        try:
            with self._lock:
                self.last_position = self.current_position
                self.current_position = (x, y)
                
                # Calculate delta (for other uses, not end-effector)
                dx = x - self.last_position[0]
                dy = y - self.last_position[1]
                
                # For end-effector control, we always process position
                # (no deadzone for absolute positioning)
                if self.enable_end_effector_control:
                    # Skip deadzone check for end-effector control
                    pass
                else:
                    # Apply deadzone only for non-end-effector uses
                    if abs(dx) < self.deadzone and abs(dy) < self.deadzone:
                        return
                
                dx *= self.sensitivity
                dy *= self.sensitivity
                
                # Update end-effector controller if enabled
                end_effector_target = None
                if self.enable_end_effector_control and self.end_effector_controller:
                    self.mouse_tracker.update_position(x, y)
                    # Use absolute positioning for end-effector control
                    end_effector_target = self.end_effector_controller.update_from_mouse(x, y)
                
                # Create mouse input message
                input_msg = MouseInput(
                    x=x,
                    y=y,
                    dx=int(dx),
                    dy=int(dy),
                    button=None,
                    is_pressed=False,
                    scroll_delta=0
                )
                
                # Add end-effector target to metadata
                if end_effector_target is not None:
                    input_msg.metadata = {
                        'end_effector_target': end_effector_target,
                        'control_mode': 'end_effector_position'
                    }
                
                # Check if we're dragging
                if self.pressed_buttons and self.drag_start_pos:
                    self.is_dragging = True
                    if not hasattr(input_msg, 'metadata'):
                        input_msg.metadata = {}
                    input_msg.metadata.update({
                        'dragging': True,
                        'drag_start': self.drag_start_pos,
                        'drag_distance': (
                            x - self.drag_start_pos[0],
                            y - self.drag_start_pos[1]
                        )
                    })
                
                # Notify callbacks
                self._notify_callbacks(input_msg)
                
        except Exception as e:
            print(f"Error handling mouse move: {e}")
    
    def _on_mouse_click(self, x, y, button, pressed):
        """Handle mouse click events"""
        try:
            button_str = self._button_to_string(button)
            
            with self._lock:
                if pressed:
                    self.pressed_buttons.add(button_str)
                    self.drag_start_pos = (x, y)
                    self.is_dragging = False
                else:
                    self.pressed_buttons.discard(button_str)
                    if not self.pressed_buttons:
                        self.drag_start_pos = None
                        self.is_dragging = False
                
                # Create mouse input message
                input_msg = MouseInput(
                    x=x,
                    y=y,
                    dx=0,
                    dy=0,
                    button=button_str,
                    is_pressed=pressed,
                    scroll_delta=0
                )
                
                # Add drag info if applicable
                if self.is_dragging:
                    input_msg.metadata = {
                        'dragging': True,
                        'drag_start': self.drag_start_pos
                    }
                
                # Notify callbacks
                self._notify_callbacks(input_msg)
                
        except Exception as e:
            print(f"Error handling mouse click: {e}")
    
    def _on_mouse_scroll(self, x, y, dx, dy):
        """Handle mouse scroll events"""
        try:
            # Update end-effector controller for Z-axis control
            end_effector_target = None
            if self.enable_end_effector_control and self.end_effector_controller:
                self.mouse_tracker.update_scroll(dy)
                # Update end-effector target with scroll for Z control
                end_effector_target = self.end_effector_controller.update_from_mouse(x, y, dy)
            
            # Create mouse input message for scroll
            input_msg = MouseInput(
                x=x,
                y=y,
                dx=0,
                dy=0,
                button='scroll',
                is_pressed=False,
                scroll_delta=int(dy)
            )
            
            # Add end-effector target to metadata
            if end_effector_target is not None:
                input_msg.metadata = {
                    'end_effector_target': end_effector_target,
                    'control_mode': 'end_effector_position',
                    'z_control': True,
                    'scroll_direction': 'up' if dy > 0 else 'down'
                }
            
            # Notify callbacks
            self._notify_callbacks(input_msg)
            
        except Exception as e:
            print(f"Error handling mouse scroll: {e}")
    
    def _button_to_string(self, button) -> str:
        """Convert pynput button to string"""
        try:
            if hasattr(button, 'name'):
                return button.name.lower()
            else:
                return str(button).lower()
        except:
            return 'unknown'
    
    def add_callback(self, callback: Callable):
        """Add callback for mouse events"""
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        """Remove callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def _notify_callbacks(self, input_msg: MouseInput):
        """Notify all registered callbacks"""
        for callback in self.callbacks:
            try:
                callback(input_msg)
            except Exception as e:
                print(f"Error in mouse callback: {e}")
    
    def get_parsed_command(self, button: str) -> Optional[ParsedCommand]:
        """Get parsed command for a mouse button"""
        return self.mouse_mappings.get(button.lower())
    
    def get_current_position(self) -> Tuple[int, int]:
        """Get current mouse position"""
        with self._lock:
            return self.current_position
    
    def get_pressed_buttons(self) -> set:
        """Get currently pressed mouse buttons"""
        with self._lock:
            return self.pressed_buttons.copy()
    
    def is_button_pressed(self, button: str) -> bool:
        """Check if a button is currently pressed"""
        with self._lock:
            return button.lower() in self.pressed_buttons
    
    def is_dragging_active(self) -> bool:
        """Check if dragging is active"""
        with self._lock:
            return self.is_dragging