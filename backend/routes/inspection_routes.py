"""
Inspection CRUD + phase-transition routes.
"""

from typing import List, Optional
from datetime import datetime, timezone, date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import Inspection, Vehicle, User, Defect
from backend.schemas import (
    InspectionCreate,
    InspectionOut,
    InspectionPhaseUpdate,
    InspectionSummary,
)
from backend.auth import get_current_user

router = APIRouter(prefix="/api/inspections", tags=["inspections"])

# Phase-to-status mapping
_PHASE_STATUS = {
    1: "pending",
    2: "scanning",
    3: "reviewing",
    4: "reviewing",
    5: "completed",
}


@router.get("/summary", response_model=InspectionSummary)
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dashboard summary statistics."""
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )

    active = db.query(Inspection).filter(
        Inspection.status.in_(["pending", "scanning", "reviewing"])
    ).count()

    completed_today = db.query(Inspection).filter(
        Inspection.status == "completed",
        Inspection.completed_at >= today_start,
    ).count()

    # "Pending reports" = reviewing phase inspections (phase 3 or 4)
    pending_reports = db.query(Inspection).filter(
        Inspection.status == "reviewing"
    ).count()

    total_vehicles = db.query(Vehicle).count()

    return InspectionSummary(
        active_inspections=active,
        completed_today=completed_today,
        pending_reports=pending_reports,
        total_vehicles=total_vehicles,
    )


@router.get("", response_model=List[InspectionOut])
def list_inspections(
    status: Optional[str] = Query(None),
    inspector_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List inspections. Managers see all; inspectors see only their own."""
    query = db.query(Inspection).options(
        joinedload(Inspection.vehicle),
        joinedload(Inspection.inspector),
    )

    # Inspectors only see their own inspections
    if current_user.role == "inspector":
        query = query.filter(Inspection.inspector_id == current_user.id)
    elif inspector_id:
        query = query.filter(Inspection.inspector_id == inspector_id)

    if status:
        query = query.filter(Inspection.status == status)

    return query.order_by(Inspection.started_at.desc()).offset(offset).limit(limit).all()


@router.get("/{inspection_id}", response_model=InspectionOut)
def get_inspection(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inspection = (
        db.query(Inspection)
        .options(
            joinedload(Inspection.vehicle),
            joinedload(Inspection.inspector),
            joinedload(Inspection.defects),
        )
        .filter(Inspection.id == inspection_id)
        .first()
    )
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return inspection


@router.post("", response_model=InspectionOut, status_code=201)
def create_inspection(
    body: InspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new inspection with vehicle data (Phase 1 — Vehicle Registration)."""
    # Create or find vehicle
    vehicle_data = body.vehicle.model_dump()
    vehicle = None

    # Try to match by VIN first
    if vehicle_data.get("vin"):
        vehicle = db.query(Vehicle).filter(Vehicle.vin == vehicle_data["vin"]).first()

    if not vehicle:
        vehicle = Vehicle(**vehicle_data)
        db.add(vehicle)
        db.flush()

    inspection = Inspection(
        vehicle_id=vehicle.id,
        inspector_id=current_user.id,
        status="pending",
        current_phase=1,
        notes=body.notes,
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    # Reload with relationships
    inspection = (
        db.query(Inspection)
        .options(joinedload(Inspection.vehicle), joinedload(Inspection.inspector))
        .filter(Inspection.id == inspection.id)
        .first()
    )
    return inspection


@router.patch("/{inspection_id}/phase", response_model=InspectionOut)
def advance_phase(
    inspection_id: str,
    body: InspectionPhaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Advance the inspection to the next phase."""
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    if body.phase < 1 or body.phase > 5:
        raise HTTPException(status_code=400, detail="Phase must be between 1 and 5")

    inspection.current_phase = body.phase
    inspection.status = _PHASE_STATUS.get(body.phase, inspection.status)

    if body.phase == 5:
        inspection.completed_at = datetime.now(timezone.utc)
        inspection.status = "completed"

    db.commit()
    db.refresh(inspection)

    inspection = (
        db.query(Inspection)
        .options(
            joinedload(Inspection.vehicle),
            joinedload(Inspection.inspector),
            joinedload(Inspection.defects),
        )
        .filter(Inspection.id == inspection.id)
        .first()
    )
    return inspection
