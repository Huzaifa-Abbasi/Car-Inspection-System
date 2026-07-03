"""
Business-logic helpers for inspections (used by routes if needed).
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.models import Inspection


def complete_inspection(db: Session, inspection_id: str) -> Inspection | None:
    """Mark an inspection as completed (Phase 5)."""
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        return None

    inspection.current_phase = 5
    inspection.status = "completed"
    inspection.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(inspection)
    return inspection
