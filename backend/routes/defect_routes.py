"""
Defect management routes: list, update (confirm/reject/severity).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Defect, User
from backend.schemas import DefectOut, DefectUpdate
from backend.auth import get_current_user

router = APIRouter(prefix="/api/defects", tags=["defects"])


@router.get("/inspection/{inspection_id}", response_model=List[DefectOut])
def list_defects(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all defects for a given inspection."""
    return (
        db.query(Defect)
        .filter(Defect.inspection_id == inspection_id)
        .order_by(Defect.detected_at.asc())
        .all()
    )


@router.get("/{defect_id}", response_model=DefectOut)
def get_defect(
    defect_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    defect = db.query(Defect).filter(Defect.id == defect_id).first()
    if not defect:
        raise HTTPException(status_code=404, detail="Defect not found")
    return defect


@router.patch("/{defect_id}", response_model=DefectOut)
def update_defect(
    defect_id: str,
    body: DefectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update defect: set severity, confirm/reject, add notes."""
    defect = db.query(Defect).filter(Defect.id == defect_id).first()
    if not defect:
        raise HTTPException(status_code=404, detail="Defect not found")

    if body.severity is not None:
        if body.severity not in ("minor", "moderate", "severe"):
            raise HTTPException(status_code=400, detail="Severity must be minor, moderate, or severe")
        defect.severity = body.severity

    if body.status is not None:
        if body.status not in ("detected", "confirmed", "rejected"):
            raise HTTPException(status_code=400, detail="Status must be detected, confirmed, or rejected")
        defect.status = body.status

    if body.notes is not None:
        defect.notes = body.notes

    db.commit()
    db.refresh(defect)
    return defect
