import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = PROJECT_ROOT / "best.pt"

# Unique BGR color per fault class (only these faults are drawn)
FAULT_CLASS_COLORS = {
    "front-windscreen-damage": (255, 128, 0),    # blue
    "headlight-damage": (0, 255, 255),           # yellow
    "rear-windscreen-damage": (255, 0, 255),     # magenta
    "runningboard-damage": (0, 165, 255),        # orange
    "sidemirror-damage": (255, 0, 128),          # purple
    "taillight-damage": (0, 255, 128),           # green-cyan
    "bonnet-dent": (0, 0, 255),                  # red
    "boot-dent": (0, 128, 255),                  # orange-red
    "doorouter-dent": (255, 0, 0),               # blue (dark)
    "fender-dent": (128, 0, 255),                # pink
    "front-bumper-dent": (0, 255, 0),            # green
    "quaterpanel-dent": (255, 255, 0),           # cyan
    "rear-bumper-dent": (128, 255, 0),           # spring green
    "roof-dent": (203, 192, 255),                # light pink
}


def _normalize_class_name(name):
    return name.strip().lower().replace("_", "-")


def _format_fault_label(name):
    return name.replace("-", " ").title()


class DefectDetector:
    """
    Dedicated processing pipeline for the YOLO object detection model.
    """
    def __init__(self, model_path=None, conf_threshold=0.45, max_box_area_ratio=0.18):
        if model_path is None:
            model_path = DEFAULT_MODEL_PATH
        else:
            model_path = Path(model_path)
            if not model_path.is_absolute():
                model_path = PROJECT_ROOT / model_path

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self.conf_threshold = conf_threshold
        self.max_box_area_ratio = max_box_area_ratio
        self.min_box_area_ratio = 0.0005
        self.model = YOLO(str(model_path))

        # Only these model classes count as faults
        self.fault_classes = {
            _normalize_class_name(name) for name in self.model.names.values()
        }
        print(f"[INFO] Initialized Defect Detector. Model path: {model_path}")
        print(f"[INFO] Tracking {len(self.fault_classes)} fault types (conf >= {conf_threshold})")

    def _is_fault(self, cls_name):
        return _normalize_class_name(cls_name) in self.fault_classes

    def _get_fault_color(self, cls_name):
        return FAULT_CLASS_COLORS.get(_normalize_class_name(cls_name), (0, 255, 255))

    def _box_area_ratio(self, box, frame_shape):
        x1, y1, x2, y2 = box
        box_area = max(0, x2 - x1) * max(0, y2 - y1)
        frame_area = frame_shape[0] * frame_shape[1]
        return box_area / frame_area if frame_area else 0.0

    def _tighten_box_to_defect(self, frame, box):
        """
        Shrink a coarse YOLO box to the most defect-like region inside it.
        """
        x1, y1, x2, y2 = box
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 - x1 < 8 or y2 - y1 < 8:
            return box

        if self._box_area_ratio(box, frame.shape) <= self.max_box_area_ratio * 0.5:
            return box

        crop = frame[y1:y2, x1:x2]
        ch, cw = crop.shape[:2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        best_score = -1.0
        best_rect = None
        base = max(min(cw, ch) // 5, 32)
        window_sizes = sorted({base, int(base * 1.5), int(base * 2.0)})

        for win in window_sizes:
            if win > min(cw, ch) or win < 20:
                continue
            step = max(win // 3, 8)
            for yy in range(0, ch - win + 1, step):
                for xx in range(0, cw - win + 1, step):
                    patch = gray[yy : yy + win, xx : xx + win]
                    lap_var = cv2.Laplacian(patch, cv2.CV_64F).var()
                    edge_density = cv2.Canny(patch, 50, 150).mean()
                    score = lap_var + edge_density * 12.0
                    if score > best_score:
                        best_score = score
                        best_rect = (xx, yy, xx + win, yy + win)

        if best_rect is None:
            return box

        bx1, by1, bx2, by2 = best_rect
        pad = 6
        tx1 = max(0, x1 + bx1 - pad)
        ty1 = max(0, y1 + by1 - pad)
        tx2 = min(w, x1 + bx2 + pad)
        ty2 = min(h, y1 + by2 + pad)

        orig_area = (x2 - x1) * (y2 - y1)
        new_area = (tx2 - tx1) * (ty2 - ty1)
        if new_area >= orig_area * 0.75:
            return box

        return [tx1, ty1, tx2, ty2]

    def _is_valid_fault_box(self, box, frame_shape):
        ratio = self._box_area_ratio(box, frame_shape)
        return self.min_box_area_ratio <= ratio <= self.max_box_area_ratio

    def detect(self, frame):
        """
        Runs inference and returns only localized fault detections.
        """
        results = self.model(frame, verbose=False, conf=self.conf_threshold)
        bboxes = results[0].boxes

        detections = []
        if bboxes is not None:
            for box in bboxes:
                conf = float(box.conf[0].cpu().numpy())
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                cls_id = int(box.cls[0].cpu().numpy())
                cls_name = self.model.names[cls_id]

                if not self._is_fault(cls_name):
                    continue

                tight_box = self._tighten_box_to_defect(frame, [x1, y1, x2, y2])
                if not self._is_valid_fault_box(tight_box, frame.shape):
                    continue

                detections.append({
                    "box": tight_box,
                    "conf": conf,
                    "cls": cls_name,
                })

        return detections

    def _draw_legend(self, frame, active_faults):
        if not active_faults:
            return frame

        x, y = 10, 24
        line_h = 22
        cv2.rectangle(frame, (5, 5), (280, 5 + line_h * (len(active_faults) + 1)), (0, 0, 0), -1)
        cv2.putText(frame, "Faults detected:", (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        for i, (cls_name, count) in enumerate(sorted(active_faults.items())):
            color = self._get_fault_color(cls_name)
            label = f"{_format_fault_label(cls_name)} ({count})"
            text_y = y + line_h * (i + 1)
            cv2.rectangle(frame, (x, text_y - 14), (x + 14, text_y - 2), color, -1)
            cv2.putText(frame, label, (x + 20, text_y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        return frame

    def draw_results(self, frame, results):
        """
        Draws colored bounding boxes for each fault type.
        """
        annotated = frame.copy()
        active_faults = {}

        for res in results:
            x1, y1, x2, y2 = res["box"]
            conf = res["conf"]
            cls = res["cls"]
            color = self._get_fault_color(cls)
            active_faults[cls] = active_faults.get(cls, 0) + 1

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            label = f"{_format_fault_label(cls)} {conf:.0%}"
            (w, h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            label_top = max(y1 - h - baseline - 4, 0)
            label_bottom = label_top + h + baseline + 4
            cv2.rectangle(annotated, (x1, label_top), (x1 + w, label_bottom), color, -1)
            cv2.putText(
                annotated,
                label,
                (x1, label_bottom - baseline - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                2,
            )

        return self._draw_legend(annotated, active_faults)
