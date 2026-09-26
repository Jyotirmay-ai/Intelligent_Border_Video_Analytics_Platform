"""
Main Engine Service for Suspicious Activity Detection (Module 6).
Orchestrates event ingestion, state management, feature extraction, and alert generation.
"""

import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from .models import (
    ZoneConfig,
    HumanTrackEvent,
    VehicleTrackEvent,
    IntrusionEvent,
    NightModeFlag,
    BehavioralAlert,
)
from .track_state import StateManager
from .feature_extractor import FeatureExtractor
from .rule_evaluator import RuleEvaluator
from .shadow_mode import ShadowModeValidator


class EngineService:
    def __init__(self, config_path: Optional[Path] = None):
        if config_path and config_path.exists():
            with open(config_path, "r") as f:
                data = json.load(f)
                self.config = ZoneConfig(**data)
        else:
            self.config = ZoneConfig(zone_id="default-zone")

        self.state_mgr = StateManager()
        self.feature_extractor = FeatureExtractor(self.config)
        self.rule_evaluator = RuleEvaluator(self.config)
        self.shadow_validator = ShadowModeValidator()
        self.night_mode_active = False

    def reload_config_from_json(self, config_json_str: str):
        """Hot-reload zone config without restarting service (FR-23C)."""
        data = json.loads(config_json_str)
        self.config = ZoneConfig(**data)
        self.feature_extractor.update_config(self.config)
        self.rule_evaluator.update_config(self.config)

    def process_night_mode_flag(self, event: NightModeFlag):
        """Consume night-mode flag from Module 7."""
        self.night_mode_active = event.night_mode_active

    def process_intrusion_event(self, event: IntrusionEvent):
        """Consume zone intrusion context from Module 5."""
        track = self.state_mgr.get_or_create_track(event.track_id)
        track.current_zone = event.zone_id
        if track.zone_entry_time is None:
            track.zone_entry_time = event.timestamp

    def process_human_track(self, event: HumanTrackEvent) -> List[BehavioralAlert]:
        """Ingest human track event and evaluate behavioral rules."""
        track = self.state_mgr.get_or_create_track(event.track_id, track_type="human")
        
        posture = None
        if event.pose_keypoints and "posture" in event.pose_keypoints:
            posture = event.pose_keypoints["posture"]

        track.add_observation(
            timestamp=event.timestamp,
            x=event.bbox.x,
            y=event.bbox.y,
            w=event.bbox.w,
            h=event.bbox.h,
            camera_id=event.camera_id,
            distance_to_fence_m=event.distance_to_fence_m,
            posture=posture,
            reid_embedding=event.reid_embedding,
        )

        features = self.feature_extractor.extract_features(
            track=track,
            state_mgr=self.state_mgr,
            current_time=event.timestamp,
            night_mode_active=self.night_mode_active,
        )

        alerts = self.rule_evaluator.evaluate_all(
            track=track,
            features=features,
            current_time=event.timestamp,
            camera_id=event.camera_id,
        )

        # Log to shadow validator if shadow mode rule
        for alert in alerts:
            if alert.is_shadow_mode:
                self.shadow_validator.log_alert(alert)

        return alerts

    def process_vehicle_track(self, event: VehicleTrackEvent) -> List[BehavioralAlert]:
        """Ingest vehicle track event and evaluate behavioral rules."""
        track = self.state_mgr.get_or_create_track(event.track_id, track_type="vehicle")
        
        track.add_observation(
            timestamp=event.timestamp,
            x=event.bbox.x,
            y=event.bbox.y,
            w=event.bbox.w,
            h=event.bbox.h,
            camera_id=event.camera_id,
            distance_to_fence_m=event.distance_to_fence_m,
        )

        features = self.feature_extractor.extract_features(
            track=track,
            state_mgr=self.state_mgr,
            current_time=event.timestamp,
            night_mode_active=self.night_mode_active,
        )

        alerts = self.rule_evaluator.evaluate_all(
            track=track,
            features=features,
            current_time=event.timestamp,
            camera_id=event.camera_id,
        )

        return alerts

