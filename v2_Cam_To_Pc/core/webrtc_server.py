import asyncio
import os
import json
import logging
import cv2
import numpy as np
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from PyQt5.QtCore import QThread, pyqtSignal
from utils.helpers import get_local_ip

class WebRTCServerThread(QThread):
    frame_received = pyqtSignal(np.ndarray)
    status_update = pyqtSignal(str, bool) # string message, bool is_error
    server_started = pyqtSignal(str) # Emits the URL
    server_stopped = pyqtSignal()
    device_connected = pyqtSignal(str) # Emits parsed device info
    
    def __init__(self, port=8080):
        super().__init__()
        self.port = port
        self.running = False
        self.loop = None
        self.pcs = set()
        self.site = None
        self.runner = None

    def run(self):
        self.running = True
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        self.status_update.emit("Starting WebRTC Server...", False)
        self.loop.run_until_complete(self.start_server())
        
        if self.running:
            self.loop.run_forever()
            
        self.loop.run_until_complete(self.cleanup())
        self.loop.close()
        self.server_stopped.emit()

    async def start_server(self):
        app = web.Application()
        app.router.add_post('/offer', self.offer)
        
        web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web')
        app.router.add_static('/static/', path=web_dir, name='static')
        app.router.add_get('/', lambda r: web.FileResponse(os.path.join(web_dir, 'index.html')))
        
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        
        local_ip = get_local_ip()
        
        try:
            from utils.helpers import generate_self_signed_cert
            import ssl
            cert_path, key_path = generate_self_signed_cert(local_ip)
            
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain(cert_path, key_path)
            
            self.site = web.TCPSite(self.runner, '0.0.0.0', self.port, ssl_context=ssl_ctx)
        except Exception as e:
            # Fallback
            print(f"HTTPS setup failed: {e}")
            ssl_ctx = None
            self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
            
        try:
            await self.site.start()
            protocol = "https" if ssl_ctx else "http"
            url = f"{protocol}://{local_ip}:{self.port}"
            self.server_started.emit(url)
            self.status_update.emit(f"Server open. Waiting for phone...", False)
        except Exception as e:
            self.status_update.emit(f"Failed to start server: {e}", True)
            self.running = False

    async def offer(self, request):
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        # Smart Device Detection
        user_agent = request.headers.get("X-Device", "Unknown")
        
        device = "Unknown"
        if "iPhone" in user_agent: device = "iPhone"
        elif "Android" in user_agent: device = "Android"
        elif "Macintosh" in user_agent: device = "Mac"
        elif "Windows" in user_agent: device = "Windows PC"
        else: device = "Mobile"
            
        browser = "Browser"
        if "Chrome" in user_agent or "CriOS" in user_agent: browser = "Chrome"
        elif "Safari" in user_agent and "Chrome" not in user_agent: browser = "Safari"
        elif "Firefox" in user_agent or "FxiOS" in user_agent: browser = "Firefox"
            
        self.device_connected.emit(f"{device} ({browser})")

        pc = RTCPeerConnection()
        self.pcs.add(pc)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if pc.connectionState == "failed":
                await pc.close()
                self.pcs.discard(pc)
                self.status_update.emit("Connection Failed.", True)
            elif pc.connectionState == "closed":
                await pc.close()
                self.pcs.discard(pc)
                self.status_update.emit("Phone Disconnected.", False)
            elif pc.connectionState == "connected":
                self.status_update.emit("Connected. Streaming Live!", False)

        @pc.on("track")
        def on_track(track):
            if track.kind == "video":
                self.status_update.emit("Receiving Video Track...", False)
                asyncio.ensure_future(self.process_video_track(track))

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
            ),
        )

    async def process_video_track(self, track):
        while True:
            try:
                frame = await track.recv()
                if not self.running:
                    break
                # to_ndarray(format="bgr24") directly outputs what cv2 uses
                img = frame.to_ndarray(format="bgr24")
                self.frame_received.emit(img)
            except Exception as e:
                # Track ended, connection closed, etc.
                break

    async def cleanup(self):
        coros = [pc.close() for pc in self.pcs]
        if coros:
            await asyncio.gather(*coros, return_exceptions=True)
        self.pcs.clear()
        
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

    def stop(self):
        if not self.running: return
        self.running = False
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.wait()
