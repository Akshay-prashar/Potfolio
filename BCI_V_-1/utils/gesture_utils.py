"""
utils/gesture_utils.py
Helper functions for calculating distances and detecting finger states.
"""
import math
from typing import Dict, Any

def get_distance(lm1: Any, lm2: Any) -> float:
    """Calculate Euclidean distance between two landmarks (normalized coordinates)."""
    return math.hypot(lm2.x - lm1.x, lm2.y - lm1.y)

def get_fingers_up(hand_landmarks: Any) -> Dict[str, bool]:
    """
    Returns a dictionary of which fingers are 'up'.
    This uses a basic y-coordinate heuristic for fingers and x-coord for thumb.
    """
    if not hand_landmarks:
        return {"thumb": False, "index": False, "middle": False, "ring": False, "pinky": False}
        
    lm = hand_landmarks.landmark
    fingers_up = {}
    
    # Handedness check is ideal, but assuming basic relative x for thumb (Right Hand default behavior)
    # A true robust thumb check evaluates distance to pinky base or checks handedness label.
    # For simplicity, if thumb tip is further right/left than its IP joint.
    # We will simply check if the thumb tip is further away from the palm center than the thumb MCP.
    palm_x = lm[0].x
    fingers_up['thumb'] = abs(lm[4].x - palm_x) > abs(lm[3].x - palm_x)
    
    # Index (Tip = 8, PIP = 6)
    fingers_up['index'] = lm[8].y < lm[6].y
    
    # Middle (Tip = 12, PIP = 10)
    fingers_up['middle'] = lm[12].y < lm[10].y
    
    # Ring (Tip = 16, PIP = 14)
    fingers_up['ring'] = lm[16].y < lm[14].y
    
    # Pinky (Tip = 20, PIP = 18)
    fingers_up['pinky'] = lm[20].y < lm[18].y
    
    return fingers_up
