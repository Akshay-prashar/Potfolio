# Gesture Control System Setup

This project is a modular, scalable Python-based gesture control system that translates webcam hand tracking into system commands using MediaPipe and PyAutoGUI.

## Dependencies

To run this project, make sure you have Python installed, and then run the following pip command:

```bash
pip install opencv-python mediapipe pyautogui
```

## Running the System

Simply execute the main loop from this directory:

```bash
python main.py
```

## How It Works

* **Move Cursor:** Raise your index finger only.
* **Click:** Pinch your thumb and index finger together.
* **Drag and Drop:** Pinch and hold, then move your hand.
* **Scroll:** Raise both your index and middle fingers. Move them around to trigger scrolling.
* **Switch Mode:** Raise your index, middle, and ring fingers together. 
  * The system cycles between **SYSTEM**, **CHROME**, and **VLC** modules. 
  * Different modules map gestures to different keyboard shortcuts depending on your active context.

To quit the program, ensure the camera window is in focus and press the `q` key.
