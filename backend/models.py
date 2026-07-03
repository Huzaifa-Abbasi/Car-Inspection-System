"""
SQLAlchemy ORM models for the Car Inspection system.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Text,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from backend.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _generate_id():
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(String(32), primary_key=True, default=_generate_id)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(SAEnum("inspector", "manager", name="user_role"), nullable=False, default="inspector")
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    inspections = relationship("Inspection", back_populates="inspector")


# ---------------------------------------------------------------------------
# Vehicle
# ---------------------------------------------------------------------------

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(String(32), primary_key=True, default=_generate_id)
    make = Column(String(80), nullable=False)
    model = Column(String(80), nullable=False)
    year = Column(Integer, nullable=True)
    license_plate = Column(String(20), nullable=True, index=True)
    vin = Column(String(17), nullable=True, unique=True)
    color = Column(String(40), nullable=True)
    mileage = Column(Integer, nullable=True)

    # Owner info
    owner_name = Column(String(120), nullable=True)
    owner_email = Column(String(255), nullable=True)
    owner_phone = Column(String(30), nullable=True)

    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    inspections = relationship("Inspection", back_populates="vehicle")


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------

class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(String(32), primary_key=True, default=_generate_id)
    vehicle_id = Column(String(32), ForeignKey("vehicles.id"), nullable=False)
    inspector_id = Column(String(32), ForeignKey("users.id"), nullable=False)
    status = Column(
        SAEnum("pending", "scanning", "reviewing", "completed", name="inspection_status"),
        nullable=False,
        default="pending",
    )
    current_phase = Column(Integer, default=1)  # 1-5
    notes = Column(Text, nullable=True)
    started_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="inspections")
    inspector = relationship("User", back_populates="inspections")
    defects = relationship("Defect", back_populates="inspection", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Defect
# ---------------------------------------------------------------------------

class Defect(Base):
    __tablename__ = "defects"

    id = Column(String(32), primary_key=True, default=_generate_id)
    inspection_id = Column(String(32), ForeignKey("inspections.id"), nullable=False)
    fault_type = Column(String(60), nullable=False)  # e.g. "doorouter-dent", "scratch"
    confidence = Column(Float, nullable=False)
    severity = Column(
        SAEnum("minor", "moderate", "severe", name="defect_severity"),
        nullable=True,
        default="moderate",
    )
    status = Column(
        SAEnum("detected", "confirmed", "rejected", name="defect_status"),
        nullable=False,
        default="detected",
    )

    # Bounding box (in the original frame)
    bbox_x1 = Column(Integer, nullable=True)
    bbox_y1 = Column(Integer, nullable=True)
    bbox_x2 = Column(Integer, nullable=True)
    bbox_y2 = Column(Integer, nullable=True)

    # Saved snapshot image path (relative to uploads/)
    snapshot_path = Column(String(500), nullable=True)

    notes = Column(Text, nullable=True)
    detected_at = Column(DateTime, default=_utcnow)

    # Relationships
    inspection = relationship("Inspection", back_populates="defects")
