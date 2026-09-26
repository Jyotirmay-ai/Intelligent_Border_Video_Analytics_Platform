"""
Shadow Mode Validation and Audit Logger (Milestone M6).
Enables testing candidate composite rules against historical or pilot footage without triggering live alarms.
"""

from typing import Dict, List, Any
from datetime import datetime
from .models import BehavioralAlert


class ShadowModeMetrics:
    def __init__(self, rule_id: str):
        self.rule_id = rule_id
        self.total_evaluations: int = 0
        self.triggered_count: int = 0
        self.true_positive_count: int = 0
        self.false_positive_count: int = 0
        self.logged_alerts: List[BehavioralAlert] = []

    def record_alert(self, alert: BehavioralAlert, is_true_positive: bool = True):
        self.triggered_count += 1
        self.logged_alerts.append(alert)
        if is_true_positive:
            self.true_positive_count += 1
        else:
            self.false_positive_count += 1

    @property
    def false_positive_rate(self) -> float:
        if self.triggered_count == 0:
            return 0.0
        return self.false_positive_count / self.triggered_count

    def summary(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "total_evaluations": self.total_evaluations,
            "triggered_count": self.triggered_count,
            "true_positives": self.true_positive_count,
            "false_positives": self.false_positive_count,
            "false_positive_rate": round(self.false_positive_rate, 4),
        }


class ShadowModeValidator:
    def __init__(self):
        self.rule_metrics: Dict[str, ShadowModeMetrics] = {}
        self.audit_log: List[Dict[str, Any]] = []

    def log_alert(self, alert: BehavioralAlert, is_ground_truth_threat: bool = True):
        if alert.rule_id not in self.rule_metrics:
            self.rule_metrics[alert.rule_id] = ShadowModeMetrics(alert.rule_id)
        
        metrics = self.rule_metrics[alert.rule_id]
        metrics.record_alert(alert, is_true_positive=is_ground_truth_threat)

        self.audit_log.append({
            "timestamp": alert.timestamp.isoformat(),
            "track_id": alert.track_id,
            "rule_id": alert.rule_id,
            "severity": alert.severity,
            "parameters_triggered": alert.parameters_triggered,
            "explanation": alert.explanation,
            "is_shadow_mode": alert.is_shadow_mode,
            "ground_truth_threat": is_ground_truth_threat,
        })

    def get_summary_report(self) -> Dict[str, Any]:
        return {
            "evaluated_rules": {
                rule_id: m.summary() for rule_id, m in self.rule_metrics.items()
            },
            "total_logged_alerts": len(self.audit_log),
        }

