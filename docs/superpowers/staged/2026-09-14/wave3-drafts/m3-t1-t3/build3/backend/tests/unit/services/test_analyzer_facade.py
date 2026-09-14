"""Unit tests for AnalyzerServiceFacade (NEM-3150).

Tests the service facade pattern that reduces direct service dependencies
in the NemotronAnalyzer class.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.analyzer_facade import (
    AnalyzerServiceFacade,
    get_analyzer_facade,
    reset_analyzer_facade,
)


@pytest.fixture(autouse=True)
def reset_facade():
    """Reset the facade singleton before and after each test."""
    reset_analyzer_facade()
    yield
    reset_analyzer_facade()


class TestAnalyzerServiceFacade:
    """Tests for the AnalyzerServiceFacade class."""

    def test_get_context_enricher_creates_singleton(self):
        """Test that get_context_enricher creates and caches the enricher."""
        facade = AnalyzerServiceFacade()

        with patch("backend.services.context_enricher.get_context_enricher") as mock_get:
            mock_enricher = MagicMock()
            mock_get.return_value = mock_enricher

            # First call should create the enricher
            result1 = facade.get_context_enricher()
            assert result1 is mock_enricher
            mock_get.assert_called_once()

            # Second call should return cached instance
            result2 = facade.get_context_enricher()
            assert result2 is mock_enricher
            assert mock_get.call_count == 1  # Still only one call

    def test_get_context_enricher_uses_existing(self):
        """Test that get_context_enricher returns pre-configured enricher."""
        mock_enricher = MagicMock()
        facade = AnalyzerServiceFacade(_context_enricher=mock_enricher)

        result = facade.get_context_enricher()

        assert result is mock_enricher

    def test_get_household_matcher_creates_singleton(self):
        """Test that get_household_matcher creates and caches the matcher."""
        facade = AnalyzerServiceFacade()

        with patch("backend.services.household_matcher.get_household_matcher") as mock_get:
            mock_matcher = MagicMock()
            mock_get.return_value = mock_matcher

            result1 = facade.get_household_matcher()
            assert result1 is mock_matcher
            mock_get.assert_called_once()

            result2 = facade.get_household_matcher()
            assert result2 is mock_matcher
            assert mock_get.call_count == 1

    def test_get_enrichment_pipeline_creates_singleton(self):
        """Test that get_enrichment_pipeline creates and caches the pipeline."""
        facade = AnalyzerServiceFacade()

        with patch("backend.services.enrichment_pipeline.get_enrichment_pipeline") as mock_get:
            mock_pipeline = MagicMock()
            mock_get.return_value = mock_pipeline

            result1 = facade.get_enrichment_pipeline()
            assert result1 is mock_pipeline
            mock_get.assert_called_once()

            result2 = facade.get_enrichment_pipeline()
            assert result2 is mock_pipeline
            assert mock_get.call_count == 1

    @pytest.mark.asyncio
    async def test_get_cache_service_creates_singleton(self):
        """Test that get_cache_service creates and caches the service."""
        facade = AnalyzerServiceFacade()

        with patch("backend.services.cache_service.get_cache_service") as mock_get:
            mock_cache = AsyncMock()
            mock_get.return_value = mock_cache

            result1 = await facade.get_cache_service()
            assert result1 is mock_cache
            mock_get.assert_called_once()

            result2 = await facade.get_cache_service()
            assert result2 is mock_cache
            assert mock_get.call_count == 1

    def test_get_inference_semaphore_creates_singleton(self):
        """Test that get_inference_semaphore creates and caches the semaphore."""
        facade = AnalyzerServiceFacade()

        with patch("backend.services.inference_semaphore.get_inference_semaphore") as mock_get:
            mock_semaphore = asyncio.Semaphore(4)
            mock_get.return_value = mock_semaphore

            result1 = facade.get_inference_semaphore()
            assert result1 is mock_semaphore
            mock_get.assert_called_once()

            result2 = facade.get_inference_semaphore()
            assert result2 is mock_semaphore
            assert mock_get.call_count == 1

    def test_get_cost_tracker_creates_singleton(self):
        """Test that get_cost_tracker creates and caches the tracker."""
        facade = AnalyzerServiceFacade()

        with patch("backend.services.cost_tracker.get_cost_tracker") as mock_get:
            mock_tracker = MagicMock()
            mock_get.return_value = mock_tracker

            result1 = facade.get_cost_tracker()
            assert result1 is mock_tracker
            mock_get.assert_called_once()

            result2 = facade.get_cost_tracker()
            assert result2 is mock_tracker
            assert mock_get.call_count == 1

    def test_get_prompt_auto_tuner_creates_singleton(self):
        """Test that get_prompt_auto_tuner creates and caches the tuner."""
        facade = AnalyzerServiceFacade()

        with patch("backend.services.prompt_auto_tuner.get_prompt_auto_tuner") as mock_get:
            mock_tuner = MagicMock()
            mock_get.return_value = mock_tuner

            result1 = facade.get_prompt_auto_tuner()
            assert result1 is mock_tuner
            mock_get.assert_called_once()

            result2 = facade.get_prompt_auto_tuner()
            assert result2 is mock_tuner
            assert mock_get.call_count == 1

    @pytest.mark.asyncio
    async def test_fetch_detections_delegates_to_batch_fetch(self):
        """Test that fetch_detections delegates to batch_fetch_detections."""
        facade = AnalyzerServiceFacade()
        mock_session = AsyncMock()
        detection_ids = [1, 2, 3]
        mock_detections = [MagicMock() for _ in range(3)]

        with patch("backend.services.batch_fetch.batch_fetch_detections") as mock_fetch:
            mock_fetch.return_value = mock_detections

            result = await facade.fetch_detections(mock_session, detection_ids)

            assert result is mock_detections
            mock_fetch.assert_called_once_with(mock_session, detection_ids)


class TestModuleLevelFunctions:
    """Tests for module-level facade functions."""

    def test_get_analyzer_facade_creates_singleton(self):
        """Test that get_analyzer_facade returns a singleton."""
        facade1 = get_analyzer_facade()
        facade2 = get_analyzer_facade()

        assert facade1 is facade2
        assert isinstance(facade1, AnalyzerServiceFacade)

    def test_reset_analyzer_facade_clears_singleton(self):
        """Test that reset_analyzer_facade clears the singleton."""
        facade1 = get_analyzer_facade()
        reset_analyzer_facade()
        facade2 = get_analyzer_facade()

        assert facade1 is not facade2

    def test_facade_can_be_injected_with_pre_configured_services(self):
        """Test that facade can be created with pre-configured services."""
        mock_enricher = MagicMock()
        mock_pipeline = MagicMock()
        mock_matcher = MagicMock()

        facade = AnalyzerServiceFacade(
            _context_enricher=mock_enricher,
            _enrichment_pipeline=mock_pipeline,
            _household_matcher=mock_matcher,
        )

        assert facade.get_context_enricher() is mock_enricher
        assert facade.get_enrichment_pipeline() is mock_pipeline
        assert facade.get_household_matcher() is mock_matcher
