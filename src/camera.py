import cv2
import time
import threading


class VideoStream:
    """
    Video capture loop that runs on a separate background thread.
    This ensures the main runtime/UI thread is not blocked by I/O operations.
    """

    def __init__(self, src=0):
        self.stream = cv2.VideoCapture(src)
        if not self.stream.isOpened():
            raise RuntimeError(f"Could not open video source: {src}")

        # BUG FIX: Initial read can fail (e.g. camera not ready yet).
        # If it does, initialise frame to None and grabbed to False rather than
        # storing a potentially garbage frame.
        self.grabbed, self.frame = self.stream.read()
        if not self.grabbed:
            self.frame = None

        self.stopped = False
        self.lock = threading.Lock()
        self.thread = None

    def start(self):
        # Start the thread to read frames from the video stream
        self.thread = threading.Thread(
            target=self.update, name="CameraBackgroundThread", daemon=True
        )
        self.thread.start()
        return self

    def update(self):
        # Keep looping indefinitely until the thread is stopped
        consecutive_failures = 0
        max_failures = 30  # ~30 retries before giving up

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
                time.sleep(0.001)
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
        # Signal the background thread to exit
        self.stopped = True
        if self.thread is not None:
            # BUG FIX: Join the thread BEFORE releasing the capture device.
            # Previously stream.release() could be called while update() was
            # still executing self.stream.read(), causing a use-after-free on
            # the VideoCapture object.
            self.thread.join(timeout=2.0)
        self.stream.release()
