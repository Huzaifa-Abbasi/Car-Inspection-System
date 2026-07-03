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
        detection_svc = DetectionService(inspection_id=inspection_id)
        detection_svc.start()
        _active_sessions[inspection_id] = detection_svc

        await websocket.send_json({"type": "status", "message": "Camera started. Scanning..."})

        paused = False
        # Track which defect boxes we've already saved (by approximate position hash)
        saved_defect_hashes: set[str] = set()

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
                elif cmd == "end_scan":
                    await websocket.send_json({"type": "status", "message": "Scan ended"})
                    break

            except asyncio.TimeoutError:
                pass  # No command received — continue streaming

            if paused:
                await asyncio.sleep(0.05)
                continue

            # Get the latest annotated frame + detections
            frame, detections = detection_svc.get_frame_and_detections()

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
