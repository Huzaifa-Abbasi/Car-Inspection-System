"""
Detection service — wraps the existing ML pipeline (src/) for web use.

Manages the camera + inference lifecycle for a single inspection session.
"""

import uuid
import base64
from pathlib import Path

import cv2
import numpy as np

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Defect
from src.pipeline import InspectionPipeline


class DetectionService:
    """
    Manages a live detection session.

    Starts the existing InspectionPipeline (camera + YOLO detector + temporal
    stability filter) and provides methods to get annotated frames, extract
    detections, and save defect snapshots.
    """

    def __init__(
        self,
        inspection_id: str,
        camera_src: int | str | None = 0,
        resize_width: int = 640,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.30,
        stability_frames: int = 5,
        require_vehicle: bool = True,
    ):
        self.inspection_id = inspection_id
        self.camera_src = camera_src
        self.resize_width = resize_width
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.stability_frames = stability_frames
        self.require_vehicle = require_vehicle

        self._pipeline: InspectionPipeline | None = None
        self._last_detections: list = []

        # Ensure snapshot directory exists
        self._snapshot_dir = settings.UPLOADS_DIR / inspection_id
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)

        self._defect_counter = 0

    def start(self):
        """Start the camera and detection pipeline."""
        self._pipeline = InspectionPipeline(
            camera_src=self.camera_src,
            resize_width=self.resize_width,
            skip_frames=False,
            conf_threshold=self.conf_threshold,
            stability_frames=self.stability_frames,
            require_vehicle=self.require_vehicle,
        )
        if self._pipeline and self._pipeline.detector:
            self._pipeline.detector.iou_threshold = self.iou_threshold

    def stop(self):
        """Stop the camera and clean up resources."""
        if self._pipeline:
            self._pipeline.stop()
            self._pipeline = None

    def get_frame_and_detections(self) -> tuple:
        """
        Get the latest annotated frame and the current detections.

        Returns:
            (annotated_frame, detections_list) — frame is a numpy array,
            detections is a list of dicts with keys: box, conf, cls
        """
        if not self._pipeline:
            return None, []

        # We need both the annotated frame AND the raw detection results.
        # The pipeline's get_processed_frame() only returns the drawn frame.
        # We'll run detection separately to get both.
        grabbed, frame = self._pipeline.stream.read()
        if not grabbed or frame is None:
            return None, []

        # Resize if needed (same logic as pipeline)
        h, w = frame.shape[:2]
        if w > self.resize_width:
            scale = self.resize_width / float(w)
            frame = cv2.resize(frame, (self.resize_width, int(h * scale)))

        # Vehicle gate — skip if no car visible
        if not self._pipeline.has_vehicle(frame):
            self._pipeline.detection_history.append([])
            self._last_detections = []
            return frame, []

        # Run detection
        raw_results = self._pipeline.detector.detect(frame)
        stable_results = self._pipeline._stable_detections(raw_results)
        self._last_detections = stable_results

        # Draw results on frame
        annotated = self._pipeline.detector.draw_results(frame, stable_results)

        return annotated, stable_results

    def process_frame(self, raw_frame_bytes) -> tuple:
        """
        Decode raw/base64 frame bytes, process them using the ML pipeline,
        and return the annotated frame and list of stable detections.
        """
        if not self._pipeline:
            return None, []

        try:
            if isinstance(raw_frame_bytes, str):
                if "," in raw_frame_bytes:
                    raw_frame_bytes = raw_frame_bytes.split(",")[1]
                raw_frame_bytes = base64.b64decode(raw_frame_bytes)

            nparr = np.frombuffer(raw_frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return None, []
        except Exception as e:
            print(f"[ERROR] Failed to decode frame: {e}")
            return None, []

        # Resize if needed (same logic as pipeline)
        h, w = frame.shape[:2]
        if w > self.resize_width:
            scale = self.resize_width / float(w)
            frame = cv2.resize(frame, (self.resize_width, int(h * scale)))

        # Vehicle gate — skip if no car visible
        if not self._pipeline.has_vehicle(frame):
            self._pipeline.detection_history.append([])
            self._last_detections = []
            return frame, []

        # Run detection
        raw_results = self._pipeline.detector.detect(frame)
        stable_results = self._pipeline._stable_detections(raw_results)
        self._last_detections = stable_results

        # Draw results on frame
        annotated = self._pipeline.detector.draw_results(frame, stable_results)

        return annotated, stable_results

    def save_defect(self, detection: dict, frame) -> str | None:
        """
        Save a defect snapshot to disk and record it in the database.

        Args:
            detection: Detection dict with keys: box, conf, cls
            frame: The full frame (numpy array) at the time of detection

        Returns:
            The defect ID, or None on failure.
        """
        if frame is None:
            return None

        try:
            self._defect_counter += 1
            defect_id = uuid.uuid4().hex

            # Crop the defect area with some padding
            fh, fw = frame.shape[:2]
            x1, y1, x2, y2 = detection["box"]
            pad = 20
            cx1 = max(0, x1 - pad)
            cy1 = max(0, y1 - pad)
            cx2 = min(fw, x2 + pad)
            cy2 = min(fh, y2 + pad)
            crop = frame[cy1:cy2, cx1:cx2]

            # Save snapshot
            filename = f"defect_{self._defect_counter:03d}_{detection['cls']}.jpg"
            snapshot_path = self._snapshot_dir / filename
            cv2.imwrite(str(snapshot_path), crop)

            # Store relative path for portability
            relative_path = f"inspections/{self.inspection_id}/{filename}"

            # Save to database
            db = SessionLocal()
            try:
                # Dynamically classify default severity based on detection confidence
                conf = detection["conf"]
                if conf < 0.55:
                    severity = "minor"
                elif conf < 0.75:
                    severity = "moderate"
                else:
                    severity = "severe"

                defect = Defect(
                    id=defect_id,
                    inspection_id=self.inspection_id,
                    fault_type=detection["cls"],
                    confidence=detection["conf"],
                    severity=severity,
                    status="detected",
                    bbox_x1=x1,
                    bbox_y1=y1,
                    bbox_x2=x2,
                    bbox_y2=y2,
                    snapshot_path=relative_path,
                )
                db.add(defect)
                db.commit()
            finally:
                db.close()

            return defect_id

        except Exception as e:
            print(f"[ERROR] Failed to save defect: {e}")
            return None
