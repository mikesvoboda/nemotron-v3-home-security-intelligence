"""Integration tests for CalibrationService and SeverityService integration.

Tests the complete flow from user feedback through calibration adjustment
to severity classification, ensuring that personalized thresholds are
correctly applied when classifying risk scores.

This test file verifies acceptance criteria for NEM-2318:
- SeverityService uses CalibrationService for thresholds
- Risk classification respects personalized thresholds
- Response includes is_calibrated flag
- Default thresholds used when no calibration exists
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.enums import Severity
from backend.services.calibration_service import (
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_MEDIUM_THRESHOLD,
    CalibrationService,
    CalibrationThresholds,
    reset_calibration_service,
)
from backend.services.severity import (
    SeverityService,
    reset_severity_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def calibration_service() -> CalibrationService:
    """Create a fresh CalibrationService instance."""
    reset_calibration_service()
    return CalibrationService()


@pytest.fixture
def severity_service() -> SeverityService:
    """Create a fresh SeverityService instance."""
    reset_severity_service()
    return SeverityService()


# =============================================================================
# Integration Tests: Feedback -> Calibration -> Classification Flow
# =============================================================================


class TestFeedbackCalibrationClassificationFlow:
    """Integration tests for the complete feedback to classification flow."""

    @pytest.mark.asyncio
    async def test_uncalibrated_user_gets_default_thresholds(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        severity_service: SeverityService,
    ) -> None:
        """Test that a user with no calibration uses default thresholds."""
        # Classify risk for a user with no calibration record
        result = await severity_service.classify_risk(
            db_session,
            score=45,  # Would be MEDIUM with defaults
            user_id="new_user_no_calibration",
            calibration_service=calibration_service,
        )

        assert result.severity == Severity.MEDIUM
        assert result.is_calibrated is False

    @pytest.mark.asyncio
    async def test_user_with_calibration_but_no_feedback_not_calibrated(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        severity_service: SeverityService,
    ) -> None:
        """Test that a user with calibration record but no feedback is not calibrated."""
        # Create a calibration record without any feedback
        calibration = await calibration_service.get_or_create_calibration(
            db_session, user_id="user_no_feedback"
        )
        assert calibration.false_positive_count == 0
        assert calibration.missed_threat_count == 0

        # Classify risk - should show is_calibrated=False
        result = await severity_service.classify_risk(
            db_session,
            score=45,
            user_id="user_no_feedback",
            calibration_service=calibration_service,
        )

        assert result.severity == Severity.MEDIUM
        assert result.is_calibrated is False

    @pytest.mark.asyncio
    async def test_user_with_feedback_is_calibrated(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        severity_service: SeverityService,
    ) -> None:
        """Test that a user with feedback history is marked as calibrated."""
        # Create calibration and manually set feedback count
        calibration = await calibration_service.get_or_create_calibration(
            db_session, user_id="user_with_feedback"
        )
        calibration.false_positive_count = 3
        await db_session.flush()

        # Classify risk - should show is_calibrated=True
        result = await severity_service.classify_risk(
            db_session,
            score=45,
            user_id="user_with_feedback",
            calibration_service=calibration_service,
        )

        assert result.is_calibrated is True

    @pytest.mark.asyncio
    async def test_calibrated_thresholds_change_classification(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        severity_service: SeverityService,
    ) -> None:
        """Test that calibrated thresholds change severity classification."""
        user_id = "user_custom_thresholds"

        # Create calibration with custom thresholds (more sensitive)
        calibration = await calibration_service.get_or_create_calibration(
            db_session, user_id=user_id
        )

        # Manually adjust thresholds to be more sensitive
        # Default: LOW < 30, MEDIUM < 60, HIGH < 85
        # Custom: LOW < 20, MEDIUM < 45, HIGH < 70
        calibration.low_threshold = 20
        calibration.medium_threshold = 45
        calibration.high_threshold = 70
        calibration.false_positive_count = 1  # Mark as calibrated
        await db_session.flush()

        # Test score that would be LOW with defaults but MEDIUM with custom
        result = await severity_service.classify_risk(
            db_session,
            score=25,  # 25 >= 20 but < 45 -> MEDIUM with custom, but LOW with defaults
            user_id=user_id,
            calibration_service=calibration_service,
        )
        assert result.severity == Severity.MEDIUM
        assert result.is_calibrated is True

        # Test score that would be MEDIUM with defaults but HIGH with custom
        result = await severity_service.classify_risk(
            db_session,
            score=50,  # 50 >= 45 but < 70 -> HIGH with custom, MEDIUM with defaults
            user_id=user_id,
            calibration_service=calibration_service,
        )
        assert result.severity == Severity.HIGH
        assert result.is_calibrated is True

        # Test score that would be HIGH with defaults but CRITICAL with custom
        result = await severity_service.classify_risk(
            db_session,
            score=75,  # 75 >= 70 -> CRITICAL with custom, HIGH with defaults
            user_id=user_id,
            calibration_service=calibration_service,
        )
        assert result.severity == Severity.CRITICAL
        assert result.is_calibrated is True

    @pytest.mark.asyncio
    async def test_different_users_have_independent_calibrations(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        severity_service: SeverityService,
    ) -> None:
        """Test that different users have independent calibration settings."""
        # User A: more sensitive (lower thresholds)
        calibration_a = await calibration_service.get_or_create_calibration(
            db_session, user_id="user_a"
        )
        calibration_a.low_threshold = 15
        calibration_a.medium_threshold = 40
        calibration_a.high_threshold = 65
        calibration_a.false_positive_count = 1
        await db_session.flush()

        # User B: less sensitive (higher thresholds)
        calibration_b = await calibration_service.get_or_create_calibration(
            db_session, user_id="user_b"
        )
        calibration_b.low_threshold = 40
        calibration_b.medium_threshold = 70
        calibration_b.high_threshold = 90
        calibration_b.false_positive_count = 1
        await db_session.flush()

        # Same score, different classifications
        score = 50

        # User A: 50 >= 40 and < 65 -> HIGH
        result_a = await severity_service.classify_risk(
            db_session,
            score=score,
            user_id="user_a",
            calibration_service=calibration_service,
        )
        assert result_a.severity == Severity.HIGH

        # User B: 50 >= 40 and < 70 -> MEDIUM
        result_b = await severity_service.classify_risk(
            db_session,
            score=score,
            user_id="user_b",
            calibration_service=calibration_service,
        )
        assert result_b.severity == Severity.MEDIUM


# =============================================================================
# Boundary Condition Tests
# =============================================================================


class TestCalibrationBoundaryConditions:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_classification_at_exact_threshold_boundaries(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        severity_service: SeverityService,
    ) -> None:
        """Test classification at exact threshold boundaries."""
        user_id = "boundary_test_user"

        calibration = await calibration_service.get_or_create_calibration(
            db_session, user_id=user_id
        )
        calibration.low_threshold = 25
        calibration.medium_threshold = 50
        calibration.high_threshold = 75
        calibration.false_positive_count = 1
        await db_session.flush()

        # Score = 24 (just below low_threshold) -> LOW
        result = await severity_service.classify_risk(
            db_session, score=24, user_id=user_id, calibration_service=calibration_service
        )
        assert result.severity == Severity.LOW

        # Score = 25 (at low_threshold) -> MEDIUM
        result = await severity_service.classify_risk(
            db_session, score=25, user_id=user_id, calibration_service=calibration_service
        )
        assert result.severity == Severity.MEDIUM

        # Score = 49 (just below medium_threshold) -> MEDIUM
        result = await severity_service.classify_risk(
            db_session, score=49, user_id=user_id, calibration_service=calibration_service
        )
        assert result.severity == Severity.MEDIUM

        # Score = 50 (at medium_threshold) -> HIGH
        result = await severity_service.classify_risk(
            db_session, score=50, user_id=user_id, calibration_service=calibration_service
        )
        assert result.severity == Severity.HIGH

        # Score = 74 (just below high_threshold) -> HIGH
        result = await severity_service.classify_risk(
            db_session, score=74, user_id=user_id, calibration_service=calibration_service
        )
        assert result.severity == Severity.HIGH

        # Score = 75 (at high_threshold) -> CRITICAL
        result = await severity_service.classify_risk(
            db_session, score=75, user_id=user_id, calibration_service=calibration_service
        )
        assert result.severity == Severity.CRITICAL

    @pytest.mark.asyncio
    async def test_extreme_threshold_values(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        severity_service: SeverityService,
    ) -> None:
        """Test classification with extreme threshold values."""
        user_id = "extreme_threshold_user"

        # Create calibration with very tight thresholds at low end
        calibration = await calibration_service.get_or_create_calibration(
            db_session, user_id=user_id
        )
        calibration.low_threshold = 5
        calibration.medium_threshold = 10
        calibration.high_threshold = 15
        calibration.false_positive_count = 1
        await db_session.flush()

        # Most scores should be CRITICAL
        result = await severity_service.classify_risk(
            db_session, score=50, user_id=user_id, calibration_service=calibration_service
        )
        assert result.severity == Severity.CRITICAL

        # Only very low scores are LOW
        result = await severity_service.classify_risk(
            db_session, score=4, user_id=user_id, calibration_service=calibration_service
        )
        assert result.severity == Severity.LOW

    @pytest.mark.asyncio
    async def test_score_zero_always_low(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        severity_service: SeverityService,
    ) -> None:
        """Test that score 0 is always classified as LOW regardless of calibration."""
        user_id = "zero_score_user"

        # Create calibration with low_threshold > 0
        calibration = await calibration_service.get_or_create_calibration(
            db_session, user_id=user_id
        )
        calibration.low_threshold = 10
        calibration.false_positive_count = 1
        await db_session.flush()

        result = await severity_service.classify_risk(
            db_session, score=0, user_id=user_id, calibration_service=calibration_service
        )
        assert result.severity == Severity.LOW

    @pytest.mark.asyncio
    async def test_score_100_always_critical(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        severity_service: SeverityService,
    ) -> None:
        """Test that score 100 is classified correctly (depends on high_threshold)."""
        user_id = "max_score_user"

        # Create calibration with high_threshold at 99
        calibration = await calibration_service.get_or_create_calibration(
            db_session, user_id=user_id
        )
        calibration.high_threshold = 99
        calibration.false_positive_count = 1
        await db_session.flush()

        result = await severity_service.classify_risk(
            db_session, score=100, user_id=user_id, calibration_service=calibration_service
        )
        assert result.severity == Severity.CRITICAL


# =============================================================================
# CalibrationThresholds Response Tests
# =============================================================================


class TestCalibrationThresholdsResponse:
    """Tests for CalibrationThresholds response structure."""

    @pytest.mark.asyncio
    async def test_get_thresholds_returns_correct_structure(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
    ) -> None:
        """Test that get_thresholds returns CalibrationThresholds with all fields."""
        thresholds = await calibration_service.get_thresholds(db_session, user_id="test_user")

        assert isinstance(thresholds, CalibrationThresholds)
        assert isinstance(thresholds.low_threshold, int)
        assert isinstance(thresholds.medium_threshold, int)
        assert isinstance(thresholds.high_threshold, int)
        assert isinstance(thresholds.is_calibrated, bool)

    @pytest.mark.asyncio
    async def test_get_thresholds_default_values_for_new_user(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
    ) -> None:
        """Test that get_thresholds returns defaults for user without calibration."""
        thresholds = await calibration_service.get_thresholds(db_session, user_id="brand_new_user")

        assert thresholds.low_threshold == DEFAULT_LOW_THRESHOLD
        assert thresholds.medium_threshold == DEFAULT_MEDIUM_THRESHOLD
        assert thresholds.high_threshold == DEFAULT_HIGH_THRESHOLD
        assert thresholds.is_calibrated is False

    @pytest.mark.asyncio
    async def test_get_thresholds_reflects_calibration_changes(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
    ) -> None:
        """Test that get_thresholds reflects changes to calibration record."""
        user_id = "calibration_change_user"

        # Get initial thresholds (defaults)
        thresholds1 = await calibration_service.get_thresholds(db_session, user_id=user_id)
        assert thresholds1.low_threshold == DEFAULT_LOW_THRESHOLD

        # Create and modify calibration
        calibration = await calibration_service.get_or_create_calibration(
            db_session, user_id=user_id
        )
        calibration.low_threshold = 25
        calibration.missed_threat_count = 2
        await db_session.flush()

        # Get updated thresholds
        thresholds2 = await calibration_service.get_thresholds(db_session, user_id=user_id)
        assert thresholds2.low_threshold == 25
        assert thresholds2.is_calibrated is True
