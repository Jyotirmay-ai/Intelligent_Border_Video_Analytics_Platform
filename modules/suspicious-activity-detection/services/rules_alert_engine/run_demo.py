"""
Interactive Simulation & Demonstration of Module 6: Suspicious Activity Detection.
Simulates real-world border scenarios and displays generated explainable behavioral alerts.
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path to allow importing src
sys.path.insert(0, str(Path(__file__).parent))

from src.engine_service import EngineService
from src.models import (
    HumanTrackEvent,
    VehicleTrackEvent,
    BoundingBox,
    IntrusionEvent,
    NightModeFlag,
)


def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  {title.upper()}")
    print("=" * 80)


def print_alert(alert):
    severity_colors = {
        "critical": "\033[91m",  # Red
        "high": "\033[93m",      # Yellow
        "medium": "\033[96m",    # Cyan
        "low": "\033[92m",       # Green
    }
    reset = "\033[0m"
    color = severity_colors.get(alert.severity, "")
    
    print(f"{color}🚨 [ALERT FIRED] {alert.rule_id.upper()} ({alert.severity.upper()}){reset}")
    print(f"   ├─ Track ID:     {alert.track_id}")
    print(f"   ├─ Camera:       {alert.camera_id}")
    print(f"   ├─ Timestamp:    {alert.timestamp.isoformat()}")
    print(f"   ├─ Parameters:   {', '.join(alert.parameters_triggered)}")
    print(f"   ├─ UI Explain:   \"{alert.explanation}\"")
    print(f"   └─ JSON Payload: {json.dumps(alert.model_dump(mode='json'), indent=2)}")


def run_scenarios():
    config_path = Path(__file__).parent / "config" / "default_zone_config.json"
    engine = EngineService(config_path)
    base_time = datetime(2026, 9, 1, 2, 14, 30)

    # -------------------------------------------------------------
    # Scenario 1: Night Intruder Loitering in Restricted Zone
    # -------------------------------------------------------------
    print_banner("Scenario 1: Night Intruder Loitering in Restricted Zone (FR-23 & FR-23A)")
    print("-> Setting Night Mode Active = True (consumed from Module 7)")
    engine.process_night_mode_flag(NightModeFlag(
        camera_id="CAM-07",
        night_mode_active=True,
        timestamp=base_time
    ))

    print("-> Registering Intrusion Event into 'restricted' zone (consumed from Module 5)")
    engine.process_intrusion_event(IntrusionEvent(
        track_id="h_4471",
        zone_id="restricted",
        severity="high",
        camera_id="CAM-07",
        timestamp=base_time
    ))

    print("-> Streaming track observations over 80 seconds...")
    for s in range(0, 85, 10):
        t = base_time + timedelta(seconds=s)
        alerts = engine.process_human_track(HumanTrackEvent(
            track_id="h_4471",
            bbox=BoundingBox(x=120, y=80, w=60, h=140),
            camera_id="CAM-07",
            timestamp=t,
            confidence=0.91,
            distance_to_fence_m=10.0  # inside restricted band
        ))
        if alerts:
            for a in alerts:
                print_alert(a)
            break

    # -------------------------------------------------------------
    # Scenario 2: Active Fence Climbing (Critical Severity)
    # -------------------------------------------------------------
    print_banner("Scenario 2: Possible Breach Attempt - Active Fence Climbing (FR-23)")
    t_climb_base = base_time + timedelta(minutes=10)
    engine.process_intrusion_event(IntrusionEvent(
        track_id="h_9012",
        zone_id="restricted",
        severity="critical",
        camera_id="CAM-03",
        timestamp=t_climb_base
    ))

    print("-> Streaming sustained climbing pose for 6 seconds at fence line...")
    for s in range(0, 7):
        t = t_climb_base + timedelta(seconds=s)
        alerts = engine.process_human_track(HumanTrackEvent(
            track_id="h_9012",
            bbox=BoundingBox(x=400, y=200, w=50, h=120),
            camera_id="CAM-03",
            timestamp=t,
            confidence=0.96,
            distance_to_fence_m=2.0,
            pose_keypoints={"posture": "climb"}
        ))
        if alerts:
            for a in alerts:
                print_alert(a)
            break

    # -------------------------------------------------------------
    # Scenario 3: Agricultural Worker Tying Shoe (Safety Guardrail Test)
    # -------------------------------------------------------------
    print_banner("Scenario 3: Farmer Crouching in Outer Field (Safety Guardrail Verification)")
    t_farmer = base_time + timedelta(hours=8)  # daytime
    print("-> Farmer crouching in outer field (150m away). Demonstrating posture false-positive filter...")
    for s in range(0, 7):
        t = t_farmer + timedelta(seconds=s)
        alerts = engine.process_human_track(HumanTrackEvent(
            track_id="h_farmer",
            bbox=BoundingBox(x=100, y=100, w=40, h=80),
            camera_id="CAM-01",
            timestamp=t,
            confidence=0.89,
            distance_to_fence_m=150.0,
            pose_keypoints={"posture": "crouch"}
        ))
    
    if not alerts or all(a.severity not in ["high", "critical"] for a in alerts):
        print("✅ [GUARDRAIL ACTIVE] No High/Critical alert fired for isolated crouching in outer field!")

    # -------------------------------------------------------------
    # Scenario 4: Cross-Camera Sector Scouting (BoT-SORT + ReID)
    # -------------------------------------------------------------
    print_banner("Scenario 4: Multi-Camera Correlation - Sector Scouting Pattern (FR-23B)")
    t_scout = base_time + timedelta(hours=2)
    print("-> Sighting 1: Subject 'h_scout' seen at CAM-01 (Sector Alpha)...")
    engine.process_human_track(HumanTrackEvent(
        track_id="h_scout",
        bbox=BoundingBox(x=50, y=50, w=40, h=80),
        camera_id="CAM-01",
        timestamp=t_scout,
        confidence=0.90,
        distance_to_fence_m=40.0
    ))

    print("-> Sighting 2: Same subject re-identified at CAM-04 (Sector Delta) 20 mins later...")
    t_scout_2 = t_scout + timedelta(minutes=20)
    alerts = engine.process_human_track(HumanTrackEvent(
        track_id="h_scout",
        bbox=BoundingBox(x=80, y=70, w=40, h=80),
        camera_id="CAM-04",
        timestamp=t_scout_2,
        confidence=0.88,
        distance_to_fence_m=35.0
    ))
    for a in alerts:
        print_alert(a)

    print_banner("All Demonstration Scenarios Completed Successfully")


if __name__ == "__main__":
    run_scenarios()

