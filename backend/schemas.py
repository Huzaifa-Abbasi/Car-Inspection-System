"""
Pydantic schemas for request / response validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


# ── Auth ─────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "inspector"  # "inspector" | "manager"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


# Fix forward reference
TokenResponse.model_rebuild()


# ── Vehicle ──────────────────────────────────────────────────────────────

class VehicleCreate(BaseModel):
    make: str
    model: str
    year: Optional[int] = None
    license_plate: Optional[str] = None
    vin: Optional[str] = None
    color: Optional[str] = None
    mileage: Optional[int] = None
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    owner_phone: Optional[str] = None


class VehicleOut(BaseModel):
    id: str
    make: str
    model: str
    year: Optional[int]
    license_plate: Optional[str]
    vin: Optional[str]
    color: Optional[str]
    mileage: Optional[int]
    owner_name: Optional[str]
    owner_email: Optional[str]
    owner_phone: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Defect ───────────────────────────────────────────────────────────────

class DefectOut(BaseModel):
    id: str
    inspection_id: str
    fault_type: str
    confidence: float
    severity: Optional[str]
    status: str
    bbox_x1: Optional[int]
    bbox_y1: Optional[int]
    bbox_x2: Optional[int]
    bbox_y2: Optional[int]
    snapshot_path: Optional[str]
    notes: Optional[str]
    detected_at: datetime

    class Config:
        from_attributes = True


class DefectUpdate(BaseModel):
    severity: Optional[str] = None
    status: Optional[str] = None   # "confirmed" | "rejected"
    notes: Optional[str] = None


# ── Inspection ───────────────────────────────────────────────────────────

class InspectionCreate(BaseModel):
    vehicle: VehicleCreate
    notes: Optional[str] = None


class InspectionOut(BaseModel):
    id: str
    vehicle_id: str
    inspector_id: str
    status: str
    current_phase: int
    notes: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    vehicle: Optional[VehicleOut] = None
    inspector: Optional[UserOut] = None
    defects: Optional[List[DefectOut]] = None

    class Config:
        from_attributes = True


class InspectionPhaseUpdate(BaseModel):
    phase: int  # target phase (2, 3, 4, or 5)


class InspectionSummary(BaseModel):
    """Dashboard summary statistics."""
    active_inspections: int
    completed_today: int
    pending_reports: int
    total_vehicles: int


# ── Report ───────────────────────────────────────────────────────────────

class ReportSendRequest(BaseModel):
    client_email: Optional[str] = None
    manager_email: Optional[str] = None
    note: Optional[str] = None
    sender_email: Optional[str] = None
    sender_password: Optional[str] = None
