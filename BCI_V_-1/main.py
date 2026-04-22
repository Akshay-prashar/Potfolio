"""
main.py
Universal gesture-based controller loop without explicit mode switching.
"""
import cv2
import time
from core.hand_tracking import HandTracker
from core.gesture_engine import GestureEngine
from core.cursor_control import CursorController
from modules.system_module import SystemModule
from config import CAM_WIDTH, CAM_HEIGHT, MARGIN_X, MARGIN_Y

def main():
    # Setup Camera
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
    
    # Core Components
    tracker = HandTracker(max_hands=1)
    gesture_engine = GestureEngine()
    cursor = CursorController()
    
    # Universal Module
    system_mod = SystemModule(cursor)
    
    print("Universal Gesture Control System Started.")
    print("Press 'q' in the camera window to quit.")
    
    pTime = 0

    while True:
        success, img = cap.read()
        if not success:
            print("Failed to capture image")
            break
            
        img = cv2.flip(img, 1)
        
        # Guide box representation of the screen boundaries
        h, w, c = img.shape
        start_point = (int(MARGIN_X * w), int(MARGIN_Y * h))
        end_point = (int((1.0 - MARGIN_X) * w), int((1.0 - MARGIN_Y) * h))
        cv2.rectangle(img, start_point, end_point, (255, 0, 255), 2)
        
        # Process and Output
        img = tracker.find_hands(img, draw=True)
        landmarks = tracker.get_landmarks()
        
        intent, position, current_mode, stable_gesture = gesture_engine.evaluate(landmarks)
        system_mod.handle_gesture(intent, position)
            
        # Draw Overlays
        cTime = time.time()
        fps = 1 / (cTime - pTime) if cTime - pTime > 0 else 0
        pTime = cTime
        
        from config import DEBUG_MODE
        if DEBUG_MODE:
            intent_text = intent if intent else "None"
            cv2.putText(img, f"Mode: {current_mode}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.putText(img, f"Action: {intent_text}", (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(img, f"Gesture: {stable_gesture}", (10, 90), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
            cv2.putText(img, f"FPS: {int(fps)}", (10, 120), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 150, 255), 2)
                        
        cv2.imshow("Hand Gesture OS Controller", img)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            cursor.min_x, cursor.max_x = 1.0, 0.0
            cursor.min_y, cursor.max_y = 1.0, 0.0
            print("Calibration Reset!")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
