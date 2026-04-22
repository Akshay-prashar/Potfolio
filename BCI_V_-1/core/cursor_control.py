"""
core/cursor_control.py
Handles mouse movement and actions using PyAutoGUI.
"""
import pyautogui
import time
from utils.smoothing import CursorSmoother
from config import SCREEN_WIDTH, SCREEN_HEIGHT

# Disable PyAutoGUI failsafe or extend it, so cursor doesn't crash app when hitting corners
pyautogui.FAILSAFE = False

class CursorController:
    def __init__(self):
        from config import SMOOTHING_FACTOR
        self.smoother = CursorSmoother(smoothing_factor=SMOOTHING_FACTOR)
        # Dynamic calibration tracking
        self.min_x = 1.0
        self.max_x = 0.0
        self.min_y = 1.0
        self.max_y = 0.0

    def move_cursor(self, x_normalized: float, y_normalized: float):
        """Moves the cursor relative to dynamically learned tracking space limits."""
        # Update dynamic bounds
        self.min_x = min(self.min_x, x_normalized)
        self.max_x = max(self.max_x, x_normalized)
        
        self.min_y = min(self.min_y, y_normalized)
        self.max_y = max(self.max_y, y_normalized)
        
        # Avoid division by zero, shrink inner tracking field by 20% to easily reach screen edges
        range_x = max(0.01, self.max_x - self.min_x) * 0.80
        range_y = max(0.01, self.max_y - self.min_y) * 0.85
        
        # Normalize dynamically to learned bounds
        adj_x = (x_normalized - self.min_x) / range_x
        adj_y = (y_normalized - self.min_y) / range_y
        
        # Add Boost for Right Edge
        adj_x = adj_x ** 0.9
        
        # Hard Snap to Edges
        if adj_x > 0.97:
            adj_x = 1.0
        elif adj_x < 0.03:
            adj_x = 0.0
            
        if adj_y > 0.97:
            adj_y = 1.0
        elif adj_y < 0.03:
            adj_y = 0.0
            
        # Guarantee it naturally clips at screen edges 
        adj_x = max(0.0, min(1.0, adj_x))
        adj_y = max(0.0, min(1.0, adj_y))
        
        target_x = adj_x * SCREEN_WIDTH
        target_y = adj_y * SCREEN_HEIGHT
        
        # Apply smoothing
        smooth_x, smooth_y = self.smoother.smooth(target_x, target_y)
        pyautogui.moveTo(smooth_x, smooth_y)

    def click(self):
        """Performs a left click. Cooldown is handled in system_module."""
        pyautogui.click()

    def scroll(self, direction: int):
        """Scrolls the mouse up or down."""
        # The direction value might need tuning depending on the OS (Windows uses larger values)
        pyautogui.scroll(direction)

    def drag(self, x_normalized: float, y_normalized: float):
        """Drags the cursor to the specified location."""
        target_x = x_normalized * SCREEN_WIDTH
        target_y = y_normalized * SCREEN_HEIGHT
        smooth_x, smooth_y = self.smoother.smooth(target_x, target_y)
        pyautogui.dragTo(smooth_x, smooth_y, button='left')

