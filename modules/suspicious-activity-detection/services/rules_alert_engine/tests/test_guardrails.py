"""
Unit tests for Safety Guardrails (RULES.md §2, PARAMETERS.md §0).
Verifies that single posture or kinematic cues cannot fire High/Critical severity alone.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pytest

# Ensure rules_alert_engine folder is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.engine_service import EngineService
from src.models import (
    HumanTrackEvent,
    BoundingBox,
    ZoneConfig,
    CompositeRuleConfig,
)


def test_single_posture_downgrade_guardrail():
    """
    If a rule is configured to fire Critical on posture alone (e.g. crouching in open field),
    the guardrail must automatically downgrade it to Low.
    """
    config = ZoneConfig(
        zone_id="open-field",
        posture_sustain_duration_s=5.0,
        composite_rules=[
            CompositeRuleConfig(
                rule_id="lone-crouch-rule",
                description="Testing single posture rule",
                conditions={"sustained_posture": "crouch"},
                severity="critical",  # Misconfigured by operator
            )
        ]
    )

    engine = EngineService()
    engine.config = config
    engine.rule_evaluator.update_config(config)
    engine.feature_extractor.update_config(config)

    base_time = datetime(2026, 9, 1, 12, 0, 0)

    alerts = []
    for s in range(0, 7):
        t = base_time + timedelta(seconds=s)
        ev = HumanTrackEvent(
            track_id="h_farmer_tying_shoe",
            bbox=BoundingBox(x=100, y=100, w=40, h=80),
            camera_id="CAM-01",
            timestamp=t,
            confidence=0.90,
            distance_to_fence_m=180.0,  # Far away in outer field
            pose_keypoints={"posture": "crouch"}
        )
        alerts = engine.process_human_track(ev)

    assert len(alerts) == 1
    # Guardrail must have downgraded critical -> low because posture was the only condition
    assert alerts[0].severity == "low"


def test_casual_proximity_no_alert():
    """
    Passing in outer watch zone during daytime for <30s should generate no high/critical alerts.
    """
    config_path = Path(__file__).parent.parent / "config" / "default_zone_config.json"
    engine = EngineService(config_path)

    base_time = datetime(2026, 9, 1, 14, 0, 0)
    alerts = []

    # 20 seconds walk in outer watch zone (150m away)
    for s in range(0, 20, 2):
        t = base_time + timedelta(seconds=s)
        ev = HumanTrackEvent(
            track_id="h_farmer_walk",
            bbox=BoundingBox(x=50 + s * 5, y=50, w=40, h=80),
            camera_id="CAM-01",
            timestamp=t,
            confidence=0.88,
            distance_to_fence_m=150.0  # outer watch
        )
        alerts = engine.process_human_track(ev)

    # Filter out any high/critical alerts
    high_alerts = [a for a in alerts if a.severity in ["high", "critical"]]
    assert len(high_alerts) == 0

