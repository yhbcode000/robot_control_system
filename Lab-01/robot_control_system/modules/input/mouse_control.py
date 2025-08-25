"""Mouse control handler for end-effector positioning"""

import numpy as np
import time
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class MouseControlConfig:
    """Configuration for mouse control"""
    # Screen to workspace mapping
    screen_width: int = 1920
    screen_height: int = 1080
    workspace_width: float = 1.2    # meters
    workspace_height: float = 1.2   # meters
    workspace_depth: float = 0.8    # meters
    
    # Workspace center in robot coordinates
    workspace_center: Tuple[float, float, float] = (0.4, 0.0, 0.4)
    
    # Mouse sensitivity
    position_sensitivity: float = 1.0
    scroll_sensitivity: float = 0.01  # meters per scroll unit
    
    # Smoothing and filtering
    enable_smoothing: bool = True
    smoothing_factor: float = 0.8  # 0 = no smoothing, 1 = max smoothing
    
    # Limits
    min_z: float = 0.1
    max_z: float = 0.8

class MouseEndEffectorController:
    """Convert mouse input to end-effector target positions"""
    
    def __init__(self, config: MouseControlConfig = None):
        self.config = config or MouseControlConfig()
        
        # Current state
        self.current_target = np.array(self.config.workspace_center)
        self.last_mouse_pos = None
        self.last_update_time = 0
        
        # Smoothing
        self.smoothed_target = self.current_target.copy()
        
        # Mouse capture state
        self.mouse_active = False
        self.center_mouse_pos = (self.config.screen_width // 2, 
                               self.config.screen_height // 2)
        
        # Window tracking - assume MuJoCo viewer window bounds
        self.window_bounds = None
        self.mouse_in_window = False
        
    def update_from_mouse(self, mouse_x: int, mouse_y: int, 
                         scroll_delta: float = 0) -> np.ndarray:
        """
        Update target end-effector position from mouse input
        
        Args:
            mouse_x: Mouse X coordinate (screen pixels)
            mouse_y: Mouse Y coordinate (screen pixels) 
            scroll_delta: Mouse scroll delta (positive = up, negative = down)
            
        Returns:
            target_position: 3D target position [x, y, z] in robot coordinates
        """
        current_time = time.time()
        
        # Check if mouse is within valid tracking bounds
        if not self._is_mouse_in_tracking_area(mouse_x, mouse_y):
            # Mouse is outside tracking area, return current target without updates
            return self.get_current_target()
        
        # Convert mouse position to workspace coordinates
        target_x, target_y = self._mouse_to_workspace(mouse_x, mouse_y)
        
        # Update Z coordinate from scroll
        if scroll_delta != 0:
            delta_z = scroll_delta * self.config.scroll_sensitivity
            self.current_target[2] += delta_z
            self.current_target[2] = np.clip(self.current_target[2], 
                                           self.config.min_z, 
                                           self.config.max_z)
        
        # Update X, Y coordinates
        self.current_target[0] = target_x
        self.current_target[1] = target_y
        
        # Apply smoothing if enabled
        if self.config.enable_smoothing:
            alpha = 1.0 - self.config.smoothing_factor
            self.smoothed_target = (alpha * self.current_target + 
                                  self.config.smoothing_factor * self.smoothed_target)
            result = self.smoothed_target
        else:
            result = self.current_target
        
        self.last_update_time = current_time
        return result.copy()
    
    def update_from_relative_movement(self, delta_x: int, delta_y: int,
                                    scroll_delta: float = 0) -> np.ndarray:
        """
        Update target from relative mouse movement (better for captured mouse)
        
        Args:
            delta_x: Mouse movement in X (pixels)
            delta_y: Mouse movement in Y (pixels)
            scroll_delta: Scroll wheel delta
            
        Returns:
            target_position: 3D target position
        """
        # Convert pixel deltas to workspace deltas
        workspace_delta_x = (delta_x / self.config.screen_width) * self.config.workspace_width
        workspace_delta_y = -(delta_y / self.config.screen_height) * self.config.workspace_height
        
        # Apply sensitivity
        workspace_delta_x *= self.config.position_sensitivity
        workspace_delta_y *= self.config.position_sensitivity
        
        # Update target position
        self.current_target[0] += workspace_delta_x
        self.current_target[1] += workspace_delta_y
        
        # Handle Z from scroll
        if scroll_delta != 0:
            delta_z = scroll_delta * self.config.scroll_sensitivity
            self.current_target[2] += delta_z
        
        # Apply workspace limits
        self.current_target = self._apply_workspace_limits(self.current_target)
        
        # Apply smoothing
        if self.config.enable_smoothing:
            alpha = 1.0 - self.config.smoothing_factor
            self.smoothed_target = (alpha * self.current_target + 
                                  self.config.smoothing_factor * self.smoothed_target)
            return self.smoothed_target.copy()
        
        return self.current_target.copy()
    
    def _mouse_to_workspace(self, mouse_x: int, mouse_y: int) -> Tuple[float, float]:
        """Convert mouse screen coordinates to workspace coordinates"""
        # Check if coordinates are already centered (MuJoCo style)
        # If mouse_x and mouse_y are small relative to screen size, assume they're centered
        if (abs(mouse_x) < self.config.screen_width // 4 and 
            abs(mouse_y) < self.config.screen_height // 4):
            # Assume coordinates are relative to center (MuJoCo viewer style)
            norm_x = mouse_x / (self.config.screen_width // 2)
            norm_y = mouse_y / (self.config.screen_height // 2)
        else:
            # Standard screen coordinates (0,0 at top-left)
            norm_x = 2.0 * (mouse_x / self.config.screen_width) - 1.0
            norm_y = 2.0 * (mouse_y / self.config.screen_height) - 1.0
        
        # Flip Y axis (screen Y=0 is top, robot Y=0 is forward)
        norm_y = -norm_y
        
        # Clamp normalized coordinates to [-1, 1]
        norm_x = np.clip(norm_x, -1.0, 1.0)
        norm_y = np.clip(norm_y, -1.0, 1.0)
        
        # Scale to workspace
        workspace_x = self.config.workspace_center[0] + norm_x * (self.config.workspace_width / 2)
        workspace_y = self.config.workspace_center[1] + norm_y * (self.config.workspace_height / 2)
        
        return workspace_x, workspace_y
    
    def _is_mouse_in_tracking_area(self, mouse_x: int, mouse_y: int) -> bool:
        """Check if mouse is within valid tracking area (MuJoCo window)"""
        # For MuJoCo viewer, assume coordinates are centered and within reasonable bounds
        # If coordinates are very large, mouse is likely outside the viewer window
        max_coord = max(self.config.screen_width, self.config.screen_height) // 2
        
        # Check if coordinates are within reasonable bounds for centered coordinate system
        if (abs(mouse_x) < self.config.screen_width // 4 and 
            abs(mouse_y) < self.config.screen_height // 4):
            # Centered coordinates (MuJoCo style) - always valid if within bounds
            return True
        
        # Standard screen coordinates - check if within screen bounds
        if (0 <= mouse_x <= self.config.screen_width and 
            0 <= mouse_y <= self.config.screen_height):
            return True
        
        # Outside valid tracking area
        return False
    
    def _apply_workspace_limits(self, position: np.ndarray) -> np.ndarray:
        """Apply workspace limits to position"""
        center = np.array(self.config.workspace_center)
        
        # X limits
        x_min = center[0] - self.config.workspace_width / 2
        x_max = center[0] + self.config.workspace_width / 2
        
        # Y limits  
        y_min = center[1] - self.config.workspace_height / 2
        y_max = center[1] + self.config.workspace_height / 2
        
        # Z limits
        z_min = self.config.min_z
        z_max = self.config.max_z
        
        limited_pos = position.copy()
        limited_pos[0] = np.clip(limited_pos[0], x_min, x_max)
        limited_pos[1] = np.clip(limited_pos[1], y_min, y_max)
        limited_pos[2] = np.clip(limited_pos[2], z_min, z_max)
        
        return limited_pos
    
    def set_target_position(self, position: np.ndarray):
        """Manually set target position"""
        self.current_target = self._apply_workspace_limits(position)
        self.smoothed_target = self.current_target.copy()
    
    def get_current_target(self) -> np.ndarray:
        """Get current target position"""
        if self.config.enable_smoothing:
            return self.smoothed_target.copy()
        return self.current_target.copy()
    
    def reset_to_center(self):
        """Reset target to workspace center"""
        self.current_target = np.array(self.config.workspace_center)
        self.smoothed_target = self.current_target.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """Get controller status"""
        return {
            'current_target': self.get_current_target(),
            'raw_target': self.current_target,
            'mouse_active': self.mouse_active,
            'workspace_center': self.config.workspace_center,
            'workspace_limits': {
                'x': (self.config.workspace_center[0] - self.config.workspace_width/2,
                      self.config.workspace_center[0] + self.config.workspace_width/2),
                'y': (self.config.workspace_center[1] - self.config.workspace_height/2,
                      self.config.workspace_center[1] + self.config.workspace_height/2),
                'z': (self.config.min_z, self.config.max_z)
            },
            'last_update': self.last_update_time
        }

class MouseTracker:
    """Track mouse position and movement"""
    
    def __init__(self):
        self.last_position = None
        self.current_position = (0, 0)
        self.movement_delta = (0, 0)
        self.scroll_delta = 0
        self.last_scroll_time = 0
        
    def update_position(self, x: int, y: int):
        """Update mouse position"""
        if self.last_position is not None:
            self.movement_delta = (x - self.last_position[0], 
                                 y - self.last_position[1])
        else:
            self.movement_delta = (0, 0)
            
        self.last_position = self.current_position
        self.current_position = (x, y)
    
    def update_scroll(self, delta: float):
        """Update scroll delta"""
        self.scroll_delta = delta
        self.last_scroll_time = time.time()
    
    def get_movement_delta(self) -> Tuple[int, int]:
        """Get movement since last update"""
        delta = self.movement_delta
        self.movement_delta = (0, 0)  # Reset after getting
        return delta
    
    def get_scroll_delta(self) -> float:
        """Get scroll delta since last update"""
        # Decay scroll delta over time
        current_time = time.time()
        if current_time - self.last_scroll_time > 0.1:  # 100ms timeout
            self.scroll_delta = 0
            
        delta = self.scroll_delta
        self.scroll_delta = 0  # Reset after getting
        return delta