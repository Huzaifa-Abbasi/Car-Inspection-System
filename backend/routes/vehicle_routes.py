"""
Vehicle CRUD routes.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Vehicle, User
from backend.schemas import VehicleCreate, VehicleOut
from backend.auth import get_current_user

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


@router.get("", response_model=List[VehicleOut])
def list_vehicles(
    search: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all registered vehicles, optionally filtered by search term."""
    query = db.query(Vehicle)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (Vehicle.make.ilike(pattern))
            | (Vehicle.model.ilike(pattern))
            | (Vehicle.license_plate.ilike(pattern))
            | (Vehicle.vin.ilike(pattern))
            | (Vehicle.owner_name.ilike(pattern))
        )
    return query.order_by(Vehicle.created_at.desc()).all()


@router.get("/{vehicle_id}", response_model=VehicleOut)
def get_vehicle(
    vehicle_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@router.post("", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    body: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vehicle = Vehicle(**body.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle
