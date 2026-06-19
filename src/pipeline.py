import cv2
from src.camera import VideoStream
from src.detector import DefectDetector

class InspectionPipeline:
    """
    Wires up the camera stream and the object detection model, handling
    performance optimizations like resizing and frame skipping.
    """
    def __init__(self, camera_src=0, model_path=None, resize_width=640, skip_frames=False):
        self.stream = VideoStream(src=camera_src).start()
        self.detector = DefectDetector(model_path=model_path)
        
        self.resize_width = resize_width
        self.skip_frames = skip_frames
        self.frame_count = 0
        self.last_results = []

    def get_processed_frame(self):
        """
        Reads a frame, applies optimizations, runs detection, and returns the annotated frame.
        """
        grabbed, frame = self.stream.read()
        if not grabbed or frame is None:
            return False, None

        # 1. OPTIMIZATION: Frame Resizing
        h, w = frame.shape[:2]
        if w > self.resize_width:
            scale = self.resize_width / float(w)
            frame = cv2.resize(frame, (self.resize_width, int(h * scale)))

        # 2. OPTIMIZATION: Alternate Frame Skipping
        self.frame_count += 1
        if self.skip_frames and self.frame_count % 2 == 0:
            # Skip inference to save GPU/CPU cycles, use results from previous frame
            annotated_frame = self.detector.draw_results(frame, self.last_results)
            return True, annotated_frame

        # 3. RUN INFERENCE & UPDATE LAST RESULTS
        results = self.detector.detect(frame)
        
        # BUG FIX: We previously carried over old results if the new detection was empty. 
        # This caused "ghost" boxes to stick on the screen forever if they were detected even once!
        self.last_results = results
        
        # 4. DRAW BOUNDING BOXES
        annotated_frame = self.detector.draw_results(frame, results)
        
        return True, annotated_frame

    def stop(self):
        self.stream.stop()
