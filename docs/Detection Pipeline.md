# Detection Pipeline

To achieve high accuracy and eliminate false positives, the system uses a **Two-Stage Cascaded Inference** pipeline.

## Pipeline Stages

### Stage 1: Vehicle Detection Gate
Before running heavy defect detection models, a lightweight pre-trained **YOLOv8n** model inspects the frame:
* Looks for classes: `Car`, `Bus`, or `Truck`.
* If no vehicle is visible, the pipeline immediately returns the clean frame.
* This prevents false positives on background clutter, walls, or human faces.
* Can be dynamically toggled via **Require Vehicle Gate** switch in the [[Architecture|Frontend UI]].

### Stage 2: Fault Detection (Specialist Model)
If a vehicle is present, the cropped region of interest is forwarded to the custom model:
* **Model**: `best.pt` (custom YOLOv8 model, 15 classes).
* **Optimization**: Frames are resized to `640w` for optimal alignment before inference, then bounding boxes are mapped back to high-resolution coordinates.

### Stage 3: Post-Processing & Refinement
* **Shape Analysis**: Uses OpenCV contour geometry to verify and classify faults (e.g. distinguishing a long scratch from a round dent).
* **Stability Filter**: Bounding boxes must persist in the same region across `5` consecutive frames to suppress flickering live artifacts.

## Live Adjustment Parameters
These parameters can be tuned in real-time from the dashboard or modified in **[[Testing Guides]]**:
* **Confidence Threshold**: Bounding box cutoff probability (default: `0.35`).
* **NMS IoU Threshold**: Controls overlap suppression to prevent double-bounding boxes (default: `0.30`).
