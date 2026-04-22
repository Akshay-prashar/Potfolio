# Wireless Camera Streaming App (WebRTC Edition)

A high-performance desktop Python application that operates as a direct WebRTC streaming server. It allows users to stream their smartphone camera directly to the PC over the local network via the phone browser, without needing third-party applications like IP Webcam.

## Features
- **Zero Install on Phone**: Your phone simply navigates to the provided local URL and streams straight from your browser.
- **WebRTC Power**: Engineered with `aiortc` and `aiohttp` for incredible sub-millisecond local network latency. 
- **Modern Desktop UI**: A sleek, dark-themed PyQt5 GUI with live stats tracking, quick full-screen modes, and fluid animations.
- **Background Processing**: Real-time integration bridging background `asyncio` event loops natively into the main `PyQt` environment.

## Setup Instructions

1. **Install Python**: Ensure you have Python 3.10+ installed.
2. **Install Dependencies**:
   Navigate to this directory inside your terminal and run:
   ```bash
   pip install -r requirements.txt
   ```
   *Note: Underneath the hood, `aiortc` utilizes `PyAV`. This will be installed seamlessly.*

3. **Run the App**:
   ```bash
   python main.py
   ```

## Getting Started:

1. Connect your smartphone and your PC to the **same Wi-Fi network**.
2. Open the app and click **🚀 Start Server**.
3. A URL will appear (e.g., `http://192.168.1.15:8080`). Type this exact URL into your phone's internet browser (Chrome/Safari).
4. *(Optional)* Click **📋 Copy Phone Link** and message it to yourself if preferred.
5. On the phone browser webpage, grant Camera permissions, and click **Start Streaming**. The video will seamlessly appear in the desktop app!

## Notes

- Some browsers (especially on iOS) require HTTPS to grant `getUserMedia` access. However, modern desktop Chrome and Safari will commonly allow camera access on `http://` internally if it's over a local IP via a local private network or if you add the IP to insecure origins whitelist. If issues arise, try using Chrome on Android, or map the IP to `localhost` rules.
