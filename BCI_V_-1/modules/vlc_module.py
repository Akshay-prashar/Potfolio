"""
modules/vlc_module.py
Media player controls (play/pause, volume) demonstrating the extension design.
"""
import pyautogui
import time

class VLCModule:
    def __init__(self):
        self.active = False
        self.last_action_time = 0
        
    def handle_gesture(self, intent, position):
        if not self.active or not intent:
            return
            
        current_time = time.time()
        cooldown = 0.5
        
        if intent == "CLICK" and (current_time - self.last_action_time > cooldown):
            # Play / Pause
            pyautogui.press('space')
            self.last_action_time = current_time
        elif intent == "SCROLL":
            # Volume control (down arrow in VLC)
            pyautogui.press('down')
        elif intent == "DRAG":
            # Volume up (up arrow in VLC)
            pyautogui.press('up')
