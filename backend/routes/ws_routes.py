"""
WebSocket route for live video streaming during car inspection.

Streams annotated frames from the ML pipeline as base64-encoded JPEG to the
browser. Also emits detection events and accepts control commands.
"""

import asyncio
import base64
import json
import time

import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import Inspection, Defect
from backend.services.detection_service import DetectionService

router = APIRouter()

def normalize_camera_source(src_raw: str) -> int | str:
    import re
    src_raw = src_raw.strip()
    if src_raw.isdigit():
        return int(src_raw)

    if src_raw.lower().startswith(("http://", "https://", "rtsp://", "rtmp://")):
        from urllib.parse import urlparse
        try:
            parsed = urlparse(src_raw)
            if parsed.path and parsed.path != "/":
                return src_raw
        except Exception:
            pass

    # Match IP address or localhost, optional port, optional trailing path
    ip_match = re.match(
        r'^(?:https?://)?(localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::(\d+))?(?:/.*)?$',
        src_raw,
        re.IGNORECASE
    )
    if ip_match:
        host = ip_match.group(1)
        port = ip_match.group(2)
        port_str = f":{port}" if port else ":4747"
        path_str = "/video"
        if "/" in src_raw:
            parts = src_raw.split("/", 3)
            for part in parts:
                if part and not part.startswith("http") and not re.match(r'^(localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::\d+)?$', part):
                    path_str = "/" + part
                    break
        return f"http://{host}{port_str}{path_str}"

    return src_raw


@router.get("/api/cameras/detect")
def detect_cameras():
    """Scan for available camera devices and DroidCam IP streams.

    Results are cached for 30 seconds to avoid spamming OpenCV backends
    with repeated probe attempts on every page navigation.

    Returns:
        {"cameras": [int, ...], "streams": [{"label": ..., "url": ...}, ...]}
    """
    import sys

    now = time.time()
    if _camera_cache["result"] and (now - _camera_cache["timestamp"]) < _CAMERA_CACHE_TTL:
        return _camera_cache["result"]

    available_indices = []
    discovered_streams = []

    # Find all camera sources currently in use by active sessions to avoid hardware conflicts
    active_sources = set()
    for svc in _active_sessions.values():
        if svc.camera_src is not None:
            active_sources.add(svc.camera_src)

    # --- Probe local camera indices (only 0-2 to reduce spam) ---
    for index in range(3):
        if index in active_sources:
            available_indices.append(index)
            continue

        cap = None
        try:
            if sys.platform.startswith("win"):
                backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF]
            else:
                backends = [cv2.CAP_ANY]

            for backend in backends:
                try:
                    cap = cv2.VideoCapture(index, backend)
                    if cap.isOpened():
                        grabbed, _ = cap.read()
                        cap.release()
                        cap = None
                        if grabbed:
                            available_indices.append(index)
                            break
                    else:
                        cap.release()
                        cap = None
                except Exception:
                    if cap:
                        cap.release()
                        cap = None
        except Exception:
            pass
        finally:
            if cap:
                try:
                    cap.release()
                except Exception:
                    pass

    # --- Auto-discover DroidCam streams on the local network in parallel ---
    try:
        import concurrent.futures
        local_ip = _get_local_ip()
        if local_ip and local_ip != "127.0.0.1":
            subnet_prefix = ".".join(local_ip.split(".")[:3])
            
            # Scan 1 to 100 in parallel to cover the user's DroidCam (on .62) and other local devices quickly
            targets = list(range(1, 101))
            
            def check_ip(octet):
                probe_ip = f"{subnet_prefix}.{octet}"
                if probe_ip == local_ip:
                    return None
                if _probe_droidcam(probe_ip, 4747):
                    return {
                        "label": f"DroidCam ({probe_ip})",
                        "url": f"http://{probe_ip}:4747/video",
                    }
                return None

            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                results = executor.map(check_ip, targets)
                for res in results:
                    if res:
                        discovered_streams.append(res)
    except Exception:
        pass

    result = {"cameras": available_indices, "streams": discovered_streams}
    _camera_cache["result"] = result
    _camera_cache["timestamp"] = now
    return result


# Cache for camera detection results to avoid repeated slow probing
_camera_cache: dict = {"result": None, "timestamp": 0.0}
_CAMERA_CACHE_TTL = 30.0  # seconds


def _get_local_ip() -> str:
    """Get the local IP address of the machine."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _get_droidcam_probe_targets() -> list[int]:
    """Return last-octet values to probe for DroidCam."""
    targets = list(range(1, 20))
    targets.extend(range(100, 115))
    targets.extend(range(50, 55))
    return targets


def _probe_droidcam(ip: str, port: int, timeout: float = 0.3) -> bool:
    """Quick TCP connect probe to check if DroidCam is listening."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((ip, port))
        s.close()
        return result == 0
    except Exception:
        return False


# Track active inspection sessions so only one camera runs at a time
_active_sessions: dict[str, DetectionService] = {}


@router.websocket("/ws/inspect/{inspection_id}")
async def websocket_inspection(websocket: WebSocket, inspection_id: str):
    """
    Real-time inspection WebSocket.

    Server → Client messages:
        {"type": "frame", "data": "<base64 JPEG>", "timestamp": ...}
        {"type": "detections", "defects": [...]}
        {"type": "defect_saved", "defect_id": "...", "fault_type": "..."}
        {"type": "status", "message": "..."}
        {"type": "error", "message": "..."}

    Client → Server commands:
        {"command": "pause"}
        {"command": "resume"}
        {"command": "end_scan"}
    """
    await websocket.accept()

    # Parse parameters from query string
    require_vehicle_param = websocket.query_params.get("require_vehicle", "true").lower() == "true"
    conf_threshold_param = float(websocket.query_params.get("conf_threshold", "0.35"))
    iou_threshold_param = float(websocket.query_params.get("iou_threshold", "0.30"))
    use_client_camera = websocket.query_params.get("use_client_camera", "false").lower() == "true"
    camera_src_raw = websocket.query_params.get("camera_src", "0")

    # Parse camera_src: if use_client_camera, it is None.
    # Otherwise, normalize it.
    if use_client_camera:
        camera_src = None
    else:
        if not camera_src_raw or camera_src_raw.strip() == "":
            camera_src = 0
        else:
            camera_src = normalize_camera_source(camera_src_raw)

    # Validate inspection exists
    db: Session = SessionLocal()
    try:
        inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
        if not inspection:
            await websocket.send_json({"type": "error", "message": "Inspection not found"})
            await websocket.close()
            return
    finally:
        db.close()

    # Start the detection service
    detection_svc = None
    try:
        detection_svc = DetectionService(
            inspection_id=inspection_id,
            camera_src=camera_src,
            require_vehicle=require_vehicle_param,
            conf_threshold=conf_threshold_param,
            iou_threshold=iou_threshold_param,
        )
        try:
            detection_svc.start()
        except RuntimeError as cam_err:
            print(f"[ERROR] Camera failed to start: {cam_err}")
            await websocket.send_json({
                "type": "error",
                "message": str(cam_err),
            })
            await websocket.close()
            return
        _active_sessions[inspection_id] = detection_svc

        await websocket.send_json({"type": "status", "message": "Camera started. Scanning..."})

        paused = False
        # Track which defect boxes we've already saved (by approximate position hash)
        saved_defect_hashes: set[str] = set()

        if use_client_camera:
            while True:
                # Block waiting for frame or command messages from client
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                cmd = msg.get("command", "")

                if cmd:
                    if cmd == "pause":
                        paused = True
                        await websocket.send_json({"type": "status", "message": "Paused"})
                        continue
                    elif cmd == "resume":
                        paused = False
                        await websocket.send_json({"type": "status", "message": "Resumed scanning..."})
                        continue
                    elif cmd == "set_require_vehicle":
                        val = msg.get("value", True)
                        detection_svc.require_vehicle = val
                        if detection_svc._pipeline:
                            detection_svc._pipeline.require_vehicle = val
                            if val and detection_svc._pipeline._vehicle_gate is None:
                                print("[INFO] Enabling vehicle detection gate (yolov8n) dynamically...")
                                from ultralytics import YOLO
                                detection_svc._pipeline._vehicle_gate = YOLO("yolov8n.pt")
                                detection_svc._pipeline._vehicle_conf = 0.30
                                detection_svc._pipeline._vehicle_cache = False
                                detection_svc._pipeline._vehicle_check_interval = 3
                                detection_svc._pipeline._vehicle_frame_counter  = 0
                            elif not val:
                                print("[INFO] Disabling vehicle detection gate dynamically...")
                                detection_svc._pipeline._vehicle_gate = None
                        await websocket.send_json({"type": "status", "message": f"Vehicle gate: {'ON' if val else 'OFF'}"})
                        continue
                    elif cmd == "set_conf_threshold":
                        val = float(msg.get("value", 0.35))
                        detection_svc.conf_threshold = val
                        if detection_svc._pipeline and detection_svc._pipeline.detector:
                            detection_svc._pipeline.detector.conf_threshold = val
                        await websocket.send_json({"type": "status", "message": f"Conf threshold: {val}"})
                        continue
                    elif cmd == "set_iou_threshold":
                        val = float(msg.get("value", 0.30))
                        detection_svc.iou_threshold = val
                        if detection_svc._pipeline and detection_svc._pipeline.detector:
                            detection_svc._pipeline.detector.iou_threshold = val
                        await websocket.send_json({"type": "status", "message": f"IoU threshold: {val}"})
                        continue
                    elif cmd == "end_scan":
                        await websocket.send_json({"type": "status", "message": "Scan ended"})
                        break

                if msg.get("type") == "frame":
                    if paused:
                        continue

                    raw_frame_data = msg.get("data", "")
                    if not raw_frame_data:
                        continue

                    frame, detections = await asyncio.to_thread(
                        detection_svc.process_frame, raw_frame_data
                    )

                    if frame is None:
                        continue

                    # Encode frame as JPEG → base64
                    _, jpeg_buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    b64_frame = base64.b64encode(jpeg_buffer).decode("utf-8")

                    # Send frame
                    await websocket.send_json({
                        "type": "frame",
                        "data": b64_frame,
                        "timestamp": time.time(),
                    })

                    # Send detections list
                    if detections:
                        defect_list = []
                        for det in detections:
                            defect_list.append({
                                "fault_type": det["cls"],
                                "confidence": round(det["conf"], 2),
                                "bbox": det["box"],
                            })
                        await websocket.send_json({
                            "type": "detections",
                            "defects": defect_list,
                        })

                        # Auto-save new defects (deduplicate by position hash)
                        for det in detections:
                            box = det["box"]
                            det_hash = f"{det['cls']}_{box[0]//20}_{box[1]//20}_{box[2]//20}_{box[3]//20}"
                            if det_hash not in saved_defect_hashes:
                                saved_defect_hashes.add(det_hash)
                                defect_id = detection_svc.save_defect(det, frame)
                                if defect_id:
                                    await websocket.send_json({
                                        "type": "defect_saved",
                                        "defect_id": defect_id,
                                        "fault_type": det["cls"],
                                        "confidence": round(det["conf"], 2),
                                    })
        else:
            while True:
                # Check for incoming commands (non-blocking)
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                    msg = json.loads(raw)
                    cmd = msg.get("command", "")

                    if cmd == "pause":
                        paused = True
                        await websocket.send_json({"type": "status", "message": "Paused"})
                        continue
                    elif cmd == "resume":
                        paused = False
                        await websocket.send_json({"type": "status", "message": "Resumed scanning..."})
                        continue
                    elif cmd == "set_require_vehicle":
                        val = msg.get("value", True)
                        detection_svc.require_vehicle = val
                        if detection_svc._pipeline:
                            detection_svc._pipeline.require_vehicle = val
                            if val and detection_svc._pipeline._vehicle_gate is None:
                                print("[INFO] Enabling vehicle detection gate (yolov8n) dynamically...")
                                from ultralytics import YOLO
                                detection_svc._pipeline._vehicle_gate = YOLO("yolov8n.pt")
                                detection_svc._pipeline._vehicle_conf = 0.30
                                detection_svc._pipeline._vehicle_cache = False
                                detection_svc._pipeline._vehicle_check_interval = 3
                                detection_svc._pipeline._vehicle_frame_counter  = 0
                            elif not val:
                                print("[INFO] Disabling vehicle detection gate dynamically...")
                                detection_svc._pipeline._vehicle_gate = None
                        await websocket.send_json({"type": "status", "message": f"Vehicle gate: {'ON' if val else 'OFF'}"})
                        continue
                    elif cmd == "set_conf_threshold":
                        val = float(msg.get("value", 0.35))
                        detection_svc.conf_threshold = val
                        if detection_svc._pipeline and detection_svc._pipeline.detector:
                            detection_svc._pipeline.detector.conf_threshold = val
                        await websocket.send_json({"type": "status", "message": f"Conf threshold: {val}"})
                        continue
                    elif cmd == "set_iou_threshold":
                        val = float(msg.get("value", 0.30))
                        detection_svc.iou_threshold = val
                        if detection_svc._pipeline and detection_svc._pipeline.detector:
                            detection_svc._pipeline.detector.iou_threshold = val
                        await websocket.send_json({"type": "status", "message": f"IoU threshold: {val}"})
                        continue
                    elif cmd == "end_scan":
                        await websocket.send_json({"type": "status", "message": "Scan ended"})
                        break

                except asyncio.TimeoutError:
                    pass  # No command received — continue streaming

                if paused:
                    await asyncio.sleep(0.05)
                    continue

                # Get the latest annotated frame + detections
                frame, detections = await asyncio.to_thread(
                    detection_svc.get_frame_and_detections
                )

                if frame is None:
                    await asyncio.sleep(0.03)
                    continue

                # Encode frame as JPEG → base64
                _, jpeg_buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                b64_frame = base64.b64encode(jpeg_buffer).decode("utf-8")

                # Send frame
                await websocket.send_json({
                    "type": "frame",
                    "data": b64_frame,
                    "timestamp": time.time(),
                })

                # Send detections list
                if detections:
                    defect_list = []
                    for det in detections:
                        defect_list.append({
                            "fault_type": det["cls"],
                            "confidence": round(det["conf"], 2),
                            "bbox": det["box"],
                        })
                    await websocket.send_json({
                        "type": "detections",
                        "defects": defect_list,
                    })

                    # Auto-save new defects (deduplicate by position hash)
                    for det in detections:
                        box = det["box"]
                        det_hash = f"{det['cls']}_{box[0]//20}_{box[1]//20}_{box[2]//20}_{box[3]//20}"
                        if det_hash not in saved_defect_hashes:
                            saved_defect_hashes.add(det_hash)
                            defect_id = detection_svc.save_defect(det, frame)
                            if defect_id:
                                await websocket.send_json({
                                    "type": "defect_saved",
                                    "defect_id": defect_id,
                                    "fault_type": det["cls"],
                                    "confidence": round(det["conf"], 2),
                                })

                # ~20 FPS target for smooth streaming
                await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if detection_svc:
            detection_svc.stop()
        _active_sessions.pop(inspection_id, None)
