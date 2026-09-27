import cv2
import time
import threading
import os
import numpy as np


class VideoStream:
    """
    Video capture loop that runs on a separate background thread.
    This ensures the main runtime/UI thread is not blocked by I/O operations.
    """

    @staticmethod
    @staticmethod
    def _open_capture(src, skip_preferred=False):
        """Try to open a VideoCapture with the best available backend.

        On Windows with an integer source, tries DirectShow first (best for
        virtual cameras like OBS / DroidCam), then falls back through MSMF
        and the auto-detected default. For URL strings the default backend
        is used directly.
        """
        import sys

        if isinstance(src, str):
            # URL / path — try FFMPEG first, then default
            backends_to_try = []
            if hasattr(cv2, "CAP_FFMPEG"):
                backends_to_try.append(("FFMPEG", cv2.CAP_FFMPEG))
            backends_to_try.append(("ANY", cv2.CAP_ANY))

            for name, backend in backends_to_try:
                try:
                    cap = cv2.VideoCapture(src, backend)
                    if cap.isOpened():
                        try:
                            grabbed, _ = cap.read()
                            if grabbed:
                                print(f"[Camera] Opened URL stream with {name} backend: {src}")
                                return cap
                        except Exception:
                            pass
                        cap.release()
                except Exception:
                    pass

            # Last resort — default backend without flags
            try:
                cap = cv2.VideoCapture(src)
                if cap.isOpened():
                    try:
                        grabbed, _ = cap.read()
                        if grabbed:
                            print(f"[Camera] Opened URL stream with default backend: {src}")
                            return cap
                    except Exception:
                        pass
                    cap.release()
            except Exception:
                pass

            return None

        # Integer index — try backends in order on Windows
        if sys.platform.startswith("win"):
            backends = []
            if not skip_preferred:
                backends.append(("DSHOW", cv2.CAP_DSHOW))
            backends.append(("MSMF", cv2.CAP_MSMF))
            backends.append(("ANY", cv2.CAP_ANY))

            for name, backend in backends:
                for retry in range(2):
                    cap = None
                    try:
                        cap = cv2.VideoCapture(src, backend)
                        if cap and cap.isOpened():
                            # Test frame read to verify device actually delivers frames and is not locked
                            try:
                                grabbed, _ = cap.read()
                                if grabbed:
                                    return cap
                            except Exception:
                                pass
                            cap.release()
                    except Exception:
                        if cap:
                            try:
                                cap.release()
                            except Exception:
                                pass
                    # Wait briefly before retry in case device handle is unlocking
                    time.sleep(0.15)
            return None
        else:
            try:
                cap = cv2.VideoCapture(src)
                if cap.isOpened():
                    grabbed, _ = cap.read()
                    if grabbed:
                        return cap
                if cap:
                    cap.release()
            except Exception:
                pass
            return None

    @staticmethod
    def _find_droidcam_stream():
        """Scan the local network for a DroidCam stream on port 4747.

        Returns the stream URL (e.g. 'http://192.168.1.5:4747/video') if
        found, or None if no DroidCam is discovered.
        """
        import socket as _socket

        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            return None

        if not local_ip or local_ip == "127.0.0.1":
            return None

        subnet = ".".join(local_ip.split(".")[:3])
        print(f"[Camera] Scanning {subnet}.* for DroidCam (port 4747)...")

        for octet in range(1, 255):
            ip = f"{subnet}.{octet}"
            if ip == local_ip:
                continue
            try:
                sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                sock.settimeout(0.10)
                result = sock.connect_ex((ip, 4747))
                sock.close()
                if result == 0:
                    url = f"http://{ip}:4747/video"
                    print(f"[Camera] Found DroidCam at: {url}")
                    return url
            except Exception:
                pass

        print("[Camera] No DroidCam found on the network.")
        return None

    def __init__(self, src=0):
        if src is None:
            self.stream = None
            self.frame = None
            self.grabbed = False
            self.stopped = True
            self.lock = threading.Lock()
            self.thread = None
            return

        if os.getenv("TESTING_MODE") == "true":
            self.stream = None
            self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(self.frame, "Mock Video Feed", (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            self.grabbed = True
            self.stopped = False
            self.lock = threading.Lock()
            self.thread = None
            return

        self.stream = self._open_capture(src)

        # If opening failed or produced no frames:
        # Check if DroidCam is connected as a virtual camera (index 2, 1, 3)
        # or as an IP stream on the network.
        if (not self.stream or not self.stream.isOpened()) and (src != 0):
            print(f"[Camera] Source {src} not available. Checking virtual cameras and DroidCam...")
            # Try alternate indices first (e.g. 2, 1, 3)
            for alt_idx in [2, 1, 3]:
                if alt_idx == src:
                    continue
                alt_cap = self._open_capture(alt_idx)
                if alt_cap and alt_cap.isOpened():
                    self.stream = alt_cap
                    src = alt_idx
                    print(f"[Camera] Connected to alternate camera at index {alt_idx}")
                    break

            # If still not open, try scanning network for DroidCam IP stream
            if not self.stream or not self.stream.isOpened():
                droidcam_url = self._find_droidcam_stream()
                if droidcam_url:
                    self.stream = self._open_capture(droidcam_url)
                    if self.stream and self.stream.isOpened():
                        src = droidcam_url

        if not self.stream or not self.stream.isOpened():
            hint = ""
            if isinstance(src, int):
                hint = (
                    f" No physical/virtual camera found at index {src}."
                    " Possible fixes:"
                    " (1) Close any other app using the camera (Zoom, Teams, Skype)."
                    " (2) Go to Windows Settings > Privacy & Security > Camera"
                    " and enable 'Allow apps to access your camera' AND"
                    " 'Allow desktop apps to access your camera'."
                    " (3) If using DroidCam, make sure DroidCam is running on"
                    " your phone and the DroidCam client is connected on this PC."
                    " (4) Check that your phone and PC are on the same WiFi network."
                )
            elif isinstance(src, str):
                hint = (
                    f" Could not connect to stream URL: {src}."
                    " Possible fixes:"
                    " (1) Make sure DroidCam is running on your phone AND"
                    " the DroidCam client is connected on this PC."
                    " (2) Check that your phone and PC are on the same WiFi network."
                    " (3) Try opening the URL in your browser to verify it works."
                    " (4) Check Windows Firewall — allow AutoScan Pro through."
                )
            raise RuntimeError(f"Could not open video source: {src}.{hint}")

        # Safe initial frame grab
        self.grabbed = False
        self.frame = None
        try:
            self.grabbed, self.frame = self.stream.read()
        except Exception as read_err:
            print(f"[Camera] Initial read error: {read_err}")
            self.grabbed = False
            self.frame = None

        if not self.grabbed:
            # Try alternate backend once before giving up
            try:
                self.stream.release()
            except Exception:
                pass
            self.stream = self._open_capture(src, skip_preferred=True)
            if self.stream and self.stream.isOpened():
                try:
                    self.grabbed, self.frame = self.stream.read()
                except Exception:
                    self.grabbed = False

            # If still no frames and not default webcam (0), try alternate camera indices and DroidCam IP stream
            if not self.grabbed and src != 0:
                if self.stream:
                    try:
                        self.stream.release()
                    except Exception:
                        pass
                    self.stream = None

                print(f"[Camera] Source {src} produced no frames. Trying alternate camera indices (2, 1, 3)...")
                for alt_idx in [2, 1, 3]:
                    if alt_idx == src:
                        continue
                    alt_cap = self._open_capture(alt_idx)
                    if alt_cap and alt_cap.isOpened():
                        try:
                            g, f = alt_cap.read()
                            if g and f is not None:
                                self.stream = alt_cap
                                self.grabbed = True
                                self.frame = f
                                print(f"[Camera] Successfully connected to camera index {alt_idx}")
                                break
                        except Exception:
                            pass
                        try:
                            alt_cap.release()
                        except Exception:
                            pass

                if not self.grabbed:
                    droidcam_url = self._find_droidcam_stream()
                    if droidcam_url:
                        self.stream = self._open_capture(droidcam_url)
                        if self.stream and self.stream.isOpened():
                            try:
                                self.grabbed, self.frame = self.stream.read()
                                if self.grabbed:
                                    print(f"[Camera] Successfully connected to DroidCam: {droidcam_url}")
                            except Exception:
                                self.grabbed = False

            if not self.grabbed:
                if self.stream:
                    try:
                        self.stream.release()
                    except Exception:
                        pass
                hint = ""
                if isinstance(src, int):
                    hint = (
                        f" Camera at index {src} opened but produced no"
                        " frames. Make sure DroidCam is running on your"
                        " phone and the DroidCam client is connected on this PC."
                    )
                raise RuntimeError(
                    f"Video source {src} opened but cannot read frames.{hint}"
                )

        self.stopped = False
        self.lock = threading.Lock()
        self.thread = None

    def start(self):
        if self.stream is None or os.getenv("TESTING_MODE") == "true":
            return self
        # Start the thread to read frames from the video stream
        self.thread = threading.Thread(
            target=self.update, name="CameraBackgroundThread", daemon=True
        )
        self.thread.start()
        return self

    def update(self):
        # Keep looping indefinitely until the thread is stopped
        consecutive_failures = 0
        max_failures = 60  # ~60 retries before giving up

        while not self.stopped:
            grabbed = False
            frame = None
            try:
                if self.stream is not None:
                    grabbed, frame = self.stream.read()
            except Exception as e:
                grabbed = False
                frame = None

            # Handle camera disconnect / repeated read failures
            if not grabbed or frame is None:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    print("[ERROR] Camera feed lost. Stopping capture thread.")
                    with self.lock:
                        self.grabbed = False
                        self.frame = None
                    self.stopped = True
                    break
                time.sleep(0.05)
                continue

            consecutive_failures = 0

            # Lock to safely update the frame without race conditions
            with self.lock:
                self.grabbed = grabbed
                self.frame = frame

            # Yield the GIL to prevent hot-spinning at 100% CPU
            time.sleep(0.001)

    def read(self):
        # Return the latest frame
        with self.lock:
            if self.frame is not None and self.grabbed:
                return True, self.frame.copy()
            return False, None

    def stop(self):
        if self.stream is None or os.getenv("TESTING_MODE") == "true":
            return
        # Signal the background thread to exit
        self.stopped = True
        if self.thread is not None:
            try:
                self.thread.join(timeout=1.5)
            except Exception:
                pass
        try:
            if self.stream is not None:
                self.stream.release()
        except Exception:
            pass
