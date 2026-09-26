"""
Pydantic v2 event schemas for the ANPR service.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BBox(BaseModel):
    x: int = Field(..., description="Left edge (pixels)")
    y: int = Field(..., description="Top edge (pixels)")
    w: int = Field(..., description="Width (pixels)", gt=0)
    h: int = Field(..., description="Height (pixels)", gt=0)


class VehicleTrack(BaseModel):
    track_id: str
    bbox: BBox
    vehicle_class: str
    camera_id: str
    timestamp: datetime
    confidence: float = Field(..., ge=0.0, le=1.0)
    model_version: str


class IntrusionEvent(BaseModel):
    track_id: str
    zone_id: str
    severity: str
    camera_id: str
    timestamp: datetime


class ANPREvent(BaseModel):
    track_id: str
    plate_text: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    registered_status: Literal["registered", "unregistered", "unknown"]
    camera_id: str
    timestamp: datetime
    model_version: str
