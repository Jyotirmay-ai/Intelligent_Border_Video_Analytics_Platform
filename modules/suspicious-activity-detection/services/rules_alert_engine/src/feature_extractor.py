"""
Feature Extraction Engine for Suspicious Activity Detection.
Computes spatial, temporal, kinematic, group, posture, vehicle, and multi-camera features.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import math
import numpy as np

from .models import ZoneConfig
from .track_state import TrackState, StateManager


class ExtractedFeatures:
    def __init__(self):
        self.dwell_time_s: float = 0.0
        self.effective_dwell_threshold_s: float = 120.0
        self.dwell_time_exceeded: bool = False
        
        self.proximity_band: str = "none"  # "restricted", "warning", "outer_watch", "none"
        self.approach_vector: str = "unknown"  # "toward", "paralleling", "away"
        self.boundary_probe_count: int = 0
        
        self.speed_mps: float = 0.0
        self.speed_is_slow: bool = False
        self.speed_is_fast: bool = False
        self.path_linearity_deviation: float = 0.0
        self.path_linearity_deviated: bool = False
        
        self.group_size: int = 1
        self.group_size_alert_exceeded: bool = False
        
        self.sustained_posture: Optional[str] = None
        self.posture_sustained_duration_s: float = 0.0
        
        self.vehicle_idle_s: float = 0.0
        self.vehicle_idle_exceeded: bool = False
        self.vehicle_repeat_passes: int = 0
        
        self.cross_camera_count: int = 1
        self.cross_camera_window_valid: bool = False
        
        self.time_is_night: bool = False
        self.off_hours: bool = False
        
        # Raw metrics for explainability breakdown
        self.metrics_summary: Dict[str, Any] = {}


class FeatureExtractor:
    def __init__(self, zone_config: ZoneConfig):
        self.config = zone_config

    def update_config(self, new_config: ZoneConfig):
        self.config = new_config

    def extract_features(
        self,
        track: TrackState,
        state_mgr: StateManager,
        current_time: datetime,
        night_mode_active: bool = False,
    ) -> ExtractedFeatures:
        feat = ExtractedFeatures()
        feat.time_is_night = night_mode_active
        # Off-hours: night mode active or late evening / early morning
        hour = current_time.hour
        feat.off_hours = night_mode_active or (hour >= 20 or hour <= 6)

        if not track.history:
            return feat

        # 1. Temporal & Dwell Time
        effective_threshold = self.config.dwell_time_threshold_s
        if night_mode_active:
            effective_threshold *= self.config.night_multiplier
        feat.effective_dwell_threshold_s = effective_threshold

        if track.zone_entry_time:
            feat.dwell_time_s = (current_time - track.zone_entry_time).total_seconds()
        elif track.first_seen:
            feat.dwell_time_s = (current_time - track.first_seen).total_seconds()
        else:
            feat.dwell_time_s = 0.0

        feat.dwell_time_exceeded = feat.dwell_time_s >= effective_threshold

        # 2. Spatial & Proximity
        last_obs = track.history[-1]
        dist = last_obs.distance_to_fence_m
        if dist is not None:
            if dist <= self.config.proximity_bands_m.restricted:
                feat.proximity_band = "restricted"
            elif dist <= self.config.proximity_bands_m.warning:
                feat.proximity_band = "warning"
            elif dist <= self.config.proximity_bands_m.outer_watch:
                feat.proximity_band = "outer_watch"
            else:
                feat.proximity_band = "outer"
        else:
            feat.proximity_band = "restricted" if track.current_zone == "restricted" else "warning"

        feat.approach_vector = self._compute_approach_vector(track)
        feat.boundary_probe_count = track.probe_count

        # 3. Kinematics & Speed
        feat.speed_mps, feat.path_linearity_deviation = self._compute_kinematics(track)
        feat.speed_is_slow = feat.speed_mps < self.config.speed_thresholds_mps.slow
        feat.speed_is_fast = feat.speed_mps > self.config.speed_thresholds_mps.fast
        feat.path_linearity_deviated = feat.path_linearity_deviation > self.config.path_linearity_max_deviation

        # 4. Group Dynamics
        feat.group_size = self._compute_group_size(track, state_mgr, current_time)
        effective_alert_size = self.config.group_size_alert
        if night_mode_active:
            effective_alert_size = max(1, effective_alert_size - 1)
        feat.group_size_alert_exceeded = feat.group_size >= effective_alert_size

        # 5. Posture Cues (Sustained >= threshold)
        if track.current_sustained_posture and track.posture_start_time:
            duration = (current_time - track.posture_start_time).total_seconds()
            feat.posture_sustained_duration_s = duration
            if duration >= self.config.posture_sustain_duration_s:
                feat.sustained_posture = track.current_sustained_posture

        # 6. Vehicle Features
        if track.track_type == "vehicle":
            if track.stationary_start_time:
                feat.vehicle_idle_s = (current_time - track.stationary_start_time).total_seconds()
            feat.vehicle_idle_exceeded = feat.vehicle_idle_s >= self.config.vehicle_idle_threshold_s
            
            # Repeat passes in window
            cutoff_pass = current_time - timedelta(minutes=self.config.vehicle_repeat_pass_window_min)
            valid_passes = [t for t in track.pass_timestamps if t >= cutoff_pass]
            feat.vehicle_repeat_passes = len(valid_passes)

        # 7. Multi-Camera ReID Correlation
        cutoff_cam = current_time - timedelta(minutes=self.config.cross_camera_reappearance_window_min)
        recent_cams = [cam for cam, ts in track.camera_sightings if ts >= cutoff_cam]
        unique_cams = set(recent_cams)
        feat.cross_camera_count = len(unique_cams)
        feat.cross_camera_window_valid = feat.cross_camera_count >= 2

        # Summary Metrics
        feat.metrics_summary = {
            "dwell_time_s": round(feat.dwell_time_s, 1),
            "dwell_threshold_s": round(effective_threshold, 1),
            "proximity_band": feat.proximity_band,
            "approach_vector": feat.approach_vector,
            "probe_count": feat.boundary_probe_count,
            "speed_mps": round(feat.speed_mps, 2),
            "path_deviation_pct": round(feat.path_linearity_deviation * 100, 1),
            "group_size": feat.group_size,
            "sustained_posture": feat.sustained_posture,
            "vehicle_idle_s": round(feat.vehicle_idle_s, 1),
            "vehicle_repeat_passes": feat.vehicle_repeat_passes,
            "cross_camera_count": feat.cross_camera_count,
            "time_is_night": feat.time_is_night,
        }

        return feat

    def _compute_approach_vector(self, track: TrackState) -> str:
        if len(track.history) < 3:
            return "unknown"
        
        obs_start = track.history[0]
        obs_end = track.history[-1]

        if obs_start.distance_to_fence_m is not None and obs_end.distance_to_fence_m is not None:
            delta = obs_end.distance_to_fence_m - obs_start.distance_to_fence_m
            if delta < -2.0:
                return "toward"
            elif delta > 2.0:
                return "away"
            else:
                return "paralleling"
        
        # Fallback to coordinate Y movement if distance not provided
        dy = obs_end.y - obs_start.y
        dx = obs_end.x - obs_start.x
        if abs(dy) > abs(dx) * 1.5:
            return "toward" if dy > 0 else "away"
        elif abs(dx) > abs(dy) * 1.5:
            return "paralleling"
        return "toward"

    def _compute_kinematics(self, track: TrackState) -> (float, float):
        if len(track.history) < 2:
            return 0.0, 0.0

        pts = [(o.x, o.y, o.timestamp) for o in track.history]
        total_dist_px = 0.0
        for i in range(1, len(pts)):
            dx = pts[i][0] - pts[i-1][0]
            dy = pts[i][1] - pts[i-1][1]
            total_dist_px += math.sqrt(dx * dx + dy * dy)

        dt = (pts[-1][2] - pts[0][2]).total_seconds()
        if dt <= 0:
            return 0.0, 0.0

        # Calibration: 20 pixels ~= 1 meter (configurable heuristic)
        px_per_meter = 20.0
        total_dist_m = total_dist_px / px_per_meter
        speed_mps = total_dist_m / dt

        # Straight-line distance
        disp_x = pts[-1][0] - pts[0][0]
        disp_y = pts[-1][1] - pts[0][1]
        straight_dist_m = math.sqrt(disp_x * disp_x + disp_y * disp_y) / px_per_meter

        if straight_dist_m > 1.0:
            deviation = max(0.0, (total_dist_m - straight_dist_m) / straight_dist_m)
        else:
            deviation = 0.0

        return speed_mps, deviation

    def _compute_group_size(
        self,
        current_track: TrackState,
        state_mgr: StateManager,
        current_time: datetime,
        radius_px: float = 100.0,
    ) -> int:
        if not current_track.history:
            return 1

        curr_obs = current_track.history[-1]
        group_members = 1
        cutoff = current_time - timedelta(seconds=5)

        for other_id, other_state in state_mgr.tracks.items():
            if other_id == current_track.track_id or not other_state.history:
                continue
            other_obs = other_state.history[-1]
            if other_obs.timestamp < cutoff or other_obs.camera_id != curr_obs.camera_id:
                continue
            
            dx = other_obs.x - curr_obs.x
            dy = other_obs.y - curr_obs.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= radius_px:
                group_members += 1

        return group_members

