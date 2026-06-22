import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = PROJECT_ROOT / "best.pt"

# Unique BGR color per fault class
FAULT_CLASS_COLORS = {
    "front-windscreen-damage": (255, 128, 0),
    "headlight-damage":        (0, 255, 255),
    "rear-windscreen-damage":  (255, 0, 255),
    "runningboard-damage":     (0, 165, 255),
    "sidemirror-damage":       (255, 0, 128),
    "taillight-damage":        (0, 255, 128),
    "bonnet-dent":             (0, 0, 255),
    "boot-dent":               (0, 128, 255),
    "doorouter-dent":          (255, 0, 0),
    "fender-dent":             (128, 0, 255),
    "front-bumper-dent":       (0, 255, 0),
    "quaterpanel-dent":        (255, 255, 0),
    "rear-bumper-dent":        (128, 255, 0),
    "roof-dent":               (203, 192, 255),
    # Post-processing override — not a model class, assigned by shape analysis
    "scratch":                 (30, 200, 255),   # vivid amber
}

LEGEND_ENTRY_H   = 22
LEGEND_PADDING_V = 6
LEGEND_PADDING_L = 10
LEGEND_WIDTH     = 285


def _normalize_class_name(name):
    return name.strip().lower().replace("_", "-")


def _format_fault_label(name):
    return name.replace("-", " ").title()


def _clamp_box(box, fw, fh):
    """Clamp box to frame bounds and guarantee x2>x1, y2>y1."""
    x1, y1, x2, y2 = box
    x1 = max(0, min(int(x1), fw - 1))
    y1 = max(0, min(int(y1), fh - 1))
    x2 = max(x1 + 1, min(int(x2), fw))
    y2 = max(y1 + 1, min(int(y2), fh))
    return [x1, y1, x2, y2]


class DefectDetector:
    def __init__(
        self,
        model_path=None,
        conf_threshold=0.20,   # lowered from 0.25 to catch more faults
        iou_threshold=0.50,    # our post-process NMS threshold
        device=None,
    ):
        if model_path is None:
            model_path = DEFAULT_MODEL_PATH
        else:
            model_path = Path(model_path)
            if not model_path.is_absolute():
                model_path = PROJECT_ROOT / model_path

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self.conf_threshold = conf_threshold
        self.iou_threshold  = iou_threshold
        self.device         = device
        self.model          = YOLO(str(model_path))

        self.fault_classes = {
            _normalize_class_name(n) for n in self.model.names.values()
        }
        print(f"[INFO] Initialized Defect Detector. Model: {model_path.name}")
        print(f"[INFO] Tracking {len(self.fault_classes)} fault types")
        print(f"[INFO] Conf threshold: {conf_threshold}  |  NMS IoU: {iou_threshold}")
        print(f"[INFO] Inference device: {self.device or 'auto'}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_fault(self, cls_name):
        return _normalize_class_name(cls_name) in self.fault_classes

    def _get_fault_color(self, cls_name):
        return FAULT_CLASS_COLORS.get(_normalize_class_name(cls_name), (0, 255, 255))

    # ------------------------------------------------------------------
    # Defect-region isolation (tightening + splitting)
    # ------------------------------------------------------------------

    def _compute_defect_mask(self, crop):
        """
        Return a binary mask highlighting defect-like pixels in ``crop``.

        Two complementary signals are combined:

        1. **LAB color deviation** — car panels have a fairly uniform paint
           color. Dents show up as local shadow bands (darker L channel) or
           exposed primer (hue shift). We estimate the panel background color
           from the border pixels of the crop (outer ring), then flag pixels
           that differ significantly from that colour in LAB space.

        2. **Edge density** — scratches, cracks and sharp dent creases produce
           concentrated edge responses. Dilating those edges fills the defect
           region without requiring an exact colour model.

        IMPORTANT — kernel sizes are deliberately capped at small absolute
        pixel values regardless of crop size. Using proportional kernels on
        large crops (e.g. a 400x300 YOLO box) produced dilation/close kernels
        of 30-40 px, which merged multiple nearby dents into one blob and
        prevented the contour-based splitting from finding separate defects.
        Small fixed kernels keep individual dent regions distinct.
        """
        h, w = crop.shape[:2]

        # Border width: small enough never to include the defect itself.
        # Cap at 15 px so large crops don't accidentally sample dent pixels.
        b = min(max(2, min(w, h) // 12), 15)

        # --- Signal 1: LAB deviation from panel background colour ---
        lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).astype(np.float32)

        border_pixels = np.vstack([
            lab[:b,  :].reshape(-1, 3),
            lab[-b:, :].reshape(-1, 3),
            lab[:,  :b].reshape(-1, 3),
            lab[:, -b:].reshape(-1, 3),
        ])
        bg = np.median(border_pixels, axis=0)   # representative panel colour

        dist = np.sqrt(np.sum((lab - bg) ** 2, axis=2))   # per-pixel ΔE-like
        thr_lab = max(np.std(dist) * 0.9, 8.0)
        mask_lab = (dist > thr_lab).astype(np.uint8) * 255

        # --- Signal 2: Edge density (scratches / sharp shadow lines) ---
        gray    = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges   = cv2.Canny(blurred, 25, 75)

        # Cap at 9 px — keeps separate dents as distinct edge clusters.
        # A 34 px kernel (old proportional sizing) would bridge dents that are
        # inches apart on the car and collapse them into one contour.
        k_e = 9
        kern_e    = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_e, k_e))
        mask_edge = cv2.dilate(edges, kern_e)

        # --- Combine ---
        combined = cv2.bitwise_or(mask_lab, mask_edge)

        # Close: fill small internal gaps within ONE dent region (cap 11 px)
        k_c    = 11
        kern_c = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_c, k_c))
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kern_c)

        # Open: remove isolated speckle noise (cap 5 px)
        k_o    = 5
        kern_o = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_o, k_o))
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kern_o)

        return combined

    def _classify_contour_shape(self, contour):
        """
        Use the minimum-area bounding rectangle of a contour to decide whether
        it represents a scratch (long, thin, linear) or a dent (compact blob).

        Decision criteria (BOTH must be true for scratch):
          1. Aspect ratio >= 4.0  — the shape is at least 4× longer than wide.
          2. Short side  <  25 px — the feature is genuinely narrow/thin.

        Using minAreaRect (vs boundingRect) handles diagonal scratches correctly
        because it finds the smallest rectangle at any rotation angle.

        Returns "scratch" if criteria are met, otherwise None (keep YOLO class).
        """
        area = cv2.contourArea(contour)
        if area < 20:
            return None

        _, (rw, rh), _ = cv2.minAreaRect(contour)
        long_side  = max(rw, rh)
        short_side = max(min(rw, rh), 1.0)
        aspect     = long_side / short_side

        if aspect >= 4.0 and short_side < 25:
            return "scratch"
        return None

    def _refine_detection(self, frame, detection):
        """
        Analyse the defect mask inside a single YOLO detection and return
        one or more refined detections:

        - If the mask contains **one significant region** → one tighter box.
        - If the mask contains **multiple distinct regions** → one separate
          box per region, so each sub-defect gets its own annotation.
        - Falls back to the original YOLO box if the mask yields no useful
          contours or the tight box would not be meaningfully smaller.
        """
        fh, fw = frame.shape[:2]
        x1, y1, x2, y2 = _clamp_box(detection["box"], fw, fh)
        box_w, box_h = x2 - x1, y2 - y1

        # Too small to refine reliably
        if box_w < 24 or box_h < 24:
            return [detection]

        crop = frame[y1:y2, x1:x2]
        mask = self._compute_defect_mask(crop)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return [detection]

        # Keep contours that are at least 0.3% of the crop area (was 2% —
        # too aggressive for small dents inside a large YOLO box).
        min_area = max((box_w * box_h) * 0.003, 12)
        valid = [c for c in contours if cv2.contourArea(c) >= min_area]
        if not valid:
            return [detection]

        pad = 8
        results = []
        for c in valid:
            cx1, cy1, cw, ch = cv2.boundingRect(c)
            tx1 = max(0, x1 + cx1 - pad)
            ty1 = max(0, y1 + cy1 - pad)
            tx2 = min(fw, x1 + cx1 + cw + pad)
            ty2 = min(fh, y1 + cy1 + ch + pad)

            if tx2 <= tx1 or ty2 <= ty1:
                continue

            # Shape-based reclassification:
            # The YOLO model has no "scratch" class so it labels all surface
            # damage as a dent variant. We override the class here based on
            # contour geometry: a scratch is long + thin (high aspect ratio
            # with a narrow short side); a dent is compact (low aspect ratio).
            shape_cls    = self._classify_contour_shape(c)
            effective_cls = shape_cls if shape_cls else detection["cls"]

            results.append({
                "box":  [tx1, ty1, tx2, ty2],
                "conf": detection["conf"],
                "cls":  effective_cls,
            })

        if not results:
            return [detection]

        # If there is only ONE tight box and it is barely smaller than the
        # original YOLO box, the refinement adds no value — keep the YOLO box.
        if len(results) == 1:
            tb = results[0]["box"]
            new_area = (tb[2] - tb[0]) * (tb[3] - tb[1])
            if new_area >= box_w * box_h * 0.85:
                return [detection]

        return results

    # ------------------------------------------------------------------
    # NMS
    # ------------------------------------------------------------------

    def _nms(self, detections, iou_threshold):
        """Remove duplicate boxes whose IoU exceeds ``iou_threshold``."""
        if not detections:
            return detections

        detections = sorted(detections, key=lambda d: d["conf"], reverse=True)
        keep = []

        for det in detections:
            b1 = det["box"]
            suppressed = False
            for kept in keep:
                b2 = kept["box"]
                ix1 = max(b1[0], b2[0]);  iy1 = max(b1[1], b2[1])
                ix2 = min(b1[2], b2[2]);  iy2 = min(b1[3], b2[3])
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                a1 = max(0, b1[2]-b1[0]) * max(0, b1[3]-b1[1])
                a2 = max(0, b2[2]-b2[0]) * max(0, b2[3]-b2[1])
                union = a1 + a2 - inter
                if union > 0 and (inter / union) > iou_threshold:
                    suppressed = True
                    break
            if not suppressed:
                keep.append(det)

        return keep

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, frame):
        """
        Run inference and return a list of refined fault detections.

        Each detection: { "box": [x1,y1,x2,y2], "conf": float, "cls": str }

        Pipeline:
          1. YOLO inference (with tuned internal NMS iou=0.45)
          2. Per-detection refinement → tighter / split boxes
          3. Our own NMS on the expanded set
        """
        if frame is None:
            return []

        fh, fw = frame.shape[:2]

        infer_kwargs = dict(verbose=False, conf=self.conf_threshold, iou=0.45)
        if self.device is not None:
            infer_kwargs["device"] = self.device

        raw    = self.model(frame, **infer_kwargs)
        bboxes = raw[0].boxes

        raw_detections = []
        if bboxes is not None:
            for box in bboxes:
                conf     = float(box.conf[0].cpu().numpy())
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                cls_id   = int(box.cls[0].cpu().numpy())
                cls_name = self.model.names[cls_id]

                if not self._is_fault(cls_name):
                    continue

                clamped = _clamp_box([x1, y1, x2, y2], fw, fh)
                raw_detections.append({
                    "box":  clamped,
                    "conf": conf,
                    "cls":  cls_name,
                })

        # Refine each YOLO detection (tighten + optionally split)
        refined = []
        for det in raw_detections:
            refined.extend(self._refine_detection(frame, det))

        # Final NMS on the potentially-expanded set
        return self._nms(refined, self.iou_threshold)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_legend(self, frame, active_faults):
        if not active_faults:
            return frame

        num_entries   = len(active_faults)
        header_y      = LEGEND_PADDING_V + LEGEND_ENTRY_H
        legend_bottom = header_y + LEGEND_ENTRY_H * num_entries + LEGEND_PADDING_V
        legend_bottom = min(legend_bottom, frame.shape[0] - 1)

        overlay = frame.copy()
        cv2.rectangle(overlay,
                      (LEGEND_PADDING_V, LEGEND_PADDING_V),
                      (LEGEND_WIDTH, legend_bottom),
                      (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)

        cv2.putText(frame, "Faults detected:",
                    (LEGEND_PADDING_L, header_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 1, cv2.LINE_AA)

        for i, (cls_name, count) in enumerate(sorted(active_faults.items())):
            color  = self._get_fault_color(cls_name)
            label  = f"{_format_fault_label(cls_name)} ({count})"
            text_y = header_y + LEGEND_ENTRY_H * (i + 1)
            if text_y > frame.shape[0] - 4:
                break
            cv2.rectangle(frame,
                          (LEGEND_PADDING_L,      text_y - 14),
                          (LEGEND_PADDING_L + 14, text_y - 2),
                          color, -1)
            cv2.putText(frame, label,
                        (LEGEND_PADDING_L + 20, text_y - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        return frame

    def draw_results(self, frame, results):
        """Draw a tight, labeled bounding box for every detection."""
        if frame is None:
            return None

        annotated     = frame.copy()
        active_faults = {}

        for res in results:
            x1, y1, x2, y2 = res["box"]
            conf  = res["conf"]
            cls   = res["cls"]
            color = self._get_fault_color(cls)
            active_faults[cls] = active_faults.get(cls, 0) + 1

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

            label = f"{_format_fault_label(cls)} {conf:.0%}"
            (tw, th), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
            )
            label_top    = max(y1 - th - baseline - 4, 0)
            label_bottom = label_top + th + baseline + 4

            cv2.rectangle(annotated,
                          (x1, label_top), (x1 + tw, label_bottom),
                          color, -1)
            cv2.putText(annotated, label,
                        (x1, label_bottom - baseline - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 0, 0), 2, cv2.LINE_AA)

        return self._draw_legend(annotated, active_faults)