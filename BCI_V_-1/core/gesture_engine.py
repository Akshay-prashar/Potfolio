"""
core/gesture_engine.py
Interprets gestures from landmarks with improved stability, modes, and swipe handling.
"""
from utils.gesture_utils import get_distance, get_fingers_up
from config import PINCH_THRESHOLD, STABILITY_FRAMES, CLICK_DURATION_MAX, DRAG_DURATION_MIN, SWIPE_THRESHOLD, SWIPE_TIME_WINDOW
import time
from collections import Counter

class GestureEngine:
    def __init__(self):
        # Stabilization
        self.raw_gesture = None
        self.stable_gesture = None
        self.gesture_history = []
        
        # Mode state
        self.current_mode = "MOVE"
        
        # Pinch state (Action mode)
        self.is_pinching = False
        self.pinch_start_time = 0
        self.drag_triggered = False
        
        # Scroll state (Control mode)
        self.prev_y = None
        
        # Swipe limit (System mode)
        self.swipe_start_time = 0
        self.swipe_start_x = None
        
        # Cooldown state (Minimize app)
        self.fist_start_time = 0
        self.is_fist = False
        
        # Double Click limit
        self.last_click_time = 0
        self.double_click_gap = 0.4
    def get_raw_gesture(self, fingers):
        # 1. Close Palm (Fist or 0 fingers up)
        if not any(fingers.values()):
            return "FIST"
            
        # 2. All 5 fingers up (Open Palm)
        if all(fingers.values()):
            return "OPEN_PALM"
            
        # 3. 3 fingers up (Index, Middle, Ring)
        if fingers['index'] and fingers['middle'] and fingers['ring'] and not fingers['pinky']:
            return "THREE_FINGERS"
            
        # 4. 2 fingers up (Index, Middle)
        if fingers['index'] and fingers['middle'] and not fingers['ring'] and not fingers['pinky']:
            return "TWO_FINGERS"
            
        # 5. Default single finger
        if fingers['index'] and not fingers['middle'] and not fingers['ring'] and not fingers['pinky']:
            return "ONE_FINGER"
            
        return "UNKNOWN"

    def evaluate(self, landmarks):
        if not landmarks:
            self.raw_gesture = None
            self.stable_gesture = None
            self.gesture_history.clear()
            self.is_pinching = False
            self.is_fist = False
            self.prev_y = None
            return None, (0.0, 0.0, 0.0), self.current_mode, "None"
            
        fingers = get_fingers_up(landmarks)
        lm = landmarks.landmark
        
        index_x, index_y = lm[8].x, lm[8].y
        pinch_dist = get_distance(lm[4], lm[8])
        
        current_time = time.time()
        
        # 1. Raw Gesture Detection and Stabilization
        detected_gesture = self.get_raw_gesture(fingers)
        self.raw_gesture = detected_gesture
        
        self.gesture_history.append(detected_gesture)
        if len(self.gesture_history) > STABILITY_FRAMES:
            self.gesture_history.pop(0)
            
        # Determine stable gesture via majority vote in the history window
        most_common = Counter(self.gesture_history).most_common(1)[0]
        if most_common[1] >= (STABILITY_FRAMES // 2) + 1:
            if self.stable_gesture != most_common[0]:
                self.stable_gesture = most_common[0]
                # Reset transition states upon entering new stable gesture
                self.prev_y = None
                self.swipe_start_x = index_x
                self.swipe_start_time = current_time
        
        # Calculate confidence score of the current stable gesture
        confidence = 0.0
        if self.stable_gesture and len(self.gesture_history) > 0:
            confidence = self.gesture_history.count(self.stable_gesture) / len(self.gesture_history)
            
        if confidence < 0.7 and self.stable_gesture is not None:
            active_gesture = "LOW_CONF"
        else:
            active_gesture = self.stable_gesture if self.stable_gesture else self.raw_gesture
        
        # 2. Assign Modes based on Stable Gesture
        if active_gesture == "ONE_FINGER":
            self.current_mode = "MOVE"
        elif active_gesture == "TWO_FINGERS":
            self.current_mode = "CONTROL" # Scroll
        elif active_gesture in ["OPEN_PALM", "FIST"]:
            self.current_mode = "SYSTEM" # Swipe/Minimize
        else:
            self.current_mode = "ACTION" # Defaults or Pinch
            
        intent = "MOVE" # Default to always moving
        position = (index_x, index_y, 0.0) # x, y, delta_y
        
        # 3. Mode Action Logic
        if self.current_mode == "SYSTEM":
            # Handle MINIMIZE
            if active_gesture == "FIST":
                if not self.is_fist:
                    self.is_fist = True
                    self.fist_start_time = current_time
                elif current_time - self.fist_start_time > 1.0:
                    intent = "MINIMIZE_APP"
                    self.fist_start_time = current_time + 2.0 
            else:
                self.is_fist = False
                
            # Handle SWIPE
            if active_gesture == "OPEN_PALM":
                if self.swipe_start_x is None:
                    self.swipe_start_x = index_x
                    self.swipe_start_time = current_time
                else:
                    dx = index_x - self.swipe_start_x
                    elapsed = current_time - self.swipe_start_time
                    if elapsed <= SWIPE_TIME_WINDOW:
                        if dx > SWIPE_THRESHOLD:
                            intent = "SWIPE_RIGHT"
                            self.swipe_start_x = index_x
                        elif dx < -SWIPE_THRESHOLD:
                            intent = "SWIPE_LEFT"
                            self.swipe_start_x = index_x
                    else:
                        self.swipe_start_x = index_x
                        self.swipe_start_time = current_time

        elif self.current_mode == "CONTROL":
            if self.prev_y is not None:
                dy = self.prev_y - index_y
                position = (index_x, index_y, dy)
                intent = "SCROLL"
            self.prev_y = index_y
            
        else: # MOVE or ACTION
            # Handle Pinch for Move/Click/Drag
            if pinch_dist < PINCH_THRESHOLD:
                self.current_mode = "ACTION"
                if not self.is_pinching:
                    self.is_pinching = True
                    self.pinch_start_time = current_time
                    self.drag_triggered = False
                else:
                    elapsed = current_time - self.pinch_start_time
                    if elapsed > DRAG_DURATION_MIN and not self.drag_triggered:
                        self.drag_triggered = True
                        intent = "DRAG_START"
                    elif self.drag_triggered:
                        intent = "DRAG_MOVE"
                    else:
                        intent = "MOVE"
            else:
                if self.is_pinching:
                    self.is_pinching = False
                    elapsed = current_time - self.pinch_start_time
                    if elapsed <= CLICK_DURATION_MAX and not self.drag_triggered:
                        if current_time - self.last_click_time < self.double_click_gap:
                            intent = "DOUBLE_CLICK"
                            self.last_click_time = 0
                        else:
                            intent = "CLICK"
                            self.last_click_time = current_time
                        self.current_mode = "ACTION"
                    elif self.drag_triggered:
                        intent = "DRAG_END"
                        self.current_mode = "ACTION"
                    else:
                        self.current_mode = "MOVE"
                        intent = "MOVE"
                else:
                    self.current_mode = "MOVE"
                    intent = "MOVE"
                    
        return intent, position, self.current_mode, str(active_gesture)

