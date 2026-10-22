"""Unit tests for backend.services.alerting.verdict (B4.1)."""

from __future__ import annotations

from types import SimpleNamespace

from backend.services.alerting.verdict import (
    FaceCandidate,
    ReidCandidate,
    ResolvedVerdict,
    SpecialistEvidence,
    external_severity_top_score,
    resolve,
)


def test_local_confirmed_verdict_resolves_local_source() -> None:
    res = resolve(
        verdict="confirmed",
        risk_score=82,
        detections=[{"id": 1, "object_type": "person", "confidence": 0.92}],
        specialists=SpecialistEvidence(),
    )
    assert res == ResolvedVerdict(
        source="local",
        verdict="confirmed",
        risk_score=82,
        recognised=(),
        suppressed_by=None,
        face_status="none",
    )


def test_vlm_failure_falls_back_to_detector_source() -> None:
    res = resolve(
        verdict="verification_failed",
        risk_score=None,
        detections=[{"id": 1, "object_type": "person", "confidence": 0.91}],
        specialists=SpecialistEvidence(),
    )
    assert res.source == "detector"
    assert res.verdict is None
    assert res.risk_score is None
    assert res.suppressed_by is None


def test_trusted_household_face_covering_every_person_suppresses() -> None:
    res = resolve(
        verdict="confirmed",
        risk_score=80,
        detections=[{"id": 1, "object_type": "person", "confidence": 0.95}],
        specialists=SpecialistEvidence(
            faces=(
                FaceCandidate(
                    person_name="Alice",
                    is_household_member=True,
                    is_auto_enrolled=False,
                    is_unknown=False,
                ),
            ),
        ),
    )
    assert res.suppressed_by == "Alice (face)"
    assert res.recognised == ("Alice",)
    assert res.face_status == "trusted"


def test_trusted_full_reid_covering_every_person_suppresses_when_no_unknown_face() -> None:
    res = resolve(
        verdict="confirmed",
        risk_score=75,
        detections=[{"id": 1, "object_type": "person", "confidence": 0.90}],
        specialists=SpecialistEvidence(
            reid=(
                ReidCandidate(
                    member_name="Bob",
                    trust_level="full",
                ),
            ),
        ),
    )
    assert res.suppressed_by == "Bob (reid)"
    assert res.recognised == ("Bob",)


def test_mixed_group_with_one_household_face_stays_unverified() -> None:
    """Two persons detected, only one trusted face match -> must NOT suppress (F1)."""
    res = resolve(
        verdict="confirmed",
        risk_score=85,
        detections=[
            {"id": 1, "object_type": "person", "confidence": 0.95},
            {"id": 2, "object_type": "person", "confidence": 0.88},
        ],
        specialists=SpecialistEvidence(
            faces=(
                FaceCandidate(
                    person_name="Alice",
                    is_household_member=True,
                    is_auto_enrolled=False,
                    is_unknown=False,
                ),
            ),
        ),
    )
    assert res.suppressed_by is None
    assert res.recognised == ("Alice",)
    assert res.face_status == "unknown"


def test_unknown_face_alongside_trusted_match_prevents_suppression() -> None:
    res = resolve(
        verdict="confirmed",
        risk_score=85,
        detections=[{"id": 1, "object_type": "person", "confidence": 0.95}],
        specialists=SpecialistEvidence(
            faces=(
                FaceCandidate(
                    person_name="Alice",
                    is_household_member=True,
                    is_auto_enrolled=False,
                    is_unknown=False,
                ),
                FaceCandidate(
                    person_name=None,
                    is_household_member=False,
                    is_auto_enrolled=False,
                    is_unknown=True,
                ),
            ),
        ),
    )
    assert res.suppressed_by is None
    assert res.recognised == ("Alice",)
    assert res.face_status == "unknown"


def test_auto_enrolled_or_non_household_or_partial_trust_stays_unverified() -> None:
    # Auto-enrolled face match
    res_auto = resolve(
        verdict="confirmed",
        risk_score=80,
        detections=[{"id": 1, "object_type": "person", "confidence": 0.95}],
        specialists=SpecialistEvidence(
            faces=(
                FaceCandidate(
                    person_name="Stranger1",
                    is_household_member=True,
                    is_auto_enrolled=True,
                    is_unknown=False,
                ),
            ),
        ),
    )
    assert res_auto.suppressed_by is None
    assert res_auto.recognised == ("Stranger1",)

    # Non-household known person
    res_visitor = resolve(
        verdict="confirmed",
        risk_score=80,
        detections=[{"id": 1, "object_type": "person", "confidence": 0.95}],
        specialists=SpecialistEvidence(
            faces=(
                FaceCandidate(
                    person_name="Courier",
                    is_household_member=False,
                    is_auto_enrolled=False,
                    is_unknown=False,
                ),
            ),
        ),
    )
    assert res_visitor.suppressed_by is None
    assert res_visitor.recognised == ("Courier",)

    # Partial / monitor trust re-ID
    for trust in ("partial", "monitor"):
        res_reid = resolve(
            verdict="confirmed",
            risk_score=80,
            detections=[{"id": 1, "object_type": "person", "confidence": 0.95}],
            specialists=SpecialistEvidence(
                reid=(ReidCandidate(member_name="Gardener", trust_level=trust),),
            ),
        )
        assert res_reid.suppressed_by is None
        assert res_reid.recognised == ("Gardener",)


def test_external_severity_top_score_and_external_event_resolution() -> None:
    low_score = external_severity_top_score("low")
    med_score = external_severity_top_score("medium")
    high_score = external_severity_top_score("high")
    crit_score = external_severity_top_score("critical")
    assert 0 < low_score < med_score < high_score < crit_score == 100
    assert external_severity_top_score(None) == med_score
    assert external_severity_top_score("  LOW  ") == low_score
    assert external_severity_top_score("HIGH") == high_score

    # Dict external event with explicit risk_score
    res_dict = resolve(
        event={"source": "external", "risk_score": 44, "risk_level": "low"},
        detections=[],
    )
    assert res_dict.source == "external"
    assert res_dict.verdict is None
    assert res_dict.risk_score == 44

    # Object external event without risk_score derives score from risk_level
    ev_obj = SimpleNamespace(source="external", risk_score=None, risk_level="high")
    res_obj = resolve(event=ev_obj, detections=[])
    assert res_obj.source == "external"
    assert res_obj.verdict is None
    assert res_obj.risk_score == high_score


def test_resolve_extracts_from_event_object_verifications_and_cloud_and_legacy() -> None:
    # Object event with verifications list picks latest id
    v1 = SimpleNamespace(id=1, verdict="rejected")
    v2 = SimpleNamespace(id=5, verdict="uncertain")
    ev_with_verifs = SimpleNamespace(risk_score=61)
    ev_with_verifs.__dict__["verifications"] = [v1, v2]
    det_obj = SimpleNamespace(object_type="Person")
    res_v = resolve(event=ev_with_verifs, detections=[det_obj])
    assert res_v.source == "local"
    assert res_v.verdict == "uncertain"
    assert res_v.risk_score == 61

    # Object event with direct .verdict attribute
    ev_direct = SimpleNamespace(risk_score=30, verdict="rejected")
    res_d = resolve(event=ev_direct, detections=[])
    assert res_d.source == "local"
    assert res_d.verdict == "rejected"
    assert res_d.risk_score == 30

    # Cloud fallback
    res_cloud = resolve(
        verdict="verification_failed",
        risk_score=None,
        cloud_verdict=("confirmed", 91),
        detections=[],
    )
    assert res_cloud.source == "cloud"
    assert res_cloud.verdict == "confirmed"
    assert res_cloud.risk_score == 91

    # Legacy scored event without verdict
    res_legacy = resolve(
        event={"risk_score": 55},
        detections=[],
    )
    assert res_legacy.source == "local"
    assert res_legacy.verdict is None
    assert res_legacy.risk_score == 55
