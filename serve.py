#!/usr/bin/env python3
"""
Simple server for the 'You Are Artificial' art installation.

Usage:
  python3 serve.py

Then open http://localhost:8080 in the display browser.
The QR code will encode your local network IP so phones on
the same WiFi can trigger playback on the display.
"""

import http.server
import json
import os
import socket
import threading
import time

PORT = int(os.environ.get("PORT", 8080))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# Shared state: when a phone hits /trigger, this flips to True.
# The display page polls /status to detect it.
trigger_lock = threading.Lock()
triggered = False
trigger_time = 0
COOLDOWN = 10  # ignore duplicate triggers for 10 seconds


def get_local_ip():
    """Get the machine's local network IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        global triggered, trigger_time

        if self.path == "/trigger" or self.path.startswith("/trigger?"):
            # Phone scanned the QR — serve the phone page (video not triggered yet)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            phone_path = os.path.join(DIRECTORY, "phone.html")
            with open(phone_path, "rb") as f:
                self.wfile.write(f.read())
            return

        if self.path == "/start" or self.path.startswith("/start?"):
            # Phone button pressed — now trigger the video on display
            with trigger_lock:
                now = time.time()
                if now - trigger_time >= COOLDOWN:
                    triggered = True
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return

        if self.path == "/status":
            # Display page polls this endpoint
            with trigger_lock:
                was_triggered = triggered
                if triggered:
                    triggered = False  # reset after reading
                    trigger_time = time.time()  # start cooldown NOW
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"play": was_triggered}).encode())
            return

        # Everything else: serve static files normally
        super().do_GET()

    def log_message(self, format, *args):
        # Quieter logging — only show requests, not every poll
        path = args[0].split()[1] if args else ""
        if path != "/status":
            super().log_message(format, *args)


if __name__ == "__main__":
    local_ip = get_local_ip()
    print(f"\n  You Are Artificial — Art Installation Server\n")
    print(f"  Display URL:  http://{local_ip}:{PORT}/qr-video-player.html")
    print(f"  QR will encode: http://{local_ip}:{PORT}/trigger")
    print(f"\n  Open the Display URL in a browser on this machine.")
    print(f"  Make sure the phone is on the same WiFi network.\n")
    print(f"  Press Ctrl+C to stop.\n")

    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.server_close()
