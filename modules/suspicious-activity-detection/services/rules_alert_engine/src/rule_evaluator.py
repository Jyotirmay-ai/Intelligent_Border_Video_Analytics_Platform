"""
Rule Engine and Guardrail Enforcer.
Evaluates composite behavioral rules against extracted track features and formats explainable alerts.
"""

from typing import List, Optional, Tuple
from datetime import datetime

from .models import ZoneConfig, CompositeRuleConfig, BehavioralAlert
from .feature_extractor import ExtractedFeatures
from .track_state import TrackState


class RuleEvaluator:
    def __init__(self, config: ZoneConfig):
        self.config = config

    def update_config(self, new_config: ZoneConfig):
        self.config = new_config

    def evaluate_all(
        self,
        track: TrackState,
        features: ExtractedFeatures,
        current_time: datetime,
        camera_id: str,
    ) -> List[BehavioralAlert]:
        alerts: List[BehavioralAlert] = []

        for rule in self.config.composite_rules:
            if not rule.enabled:
                continue

            matches, triggered_params, explanation = self._evaluate_rule_conditions(rule, features)
            if matches:
                # Apply Guardrails: prevent single posture/kinematic high/critical alerts
                effective_severity = self._apply_safety_guardrails(rule, triggered_params)
                
                alert = BehavioralAlert(
                    track_id=track.track_id,
                    rule_id=rule.rule_id,
                    parameters_triggered=triggered_params,
                    severity=effective_severity,
                    camera_id=camera_id,
                    timestamp=current_time,
                    explanation=explanation,
                    is_shadow_mode=rule.shadow_mode,
                )
                alerts.append(alert)

        return alerts

    def _evaluate_rule_conditions(
        self,
        rule: CompositeRuleConfig,
        feat: ExtractedFeatures,
    ) -> Tuple[bool, List[str], str]:
        conditions = rule.conditions
        triggered_params: List[str] = []
        explanation_parts: List[str] = []
        all_passed = True

        # 1. Dwell Time check
        if "dwell_time_exceeded" in conditions:
            if feat.dwell_time_exceeded:
                triggered_params.append(f"dwell_time>{int(feat.effective_dwell_threshold_s)}s")
                explanation_parts.append(f"Loitering {int(feat.dwell_time_s)}s")
            else:
                all_passed = False

        # 2. Zone check
        if "zone_equals" in conditions:
            target_zone = conditions["zone_equals"]
            if feat.proximity_band == target_zone:
                triggered_params.append(f"zone={target_zone}")
                explanation_parts.append(f"{target_zone.capitalize()} zone")
            else:
                all_passed = False

        if "zone_in" in conditions:
            target_zones = conditions["zone_in"]
            if feat.proximity_band in target_zones:
                triggered_params.append(f"zone={feat.proximity_band}")
                explanation_parts.append(f"{feat.proximity_band.capitalize()} zone")
            else:
                all_passed = False

        # 3. Night / Off-Hours check
        if "time_is_night" in conditions:
            if feat.time_is_night:
                triggered_params.append("time=night")
                explanation_parts.append("Night")
            else:
                all_passed = False

        if "off_hours" in conditions:
            if feat.off_hours:
                triggered_params.append("time=off-hours")
                explanation_parts.append("Off-hours")
            else:
                all_passed = False

        # 4. Group Size check
        if "group_size_alert_exceeded" in conditions:
            if feat.group_size_alert_exceeded:
                triggered_params.append(f"group_size={feat.group_size}")
                explanation_parts.append(f"Group of {feat.group_size}")
            else:
                all_passed = False

        # 5. Approach Vector check
        if "approach_vector_equals" in conditions:
            target_vec = conditions["approach_vector_equals"]
            if feat.approach_vector == target_vec:
                triggered_params.append(f"approach_vector={target_vec}")
                explanation_parts.append(f"Vector {target_vec}")
            else:
                all_passed = False

        # 6. Posture check
        if "sustained_posture" in conditions:
            target_posture = conditions["sustained_posture"]
            if feat.sustained_posture == target_posture:
                triggered_params.append(f"posture={target_posture}")
                explanation_parts.append(f"Sustained {target_posture}")
            else:
                all_passed = False

        # 7. Multi-Camera check
        if "cross_camera_count_gte" in conditions:
            min_count = conditions["cross_camera_count_gte"]
            if feat.cross_camera_count >= min_count:
                triggered_params.append(f"cameras_sighted={feat.cross_camera_count}")
                explanation_parts.append(f"Sighted across {feat.cross_camera_count} cameras")
            else:
                all_passed = False

        # 8. Vehicle check
        if "vehicle_idle_exceeded" in conditions:
            if feat.vehicle_idle_exceeded:
                triggered_params.append(f"vehicle_idle>{int(feat.vehicle_idle_s)}s")
                explanation_parts.append(f"Vehicle idling {int(feat.vehicle_idle_s)}s")
            else:
                all_passed = False

        if "vehicle_repeat_passes_gte" in conditions:
            min_passes = conditions["vehicle_repeat_passes_gte"]
            if feat.vehicle_repeat_passes >= min_passes:
                triggered_params.append(f"repeat_passes={feat.vehicle_repeat_passes}")
                explanation_parts.append(f"{feat.vehicle_repeat_passes} repeat passes")
            else:
                all_passed = False

        # 9. Kinematic Path / Speed check
        if "path_linearity_deviated" in conditions:
            if feat.path_linearity_deviated:
                triggered_params.append(f"path_deviation>{int(feat.path_linearity_deviation * 100)}%")
                explanation_parts.append("Erratic movement")
            else:
                all_passed = False

        if "speed_is_fast" in conditions:
            if feat.speed_is_fast:
                triggered_params.append(f"speed={round(feat.speed_mps, 1)}mps")
                explanation_parts.append(f"Fast sprint ({round(feat.speed_mps, 1)} m/s)")
            else:
                all_passed = False

        explanation_str = " + ".join(explanation_parts) if all_passed else ""
        return all_passed, triggered_params, explanation_str

    def _apply_safety_guardrails(self, rule: CompositeRuleConfig, triggered_params: List[str]) -> str:
        """
        Hard rule enforcement (RULES.md §2, PARAMETERS.md §0):
        No single posture or kinematic parameter can trigger high/critical severity alone.
        Must combine with proximity or temporal parameters.
        """
        severity = rule.severity

        # Check if only a single parameter or single posture cue is present
        is_posture_only = any(p.startswith("posture=") for p in triggered_params) and len(triggered_params) == 1
        is_kinematic_only = any(p.startswith("speed=") or p.startswith("path_deviation=") for p in triggered_params) and len(triggered_params) == 1

        has_corroborating_signal = any(
            p.startswith("zone=") or p.startswith("dwell_time>") or p.startswith("time=") or p.startswith("group_size=")
            for p in triggered_params
        )

        if is_posture_only and not has_corroborating_signal:
            if severity in ["high", "critical"]:
                return "low"  # Downgrade to low due to high false-positive rate of posture alone
        
        if is_kinematic_only and not has_corroborating_signal:
            if severity in ["high", "critical"]:
                return "medium"

        return severity

