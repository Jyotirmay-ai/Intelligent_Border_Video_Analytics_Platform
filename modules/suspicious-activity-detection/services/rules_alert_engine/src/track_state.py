"""
Track State Buffer and History Manager.
Maintains sliding-window spatial, kinematic, and behavioral history for active tracks.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import math
from collections import deque


class Observation:
    def __init__(
        self,
        timestamp: datetime,
        x: float,
        y: float,
        w: float,
        h: float,
        camera_id: str,
        distance_to_fence_m: Optional[float] = None,
        posture: Optional[str] = None,
        zone_id: Optional[str] = None,
    ):
        self.timestamp = timestamp
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.camera_id = camera_id
        self.distance_to_fence_m = distance_to_fence_m
        self.posture = posture
        self.zone_id = zone_id


class TrackState:
    def __init__(self, track_id: str, track_type: str = "human", max_history: int = 300):
        self.track_id = track_id
        self.track_type = track_type  # "human" or "vehicle"
        self.history: deque[Observation] = deque(maxlen=max_history)
        self.first_seen: datetime = None
        self.last_seen: datetime = None
        
        # Zone tracking
        self.current_zone: Optional[str] = None
        self.zone_entry_time: Optional[datetime] = None
        
        # Boundary approach & retreat cycle counter (probing)
        self.probe_count: int = 0
        self._last_distance_trend: Optional[str] = None  # "approaching", "retreating"
        self._min_distance_in_probe: float = float("inf")
        
        # Posture sustain tracking
        self.current_sustained_posture: Optional[str] = None
        self.posture_start_time: Optional[datetime] = None
        
        # Sighted cameras history (for cross-camera ReID)
        self.camera_sightings: List[Tuple[str, datetime]] = []
        
        # Vehicle specific tracking
        self.is_stationary: bool = False
        self.stationary_start_time: Optional[datetime] = None
        self.pass_timestamps: List[datetime] = []
        self.reid_embedding: Optional[List[float]] = None

    def add_observation(
        self,
        timestamp: datetime,
        x: float,
        y: float,
        w: float,
        h: float,
        camera_id: str,
        distance_to_fence_m: Optional[float] = None,
        posture: Optional[str] = None,
        zone_id: Optional[str] = None,
        reid_embedding: Optional[List[float]] = None,
    ):
        obs = Observation(
            timestamp=timestamp,
            x=x,
            y=y,
            w=w,
            h=h,
            camera_id=camera_id,
            distance_to_fence_m=distance_to_fence_m,
            posture=posture,
            zone_id=zone_id or self.current_zone,
        )
        self.history.append(obs)
        if self.first_seen is None:
            self.first_seen = timestamp
        self.last_seen = timestamp

        if reid_embedding:
            self.reid_embedding = reid_embedding

        # Update camera sightings
        if not self.camera_sightings or self.camera_sightings[-1][0] != camera_id:
            self.camera_sightings.append((camera_id, timestamp))

        # Update Zone Entry Time
        if zone_id and zone_id != self.current_zone:
            self.current_zone = zone_id
            self.zone_entry_time = timestamp
        elif self.current_zone is None and zone_id:
            self.current_zone = zone_id
            self.zone_entry_time = timestamp

        # Update Posture History
        if posture:
            if posture == self.current_sustained_posture:
                pass  # Continuing current posture
            else:
                self.current_sustained_posture = posture
                self.posture_start_time = timestamp
        else:
            self.current_sustained_posture = None
            self.posture_start_time = None

        # Update Boundary Probe Tracker (Approaching then retreating)
        if distance_to_fence_m is not None:
            self._update_probe_tracking(distance_to_fence_m)

        # Update Stationary / Idle tracker
        self._update_stationary_tracking(x, y, timestamp)

    def _update_probe_tracking(self, current_dist: float):
        if len(self.history) < 2:
            return
        prev_dist = self.history[-2].distance_to_fence_m
        if prev_dist is None:
            return

        diff = current_dist - prev_dist
        if diff < -1.0:  # Moving closer by > 1m
            if self._last_distance_trend == "retreating":
                # Changed from retreat to approach
                pass
            self._last_distance_trend = "approaching"
            self._min_distance_in_probe = min(self._min_distance_in_probe, current_dist)
        elif diff > 1.0:  # Moving away by > 1m
            if self._last_distance_trend == "approaching" and self._min_distance_in_probe < 50.0:
                # Completed an approach-retreat cycle near boundary
                self.probe_count += 1
                self._min_distance_in_probe = float("inf")
            self._last_distance_trend = "retreating"

    def _update_stationary_tracking(self, x: float, y: float, timestamp: datetime):
        if len(self.history) < 2:
            self.is_stationary = True
            self.stationary_start_time = timestamp
            return
        
        first_obs = self.history[0] if len(self.history) < 5 else self.history[-5]
        dx = x - first_obs.x
        dy = y - first_obs.y
        dist = math.sqrt(dx * dx + dy * dy)
        dt = (timestamp - first_obs.timestamp).total_seconds()
        
        if dt > 0:
            speed_px = dist / dt
            if speed_px < 5.0:  # Minimal pixel displacement
                if not self.is_stationary or self.stationary_start_time is None:
                    self.is_stationary = True
                    self.stationary_start_time = first_obs.timestamp
            else:
                self.is_stationary = False
                self.stationary_start_time = None

    def record_pass(self, timestamp: datetime):
        self.pass_timestamps.append(timestamp)


class StateManager:
    def __init__(self, ttl_seconds: int = 3600):
        self.tracks: Dict[str, TrackState] = {}
        self.ttl_seconds = ttl_seconds

    def get_or_create_track(self, track_id: str, track_type: str = "human") -> TrackState:
        if track_id not in self.tracks:
            self.tracks[track_id] = TrackState(track_id=track_id, track_type=track_type)
        return self.tracks[track_id]

    def prune_stale_tracks(self, current_time: datetime):
        cutoff = current_time - timedelta(seconds=self.ttl_seconds)
        stale_ids = [
            tid for tid, state in self.tracks.items()
            if state.last_seen and state.last_seen < cutoff
        ]
        for tid in stale_ids:
            del self.tracks[tid]

