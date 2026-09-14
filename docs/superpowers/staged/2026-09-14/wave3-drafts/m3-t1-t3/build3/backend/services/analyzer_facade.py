"""Service facade for NemotronAnalyzer dependencies (NEM-3150).

This module provides a facade pattern to reduce direct service dependencies
in the NemotronAnalyzer class. Instead of importing 8+ services directly,
the analyzer can use this facade which provides lazy-loaded access to services.

Benefits:
- Reduces coupling between NemotronAnalyzer and individual services
- Simplifies testing by providing a single mock target
- Makes service dependencies explicit and documented
- Enables easier refactoring of underlying service implementations

Usage:
    # In NemotronAnalyzer
    from backend.services.analyzer_facade import (
        AnalyzerServiceFacade,
        get_analyzer_facade,
    )

    facade = get_analyzer_facade()
    enricher = facade.get_context_enricher()
    context = await enricher.enrich(batch_id, camera_id, detection_ids)
"""

__all__ = [
    "AnalyzerServiceFacade",
    "get_analyzer_facade",
    "reset_analyzer_facade",
]

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.models.detection import Detection
    from backend.services.cache_service import CacheService
    from backend.services.context_enricher import ContextEnricher
    from backend.services.cost_tracker import CostTracker
    from backend.services.enrichment_pipeline import EnrichmentPipeline
    from backend.services.household_matcher import HouseholdMatcher
    from backend.services.prompt_auto_tuner import PromptAutoTuner

logger = get_logger(__name__)


@dataclass
class AnalyzerServiceFacade:
    """Facade aggregating services used by NemotronAnalyzer.

    This class provides lazy-loaded access to the various services
    that NemotronAnalyzer depends on, reducing direct import dependencies
    from 8+ to 2-3.

    Services are lazily loaded to avoid import-time overhead and to
    support easier mocking in tests. Each getter returns the actual
    service instance, allowing the caller to use the service's full API.

    Attributes:
        _context_enricher: Optional pre-configured context enricher
        _enrichment_pipeline: Optional pre-configured enrichment pipeline
        _household_matcher: Optional pre-configured household matcher
        _cache_service: Optional pre-configured cache service
        _cost_tracker: Optional pre-configured cost tracker
        _prompt_auto_tuner: Optional pre-configured prompt auto tuner
        _inference_semaphore: Optional pre-configured inference semaphore
    """

    _context_enricher: ContextEnricher | None = field(default=None, repr=False)
    _enrichment_pipeline: EnrichmentPipeline | None = field(default=None, repr=False)
    _household_matcher: HouseholdMatcher | None = field(default=None, repr=False)
    _cache_service: CacheService | None = field(default=None, repr=False)
    _cost_tracker: CostTracker | None = field(default=None, repr=False)
    _prompt_auto_tuner: PromptAutoTuner | None = field(default=None, repr=False)
    _inference_semaphore: asyncio.Semaphore | None = field(default=None, repr=False)

    # =========================================================================
    # Context Enrichment Services
    # =========================================================================

    def get_context_enricher(self) -> ContextEnricher:
        """Get or create the context enricher service.

        Returns:
            ContextEnricher instance for adding zone, baseline, and
            cross-camera context to detections.
        """
        if self._context_enricher is None:
            from backend.services.context_enricher import (
                get_context_enricher as _get_context_enricher,
            )

            self._context_enricher = _get_context_enricher()
        return self._context_enricher

    # =========================================================================
    # Household Matching Services
    # =========================================================================

    def get_household_matcher(self) -> HouseholdMatcher:
        """Get or create the household matcher service.

        Returns:
            HouseholdMatcher instance for matching detected faces/features
            against household members.
        """
        if self._household_matcher is None:
            from backend.services.household_matcher import (
                get_household_matcher as _get_household_matcher,
            )

            self._household_matcher = _get_household_matcher()
        return self._household_matcher

    # =========================================================================
    # Enrichment Pipeline Services
    # =========================================================================

    def get_enrichment_pipeline(self) -> EnrichmentPipeline:
        """Get or create the enrichment pipeline service.

        Returns:
            EnrichmentPipeline instance for license plate, face, and
            OCR enrichment.
        """
        if self._enrichment_pipeline is None:
            from backend.services.enrichment_pipeline import (
                get_enrichment_pipeline as _get_enrichment_pipeline,
            )

            self._enrichment_pipeline = _get_enrichment_pipeline()
        return self._enrichment_pipeline

    # =========================================================================
    # Cache Services
    # =========================================================================

    async def get_cache_service(self) -> CacheService:
        """Get or create the cache service.

        Returns:
            CacheService instance for caching analysis results.
        """
        if self._cache_service is None:
            from backend.services.cache_service import (
                get_cache_service as _get_cache_service,
            )

            self._cache_service = await _get_cache_service()
        return self._cache_service

    # =========================================================================
    # Inference Control Services
    # =========================================================================

    def get_inference_semaphore(self) -> asyncio.Semaphore:
        """Get or create the inference semaphore.

        Returns:
            Semaphore for limiting concurrent AI inference operations.
        """
        if self._inference_semaphore is None:
            from backend.services.inference_semaphore import (
                get_inference_semaphore as _get_inference_semaphore,
            )

            self._inference_semaphore = _get_inference_semaphore()
        return self._inference_semaphore

    # =========================================================================
    # Cost Tracking Services
    # =========================================================================

    def get_cost_tracker(self) -> CostTracker:
        """Get or create the cost tracker service.

        Returns:
            CostTracker instance for tracking inference costs.
        """
        if self._cost_tracker is None:
            from backend.services.cost_tracker import (
                get_cost_tracker as _get_cost_tracker,
            )

            self._cost_tracker = _get_cost_tracker()
        return self._cost_tracker

    # =========================================================================
    # Prompt Auto-Tuning Services
    # =========================================================================

    def get_prompt_auto_tuner(self) -> PromptAutoTuner:
        """Get or create the prompt auto-tuner service.

        Returns:
            PromptAutoTuner instance for dynamic prompt optimization.
        """
        if self._prompt_auto_tuner is None:
            from backend.services.prompt_auto_tuner import (
                get_prompt_auto_tuner as _get_prompt_auto_tuner,
            )

            self._prompt_auto_tuner = _get_prompt_auto_tuner()
        return self._prompt_auto_tuner

    # =========================================================================
    # Data Fetching Services
    # =========================================================================

    async def fetch_detections(
        self,
        session: AsyncSession,
        detection_ids: list[int],
    ) -> list[Detection]:
        """Fetch detections from the database.

        Args:
            session: Database session
            detection_ids: List of detection IDs to fetch

        Returns:
            List of Detection objects.
        """
        from backend.services.batch_fetch import batch_fetch_detections

        return await batch_fetch_detections(session, detection_ids)


# Module-level singleton
_facade_instance: AnalyzerServiceFacade | None = None


def get_analyzer_facade() -> AnalyzerServiceFacade:
    """Get or create the global AnalyzerServiceFacade instance.

    Returns:
        The singleton AnalyzerServiceFacade instance.
    """
    global _facade_instance  # noqa: PLW0603 - Singleton pattern
    if _facade_instance is None:
        _facade_instance = AnalyzerServiceFacade()
        logger.debug("Created AnalyzerServiceFacade singleton")
    return _facade_instance


def reset_analyzer_facade() -> None:
    """Reset the global AnalyzerServiceFacade instance.

    Used for testing to ensure clean state between tests.
    """
    global _facade_instance  # noqa: PLW0603 - Singleton pattern
    _facade_instance = None
    logger.debug("Reset AnalyzerServiceFacade singleton")
