"""
core/hand_tracking.py
Handles MediaPipe detection and returns landmarks.
"""
import cv2
import sys

try:
    import mediapipe as mp
    # Test access to verify DLLs loaded correctly
    _ = mp.solutions.hands
except AttributeError:
    print('\n' + '='*70)
    print('CRITICAL ERROR: MediaPipe failed to load its internal modules (solutions).')
    print('='*70)
    print('This happens when MediaPipe\'s C++ backend fails to load on Windows.\n')
    print('To fix this, please ensure:\n')
    print('1. You are using Python 3.10 or 3.11 (Python 3.12/3.13 often break MediaPipe).')
    print(f'   You are currently running: Python {sys.version.split(" ")[0]}\n')
    print('2. You have the Visual C++ Redistributable installed.')
    print('   Download here: https://aka.ms/vs/17/release/vc_redist.x64.exe')
    print('='*70 + '\n')
    sys.exit(1)

class HandTracker:
    def __init__(self, mode=False, max_hands=1, detection_con=0.7, track_con=0.7):
        """Initializes the mediapipe hands model."""
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=mode,
            max_num_hands=max_hands,
            min_detection_confidence=detection_con,
            min_tracking_confidence=track_con
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.results = None

    def find_hands(self, img, draw=True):
        """Processes the image and draws hand landmarks."""
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.results = self.hands.process(img_rgb)
        
        if self.results.multi_hand_landmarks and draw:
            for hand_landmarks in self.results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(
                    img, 
                    hand_landmarks, 
                    self.mp_hands.HAND_CONNECTIONS
                )
        return img

    def get_landmarks(self):
        """Returns the first detected hand's landmarks."""
        if self.results and self.results.multi_hand_landmarks:
            return self.results.multi_hand_landmarks[0]
        return None
