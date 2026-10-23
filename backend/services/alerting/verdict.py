"""Verdict chain resolution and trusted-match suppression (B4.1 / 4n-alerting.md).

Walks the three-step chain (local VLM -> cloud VLM slot -> detector + Triton
specialists) and applies the biometric suppression invariant (F1):
an alert is suppressed by recognition ONLY when no face is unknown and trusted
matches cover every person detected.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from backend.services.severity import get_severity_service

VerdictSource = Literal["local", "cloud", "detector", "external"]
VerdictKind = Literal["confirmed", "uncertain", "rejected"]
FaceStatus = Literal["trusted", "unknown", "none"]


def external_severity_top_score(severity: str | None) -> int:
    """Return the top of the SeverityService band for `severity` (4n-arming.md A4)."""
    sev = get_severity_service()
    key = str(severity or "medium").strip().lower()
    if key == "low":
        return int(sev.low_max)
    if key == "medium":
        return int(sev.medium_max)
    if key == "high":
        return int(sev.high_max)
    if key == "critical":
        return 100
    return int(sev.medium_max)


@dataclass(frozen=True, slots=True)
class FaceCandidate:
    """One face observation in the event's window."""

    person_name: str | None = None
    is_household_member: bool = False
    is_auto_enrolled: bool = False
    is_unknown: bool = True

    @property
    def is_trusted(self) -> bool:
        return bool(
            not self.is_unknown
            and self.person_name
            and self.is_household_member
            and not self.is_auto_enrolled
        )


@dataclass(frozen=True, slots=True)
class ReidCandidate:
    """One person re-ID match in the event's window."""

    member_name: str
    trust_level: str = "monitor"

    @property
    def is_trusted(self) -> bool:
        return bool(self.member_name and self.trust_level.lower() == "full")


@dataclass(frozen=True, slots=True)
class SpecialistEvidence:
    """Face and re-ID observations associated with an event."""

    faces: tuple[FaceCandidate, ...] = ()
    reid: tuple[ReidCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedVerdict:
    """Resolved verdict from the chain plus recognition/suppression state."""

    source: VerdictSource
    verdict: VerdictKind | None
    risk_score: int | None
    recognised: tuple[str, ...] = ()
    suppressed_by: str | None = None
    face_status: FaceStatus = "none"


def _extract_object_type(det: Any) -> str | None:
    if isinstance(det, Mapping):
        val = det.get("object_type")
    else:
        val = getattr(det, "object_type", None)
    return str(val).lower() if val else None


def _extract_event_verdict_and_score(
    event: Any,
    verdict: str | None,
    risk_score: int | None,
) -> tuple[str | None, int | None]:
    resolved_verdict = verdict
    resolved_score = risk_score
    if event is not None:
        if resolved_score is None:
            raw_score = (
                event.get("risk_score")
                if isinstance(event, Mapping)
                else getattr(event, "risk_score", None)
            )
            if raw_score is not None:
                resolved_score = int(raw_score)
        if resolved_verdict is None:
            if isinstance(event, Mapping):
                resolved_verdict = event.get("verdict")
            else:
                verifs = getattr(event, "__dict__", {}).get("verifications")
                if isinstance(verifs, list) and verifs:
                    latest = max(
                        verifs,
                        key=lambda r: (
                            getattr(r, "created_at", None) is not None,
                            getattr(r, "id", 0),
                        ),
                    )
                    resolved_verdict = getattr(latest, "verdict", None)
                else:
                    resolved_verdict = getattr(event, "verdict", None)
    return resolved_verdict, resolved_score


def resolve(
    event: Any = None,
    detections: Sequence[Any] = (),
    specialists: SpecialistEvidence | None = None,
    *,
    verdict: str | None = None,
    risk_score: int | None = None,
    cloud_verdict: tuple[VerdictKind, int] | None = None,
) -> ResolvedVerdict:
    """Resolve the verdict source, verdict value, recognised names, and trusted suppression."""
    spec = specialists or SpecialistEvidence()
    raw_verdict, raw_score = _extract_event_verdict_and_score(event, verdict, risk_score)
    event_source = (
        event.get("source") if isinstance(event, Mapping) else getattr(event, "source", None)
    )

    # Step 1 -> 2 -> 3 chain: local VLM -> cloud VLM slot -> detector fallback, plus external (B4.7)
    source: VerdictSource
    final_verdict: VerdictKind | None
    final_score: int | None

    if str(event_source or "").lower() == "external":
        source = "external"
        final_verdict = None
        if raw_score is not None:
            final_score = int(raw_score)
        else:
            raw_level = (
                event.get("risk_level")
                if isinstance(event, Mapping)
                else getattr(event, "risk_level", None)
            )
            final_score = external_severity_top_score(raw_level)
    elif raw_verdict in ("confirmed", "uncertain", "rejected") and raw_score is not None:
        source = "local"
        final_verdict = raw_verdict  # type: ignore[assignment]
        final_score = int(raw_score)
    elif cloud_verdict is not None:
        source = "cloud"
        final_verdict, final_score = cloud_verdict
    elif raw_score is not None and raw_verdict != "verification_failed":
        # Legacy scored event with no verification row
        source = "local"
        final_verdict = None
        final_score = int(raw_score)
    else:
        source = "detector"
        final_verdict = None
        final_score = None

    # Recognition and F1 trusted-match suppression check
    recognised_names: list[str] = []
    trusted_legs: list[str] = []
    has_unknown_face = False
    has_any_face = len(spec.faces) > 0

    for fc in spec.faces:
        if fc.is_unknown or not fc.person_name:
            has_unknown_face = True
            continue
        if fc.person_name not in recognised_names:
            recognised_names.append(fc.person_name)
        if fc.is_trusted:
            trusted_legs.append(f"{fc.person_name} (face)")
        else:
            has_unknown_face = True

    for rc in spec.reid:
        if rc.member_name and rc.member_name not in recognised_names:
            recognised_names.append(rc.member_name)
        if rc.is_trusted:
            trusted_legs.append(f"{rc.member_name} (reid)")

    person_count = sum(1 for d in detections if _extract_object_type(d) == "person")
    trusted_face_count = sum(1 for fc in spec.faces if fc.is_trusted)
    trusted_reid_count = sum(1 for rc in spec.reid if rc.is_trusted)
    trusted_covered_count = max(trusted_face_count, trusted_reid_count)

    suppressed_by: str | None = None
    if (
        person_count > 0
        and not has_unknown_face
        and trusted_covered_count >= person_count
        and trusted_legs
    ):
        suppressed_by = ", ".join(dict.fromkeys(trusted_legs))

    if suppressed_by is not None:
        face_status: FaceStatus = "trusted"
    elif has_unknown_face or (
        person_count > 0 and trusted_covered_count < person_count and (has_any_face or spec.reid)
    ):
        face_status = "unknown"
    else:
        face_status = "none"

    return ResolvedVerdict(
        source=source,
        verdict=final_verdict,
        risk_score=final_score,
        recognised=tuple(recognised_names),
        suppressed_by=suppressed_by,
        face_status=face_status,
    )
