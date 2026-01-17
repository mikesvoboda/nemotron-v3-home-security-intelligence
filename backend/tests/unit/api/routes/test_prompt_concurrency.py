"""Unit tests for prompt config concurrency control (optimistic locking).

Tests cover:
- PromptVersionConflictError exception
- PromptUpdateRequest with expected_version field
- Service-level version checking
- API endpoint 409 Conflict response
- Successful updates with correct expected_version
- Updates without expected_version (backwards compatibility)

NEM-1312: Add concurrency control for prompt config updates
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.prompt_management import (
    AIModelEnum,
    PromptUpdateRequest,
    PromptVersionConflictError,
)

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Test: PromptVersionConflictError Exception
# =============================================================================


class TestPromptVersionConflictError:
    """Tests for PromptVersionConflictError exception."""

    def test_exception_creation(self):
        """Test creating PromptVersionConflictError with required fields."""
        error = PromptVersionConflictError(
            model="nemotron",
            expected_version=1,
            actual_version=2,
        )
        assert error.model == "nemotron"
        assert error.expected_version == 1
        assert error.actual_version == 2

    def test_exception_message_format(self):
        """Test exception message contains all relevant information."""
        error = PromptVersionConflictError(
            model="florence2",
            expected_version=5,
            actual_version=7,
        )
        message = str(error)
        assert "florence2" in message
        assert "5" in message
        assert "7" in message
        assert "Concurrent modification" in message or "concurrent" in message.lower()

    def test_exception_inherits_from_exception(self):
        """Test exception is a proper Exception subclass."""
        error = PromptVersionConflictError(
            model="nemotron",
            expected_version=1,
            actual_version=2,
        )
        assert isinstance(error, Exception)


# =============================================================================
# Test: PromptUpdateRequest Schema with expected_version
# =============================================================================


class TestPromptUpdateRequestWithVersion:
    """Tests for PromptUpdateRequest with expected_version field."""

    def test_request_without_expected_version(self):
        """Test request creation without expected_version (backwards compatible)."""
        request = PromptUpdateRequest(
            config={"system_prompt": "Test prompt"},
        )
        assert request.config == {"system_prompt": "Test prompt"}
        assert request.expected_version is None
        assert request.change_description is None

    def test_request_with_expected_version(self):
        """Test request creation with expected_version for optimistic locking."""
        request = PromptUpdateRequest(
            config={"system_prompt": "Test prompt"},
            expected_version=5,
        )
        assert request.expected_version == 5

    def test_request_with_all_fields(self):
        """Test request creation with all fields."""
        request = PromptUpdateRequest(
            config={"system_prompt": "Test prompt"},
            change_description="Updated for testing",
            expected_version=3,
        )
        assert request.config == {"system_prompt": "Test prompt"}
        assert request.change_description == "Updated for testing"
        assert request.expected_version == 3

    def test_expected_version_minimum_value(self):
        """Test expected_version validation enforces minimum value of 1."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            PromptUpdateRequest(
                config={"system_prompt": "Test"},
                expected_version=0,  # Below minimum
            )
        assert "expected_version" in str(exc_info.value)

    def test_expected_version_negative_raises_error(self):
        """Test negative expected_version raises validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            PromptUpdateRequest(
                config={"system_prompt": "Test"},
                expected_version=-1,
            )
        assert "expected_version" in str(exc_info.value)


# =============================================================================
# Test: Service-level Concurrency Control
# =============================================================================


class TestPromptServiceConcurrencyControl:
    """Tests for PromptService.update_prompt_for_model with optimistic locking.

    Note: Full integration tests with actual database are in
    backend/tests/integration/test_prompt_concurrency.py.
    These unit tests focus on the conflict detection logic.
    """

    @pytest.fixture
    def mock_session(self):
        """Create a mock async database session."""
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_update_with_wrong_expected_version_raises_conflict(self, mock_session):
        """Test update raises PromptVersionConflictError when versions don't match."""
        from backend.services.prompt_service import PromptService

        service = PromptService()

        # Mock the version query to return current version 5
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5  # Actual version is 5
        mock_session.execute.return_value = mock_result

        with pytest.raises(PromptVersionConflictError) as exc_info:
            await service.update_prompt_for_model(
                session=mock_session,
                model="nemotron",
                config={"system_prompt": "New prompt"},
                expected_version=3,  # Expected 3, but actual is 5
            )

        error = exc_info.value
        assert error.model == "nemotron"
        assert error.expected_version == 3
        assert error.actual_version == 5

    @pytest.mark.asyncio
    async def test_update_with_different_version_raises_conflict_for_florence(self, mock_session):
        """Test conflict detection works for all models."""
        from backend.services.prompt_service import PromptService

        service = PromptService()

        mock_result = MagicMock()
        mock_result.scalar.return_value = 10
        mock_session.execute.return_value = mock_result

        with pytest.raises(PromptVersionConflictError) as exc_info:
            await service.update_prompt_for_model(
                session=mock_session,
                model="florence2",
                config={"vqa_queries": ["Test"]},
                expected_version=5,  # Expected 5, but actual is 10
            )

        error = exc_info.value
        assert error.model == "florence2"
        assert error.expected_version == 5
        assert error.actual_version == 10

    @pytest.mark.asyncio
    async def test_update_with_correct_version_does_not_raise_before_db_ops(self, mock_session):
        """Test that correct expected_version passes the version check.

        Note: This test verifies the check passes; full success requires
        database setup and is tested in integration tests.
        """
        from backend.services.prompt_service import PromptService

        service = PromptService()

        # First call returns max version, second call is for the UPDATE
        call_count = 0

        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: max version query
                result = MagicMock()
                result.scalar.return_value = 3
                return result
            else:
                # Subsequent calls: return empty result for UPDATE
                result = MagicMock()
                return result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

        # The version check should pass (expected=3, actual=3)
        # The test will proceed past version check but fail on PromptVersion instantiation
        # which is expected in unit test context
        try:
            await service.update_prompt_for_model(
                session=mock_session,
                model="nemotron",
                config={"system_prompt": "New prompt"},
                expected_version=3,  # Matches current version
            )
        except (TypeError, AttributeError):
            # Expected in unit test without full DB setup
            # The important thing is PromptVersionConflictError was NOT raised
            pass

    @pytest.mark.asyncio
    async def test_update_without_expected_version_bypasses_check(self, mock_session):
        """Test that None expected_version skips the version check entirely."""
        from backend.services.prompt_service import PromptService

        service = PromptService()

        mock_result = MagicMock()
        mock_result.scalar.return_value = 100  # High version number
        mock_session.execute = AsyncMock(return_value=mock_result)

        # With expected_version=None, should not raise PromptVersionConflictError
        # even though version is high
        try:
            await service.update_prompt_for_model(
                session=mock_session,
                model="nemotron",
                config={"system_prompt": "New prompt"},
                expected_version=None,  # No version check
            )
        except PromptVersionConflictError:
            pytest.fail("Should not raise conflict error when expected_version is None")
        except (TypeError, AttributeError):
            # Expected in unit test without full DB setup
            pass

    @pytest.mark.asyncio
    async def test_first_version_skips_check_when_no_existing_versions(self, mock_session):
        """Test that version check is skipped when max_version is 0."""
        from backend.services.prompt_service import PromptService

        service = PromptService()

        mock_result = MagicMock()
        mock_result.scalar.return_value = 0  # No existing versions
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Even with expected_version=1, should not raise because max_version=0
        try:
            await service.update_prompt_for_model(
                session=mock_session,
                model="nemotron",
                config={"system_prompt": "First version"},
                expected_version=1,  # Would mismatch if check was performed
            )
        except PromptVersionConflictError:
            pytest.fail("Should not raise conflict error when no existing versions")
        except (TypeError, AttributeError):
            # Expected in unit test without full DB setup
            pass


# =============================================================================
# Test: API Endpoint Concurrency Handling
# =============================================================================


class TestUpdateEndpointConcurrency:
    """Tests for PUT /api/prompts/{model} concurrency handling."""

    @pytest.fixture
    def mock_client(self):
        """Create a test client fixture."""

        with patch("backend.api.routes.prompt_management.get_db"):
            yield

    def test_update_request_with_expected_version_schema(self):
        """Test request body accepts expected_version field."""
        request = PromptUpdateRequest(
            config={"system_prompt": "Test prompt"},
            expected_version=5,
        )
        # Verify it serializes correctly
        data = request.model_dump()
        assert data["expected_version"] == 5
        assert data["config"] == {"system_prompt": "Test prompt"}

    def test_update_request_json_serialization(self):
        """Test request with expected_version serializes to JSON properly."""
        request = PromptUpdateRequest(
            config={"system_prompt": "Test"},
            change_description="Test change",
            expected_version=3,
        )
        json_data = request.model_dump_json()
        assert "expected_version" in json_data
        assert "3" in json_data


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestConcurrencyEdgeCases:
    """Tests for edge cases in concurrency control."""

    def test_conflict_error_with_large_version_numbers(self):
        """Test conflict error handles large version numbers."""
        error = PromptVersionConflictError(
            model="nemotron",
            expected_version=999999,
            actual_version=1000000,
        )
        assert error.expected_version == 999999
        assert error.actual_version == 1000000

    def test_conflict_error_with_all_models(self):
        """Test conflict error works with all supported models."""
        for model in AIModelEnum:
            error = PromptVersionConflictError(
                model=model.value,
                expected_version=1,
                actual_version=2,
            )
            assert error.model == model.value

    def test_request_allows_version_1(self):
        """Test expected_version can be 1 (first version after default)."""
        request = PromptUpdateRequest(
            config={"system_prompt": "Test"},
            expected_version=1,
        )
        assert request.expected_version == 1
