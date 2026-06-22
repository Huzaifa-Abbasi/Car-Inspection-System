import cv2
from src.pipeline import InspectionPipeline


def main():
    print("[INFO] Starting Car Inspection System...")

    pipeline = InspectionPipeline(
        camera_src=0,
        resize_width=640,
        skip_frames=False,
        # Stricter confidence for live use — suppresses false positives on
        # non-car content (people, walls, furniture).
        # Lower to 0.25 only when inspecting an actual car up close.
        conf_threshold=0.35,
        # A detection must appear in the same location for this many
        # consecutive frames before it is drawn.  Eliminates flickering
        # false positives on moving objects (a genuine car dent is static).
        stability_frames=5,
    )

    try:
        while True:
            success, annotated = pipeline.get_processed_frame()
            if not success:
                print("[ERROR] Failed to read from video stream. Exiting...")
                break

            cv2.imshow("Car Inspection", annotated)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

    except KeyboardInterrupt:
        print("[INFO] User interrupted.")
    finally:
        print("[INFO] Cleaning up...")
        pipeline.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
