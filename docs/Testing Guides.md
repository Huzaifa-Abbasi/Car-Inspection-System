# Testing Guides

We provide several local testing scripts to evaluate the detector under different environments.

## Available Testing Workflows

### 1. Static Image Testing (`test.py`)
Used to run batch validation on static images (`1.jpg`, `2.jpg`, etc.) located in the script directory:
* **Configuration**: Set `TEST_IMAGE_NAME` at the top of the file to inspect a single image, or set to `None` to loop through all images.
* **Sensitivity**: Initialized with `conf_threshold = 0.05` to capture subtle defects.
* **Run**:
  ```powershell
  python path/to/test.py
  ```

### 2. Video Stream Testing (`test_youtube.py`)
Evaluates the model against local video files or live YouTube links:
* **Features**:
  * Adjusts speed dynamically so playback is real-time.
  * Reuses previous detections on alternate frames (skipping inference) if the CPU/GPU lags behind the frame budget.
  * Allows pausing/resuming (`SPACE`) and saving snapshots (`s`).
* **Configuration**: Set `VIDEO_SOURCE = "video.mp4"` or a YouTube URL at the top.
* **Run**:
  ```powershell
  python path/to/test_youtube.py
  ```

### 3. Live Webcam Testing (`app.py` or `main.py`)
* Runs the live camera stream utilizing the full **[[Detection Pipeline]]** stability filter and vehicle gatekeeper.
* **Run App**:
  ```powershell
  python app.py
  ```
* **Run Web App**:
  ```powershell
  python main.py
  ```
