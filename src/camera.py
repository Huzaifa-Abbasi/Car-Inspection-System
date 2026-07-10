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
    def _open_capture(src, skip_preferred=False):
        """Try to open a VideoCapture with the best available backend.

        On Windows with an integer source, tries DirectShow first (best for
        virtual cameras like OBS / DroidCam), then falls back through MSMF
        and the auto-detected default.  For URL strings the default backend
        is used directly.

        Args:
            src: Camera index (int) or stream URL (str).
            skip_preferred: If True, skip the preferred DSHOW backend and
                go straight to fallback backends.  Used when the preferred
                backend opened but couldn't deliver frames.
        """
        import sys

        if isinstance(src, str):
            # URL / path — use default backend
            cap = cv2.VideoCapture(src)
            return cap if cap.isOpened() else None

        # Integer index — try backends in order on Windows
        if sys.platform.startswith("win"):
            backends = []
            if not skip_preferred:
                backends.append(("DSHOW", cv2.CAP_DSHOW))
            backends.append(("MSMF", cv2.CAP_MSMF))
            backends.append(("ANY", cv2.CAP_ANY))

            for name, backend in backends:
                try:
                    cap = cv2.VideoCapture(src, backend)
                    if cap.isOpened():
                        return cap
                    cap.release()
                except Exception:
                    pass
            return None
        else:
            cap = cv2.VideoCapture(src)
            return cap if cap.isOpened() else None

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

        if not self.stream or not self.stream.isOpened():
            hint = ""
            if isinstance(src, int):
                hint = (
                    f" No physical/virtual camera found at index {src}."
                    " If using DroidCam, enter the IP stream URL instead"
                    " (e.g. http://<phone-ip>:4747/video)."
                    " If using OBS Virtual Camera, make sure the virtual"
                    " camera is started in OBS before scanning."
                )
            raise RuntimeError(f"Could not open video source: {src}.{hint}")

        # Validate with a test read — some backends (e.g. MSMF on Windows)
        # report isOpened()==True but immediately fail every read().
        self.grabbed, self.frame = self.stream.read()
        if not self.grabbed:
            # Camera opened but can't grab frames — try to re-open with
            # a different backend before giving up.
            self.stream.release()
            self.stream = self._open_capture(src, skip_preferred=True)
            if self.stream and self.stream.isOpened():
                self.grabbed, self.frame = self.stream.read()
            if not self.grabbed:
                if self.stream:
                    self.stream.release()
                hint = ""
                if isinstance(src, int):
                    hint = (
                        f" Camera at index {src} opened but produced no"
                        " frames. If using DroidCam, use the IP stream URL"
                        " (e.g. http://<phone-ip>:4747/video) instead of"
                        " a camera index."
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
        max_failures = 100  # ~100 retries before giving up

        while not self.stopped:
            grabbed, frame = self.stream.read()

            # Handle camera disconnect / repeated read failures
            if not grabbed:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    print("[ERROR] Camera feed lost. Stopping capture thread.")
                    with self.lock:
                        # BUG FIX: Keep grabbed and frame in sync — both must
                        # reflect the failure together under the same lock so
                        # read() never returns grabbed=True with frame=None.
                        self.grabbed = False
                        self.frame = None
                    self.stopped = True
                    break
                time.sleep(0.05)  # 50ms sleep to allow camera to recover and avoid hot-spinning
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
            # BUG FIX: Always return grabbed and frame atomically from the same
            # locked snapshot so callers can rely on grabbed==True <=> frame is
            # not None.
            if self.frame is not None:
                return self.grabbed, self.frame.copy()
            return False, None

    def stop(self):
        if self.stream is None or os.getenv("TESTING_MODE") == "true":
            return
        # Signal the background thread to exit
        self.stopped = True
        if self.thread is not None:
            # BUG FIX: Join the thread BEFORE releasing the capture device.
            # Previously stream.release() could be called while update() was
            # still executing self.stream.read(), causing a use-after-free on
            # the VideoCapture object.
            self.thread.join(timeout=2.0)
        self.stream.release()
