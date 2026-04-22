"""
config.py
Configuration values for the Gesture Control System.
"""
import ctypes

# Utility to get the actual screen resolution on Windows
try:
    user32 = ctypes.windll.user32
    SCREEN_WIDTH = user32.GetSystemMetrics(0)
    SCREEN_HEIGHT = user32.GetSystemMetrics(1)
except Exception:
    SCREEN_WIDTH = 1920
    SCREEN_HEIGHT = 1080

# Camera Resolution (lower for better performance)
CAM_WIDTH = 640
CAM_HEIGHT = 480

# UI and Debugging
DEBUG_MODE = True  # Show gesture, mode, and action text on camera feed

# Smoothing
SMOOTHING_FACTOR = 0.85  # 0.0 to 1.0 (higher = smoother but more lag)

# Gesture & Stability Thresholds
STABILITY_FRAMES = 5       # A gesture must be the same for this many frames to lock in
ACTION_COOLDOWN = 0.5      # Universal cooldown between distinct actions
DOUBLE_CLICK_COOLDOWN = 0.6 # Minimum time between double clicks to prevent triple clicks
PINCH_THRESHOLD = 0.05
CLICK_DURATION_MAX = 1.0   # Pinch held less than this is a CLICK
DRAG_DURATION_MIN = 1.5    # Pinch held longer than this is a DRAG

# Scrolling & Swipe
SCROLL_SCALING = 5000      # Multiplier for continuous velocity-based vertical scrolling
SWIPE_THRESHOLD = 0.15     # Minimum horizontal X travel required to register a swipe
SWIPE_TIME_WINDOW = 1.0    # Timeframe in which swipe must be completed

# Bounding box margins for the camera feed
MARGIN_X = 0.10
MARGIN_Y = 0.15

