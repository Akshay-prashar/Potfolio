import sys
import os
import cv2
import time
import numpy as np
import qrcode
from PIL import Image
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFrame, QGraphicsDropShadowEffect, QApplication, 
                             QSizePolicy, QStackedLayout)
from PyQt5.QtCore import Qt, pyqtSlot, QPropertyAnimation, QPoint, QEasingCurve
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor

from core.webrtc_server import WebRTCServerThread

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wireless Vision - Professional Mode")
        self.resize(1100, 750)
        
        # 🎨 Premium Modern Dark Theme
        self.setStyleSheet("""
            QWidget {
                background-color: #0f172a;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            .url-display {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 15px;
                color: #e2e8f0;
                font-size: 14px;
            }
            QPushButton {
                border-radius: 10px;
                color: white;
                font-size: 14px;
                font-weight: 600;
                padding: 12px 20px;
                border: none;
                background-color: #334155;
            }
            QPushButton:hover {
                background-color: #475569;
            }
            QPushButton#btn_start {
                background-color: #22c55e;
            }
            QPushButton#btn_start:hover {
                background-color: #16a34a;
            }
            QPushButton#btn_stop {
                background-color: #ef4444;
            }
            QPushButton#btn_stop:hover {
                background-color: #dc2626;
            }
            QPushButton#btn_copy {
                background-color: #4f46e5;
            }
            QPushButton#btn_copy:hover {
                background-color: #4338ca;
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #64748b;
            }
            #video_container {
                background-color: #000000;
                border-radius: 12px;
            }
        """)

        self.webrtc_thread = None
        self.server_url = ""
        
        # Performance Tracking
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.current_fps = 0
        
        self.flip_180 = False # Orientation fallback hook
        self.cached_size = None # Layout jitter prevention

        self.setup_ui()

    def add_shadow(self, widget, blur=20, alpha=50):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur)
        shadow.setColor(QColor(0, 0, 0, alpha))
        shadow.setOffset(0, 4)
        widget.setGraphicsEffect(shadow)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # --- Top Hero Bar ---
        top_layout = QHBoxLayout()
        
        title = QLabel("Wireless Vision")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet("color: #ffffff; background: transparent;")
        
        self.lbl_status_icon = QLabel("⚫ Waiting")
        self.lbl_status_icon.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_status_icon.setStyleSheet("color: #94a3b8; background: transparent;")
        
        self.lbl_url = QLabel("Offline")
        self.lbl_url.setProperty("class", "url-display")
        self.lbl_url.setAlignment(Qt.AlignCenter)
        
        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(self.lbl_url)
        top_layout.addSpacing(25)
        top_layout.addWidget(self.lbl_status_icon)
        
        main_layout.addLayout(top_layout)

        # --- Middle Video Container (Dominate Screen) integrating QStackedLayout ---
        self.video_container = QFrame()
        self.video_container.setObjectName("video_container")
        self.video_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.add_shadow(self.video_container)
        
        # STACK LAYOUT: Fixes resize bugs inherently instead of .move()
        self.stacked_layout = QStackedLayout(self.video_container)
        self.stacked_layout.setStackingMode(QStackedLayout.StackAll)
        
        # --- LAYER 0: Video Output ---
        self.lbl_video = QLabel()
        # Strictly ensure QLabel doesn't inherit opaque backgrounds in stack
        self.lbl_video.setStyleSheet("background-color: transparent;") 
        self.lbl_video.setAlignment(Qt.AlignCenter)
        self.lbl_video.setMinimumSize(1, 1) 
        self.stacked_layout.addWidget(self.lbl_video)
        self.lbl_video.hide()

        # --- LAYER 1: Statistics Overlays ---
        self.stats_widget = QWidget()
        # CRITICAL: Transparent background for intermediate layer
        self.stats_widget.setStyleSheet("background-color: transparent;") 
        self.stats_widget.setAttribute(Qt.WA_TransparentForMouseEvents)
        stats_layout = QVBoxLayout(self.stats_widget)
        stats_layout.setContentsMargins(15, 15, 15, 15)
        
        top_stats = QHBoxLayout()
        
        self.overlay_live = QLabel("🔴 LIVE")
        self.overlay_live.setStyleSheet("background-color: rgba(239, 68, 68, 0.9); color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 12px;")
        self.overlay_live.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.overlay_live.hide()
        
        top_stats.addWidget(self.overlay_live, alignment=Qt.AlignTop | Qt.AlignLeft)
        top_stats.addStretch()
        
        right_stats = QVBoxLayout()
        right_stats.setSpacing(10)
        self.overlay_fps = QLabel("FPS: 0")
        self.overlay_fps.setStyleSheet("background-color: rgba(15, 23, 42, 0.7); color: #22c55e; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 12px;")
        self.overlay_fps.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.overlay_fps.hide()
        
        self.overlay_device = QLabel("📱 Device: --")
        self.overlay_device.setStyleSheet("background-color: rgba(15, 23, 42, 0.85); color: #94a3b8; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 12px;")
        self.overlay_device.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.overlay_device.hide()
        
        right_stats.addWidget(self.overlay_fps, alignment=Qt.AlignRight)
        right_stats.addWidget(self.overlay_device, alignment=Qt.AlignRight)
        
        top_stats.addLayout(right_stats)
        stats_layout.addLayout(top_stats)
        stats_layout.addStretch()
        self.stacked_layout.addWidget(self.stats_widget)

        # --- LAYER 2: QR Pairing Central Block ---
        self.qr_widget_layer = QWidget()
        # CRITICAL: Prevent QWidget blanking the entire screen natively
        self.qr_widget_layer.setStyleSheet("background-color: transparent;") 
        qr_outer_layout = QVBoxLayout(self.qr_widget_layer)
        qr_outer_layout.setAlignment(Qt.AlignCenter)
        
        self.qr_frame = QFrame()
        self.qr_frame.setFixedSize(400, 460)
        self.qr_frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 20px;
                border: 2px solid #334155;
            }
            QLabel {
                background-color: transparent;
                border: none;
            }
        """)
        qr_inner = QVBoxLayout(self.qr_frame)
        qr_inner.setContentsMargins(40, 40, 40, 40)
        qr_inner.setSpacing(25)
        qr_inner.setAlignment(Qt.AlignCenter)
        
        self.lbl_qr_title = QLabel("Scan to Connect")
        self.lbl_qr_title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self.lbl_qr_title.setStyleSheet("color: white; background-color: transparent;")
        self.lbl_qr_title.setAlignment(Qt.AlignCenter)
        qr_inner.addWidget(self.lbl_qr_title)
        
        self.lbl_qr_img = QLabel()
        self.lbl_qr_img.setAlignment(Qt.AlignCenter)
        self.lbl_qr_img.setFixedSize(300, 300)
        self.lbl_qr_img.setStyleSheet("background-color: white; border-radius: 8px;")
        qr_inner.addWidget(self.lbl_qr_img)
        
        qr_outer_layout.addWidget(self.qr_frame, alignment=Qt.AlignCenter)
        self.stacked_layout.addWidget(self.qr_widget_layer)

        # Hard-hide the frames until cleanly called
        self.qr_frame.hide()

        main_layout.addWidget(self.video_container, stretch=1)

        # --- Bottom Control Section ---
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(15)

        self.btn_start = QPushButton("Start Server")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.clicked.connect(self.start_server)
        self.add_shadow(self.btn_start)
        
        self.btn_stop = QPushButton("Stop Session")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.clicked.connect(self.stop_server)
        self.btn_stop.setEnabled(False)
        self.add_shadow(self.btn_stop)
        
        self.btn_copy = QPushButton("Copy URL")
        self.btn_copy.setObjectName("btn_copy")
        self.btn_copy.clicked.connect(self.copy_link)
        self.btn_copy.setEnabled(False)
        self.add_shadow(self.btn_copy)
        
        self.btn_flip = QPushButton("🔄 Flip 180°")
        self.btn_flip.clicked.connect(self.toggle_flip)
        self.add_shadow(self.btn_flip)
        
        self.btn_capture = QPushButton("Snapshot")
        self.btn_capture.clicked.connect(self.take_snapshot)
        self.btn_capture.setEnabled(False)
        self.add_shadow(self.btn_capture)
        
        self.btn_full = QPushButton("Fullscreen")
        self.btn_full.clicked.connect(self.toggle_fullscreen)
        self.add_shadow(self.btn_full)

        bottom_layout.addWidget(self.btn_start)
        bottom_layout.addWidget(self.btn_stop)
        bottom_layout.addWidget(self.btn_copy)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_flip)
        bottom_layout.addWidget(self.btn_capture)
        bottom_layout.addWidget(self.btn_full)

        main_layout.addLayout(bottom_layout)
        
        self.current_frame = None
        self.is_fullscreen = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.cached_size = self.video_container.size()
        if self.current_frame is not None:
            self.draw_frame(self.current_frame)

    def update_status(self, msg, is_error=False):
        if is_error or "Failed" in msg:
            self.lbl_status_icon.setText("🔴 Error")
            self.lbl_status_icon.setStyleSheet("color: #ef4444; background: transparent;")
        elif "Waiting for phone" in msg:
            self.lbl_status_icon.setText("🟡 Pairing")
            self.lbl_status_icon.setStyleSheet("color: #eab308; background: transparent;")
        elif "Connected" in msg or "Live" in msg:
            self.lbl_status_icon.setText("🟢 Connected")
            self.lbl_status_icon.setStyleSheet("color: #22c55e; background: transparent;")
            self.overlay_live.show()
            self.overlay_fps.show()
            self.overlay_device.show()
            self.current_frame = None 
        elif "Disconnected" in msg:
            self.lbl_status_icon.setText("🟡 Offline")
            self.lbl_status_icon.setStyleSheet("color: #94a3b8; background: transparent;")
            self.overlay_live.hide()
            self.overlay_fps.hide()
            self.lbl_video.clear()
            self.lbl_video.hide()
            self.current_frame = None
            
            if self.webrtc_thread and self.webrtc_thread.isRunning():
                self.qr_frame.show()
            
    def generate_qr(self, url):
        qr = qrcode.QRCode(version=1, box_size=10, border=3)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        from io import BytesIO
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        
        qim = QImage()
        qim.loadFromData(buffer.getvalue())
        self.lbl_qr_img.setPixmap(QPixmap.fromImage(qim).scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    @pyqtSlot(str)
    def on_server_started(self, url):
        self.server_url = url
        self.lbl_url.setText(f"{url}")
        self.btn_copy.setEnabled(True)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        
        self.generate_qr(url)
        self.qr_frame.show()

    @pyqtSlot(str)
    def on_device_connected(self, device_info):
        self.overlay_device.setText(f"📱 Client: {device_info}")

    def start_server(self):
        self.frame_count = 0
        self.last_fps_time = time.time()
        
        self.webrtc_thread = WebRTCServerThread(port=8080)
        self.webrtc_thread.status_update.connect(self.update_status)
        self.webrtc_thread.server_started.connect(self.on_server_started)
        self.webrtc_thread.device_connected.connect(self.on_device_connected)
        self.webrtc_thread.frame_received.connect(self.update_frame)
        self.webrtc_thread.server_stopped.connect(self.on_server_stopped)
        self.webrtc_thread.start()

    @pyqtSlot()
    def on_server_stopped(self):
        self.lbl_url.setText("Offline")
        self.lbl_status_icon.setText("⚫ Disconnected")
        self.lbl_status_icon.setStyleSheet("color: #94a3b8; background: transparent;")
        self.btn_start.setEnabled(True)
        self.btn_copy.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_capture.setEnabled(False)
        
        self.qr_frame.hide()
        self.overlay_fps.hide()
        self.overlay_device.hide()
        self.overlay_live.hide()
        self.lbl_video.clear()
        self.lbl_video.hide()

    def stop_server(self):
        if self.webrtc_thread and self.webrtc_thread.isRunning():
            self.webrtc_thread.stop()
        self.current_frame = None

    def copy_link(self):
        if self.server_url:
            QApplication.clipboard().setText(self.server_url)
            
    def toggle_flip(self):
        self.flip_180 = not self.flip_180

    @pyqtSlot(np.ndarray)
    def update_frame(self, frame):
        if self.current_frame is None:
            self.qr_frame.hide()
            self.lbl_video.show()
            
        self.current_frame = frame
        self.btn_capture.setEnabled(True)
        
        h, w = frame.shape[:2]
        if h > w:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            
        if self.flip_180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)

        self.frame_count += 1
        curr_time = time.time()
        if curr_time - self.last_fps_time >= 1.0:
            self.current_fps = self.frame_count / (curr_time - self.last_fps_time)
            self.overlay_fps.setText(f"FPS: {int(self.current_fps)}")
            self.frame_count = 0
            self.last_fps_time = curr_time

        self.draw_frame(frame)

    def draw_frame(self, frame):
        target_size = self.cached_size or self.video_container.size()
        tw, th = target_size.width(), target_size.height()
        if tw <= 0 or th <= 0:
            return

        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        
        qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        scaled_img = qt_format.scaled(
            tw, 
            th, 
            Qt.KeepAspectRatioByExpanding, 
            Qt.SmoothTransformation
        )
        
        crop_x = max(0, (scaled_img.width() - tw) // 2)
        crop_y = max(0, (scaled_img.height() - th) // 2)
        final_img = scaled_img.copy(crop_x, crop_y, tw, th)
        
        self.lbl_video.setPixmap(QPixmap.fromImage(final_img))

    def take_snapshot(self):
        if self.current_frame is not None:
            if not os.path.exists("snapshots"):
                os.makedirs("snapshots")
            filename = f"snapshots/snap_{int(time.time())}.jpg"
            cv2.imwrite(filename, self.current_frame)

    def toggle_fullscreen(self):
        if not self.is_fullscreen:
            self.showFullScreen()
            self.btn_full.setText("Windowed Mode")
            self.is_fullscreen = True
        else:
            self.showNormal()
            self.btn_full.setText("Fullscreen")
            self.is_fullscreen = False

    def closeEvent(self, event):
        self.stop_server()
        event.accept()
