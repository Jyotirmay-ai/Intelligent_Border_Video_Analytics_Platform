"""
Unit tests for Feature Extractor (Dwell time, night multiplier, speed, path linearity, boundary probes).
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pytest

# Ensure rules_alert_engine folder is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import ZoneConfig, ProximityBands, SpeedThresholds
from src.track_state import StateManager
from src.feature_extractor import FeatureExtractor


@pytest.fixture
def default_config():
    return ZoneConfig(
        zone_id="test-zone",
        proximity_bands_m=ProximityBands(outer_watch=200.0, warning=50.0, restricted=15.0),
        dwell_time_threshold_s=100.0,
        night_multiplier=0.6,
        speed_thresholds_mps=SpeedThresholds(slow=0.3, fast=3.5),
        path_linearity_max_deviation=0.4,
    )


def test_dwell_time_and_night_multiplier(default_config):
    state_mgr = StateManager()
    extractor = FeatureExtractor(default_config)
    track = state_mgr.get_or_create_track("h_1")

    base_time = datetime(2026, 9, 1, 2, 0, 0)
    
    # Add first observation at t=0
    track.add_observation(
        timestamp=base_time,
        x=100, y=100, w=50, h=100,
        camera_id="CAM-01",
        distance_to_fence_m=10.0,
        zone_id="restricted"
    )

    # 1. Daytime evaluation at t=70s (dwell threshold is 100s -> not exceeded)
    t_70 = base_time + timedelta(seconds=70)
    track.add_observation(
        timestamp=t_70,
        x=102, y=101, w=50, h=100,
        camera_id="CAM-01",
        distance_to_fence_m=10.0,
        zone_id="restricted"
    )
    feat_day = extractor.extract_features(track, state_mgr, t_70, night_mode_active=False)
    assert feat_day.dwell_time_s == 70.0
    assert feat_day.effective_dwell_threshold_s == 100.0
    assert not feat_day.dwell_time_exceeded

    # 2. Night mode evaluation at t=70s (effective threshold is 100 * 0.6 = 60s -> exceeded!)
    feat_night = extractor.extract_features(track, state_mgr, t_70, night_mode_active=True)
    assert feat_night.effective_dwell_threshold_s == 60.0
    assert feat_night.dwell_time_exceeded


def test_boundary_probe_counting(default_config):
    state_mgr = StateManager()
    track = state_mgr.get_or_create_track("h_probe")
    base_time = datetime(2026, 9, 1, 12, 0, 0)

    # Cycle 1: Approach from 80m to 20m, then retreat to 70m
    distances = [80.0, 50.0, 20.0, 45.0, 70.0]
    for idx, d in enumerate(distances):
        t = base_time + timedelta(seconds=idx * 5)
        track.add_observation(
            timestamp=t,
            x=100, y=100, w=50, h=100,
            camera_id="CAM-01",
            distance_to_fence_m=d,
        )

    assert track.probe_count == 1

    # Cycle 2: Approach again to 15m, then retreat to 60m
    distances_2 = [30.0, 15.0, 40.0, 60.0]
    for idx, d in enumerate(distances_2):
        t = base_time + timedelta(seconds=30 + idx * 5)
        track.add_observation(
            timestamp=t,
            x=100, y=100, w=50, h=100,
            camera_id="CAM-01",
            distance_to_fence_m=d,
        )

    assert track.probe_count == 2


def test_sustained_posture_filter(default_config):
    state_mgr = StateManager()
    extractor = FeatureExtractor(default_config)
    track = state_mgr.get_or_create_track("h_posture")
    base_time = datetime(2026, 9, 1, 12, 0, 0)

    # Momentary crouch (3 seconds) -> should not register as sustained
    track.add_observation(
        timestamp=base_time,
        x=100, y=100, w=50, h=100,
        camera_id="CAM-01",
        posture="crouch"
    )
    t_3 = base_time + timedelta(seconds=3)
    feat = extractor.extract_features(track, state_mgr, t_3)
    assert feat.sustained_posture is None

    # Sustained crouch (6 seconds >= 5s threshold)
    t_6 = base_time + timedelta(seconds=6)
    track.add_observation(
        timestamp=t_6,
        x=100, y=100, w=50, h=100,
        camera_id="CAM-01",
        posture="crouch"
    )
    feat_sustained = extractor.extract_features(track, state_mgr, t_6)
    assert feat_sustained.sustained_posture == "crouch"

