"""Summary generator service for dashboard event summaries.

This service generates hourly and daily narrative summaries of high/critical
security events using the Nemotron LLM. Summaries are stored in the database
and displayed on the dashboard.

Features:
    - Hourly summaries: past 60 minutes
    - Daily summaries: since midnight today
    - LLM-generated natural language narratives (2-4 sentences)
    - Fallback behavior when Nemotron is unavailable
    - "All clear" messaging when no high/critical events

Example:
    async with get_session() as session:
        generator = SummaryGenerator()
        summaries = await generator.generate_all_summaries(session)
        print(summaries["hourly"].content)
        print(summaries["daily"].content)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

from backend.core.config import get_settings
from backend.core.database import get_session
from backend.core.logging import get_logger
from backend.models.summary import Summary, SummaryType
from backend.repositories.event_repository import EventRepository
from backend.repositories.summary_repository import SummaryRepository
from backend.services.prompts import build_summary_prompt

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.models.event import Event

__all__ = [
    "SummaryGenerator",
    "get_summary_generator",
]

logger = get_logger(__name__)

# Timeout for summary LLM calls (shorter than risk analysis since simpler)
SUMMARY_LLM_TIMEOUT = 60.0
SUMMARY_LLM_CONNECT_TIMEOUT = 10.0


class SummaryGenerator:
    """Generates dashboard summaries using Nemotron LLM.

    This service queries high/critical events, builds prompts for the LLM,
    and stores the generated summaries in the database.

    Attributes:
        _llm_url: URL for the Nemotron llama.cpp server
        _api_key: Optional API key for authentication
        _timeout: HTTP timeout configuration
    """

    def __init__(
        self,
        llm_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """Initialize the summary generator.

        Args:
            llm_url: Override URL for Nemotron server. If not provided,
                uses NEMOTRON_URL from settings.
            api_key: Override API key. If not provided, uses settings.
            timeout: Override timeout in seconds. Default is 60s.
        """
        settings = get_settings()
        self._llm_url = llm_url or settings.nemotron_url
        self._api_key = api_key if api_key is not None else settings.nemotron_api_key
        self._timeout = httpx.Timeout(
            connect=SUMMARY_LLM_CONNECT_TIMEOUT,
            read=timeout or SUMMARY_LLM_TIMEOUT,
            write=timeout or SUMMARY_LLM_TIMEOUT,
            pool=SUMMARY_LLM_CONNECT_TIMEOUT,
        )

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for LLM requests.

        Returns:
            Dictionary of headers including API key if configured.
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}
        # Support both SecretStr and str for api_key
        if self._api_key:
            api_key_value: str = (
                self._api_key.get_secret_value()
                if hasattr(self._api_key, "get_secret_value")
                else str(self._api_key)
            )
            headers["X-API-Key"] = api_key_value
        return headers

    async def generate_hourly_summary(
        self,
        session: AsyncSession | None = None,
    ) -> Summary:
        """Generate an hourly summary covering the past 60 minutes.

        Queries high/critical events from the past hour, generates a narrative
        summary using Nemotron, and stores the result in the database.

        Args:
            session: Optional database session. If not provided, creates one.

        Returns:
            The created Summary object.

        Example:
            generator = SummaryGenerator()
            summary = await generator.generate_hourly_summary()
            print(summary.content)
        """
        if session is None:
            async with get_session() as db_session:
                return await self._generate_summary(
                    session=db_session,
                    summary_type=SummaryType.HOURLY,
                    window_start=datetime.now(UTC) - timedelta(minutes=60),
                    window_end=datetime.now(UTC),
                    period_type="hour",
                )
        return await self._generate_summary(
            session=session,
            summary_type=SummaryType.HOURLY,
            window_start=datetime.now(UTC) - timedelta(minutes=60),
            window_end=datetime.now(UTC),
            period_type="hour",
        )

    async def generate_daily_summary(
        self,
        session: AsyncSession | None = None,
    ) -> Summary:
        """Generate a daily summary covering since midnight today.

        Queries high/critical events from today, generates a narrative
        summary using Nemotron, and stores the result in the database.

        Args:
            session: Optional database session. If not provided, creates one.

        Returns:
            The created Summary object.

        Example:
            generator = SummaryGenerator()
            summary = await generator.generate_daily_summary()
            print(summary.content)
        """
        now = datetime.now(UTC)
        # DATE_TRUNC('day', NOW()) equivalent
        midnight_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if session is None:
            async with get_session() as db_session:
                return await self._generate_summary(
                    session=db_session,
                    summary_type=SummaryType.DAILY,
                    window_start=midnight_today,
                    window_end=now,
                    period_type="day",
                )
        return await self._generate_summary(
            session=session,
            summary_type=SummaryType.DAILY,
            window_start=midnight_today,
            window_end=now,
            period_type="day",
        )

    async def generate_all_summaries(
        self,
        session: AsyncSession | None = None,
    ) -> dict[str, Summary]:
        """Generate both hourly and daily summaries in one call.

        Args:
            session: Optional database session. If not provided, creates one.

        Returns:
            Dictionary with 'hourly' and 'daily' keys containing Summary objects.

        Example:
            generator = SummaryGenerator()
            summaries = await generator.generate_all_summaries()
            print(summaries["hourly"].content)
            print(summaries["daily"].content)
        """
        if session is None:
            async with get_session() as db_session:
                hourly = await self.generate_hourly_summary(db_session)
                daily = await self.generate_daily_summary(db_session)
                return {"hourly": hourly, "daily": daily}

        hourly = await self.generate_hourly_summary(session)
        daily = await self.generate_daily_summary(session)
        return {"hourly": hourly, "daily": daily}

    async def _generate_summary(
        self,
        session: AsyncSession,
        summary_type: SummaryType,
        window_start: datetime,
        window_end: datetime,
        period_type: str,
    ) -> Summary:
        """Internal method to generate a summary of a specific type.

        Args:
            session: Database session
            summary_type: HOURLY or DAILY
            window_start: Start of the time window
            window_end: End of the time window
            period_type: "hour" or "day" for prompt formatting

        Returns:
            The created Summary object.
        """
        # Query high/critical events for the time window
        event_repo = EventRepository(session)
        events = await self._get_high_critical_events(event_repo, window_start, window_end)

        # Extract event IDs
        event_ids = [event.id for event in events]
        event_count = len(events)

        logger.info(
            f"Generating {summary_type.value} summary",
            extra={
                "summary_type": summary_type.value,
                "event_count": event_count,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
            },
        )

        # Build event context for prompt
        event_context = self._build_event_context(events)

        # Generate summary content via LLM
        generated_at = datetime.now(UTC)
        try:
            content = await self._call_nemotron(
                window_start=window_start,
                window_end=window_end,
                period_type=period_type,
                events=event_context,
            )
        except Exception as e:
            logger.warning(
                f"Nemotron unavailable for {summary_type.value} summary, using fallback",
                extra={
                    "summary_type": summary_type.value,
                    "error": str(e),
                    "event_count": event_count,
                },
            )
            content = self._get_fallback_content(event_count)

        # Store in database
        summary_repo = SummaryRepository(session)
        summary = await summary_repo.create_summary(
            summary_type=summary_type,
            content=content,
            event_count=event_count,
            event_ids=event_ids if event_ids else None,
            window_start=window_start,
            window_end=window_end,
            generated_at=generated_at,
        )

        logger.info(
            f"Created {summary_type.value} summary",
            extra={
                "summary_id": summary.id,
                "summary_type": summary_type.value,
                "event_count": event_count,
                "content_length": len(content),
            },
        )

        return summary

    async def _get_high_critical_events(
        self,
        event_repo: EventRepository,
        window_start: datetime,
        window_end: datetime,
    ) -> Sequence[Event]:
        """Query high and critical events within the time window.

        Args:
            event_repo: Event repository instance
            window_start: Start of the time window
            window_end: End of the time window

        Returns:
            Sequence of Event objects with risk_level 'high' or 'critical'.
        """
        # Get events in date range with camera relationship eager loaded
        # (required for _build_event_context to access event.camera without lazy loading)
        all_events = await event_repo.get_in_date_range(
            window_start, window_end, eager_load_camera=True
        )

        # Filter to high/critical only
        high_critical_events = [
            event for event in all_events if event.risk_level in ("high", "critical")
        ]

        return high_critical_events

    def _build_event_context(self, events: Sequence[Event]) -> list[dict[str, Any]]:
        """Build event context list for the summary prompt.

        Transforms Event objects into dictionaries suitable for the
        build_summary_prompt function.

        Args:
            events: Sequence of Event objects

        Returns:
            List of event dictionaries with timestamp, camera_name, risk_level,
            risk_score, summary, and object_types keys.
        """
        context: list[dict[str, Any]] = []

        for event in events:
            # Format timestamp for human readability
            timestamp = (
                event.started_at.strftime("%I:%M %p") if event.started_at else "Unknown time"
            )

            # Get camera name from relationship or use camera_id
            camera_name = event.camera_id
            if hasattr(event, "camera") and event.camera is not None:
                camera_name = event.camera.name or event.camera_id

            context.append(
                {
                    "timestamp": timestamp,
                    "camera_name": camera_name,
                    "risk_level": event.risk_level or "unknown",
                    "risk_score": event.risk_score or 0,
                    "summary": event.summary or "No summary available",
                    "object_types": event.object_types or "Unknown objects",
                }
            )

        return context

    async def _call_nemotron(
        self,
        window_start: datetime,
        window_end: datetime,
        period_type: str,
        events: list[dict[str, Any]],
    ) -> str:
        """Call Nemotron LLM to generate summary content.

        Args:
            window_start: Start of the time window
            window_end: End of the time window
            period_type: "hour" or "day"
            events: List of event context dictionaries

        Returns:
            Generated summary text (2-4 sentences).

        Raises:
            httpx.HTTPError: If LLM request fails
            asyncio.TimeoutError: If request times out
            ValueError: If response cannot be parsed
        """
        # Format timestamps for prompt
        formatted_start = window_start.strftime("%I:%M %p")
        formatted_end = window_end.strftime("%I:%M %p")

        # Build prompts using the helper from prompts.py
        system_prompt, user_prompt = build_summary_prompt(
            window_start=formatted_start,
            window_end=formatted_end,
            period_type=period_type,
            events=events,
            routine_count=0,  # Could be enhanced to pass actual routine counts
        )

        # Format as ChatML for Nemotron
        full_prompt = f"""<|im_start|>system
{system_prompt}<|im_end|>
<|im_start|>user
{user_prompt}<|im_end|>
<|im_start|>assistant
"""

        # Call llama.cpp completion endpoint
        payload = {
            "prompt": full_prompt,
            "temperature": 0.7,
            "top_p": 0.95,
            "max_tokens": 256,  # Summaries are short (2-4 sentences)
            "stop": ["<|im_end|>", "<|im_start|>"],
        }

        settings = get_settings()
        explicit_timeout = settings.nemotron_read_timeout + settings.ai_connect_timeout

        async with asyncio.timeout(explicit_timeout):
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._llm_url}/completion",
                    json=payload,
                    headers=self._get_auth_headers(),
                )
                response.raise_for_status()
                result = response.json()

        # Extract completion text
        content = result.get("content", "").strip()
        if not content:
            raise ValueError("Empty completion from LLM")

        # Clean up any remaining think tags or artifacts
        import re

        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        logger.debug(
            "Generated summary via Nemotron",
            extra={
                "period_type": period_type,
                "content_length": len(content),
                "event_count": len(events),
            },
        )

        return content

    def _get_fallback_content(self, event_count: int) -> str:
        """Generate fallback content when Nemotron is unavailable.

        Args:
            event_count: Number of high/critical events in the period

        Returns:
            Fallback summary message.
        """
        if event_count == 0:
            return "No high-priority security events detected in this period. The property has been quiet."
        return (
            f"Summary temporarily unavailable. {event_count} high/critical events in this period."
        )


# Module-level singleton instance
_summary_generator: SummaryGenerator | None = None


def get_summary_generator() -> SummaryGenerator:
    """Get the singleton SummaryGenerator instance.

    Returns:
        The global SummaryGenerator instance.

    Example:
        generator = get_summary_generator()
        summary = await generator.generate_hourly_summary()
    """
    global _summary_generator  # noqa: PLW0603
    if _summary_generator is None:
        _summary_generator = SummaryGenerator()
    return _summary_generator
