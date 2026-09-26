"""
Unit tests verifying Composite Behavioral Rules from PARAMETERS.md §8.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pytest

# Ensure rules_alert_engine folder is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.engine_service import EngineService
from src.models import HumanTrackEvent, VehicleTrackEvent, BoundingBox, IntrusionEvent, NightModeFlag


@pytest.fixture
def engine():
    config_path = Path(__file__).parent.parent / "config" / "default_zone_config.json"
    return EngineService(config_path)


def test_reconnaissance_pattern_rule(engine):
    """Rule: dwell_time > threshold, zone = restricted, time = night -> High Severity"""
    base_time = datetime(2026, 9, 1, 2, 0, 0)
    
    # 1. Enable night mode
    engine.process_night_mode_flag(NightModeFlag(
        camera_id="CAM-07",
        night_mode_active=True,
        timestamp=base_time
    ))

    # 2. Mark track entering restricted zone
    engine.process_intrusion_event(IntrusionEvent(
        track_id="h_4471",
        zone_id="restricted",
        severity="high",
        camera_id="CAM-07",
        timestamp=base_time
    ))

    # 3. Simulate loitering past effective threshold (120s * 0.6 = 72s)
    alerts = []
    for s in range(0, 90, 10):
        t = base_time + timedelta(seconds=s)
        ev = HumanTrackEvent(
            track_id="h_4471",
            bbox=BoundingBox(x=120, y=80, w=60, h=140),
            camera_id="CAM-07",
            timestamp=t,
            confidence=0.92,
            distance_to_fence_m=10.0  # restricted band <= 15m
        )
        alerts = engine.process_human_track(ev)

    assert len(alerts) >= 1
    recom_alert = next((a for a in alerts if a.rule_id == "reconnaissance-pattern"), None)
    assert recom_alert is not None
    assert recom_alert.severity == "high"
    assert "time=night" in recom_alert.parameters_triggered
    assert "zone=restricted" in recom_alert.parameters_triggered
    assert any(p.startswith("dwell_time>") for p in recom_alert.parameters_triggered)
    assert "Loitering" in recom_alert.explanation


def test_possible_breach_attempt_rule(engine):
    """Rule: posture = climb, zone = restricted -> Critical Severity"""
    base_time = datetime(2026, 9, 1, 14, 0, 0)

    engine.process_intrusion_event(IntrusionEvent(
        track_id="h_climb",
        zone_id="restricted",
        severity="critical",
        camera_id="CAM-02",
        timestamp=base_time
    ))

    alerts = []
    # Sustained climb for 6 seconds
    for s in range(0, 7):
        t = base_time + timedelta(seconds=s)
        ev = HumanTrackEvent(
            track_id="h_climb",
            bbox=BoundingBox(x=200, y=150, w=50, h=120),
            camera_id="CAM-02",
            timestamp=t,
            confidence=0.95,
            distance_to_fence_m=5.0,
            pose_keypoints={"posture": "climb"}
        )
        alerts = engine.process_human_track(ev)

    breach_alert = next((a for a in alerts if a.rule_id == "possible-breach-attempt"), None)
    assert breach_alert is not None
    assert breach_alert.severity == "critical"
    assert "posture=climb" in breach_alert.parameters_triggered
    assert "zone=restricted" in breach_alert.parameters_triggered


def test_sector_scouting_rule(engine):
    """Rule: cross_camera_reappearance within window, >=2 distinct cameras -> High Severity"""
    base_time = datetime(2026, 9, 1, 10, 0, 0)
    
    # Sighting 1 at CAM-01
    engine.process_human_track(HumanTrackEvent(
        track_id="h_scout",
        bbox=BoundingBox(x=50, y=50, w=40, h=80),
        camera_id="CAM-01",
        timestamp=base_time,
        confidence=0.90,
        distance_to_fence_m=40.0
    ))

    # Sighting 2 at non-adjacent CAM-04 15 minutes later
    t_15m = base_time + timedelta(minutes=15)
    alerts = engine.process_human_track(HumanTrackEvent(
        track_id="h_scout",
        bbox=BoundingBox(x=60, y=60, w=40, h=80),
        camera_id="CAM-04",
        timestamp=t_15m,
        confidence=0.88,
        distance_to_fence_m=35.0
    ))

    scout_alert = next((a for a in alerts if a.rule_id == "sector-scouting"), None)
    assert scout_alert is not None
    assert scout_alert.severity == "high"
    assert "cameras_sighted=2" in scout_alert.parameters_triggered


def test_vehicle_surveillance_rule(engine):
    """Rule: vehicle_idle > threshold, repeat_pass >= 2 -> Medium Severity"""
    base_time = datetime(2026, 9, 1, 11, 0, 0)

    track_state = engine.state_mgr.get_or_create_track("v_truck", track_type="vehicle")
    # Record 2 prior passes in the last 20 minutes
    track_state.record_pass(base_time - timedelta(minutes=15))
    track_state.record_pass(base_time - timedelta(minutes=5))

    # Vehicle stopped/stationary for 200 seconds (> 180s threshold)
    alerts = []
    for s in range(0, 210, 10):
        t = base_time + timedelta(seconds=s)
        alerts = engine.process_vehicle_track(VehicleTrackEvent(
            track_id="v_truck",
            bbox=BoundingBox(x=300, y=200, w=180, h=120),
            vehicle_class="truck",
            camera_id="CAM-05",
            timestamp=t,
            confidence=0.91,
            distance_to_fence_m=20.0
        ))

    surv_alert = next((a for a in alerts if a.rule_id == "vehicle-surveillance"), None)
    assert surv_alert is not None
    assert surv_alert.severity == "medium"
    assert "repeat_passes=2" in surv_alert.parameters_triggered
    assert any(p.startswith("vehicle_idle>") for p in surv_alert.parameters_triggered)

