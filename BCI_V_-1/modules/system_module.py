"""
modules/system_module.py
Universal system controls mapped to gestures.
"""
import pyautogui
import time
from config import SCROLL_SCALING, ACTION_COOLDOWN

class SystemModule:
    def __init__(self, cursor_controller):
        self.cursor = cursor_controller
        self.last_action_time = 0
        self.is_dragging = False

    def handle_gesture(self, intent, position):
        if not intent:
            return

        x, y, dy = position
        current_time = time.time()

        if intent == "MOVE":
            self.cursor.move_cursor(x, y)
        elif intent == "CLICK":
            if current_time - self.last_action_time > ACTION_COOLDOWN:
                self.cursor.move_cursor(x, y)
                self.cursor.click()
                self.last_action_time = current_time
        elif intent == "DRAG_START":
            if not self.is_dragging:
                self.cursor.move_cursor(x, y)  # align cursor first
                pyautogui.mouseDown(button='left')
                self.is_dragging = True
        elif intent == "DRAG_MOVE":
            if self.is_dragging:
                # Move WHILE holding mouse (critical)
                self.cursor.move_cursor(x, y)
        elif intent == "DRAG_END":
            if self.is_dragging:
                self.cursor.move_cursor(x, y)
                pyautogui.mouseUp(button='left')
                self.is_dragging = False
        elif intent == "SCROLL":
            self.cursor.move_cursor(x, y)
            # Velocity based scrolling
            scroll_amount = int(dy * SCROLL_SCALING)
            if scroll_amount != 0:
                pyautogui.scroll(scroll_amount)
        elif intent == "SWIPE_RIGHT":
            if current_time - self.last_action_time > ACTION_COOLDOWN:
                # App Switch next
                pyautogui.hotkey('alt', 'tab')
                self.last_action_time = current_time
        elif intent == "SWIPE_LEFT":
            if current_time - self.last_action_time > ACTION_COOLDOWN:
                # App Switch previous
                pyautogui.hotkey('alt', 'shift', 'tab')
                self.last_action_time = current_time
        elif intent == "DOUBLE_CLICK":
            from config import DOUBLE_CLICK_COOLDOWN
            if current_time - self.last_action_time > DOUBLE_CLICK_COOLDOWN:
                self.cursor.move_cursor(x, y)
                pyautogui.doubleClick()
                self.last_action_time = current_time
        elif intent == "MINIMIZE_APP":
            if current_time - self.last_action_time > ACTION_COOLDOWN:
                # Windows Shortcut for Minimize
                pyautogui.hotkey('win', 'down')
                self.last_action_time = current_time

