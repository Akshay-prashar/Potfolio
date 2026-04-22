"""
modules/chrome_module.py
Browser-specific controls (scroll, tab switch). This acts as a plugin.
"""
import pyautogui
import time

class ChromeModule:
    def __init__(self):
        self.active = False
        self.last_action_time = 0
        
    def handle_gesture(self, intent, position):
        if not self.active or not intent:
            return
            
        current_time = time.time()
        cooldown = 0.5
        
        if intent == "SCROLL":
            # Chrome fast scroll
            pyautogui.scroll(-100)
        elif intent == "CLICK" and (current_time - self.last_action_time > cooldown):
            # Tab switch via shortcut (Ctrl+Tab) for demonstration of modular mapping
            pyautogui.hotkey('ctrl', 'tab')
            self.last_action_time = current_time
        elif intent == "DRAG" and (current_time - self.last_action_time > cooldown):
            # Go back one page
            pyautogui.hotkey('alt', 'left')
            self.last_action_time = current_time
