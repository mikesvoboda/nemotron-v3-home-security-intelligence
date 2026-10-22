"""Unit tests for backend.services.alerting.verdict (B4.1)."""

from __future__ import annotations

from backend.services.alerting.verdict import (
    FaceCandidate,
    ReidCandidate,
    ResolvedVerdict,
    SpecialistEvidence,
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
