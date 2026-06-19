import cv2
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

        self.grabbed, self.frame = self.stream.read()
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
        while not self.stopped:
            grabbed, frame = self.stream.read()
            # Lock to safely update the frame without race conditions
            with self.lock:
                self.grabbed = grabbed
                self.frame = frame

    def read(self):
        # Return the latest frame
        with self.lock:
            if self.frame is not None:
                return self.grabbed, self.frame.copy()
            return self.grabbed, None

    def stop(self):
        self.stopped = True
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        self.stream.release()
