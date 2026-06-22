import cv2
from collections import deque
from src.camera import VideoStream
from src.detector import DefectDetector


class InspectionPipeline:
    """
    Wires up the camera stream and the object detection model, handling
    performance optimizations like resizing and frame skipping.

    For live webcam use a ``stability_frames`` filter is applied: a detection
    must appear in the same location across N consecutive inference frames
    before it is drawn. This eliminates flickering false positives caused by
    non-car content (people, walls, furniture) whose appearance changes frame-
    to-frame, while genuine static car damage is shown consistently.
    """

    def __init__(
        self,
        camera_src=0,
        model_path=None,
        resize_width=640,
        skip_frames=False,
        conf_threshold=0.35,   # higher than image-test mode to suppress false
                               # positives on non-car content in live feeds
        stability_frames=5,    # frames a detection must persist before shown
    ):
        self.stream   = VideoStream(src=camera_src).start()
        self.detector = DefectDetector(
            model_path=model_path,
            conf_threshold=conf_threshold,
        )

        self.resize_width   = resize_width
        self.skip_frames    = skip_frames
        self.frame_count    = 0
        self.last_results   = []
        self.last_frame_shape = None

        # Temporal stability state
        self.stability_frames    = stability_frames
        self.detection_history   = deque(maxlen=stability_frames)

    # ------------------------------------------------------------------
    # Temporal stability filter
    # ------------------------------------------------------------------

    def _iou(self, b1, b2):
        """Intersection-over-Union of two [x1,y1,x2,y2] boxes."""
        ix1 = max(b1[0], b2[0]);  iy1 = max(b1[1], b2[1])
        ix2 = min(b1[2], b2[2]);  iy2 = min(b1[3], b2[3])
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        a1    = max(0, b1[2]-b1[0]) * max(0, b1[3]-b1[1])
        a2    = max(0, b2[2]-b2[0]) * max(0, b2[3]-b2[1])
        union = a1 + a2 - inter
        return (inter / union) if union > 0 else 0.0

    def _overlaps_in_frame(self, det, past_frame, min_iou=0.35):
        """True if ``det`` overlaps a same-class box in ``past_frame``."""
        for d2 in past_frame:
            if d2["cls"] == det["cls"] and self._iou(det["box"], d2["box"]) >= min_iou:
                return True
        return False

    def _stable_detections(self, current):
        """
        Push ``current`` detections into the rolling history and return only
        those that overlapped with a matching detection in every one of the
        previous (stability_frames - 1) frames.

        Behaviour:
        - During the first ``stability_frames`` frames the buffer is still
          filling → return an empty list (no premature boxes).
        - A detection on a moving person disappears or shifts each frame, so
          it never satisfies all history slots → filtered out.
        - A detection on a static car dent stays in the same spot every frame
          → passes all history checks → shown.
        """
        self.detection_history.append(current)

        # Not enough history yet
        if len(self.detection_history) < self.stability_frames:
            return []

        past_frames = list(self.detection_history)[:-1]   # all but current
        stable = [
            det for det in current
            if all(self._overlaps_in_frame(det, pf) for pf in past_frames)
        ]
        return stable

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    def get_processed_frame(self):
        """
        Read a frame, resize, run detection, apply stability filter,
        draw results, and return the annotated frame.
        """
        grabbed, frame = self.stream.read()
        if not grabbed or frame is None:
            return False, None

        # 1. OPTIMIZATION: Frame Resizing (downscale only)
        h, w = frame.shape[:2]
        if w > self.resize_width:
            scale = self.resize_width / float(w)
            frame = cv2.resize(frame, (self.resize_width, int(h * scale)))

        # 2. OPTIMIZATION: Alternate Frame Skipping
        self.frame_count += 1
        if self.skip_frames and self.frame_count % 2 == 0:
            if (
                self.last_frame_shape is not None
                and frame.shape[:2] == self.last_frame_shape
                and self.last_results is not None
            ):
                annotated_frame = self.detector.draw_results(frame, self.last_results)
                return True, annotated_frame

        # 3. RUN INFERENCE
        raw_results = self.detector.detect(frame)

        # 4. TEMPORAL STABILITY FILTER
        #    Only show detections that were present in all recent frames.
        #    This kills false positives on moving non-car content.
        stable_results = self._stable_detections(raw_results)

        self.last_results    = stable_results
        self.last_frame_shape = frame.shape[:2]

        # 5. DRAW BOUNDING BOXES
        annotated_frame = self.detector.draw_results(frame, stable_results)
        if annotated_frame is None:
            return False, None

        return True, annotated_frame

    def stop(self):
        self.stream.stop()
