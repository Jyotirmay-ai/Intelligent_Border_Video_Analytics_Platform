"""
Pydantic Data Models and Contracts for Rules Alert Engine.
Adheres strictly to CONTRACTS.md and PARAMETERS.md.
"""

from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime, timezone


# ==========================================
# Input Event Contracts (CONTRACTS.md)
# ==========================================

class BoundingBox(BaseModel):
    x: float
    y: float
    w: float
    h: float


class HumanTrackEvent(BaseModel):
    track_id: str
    bbox: BoundingBox
    camera_id: str
    timestamp: datetime
    confidence: float
    model_version: str = "yolo26-nano-v1"
    # Optional pose keypoint information if forwarded
    pose_keypoints: Optional[Dict[str, Any]] = None
    # ReID embedding vector if available from tracker
    reid_embedding: Optional[List[float]] = None
    # Optional distance to fence line in meters
    distance_to_fence_m: Optional[float] = None


class VehicleTrackEvent(BaseModel):
    track_id: str
    bbox: BoundingBox
    vehicle_class: str
    camera_id: str
    timestamp: datetime
    confidence: float
    model_version: str = "yolo26-nano-v1"
    distance_to_fence_m: Optional[float] = None


class IntrusionEvent(BaseModel):
    track_id: str
    zone_id: str
    severity: Literal["low", "medium", "high", "critical"]
    camera_id: str
    timestamp: datetime


class NightModeFlag(BaseModel):
    camera_id: str
    night_mode_active: bool
    confidence_multiplier: float = 0.85
    timestamp: datetime


# ==========================================
# Output Event Contract (CONTRACTS.md §6)
# ==========================================

class BehavioralAlert(BaseModel):
    track_id: str
    rule_id: str
    parameters_triggered: List[str]
    severity: Literal["low", "medium", "high", "critical"]
    camera_id: str
    timestamp: datetime
    explanation: Optional[str] = None  # Plain language for UI Alert Rail (DESIGN.md)
    is_shadow_mode: bool = False


# ==========================================
# Configuration Models (PARAMETERS.md §9)
# ==========================================

class ProximityBands(BaseModel):
    outer_watch: float = 200.0
    warning: float = 50.0
    restricted: float = 15.0


class SpeedThresholds(BaseModel):
    slow: float = 0.3
    fast: float = 3.5


class CompositeRuleConfig(BaseModel):
    rule_id: str
    description: str
    conditions: Dict[str, Any]
    severity: Literal["low", "medium", "high", "critical"]
    enabled: bool = True
    shadow_mode: bool = False


class ZoneConfig(BaseModel):
    zone_id: str
    proximity_bands_m: ProximityBands = Field(default_factory=ProximityBands)
    dwell_time_threshold_s: float = 120.0
    night_multiplier: float = 0.6
    group_size_baseline: int = 2
    group_size_alert: int = 3
    speed_thresholds_mps: SpeedThresholds = Field(default_factory=SpeedThresholds)
    path_linearity_max_deviation: float = 0.4
    posture_flags: List[str] = Field(default_factory=lambda: ["crouch", "crawl", "climb", "prone"])
    posture_sustain_duration_s: float = 5.0
    vehicle_idle_threshold_s: float = 180.0
    vehicle_repeat_pass_window_min: float = 30.0
    cross_camera_reappearance_window_min: float = 45.0
    composite_rules: List[CompositeRuleConfig] = Field(default_factory=list)
    created_by: str = "system"
    approved_by: str = "supervisor"
    version: int = 1
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

