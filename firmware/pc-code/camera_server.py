import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

# Camera Mapping
DEFAULT_MAIN_ID = 2
DEFAULT_LEFT_ID = 0
DEFAULT_RIGHT_ID = 1

WIDTH = 640
HEIGHT = 480
PORT = 8080

# Shared state
frame_lock = threading.Lock()
frames_jpeg = {"main": None, "left": None, "right": None}
fps_stats = {"main": 0.0, "left": 0.0, "right": 0.0}

cloud_lock = threading.Lock()
latest_cloud = {"ok": False, "points": [], "colors": []}


def make_standby_frame(label="CONNECTING..."):
    """Generate dark placeholder frame when a camera is offline."""
    import numpy as np
    img = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    img[:] = (14, 15, 18)
    img[::32, :, :] = (24, 26, 32)
    img[:, ::32, :] = (24, 26, 32)
    cv2.putText(img, label, (80, HEIGHT // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 115, 135), 2)
    _, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    return buf.tobytes()


STANDBY_FRAMES = {
    "main": make_standby_frame("MAIN CAMERA // CONNECTING..."),
    "left": make_standby_frame("LEFT STEREO // CONNECTING..."),
    "right": make_standby_frame("RIGHT STEREO // CONNECTING..."),
}


class ThreadedCamera:
    def __init__(self, name, cam_id, width=WIDTH, height=HEIGHT, fps=30):
        self.name = name
        self.cam_id = cam_id
        self.width = width
        self.height = height
        self.fps = fps
        self.cap = None
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _open(self):
        # 1. DirectShow with MJPG
        cap = cv2.VideoCapture(self.cam_id, cv2.CAP_DSHOW)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"M", "J", "P", "G"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.fps)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ret, _ = cap.read()
            if ret:
                print(f"[+] Camera {self.cam_id} ({self.name}) opened (DSHOW MJPG).", flush=True)
                return cap
            cap.release()

        # 2. DirectShow default format
        cap = cv2.VideoCapture(self.cam_id, cv2.CAP_DSHOW)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ret, _ = cap.read()
            if ret:
                print(f"[+] Camera {self.cam_id} ({self.name}) opened (DSHOW Default).", flush=True)
                return cap
            cap.release()

        # 3. Standard fallback
        cap = cv2.VideoCapture(self.cam_id)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ret, _ = cap.read()
            if ret:
                print(f"[+] Camera {self.cam_id} ({self.name}) opened (Standard).", flush=True)
                return cap
            cap.release()

        return None

    def _worker(self):
        global frames_jpeg, fps_stats

        cap = self._open()
        count = 0
        t0 = time.time()

        while self.running:
            if cap is None or not cap.isOpened():
                time.sleep(2.0)
                cap = self._open()
                continue

            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            _, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            jpeg_bytes = buf.tobytes()

            with frame_lock:
                frames_jpeg[self.name] = jpeg_bytes

            count += 1
            now = time.time()
            if now - t0 >= 1.0:
                fps_stats[self.name] = round(count / (now - t0), 1)
                count = 0
                t0 = now

        if cap:
            cap.release()

class MultiCameraHandler(BaseHTTPRequestHandler):
    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def _stream_mjpeg(self, cam_key):
        self.send_response(200)
        self._send_cors()
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.end_headers()

        try:
            while True:
                with frame_lock:
                    jpeg = frames_jpeg.get(cam_key) or STANDBY_FRAMES.get(cam_key)

                self.wfile.write(b"--frame\r\n")
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(jpeg)))
                self.end_headers()
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
                self.wfile.flush()

                time.sleep(0.033)  # ~30 FPS delivery
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, OSError):
            pass

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        # MJPEG Streams
        if path in ("/stream/main", "/api/stream/main"):
            self._stream_mjpeg("main")
        elif path in ("/stream/secondary", "/api/stream/secondary", "/stream/left", "/api/stream/left"):
            self._stream_mjpeg("left")
        elif path in ("/stream/right", "/api/stream/right"):
            self._stream_mjpeg("right")

        # Single JPEG Snapshots
        elif path in ("/frame/main", "/api/frame/main"):
            self._send_snapshot("main")
        elif path in ("/frame/secondary", "/api/frame/secondary", "/frame/left", "/api/frame/left"):
            self._send_snapshot("left")
        elif path in ("/frame/right", "/api/frame/right"):
            self._send_snapshot("right")

        # Point Cloud Query (Served to Dashboard)
        elif path in ("/pointcloud", "/api/pointcloud"):
            with cloud_lock:
                payload = json.dumps(latest_cloud).encode("utf-8")
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        # Stats API
        elif path in ("/stats", "/api/stats"):
            with frame_lock:
                data = json.dumps({"fps": fps_stats, "active": {k: v is not None for k, v in frames_jpeg.items()}}).encode("utf-8")
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        else:
            self.send_response(404)
            self._send_cors()
            self.end_headers()

    def do_POST(self):
        global latest_cloud
        path = self.path.split("?")[0].rstrip("/")

        # Depth process sends latest pointcloud here
        if path in ("/pointcloud", "/api/pointcloud"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
                with cloud_lock:
                    latest_cloud = data
                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as e:
                self.send_response(400)
                self._send_cors()
                self.end_headers()
                self.wfile.write(f'{{"error":"{str(e)}"}}'.encode("utf-8"))
        else:
            self.send_response(404)
            self._send_cors()
            self.end_headers()

    def _send_snapshot(self, cam_key):
        with frame_lock:
            jpeg = frames_jpeg.get(cam_key) or STANDBY_FRAMES.get(cam_key)
        self.send_response(200)
        self._send_cors()
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(jpeg)))
        self.end_headers()
        self.wfile.write(jpeg)

    def log_message(self, *args):
        pass


def main():
    global DEFAULT_MAIN_ID, DEFAULT_LEFT_ID, DEFAULT_RIGHT_ID, PORT

    parser = argparse.ArgumentParser(description="camera server")
    parser.add_argument("--main", type=int, default=DEFAULT_MAIN_ID, help=f"Main camera index (default: {DEFAULT_MAIN_ID})")
    parser.add_argument("--left", type=int, default=DEFAULT_LEFT_ID, help=f"Left stereo camera index (default: {DEFAULT_LEFT_ID})")
    parser.add_argument("--right", type=int, default=DEFAULT_RIGHT_ID, help=f"Right stereo camera index (default: {DEFAULT_RIGHT_ID})")
    parser.add_argument("-p", "--port", type=int, default=PORT, help=f"Port (default: {PORT})")
    args = parser.parse_args()

    DEFAULT_MAIN_ID = args.main
    DEFAULT_LEFT_ID = args.left
    DEFAULT_RIGHT_ID = args.right
    PORT = args.port

    print("       REVO CAMERA SERVER        ")
    print(f"[*] Main Camera:   Index {DEFAULT_MAIN_ID}")
    print(f"[*] Left Stereo:   Index {DEFAULT_LEFT_ID}")
    print(f"[*] Right Stereo:  Index {DEFAULT_RIGHT_ID}")
    print(f"[*] Listening on:  http://localhost:{PORT}")
    print("...also this listens and hosts pointcloud :)")

    ThreadedCamera("main", DEFAULT_MAIN_ID)
    ThreadedCamera("left", DEFAULT_LEFT_ID)
    ThreadedCamera("right", DEFAULT_RIGHT_ID)

    server = ThreadingHTTPServer(("0.0.0.0", PORT), MultiCameraHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down camera server...")


if __name__ == "__main__":
    main()
