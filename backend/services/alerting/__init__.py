"""Alerting package (B4.1 / docs/uplevel/4n-alerting.md)."""

from backend.services.alerting.pipeline import AlertPipeline, PipelineResult
from backend.services.alerting.policy import (
    PolicyContext,
    RuleMatch,
    SnoozeEntry,
    check_schedule_window,
    default_rule_from_settings,
    evaluate,
    evaluate_rule,
)
from backend.services.alerting.verdict import (
    FaceCandidate,
    ReidCandidate,
    ResolvedVerdict,
    SpecialistEvidence,
    resolve,
)

__all__ = [
    "AlertPipeline",
    "FaceCandidate",
    "PipelineResult",
    "PolicyContext",
    "ReidCandidate",
    "ResolvedVerdict",
    "RuleMatch",
    "SnoozeEntry",
    "SpecialistEvidence",
    "check_schedule_window",
    "default_rule_from_settings",
    "evaluate",
    "evaluate_rule",
    "resolve",
]
