"""
utils/smoothing.py
Cursor smoothing algorithm to reduce jitter.
"""
from typing import Tuple
import math

class CursorSmoother:
    def __init__(self, smoothing_factor: float = 0.5):
        """
        :param smoothing_factor: 0.0 to 1.0. 
                                 Closer to 1.0 gives smoother movement but more latency.
        """
        self.smoothing_factor = max(0.0, min(1.0, smoothing_factor))
        self.prev_x = 0.0
        self.prev_y = 0.0

    def smooth(self, target_x: float, target_y: float) -> Tuple[int, int]:
        """Applies exponential smoothing with dynamic responsiveness."""
        if self.prev_x == 0.0 and self.prev_y == 0.0:
            self.prev_x, self.prev_y = target_x, target_y
            
        dist = math.hypot(target_x - self.prev_x, target_y - self.prev_y)
        
        # Dynamic factor: fast movements decrease lag (lower smoothing)
        dynamic_factor = self.smoothing_factor
        if dist > 30:
            # Reduce smoothing by 0.3 for rapid tracking but keep a minimum floor
            dynamic_factor = max(0.1, self.smoothing_factor - 0.3)
            
        smoothed_x = self.prev_x + (target_x - self.prev_x) * (1.0 - dynamic_factor)
        smoothed_y = self.prev_y + (target_y - self.prev_y) * (1.0 - dynamic_factor)
        
        self.prev_x, self.prev_y = smoothed_x, smoothed_y
        return int(smoothed_x), int(smoothed_y)

