# AI Performance Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a comprehensive AI pipeline audit system with self-evaluation, dashboard, and event drill-down.

**Architecture:** Backend service captures model contributions inline, runs Nemotron self-evaluation on-demand/background, exposes via REST API. Frontend adds AI Performance page with aggregate stats and integrates audit details into EventDetailModal.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Alembic, React/TypeScript, Tailwind CSS, Tremor charts

---

## Phase 1: Backend Data Model

### Task 1.1: Create EventAudit Model

**Files:**

- Create: `backend/models/event_audit.py`
- Modify: `backend/models/__init__.py`

**Step 1: Write the model file**

```python
# backend/models/event_audit.py
"""EventAudit model for AI pipeline performance tracking."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .event import Event


def _utc_now() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


class EventAudit(Base):
    """Audit record for AI pipeline performance on an event.

    Tracks which models contributed to an event's analysis, quality scores
    from Nemotron self-evaluation, and prompt improvement suggestions.
    """

    __tablename__ = "event_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    audited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    # Model contribution flags (captured real-time)
    has_rtdetr: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_florence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_clip: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_violence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_clothing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_vehicle: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_pet: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_weather: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_image_quality: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_zones: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_baseline: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_cross_camera: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Prompt metrics
    prompt_length: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prompt_token_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enrichment_utilization: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Self-evaluation scores (1-5 scale, NULL if not yet evaluated)
    context_usage_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning_coherence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_justification_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Consistency check data
    consistency_risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consistency_diff: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Self-evaluation text
    self_eval_critique: Mapped[str | None] = mapped_column(Text, nullable=True)
    self_eval_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    self_eval_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Prompt improvement suggestions (JSON arrays stored as text)
    missing_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    confusing_sections: Mapped[str | None] = mapped_column(Text, nullable=True)
    unused_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    format_suggestions: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_gaps: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    event: Mapped[Event] = relationship("Event", back_populates="audit")

    # Indexes
    __table_args__ = (
        Index("idx_event_audits_event_id", "event_id"),
        Index("idx_event_audits_audited_at", "audited_at"),
        Index("idx_event_audits_overall_score", "overall_quality_score"),
    )

    @property
    def is_fully_evaluated(self) -> bool:
        """Check if full self-evaluation has been run."""
        return self.overall_quality_score is not None

    def __repr__(self) -> str:
        return (
            f"<EventAudit(id={self.id}, event_id={self.event_id}, "
            f"overall_score={self.overall_quality_score})>"
        )
```

**Step 2: Add relationship to Event model**

Modify `backend/models/event.py`, add after `alerts` relationship (~line 63):

```python
    audit: Mapped[EventAudit | None] = relationship(
        "EventAudit", back_populates="event", uselist=False, cascade="all, delete-orphan"
    )
```

And add import at top:

```python
if TYPE_CHECKING:
    from .alert import Alert
    from .camera import Camera
    from .event_audit import EventAudit
```

**Step 3: Update models **init**.py**

Add to `backend/models/__init__.py`:

```python
from .event_audit import EventAudit
```

**Step 4: Verify imports work**

Run: `cd backend && python -c "from models.event_audit import EventAudit; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add backend/models/event_audit.py backend/models/event.py backend/models/__init__.py
git commit -m "feat(audit): add EventAudit model for AI pipeline tracking"
```

---

### Task 1.2: Create Database Migration

**Files:**

- Create: `backend/alembic/versions/add_event_audits_table.py`

**Step 1: Write the migration**

```python
# backend/alembic/versions/add_event_audits_table.py
"""Add event_audits table for AI pipeline performance tracking

Revision ID: add_event_audits
Revises: add_llm_prompt
Create Date: 2026-01-02 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "add_event_audits"
down_revision: str | Sequence[str] | None = "add_llm_prompt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create event_audits table."""
    op.create_table(
        "event_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("audited_at", sa.DateTime(timezone=True), nullable=False),
        # Model contribution flags
        sa.Column("has_rtdetr", sa.Boolean(), nullable=False, default=False),
        sa.Column("has_florence", sa.Boolean(), nullable=False, default=False),
        sa.Column("has_clip", sa.Boolean(), nullable=False, default=False),
        sa.Column("has_violence", sa.Boolean(), nullable=False, default=False),
        sa.Column("has_clothing", sa.Boolean(), nullable=False, default=False),
        sa.Column("has_vehicle", sa.Boolean(), nullable=False, default=False),
        sa.Column("has_pet", sa.Boolean(), nullable=False, default=False),
        sa.Column("has_weather", sa.Boolean(), nullable=False, default=False),
        sa.Column("has_image_quality", sa.Boolean(), nullable=False, default=False),
        sa.Column("has_zones", sa.Boolean(), nullable=False, default=False),
        sa.Column("has_baseline", sa.Boolean(), nullable=False, default=False),
        sa.Column("has_cross_camera", sa.Boolean(), nullable=False, default=False),
        # Prompt metrics
        sa.Column("prompt_length", sa.Integer(), nullable=False, default=0),
        sa.Column("prompt_token_estimate", sa.Integer(), nullable=False, default=0),
        sa.Column("enrichment_utilization", sa.Float(), nullable=False, default=0.0),
        # Self-evaluation scores
        sa.Column("context_usage_score", sa.Float(), nullable=True),
        sa.Column("reasoning_coherence_score", sa.Float(), nullable=True),
        sa.Column("risk_justification_score", sa.Float(), nullable=True),
        sa.Column("consistency_score", sa.Float(), nullable=True),
        sa.Column("overall_quality_score", sa.Float(), nullable=True),
        # Consistency check
        sa.Column("consistency_risk_score", sa.Integer(), nullable=True),
        sa.Column("consistency_diff", sa.Integer(), nullable=True),
        # Self-evaluation text
        sa.Column("self_eval_critique", sa.Text(), nullable=True),
        sa.Column("self_eval_prompt", sa.Text(), nullable=True),
        sa.Column("self_eval_response", sa.Text(), nullable=True),
        # Prompt improvements (JSON as text)
        sa.Column("missing_context", sa.Text(), nullable=True),
        sa.Column("confusing_sections", sa.Text(), nullable=True),
        sa.Column("unused_data", sa.Text(), nullable=True),
        sa.Column("format_suggestions", sa.Text(), nullable=True),
        sa.Column("model_gaps", sa.Text(), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("event_id"),
    )

    # Create indexes
    op.create_index("idx_event_audits_event_id", "event_audits", ["event_id"])
    op.create_index("idx_event_audits_audited_at", "event_audits", ["audited_at"])
    op.create_index("idx_event_audits_overall_score", "event_audits", ["overall_quality_score"])


def downgrade() -> None:
    """Drop event_audits table."""
    op.drop_index("idx_event_audits_overall_score", "event_audits")
    op.drop_index("idx_event_audits_audited_at", "event_audits")
    op.drop_index("idx_event_audits_event_id", "event_audits")
    op.drop_table("event_audits")
```

**Step 2: Run migration in container**

```bash
podman exec dev-1_backend_1 bash -c 'cd /app && PYTHONPATH=/app alembic -c backend/alembic.ini upgrade head'
```

Expected: `Running upgrade add_llm_prompt -> add_event_audits`

**Step 3: Verify table exists**

```bash
podman exec dev-1_postgres_1 psql -U security -d security -c "\\d event_audits" | head -20
```

Expected: Table schema output

**Step 4: Commit**

```bash
git add backend/alembic/versions/add_event_audits_table.py
git commit -m "feat(audit): add event_audits migration"
```

---

## Phase 2: Backend Audit Service

### Task 2.1: Create Pydantic Schemas

**Files:**

- Create: `backend/api/schemas/audit.py`

**Step 1: Write the schemas**

```python
# backend/api/schemas/audit.py
"""Pydantic schemas for AI audit API endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelContributions(BaseModel):
    """Model contribution flags."""

    rtdetr: bool = Field(False, description="RT-DETR object detection")
    florence: bool = Field(False, description="Florence-2 vision attributes")
    clip: bool = Field(False, description="CLIP embeddings")
    violence: bool = Field(False, description="Violence detection")
    clothing: bool = Field(False, description="Clothing analysis")
    vehicle: bool = Field(False, description="Vehicle classification")
    pet: bool = Field(False, description="Pet classification")
    weather: bool = Field(False, description="Weather classification")
    image_quality: bool = Field(False, description="Image quality assessment")
    zones: bool = Field(False, description="Zone analysis")
    baseline: bool = Field(False, description="Baseline comparison")
    cross_camera: bool = Field(False, description="Cross-camera correlation")


class QualityScores(BaseModel):
    """Self-evaluation quality scores (1-5 scale)."""

    context_usage: float | None = Field(None, ge=1, le=5)
    reasoning_coherence: float | None = Field(None, ge=1, le=5)
    risk_justification: float | None = Field(None, ge=1, le=5)
    consistency: float | None = Field(None, ge=1, le=5)
    overall: float | None = Field(None, ge=1, le=5)


class PromptImprovements(BaseModel):
    """Prompt improvement suggestions from self-evaluation."""

    missing_context: list[str] = Field(default_factory=list)
    confusing_sections: list[str] = Field(default_factory=list)
    unused_data: list[str] = Field(default_factory=list)
    format_suggestions: list[str] = Field(default_factory=list)
    model_gaps: list[str] = Field(default_factory=list)


class EventAuditResponse(BaseModel):
    """Full audit response for a single event."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    audited_at: datetime
    is_fully_evaluated: bool

    # Model contributions
    contributions: ModelContributions

    # Prompt metrics
    prompt_length: int
    prompt_token_estimate: int
    enrichment_utilization: float

    # Quality scores (None if not evaluated)
    scores: QualityScores

    # Consistency check
    consistency_risk_score: int | None = None
    consistency_diff: int | None = None

    # Self-evaluation text
    self_eval_critique: str | None = None

    # Prompt improvements
    improvements: PromptImprovements


class AuditStatsResponse(BaseModel):
    """Aggregate audit statistics."""

    total_events: int
    audited_events: int
    fully_evaluated_events: int

    avg_quality_score: float | None
    avg_consistency_rate: float | None
    avg_enrichment_utilization: float | None

    # Model contribution rates (0-1)
    model_contribution_rates: dict[str, float]

    # Audits by day for trending
    audits_by_day: list[dict]


class ModelLeaderboardEntry(BaseModel):
    """Single entry in model leaderboard."""

    model_name: str
    contribution_rate: float
    quality_correlation: float | None
    event_count: int


class LeaderboardResponse(BaseModel):
    """Model leaderboard response."""

    entries: list[ModelLeaderboardEntry]
    period_days: int


class RecommendationItem(BaseModel):
    """Single recommendation item."""

    category: str  # missing_context, unused_data, model_gaps, etc.
    suggestion: str
    frequency: int  # How many events mentioned this
    priority: str  # high, medium, low


class RecommendationsResponse(BaseModel):
    """Aggregated recommendations response."""

    recommendations: list[RecommendationItem]
    total_events_analyzed: int


class BatchAuditRequest(BaseModel):
    """Request for batch audit processing."""

    limit: int = Field(100, ge=1, le=1000)
    min_risk_score: int | None = Field(None, ge=0, le=100)
    force_reevaluate: bool = False


class BatchAuditResponse(BaseModel):
    """Response for batch audit request."""

    queued_count: int
    message: str
```

**Step 2: Commit**

```bash
git add backend/api/schemas/audit.py
git commit -m "feat(audit): add Pydantic schemas for audit API"
```

---

### Task 2.2: Create Audit Service - Core Logic

**Files:**

- Create: `backend/services/audit_service.py`

**Step 1: Write the service (part 1 - model contributions)**

```python
# backend/services/audit_service.py
"""AI Pipeline Audit Service.

Handles creation of audit records, self-evaluation via Nemotron,
and aggregation of statistics.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.models.event import Event
from backend.models.event_audit import EventAudit

if TYPE_CHECKING:
    from backend.services.enrichment_pipeline import EnrichmentResult
    from backend.services.context_enricher import EnrichedContext

logger = get_logger(__name__)
settings = get_settings()

# Model names for contribution tracking
MODEL_NAMES = [
    "rtdetr", "florence", "clip", "violence", "clothing",
    "vehicle", "pet", "weather", "image_quality", "zones",
    "baseline", "cross_camera"
]

# Evaluation prompt templates
SELF_CRITIQUE_PROMPT = """<|im_start|>system
You are evaluating your own previous security analysis. Be critical and objective.<|im_end|>
<|im_start|>user
You previously analyzed a security event and provided this assessment:
- Risk Score: {risk_score}
- Summary: {summary}
- Reasoning: {reasoning}

Original context provided to you:
{llm_prompt}

Critique your own response:
1. What did you do well?
2. What could be improved?
3. What context did you ignore or underweight?

Provide a concise critique (2-3 paragraphs).<|im_end|>
<|im_start|>assistant
"""

RUBRIC_EVAL_PROMPT = """<|im_start|>system
You are scoring a security analysis on specific quality dimensions. Output valid JSON only.<|im_end|>
<|im_start|>user
Evaluate this security analysis on a 1-5 scale for each dimension:

Original prompt given: {llm_prompt}

Response produced:
- Risk Score: {risk_score}
- Summary: {summary}
- Reasoning: {reasoning}

Score each dimension (1=poor, 3=adequate, 5=excellent):
1. CONTEXT_USAGE: Did the analysis reference all relevant enrichment data provided?
2. REASONING_COHERENCE: Is the reasoning logical, well-structured, and easy to follow?
3. RISK_JUSTIFICATION: Does the evidence presented support the assigned risk score?
4. ACTIONABILITY: Is the summary useful and actionable for a homeowner?

Output JSON: {{"context_usage": N, "reasoning_coherence": N, "risk_justification": N, "actionability": N, "explanation": "brief explanation"}}<|im_end|>
<|im_start|>assistant
"""

CONSISTENCY_CHECK_PROMPT = """<|im_start|>system
You are a home security risk analyzer. Output valid JSON only.<|im_end|>
<|im_start|>user
{llm_prompt_clean}

Output JSON: {{"risk_score": N, "risk_level": "level", "brief_reason": "one sentence"}}<|im_end|>
<|im_start|>assistant
"""

PROMPT_IMPROVEMENT_PROMPT = """<|im_start|>system
You are analyzing a prompt template for improvement opportunities. Output valid JSON only.<|im_end|>
<|im_start|>user
You were given this prompt for security analysis:

{llm_prompt}

And you produced this response:
- Risk Score: {risk_score}
- Reasoning: {reasoning}

Analyze the PROMPT itself (not your response). What would help you make better assessments?

Identify:
1. MISSING_CONTEXT: What information would have helped? (e.g., "time since last motion", "historical activity")
2. CONFUSING_SECTIONS: Which parts were unclear or contradictory?
3. UNUSED_DATA: Which provided data was not useful for this analysis?
4. FORMAT_SUGGESTIONS: How could the prompt structure be improved?
5. MODEL_GAPS: Which AI models should have provided data but didn't?

Output JSON: {{
  "missing_context": ["item1", "item2"],
  "confusing_sections": ["item1"],
  "unused_data": ["item1"],
  "format_suggestions": ["item1"],
  "model_gaps": ["item1"]
}}<|im_end|>
<|im_start|>assistant
"""


class AuditService:
    """Service for AI pipeline auditing and self-evaluation."""

    def __init__(self) -> None:
        self._llm_url = settings.NEMOTRON_URL
        self._timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)

    def create_partial_audit(
        self,
        event_id: int,
        llm_prompt: str | None,
        enriched_context: EnrichedContext | None,
        enrichment_result: EnrichmentResult | None,
    ) -> EventAudit:
        """Create a partial audit record with model contribution flags.

        Called inline when event is created. Does NOT call LLM.
        """
        audit = EventAudit(
            event_id=event_id,
            audited_at=datetime.now(UTC),
            # Model contributions
            has_rtdetr=True,  # Always true if we have detections
            has_florence=self._has_florence(enrichment_result),
            has_clip=self._has_clip(enrichment_result),
            has_violence=self._has_violence(enrichment_result),
            has_clothing=self._has_clothing(enrichment_result),
            has_vehicle=self._has_vehicle(enrichment_result),
            has_pet=self._has_pet(enrichment_result),
            has_weather=self._has_weather(enrichment_result),
            has_image_quality=self._has_image_quality(enrichment_result),
            has_zones=self._has_zones(enriched_context),
            has_baseline=self._has_baseline(enriched_context),
            has_cross_camera=self._has_cross_camera(enriched_context),
            # Prompt metrics
            prompt_length=len(llm_prompt) if llm_prompt else 0,
            prompt_token_estimate=self._estimate_tokens(llm_prompt),
            enrichment_utilization=self._calc_utilization(enriched_context, enrichment_result),
        )
        return audit

    def _has_florence(self, result: EnrichmentResult | None) -> bool:
        return result is not None and result.has_vision_extraction

    def _has_clip(self, result: EnrichmentResult | None) -> bool:
        return result is not None and (
            result.person_reid_matches or result.vehicle_reid_matches
        )

    def _has_violence(self, result: EnrichmentResult | None) -> bool:
        return result is not None and result.has_violence

    def _has_clothing(self, result: EnrichmentResult | None) -> bool:
        return result is not None and result.has_clothing_classifications

    def _has_vehicle(self, result: EnrichmentResult | None) -> bool:
        return result is not None and (
            result.has_vehicle_classifications or result.has_vehicle_damage
        )

    def _has_pet(self, result: EnrichmentResult | None) -> bool:
        return result is not None and result.has_pet_classifications

    def _has_weather(self, result: EnrichmentResult | None) -> bool:
        return result is not None and result.weather_classification is not None

    def _has_image_quality(self, result: EnrichmentResult | None) -> bool:
        return result is not None and result.has_image_quality

    def _has_zones(self, context: EnrichedContext | None) -> bool:
        return context is not None and bool(context.zones)

    def _has_baseline(self, context: EnrichedContext | None) -> bool:
        return context is not None and context.baselines is not None

    def _has_cross_camera(self, context: EnrichedContext | None) -> bool:
        return context is not None and context.cross_camera is not None

    def _estimate_tokens(self, text: str | None) -> int:
        """Rough token estimate (chars / 4)."""
        if not text:
            return 0
        return len(text) // 4

    def _calc_utilization(
        self,
        context: EnrichedContext | None,
        result: EnrichmentResult | None,
    ) -> float:
        """Calculate enrichment utilization (0-1)."""
        total = 12  # Total possible enrichments
        count = sum([
            True,  # rtdetr always
            self._has_florence(result),
            self._has_clip(result),
            self._has_violence(result),
            self._has_clothing(result),
            self._has_vehicle(result),
            self._has_pet(result),
            self._has_weather(result),
            self._has_image_quality(result),
            self._has_zones(context),
            self._has_baseline(context),
            self._has_cross_camera(context),
        ])
        return count / total

    async def run_full_evaluation(
        self,
        audit: EventAudit,
        event: Event,
        session: AsyncSession,
    ) -> EventAudit:
        """Run all 4 self-evaluation modes on an event.

        Updates the audit record with scores and recommendations.
        """
        if not event.llm_prompt:
            logger.warning(f"Event {event.id} has no llm_prompt, skipping evaluation")
            return audit

        # Mode 1: Self-critique
        critique = await self._run_self_critique(event)
        audit.self_eval_critique = critique

        # Mode 2: Rubric scoring
        scores = await self._run_rubric_eval(event)
        audit.context_usage_score = scores.get("context_usage")
        audit.reasoning_coherence_score = scores.get("reasoning_coherence")
        audit.risk_justification_score = scores.get("risk_justification")
        # Actionability maps to overall for now
        actionability = scores.get("actionability", 3.0)

        # Calculate overall as average of available scores
        score_values = [
            audit.context_usage_score,
            audit.reasoning_coherence_score,
            audit.risk_justification_score,
            actionability,
        ]
        valid_scores = [s for s in score_values if s is not None]
        audit.overall_quality_score = sum(valid_scores) / len(valid_scores) if valid_scores else None

        # Mode 3: Consistency check
        consistency_result = await self._run_consistency_check(event)
        audit.consistency_risk_score = consistency_result.get("risk_score")
        if audit.consistency_risk_score is not None and event.risk_score is not None:
            audit.consistency_diff = abs(audit.consistency_risk_score - event.risk_score)
            # Score consistency: 5 if diff <= 5, down to 1 if diff >= 25
            audit.consistency_score = max(1.0, 5.0 - (audit.consistency_diff / 5))

        # Mode 4: Prompt improvement
        improvements = await self._run_prompt_improvement(event)
        audit.missing_context = json.dumps(improvements.get("missing_context", []))
        audit.confusing_sections = json.dumps(improvements.get("confusing_sections", []))
        audit.unused_data = json.dumps(improvements.get("unused_data", []))
        audit.format_suggestions = json.dumps(improvements.get("format_suggestions", []))
        audit.model_gaps = json.dumps(improvements.get("model_gaps", []))

        # Store the evaluation prompt for debugging
        audit.self_eval_prompt = RUBRIC_EVAL_PROMPT.format(
            llm_prompt=event.llm_prompt[:500] + "..." if len(event.llm_prompt) > 500 else event.llm_prompt,
            risk_score=event.risk_score,
            summary=event.summary,
            reasoning=event.reasoning[:300] + "..." if event.reasoning and len(event.reasoning) > 300 else event.reasoning,
        )

        audit.audited_at = datetime.now(UTC)

        await session.commit()
        await session.refresh(audit)

        return audit

    async def _call_llm(self, prompt: str) -> str:
        """Call Nemotron LLM and return completion text."""
        payload = {
            "prompt": prompt,
            "temperature": 0.3,  # Lower temp for evaluation
            "top_p": 0.9,
            "max_tokens": 1024,
            "stop": ["<|im_end|>", "<|im_start|>"],
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._llm_url}/completion",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

        return result.get("content", "")

    async def _run_self_critique(self, event: Event) -> str:
        """Run Mode 1: Self-critique."""
        try:
            prompt = SELF_CRITIQUE_PROMPT.format(
                risk_score=event.risk_score,
                summary=event.summary,
                reasoning=event.reasoning,
                llm_prompt=event.llm_prompt,
            )
            return await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"Self-critique failed for event {event.id}: {e}")
            return f"Evaluation failed: {e}"

    async def _run_rubric_eval(self, event: Event) -> dict[str, float]:
        """Run Mode 2: Rubric scoring."""
        try:
            prompt = RUBRIC_EVAL_PROMPT.format(
                llm_prompt=event.llm_prompt,
                risk_score=event.risk_score,
                summary=event.summary,
                reasoning=event.reasoning,
            )
            response = await self._call_llm(prompt)

            # Parse JSON from response
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {}
        except Exception as e:
            logger.error(f"Rubric eval failed for event {event.id}: {e}")
            return {}

    async def _run_consistency_check(self, event: Event) -> dict[str, Any]:
        """Run Mode 3: Consistency check."""
        try:
            # Remove the assistant's previous response from prompt
            clean_prompt = event.llm_prompt
            if "<|im_start|>assistant" in clean_prompt:
                clean_prompt = clean_prompt.split("<|im_start|>assistant")[0]

            prompt = CONSISTENCY_CHECK_PROMPT.format(llm_prompt_clean=clean_prompt)
            response = await self._call_llm(prompt)

            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {}
        except Exception as e:
            logger.error(f"Consistency check failed for event {event.id}: {e}")
            return {}

    async def _run_prompt_improvement(self, event: Event) -> dict[str, list[str]]:
        """Run Mode 4: Prompt improvement suggestions."""
        try:
            prompt = PROMPT_IMPROVEMENT_PROMPT.format(
                llm_prompt=event.llm_prompt,
                risk_score=event.risk_score,
                reasoning=event.reasoning,
            )
            response = await self._call_llm(prompt)

            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {}
        except Exception as e:
            logger.error(f"Prompt improvement failed for event {event.id}: {e}")
            return {}

    async def get_stats(
        self,
        session: AsyncSession,
        days: int = 7,
        camera_id: str | None = None,
    ) -> dict[str, Any]:
        """Get aggregate audit statistics."""
        cutoff = datetime.now(UTC) - timedelta(days=days)

        # Base query
        query = select(EventAudit).join(Event).where(EventAudit.audited_at >= cutoff)
        if camera_id:
            query = query.where(Event.camera_id == camera_id)

        result = await session.execute(query)
        audits = list(result.scalars().all())

        total_events = len(audits)
        fully_evaluated = sum(1 for a in audits if a.is_fully_evaluated)

        # Calculate averages
        quality_scores = [a.overall_quality_score for a in audits if a.overall_quality_score]
        consistency_scores = [a.consistency_score for a in audits if a.consistency_score]
        utilization_values = [a.enrichment_utilization for a in audits]

        # Model contribution rates
        contribution_rates = {}
        for model in MODEL_NAMES:
            attr = f"has_{model}"
            count = sum(1 for a in audits if getattr(a, attr, False))
            contribution_rates[model] = count / total_events if total_events > 0 else 0

        return {
            "total_events": total_events,
            "audited_events": total_events,
            "fully_evaluated_events": fully_evaluated,
            "avg_quality_score": sum(quality_scores) / len(quality_scores) if quality_scores else None,
            "avg_consistency_rate": sum(consistency_scores) / len(consistency_scores) if consistency_scores else None,
            "avg_enrichment_utilization": sum(utilization_values) / len(utilization_values) if utilization_values else None,
            "model_contribution_rates": contribution_rates,
            "audits_by_day": [],  # TODO: Implement daily breakdown
        }

    async def get_leaderboard(
        self,
        session: AsyncSession,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Get model leaderboard ranked by usefulness."""
        stats = await self.get_stats(session, days)

        entries = []
        for model in MODEL_NAMES:
            rate = stats["model_contribution_rates"].get(model, 0)
            entries.append({
                "model_name": model,
                "contribution_rate": rate,
                "quality_correlation": None,  # TODO: Calculate correlation
                "event_count": int(rate * stats["total_events"]),
            })

        # Sort by contribution rate descending
        entries.sort(key=lambda x: x["contribution_rate"], reverse=True)
        return entries

    async def get_recommendations(
        self,
        session: AsyncSession,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Aggregate recommendations from all audits."""
        cutoff = datetime.now(UTC) - timedelta(days=days)

        result = await session.execute(
            select(EventAudit).where(
                EventAudit.audited_at >= cutoff,
                EventAudit.overall_quality_score.isnot(None),
            )
        )
        audits = list(result.scalars().all())

        # Aggregate suggestions by category
        categories = ["missing_context", "unused_data", "model_gaps", "format_suggestions"]
        suggestions: dict[str, dict[str, int]] = {cat: {} for cat in categories}

        for audit in audits:
            for cat in categories:
                items_json = getattr(audit, cat, None)
                if items_json:
                    try:
                        items = json.loads(items_json)
                        for item in items:
                            suggestions[cat][item] = suggestions[cat].get(item, 0) + 1
                    except json.JSONDecodeError:
                        pass

        # Build recommendations list
        recommendations = []
        for cat, items in suggestions.items():
            for suggestion, count in sorted(items.items(), key=lambda x: -x[1])[:5]:
                recommendations.append({
                    "category": cat,
                    "suggestion": suggestion,
                    "frequency": count,
                    "priority": "high" if count > len(audits) * 0.3 else "medium" if count > len(audits) * 0.1 else "low",
                })

        recommendations.sort(key=lambda x: -x["frequency"])
        return recommendations[:20]


# Singleton
_audit_service: AuditService | None = None


def get_audit_service() -> AuditService:
    """Get or create audit service singleton."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
```

**Step 2: Commit**

```bash
git add backend/services/audit_service.py
git commit -m "feat(audit): add AuditService with self-evaluation logic"
```

---

### Task 2.3: Create API Routes

**Files:**

- Create: `backend/api/routes/audit.py`
- Modify: `backend/main.py` (add router)

**Step 1: Write the routes**

```python
# backend/api/routes/audit.py
"""API routes for AI pipeline auditing."""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.audit import (
    AuditStatsResponse,
    BatchAuditRequest,
    BatchAuditResponse,
    EventAuditResponse,
    LeaderboardResponse,
    ModelContributions,
    ModelLeaderboardEntry,
    PromptImprovements,
    QualityScores,
    RecommendationItem,
    RecommendationsResponse,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.services.audit_service import get_audit_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/audit", tags=["audit"])


def _audit_to_response(audit: EventAudit) -> EventAuditResponse:
    """Convert EventAudit model to response schema."""
    return EventAuditResponse(
        id=audit.id,
        event_id=audit.event_id,
        audited_at=audit.audited_at,
        is_fully_evaluated=audit.is_fully_evaluated,
        contributions=ModelContributions(
            rtdetr=audit.has_rtdetr,
            florence=audit.has_florence,
            clip=audit.has_clip,
            violence=audit.has_violence,
            clothing=audit.has_clothing,
            vehicle=audit.has_vehicle,
            pet=audit.has_pet,
            weather=audit.has_weather,
            image_quality=audit.has_image_quality,
            zones=audit.has_zones,
            baseline=audit.has_baseline,
            cross_camera=audit.has_cross_camera,
        ),
        prompt_length=audit.prompt_length,
        prompt_token_estimate=audit.prompt_token_estimate,
        enrichment_utilization=audit.enrichment_utilization,
        scores=QualityScores(
            context_usage=audit.context_usage_score,
            reasoning_coherence=audit.reasoning_coherence_score,
            risk_justification=audit.risk_justification_score,
            consistency=audit.consistency_score,
            overall=audit.overall_quality_score,
        ),
        consistency_risk_score=audit.consistency_risk_score,
        consistency_diff=audit.consistency_diff,
        self_eval_critique=audit.self_eval_critique,
        improvements=PromptImprovements(
            missing_context=json.loads(audit.missing_context) if audit.missing_context else [],
            confusing_sections=json.loads(audit.confusing_sections) if audit.confusing_sections else [],
            unused_data=json.loads(audit.unused_data) if audit.unused_data else [],
            format_suggestions=json.loads(audit.format_suggestions) if audit.format_suggestions else [],
            model_gaps=json.loads(audit.model_gaps) if audit.model_gaps else [],
        ),
    )


@router.get("/events/{event_id}", response_model=EventAuditResponse)
async def get_event_audit(
    event_id: int,
    db: AsyncSession = Depends(get_db),
) -> EventAuditResponse:
    """Get audit details for a specific event."""
    result = await db.execute(
        select(EventAudit).where(EventAudit.event_id == event_id)
    )
    audit = result.scalar_one_or_none()

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit found for event {event_id}",
        )

    return _audit_to_response(audit)


@router.post("/events/{event_id}/evaluate", response_model=EventAuditResponse)
async def evaluate_event(
    event_id: int,
    force: bool = Query(False, description="Force re-evaluation even if already done"),
    db: AsyncSession = Depends(get_db),
) -> EventAuditResponse:
    """Trigger full self-evaluation for an event."""
    # Get event
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    # Get or create audit
    audit_result = await db.execute(
        select(EventAudit).where(EventAudit.event_id == event_id)
    )
    audit = audit_result.scalar_one_or_none()

    if not audit:
        # Create minimal audit record
        service = get_audit_service()
        audit = service.create_partial_audit(
            event_id=event_id,
            llm_prompt=event.llm_prompt,
            enriched_context=None,
            enrichment_result=None,
        )
        db.add(audit)
        await db.commit()
        await db.refresh(audit)

    # Check if already evaluated
    if audit.is_fully_evaluated and not force:
        return _audit_to_response(audit)

    # Run full evaluation
    service = get_audit_service()
    audit = await service.run_full_evaluation(audit, event, db)

    return _audit_to_response(audit)


@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_stats(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    db: AsyncSession = Depends(get_db),
) -> AuditStatsResponse:
    """Get aggregate audit statistics."""
    service = get_audit_service()
    stats = await service.get_stats(db, days, camera_id)
    return AuditStatsResponse(**stats)


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_model_leaderboard(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardResponse:
    """Get model rankings by contribution rate and quality correlation."""
    service = get_audit_service()
    entries = await service.get_leaderboard(db, days)
    return LeaderboardResponse(
        entries=[ModelLeaderboardEntry(**e) for e in entries],
        period_days=days,
    )


@router.get("/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
) -> RecommendationsResponse:
    """Get aggregated improvement recommendations."""
    service = get_audit_service()
    recommendations = await service.get_recommendations(db, days)

    # Count total evaluated events
    from datetime import UTC, datetime, timedelta
    cutoff = datetime.now(UTC) - timedelta(days=days)
    count_result = await db.execute(
        select(EventAudit).where(
            EventAudit.audited_at >= cutoff,
            EventAudit.overall_quality_score.isnot(None),
        )
    )
    total = len(list(count_result.scalars().all()))

    return RecommendationsResponse(
        recommendations=[RecommendationItem(**r) for r in recommendations],
        total_events_analyzed=total,
    )


@router.post("/batch", response_model=BatchAuditResponse)
async def trigger_batch_audit(
    request: BatchAuditRequest,
    db: AsyncSession = Depends(get_db),
) -> BatchAuditResponse:
    """Trigger batch audit processing for recent unevaluated events."""
    # Find events without full evaluation
    query = select(Event).outerjoin(EventAudit).where(
        EventAudit.overall_quality_score.is_(None)
    )

    if request.min_risk_score is not None:
        query = query.where(Event.risk_score >= request.min_risk_score)

    query = query.order_by(Event.risk_score.desc()).limit(request.limit)

    result = await db.execute(query)
    events = list(result.scalars().all())

    # Process events (synchronously for now, could be async job)
    service = get_audit_service()
    processed = 0

    for event in events:
        try:
            # Get or create audit
            audit_result = await db.execute(
                select(EventAudit).where(EventAudit.event_id == event.id)
            )
            audit = audit_result.scalar_one_or_none()

            if not audit:
                audit = service.create_partial_audit(
                    event_id=event.id,
                    llm_prompt=event.llm_prompt,
                    enriched_context=None,
                    enrichment_result=None,
                )
                db.add(audit)
                await db.commit()
                await db.refresh(audit)

            if not audit.is_fully_evaluated or request.force_reevaluate:
                await service.run_full_evaluation(audit, event, db)
                processed += 1
        except Exception as e:
            logger.error(f"Batch audit failed for event {event.id}: {e}")

    return BatchAuditResponse(
        queued_count=processed,
        message=f"Processed {processed} of {len(events)} events",
    )
```

**Step 2: Add router to main.py**

Add import and include_router in `backend/main.py`:

```python
from backend.api.routes.audit import router as audit_router
# ... in create_app() or where other routers are included:
app.include_router(audit_router)
```

**Step 3: Commit**

```bash
git add backend/api/routes/audit.py backend/main.py
git commit -m "feat(audit): add API routes for audit endpoints"
```

---

## Phase 3: Real-time Integration

### Task 3.1: Integrate Audit Creation in NemotronAnalyzer

**Files:**

- Modify: `backend/services/nemotron_analyzer.py`

**Step 1: Add audit creation after event creation**

In `analyze_batch()` method, after the event is created and committed (~line 415), add:

```python
            # Create partial audit record for model contribution tracking
            try:
                from backend.services.audit_service import get_audit_service
                audit_service = get_audit_service()
                audit = audit_service.create_partial_audit(
                    event_id=event.id,
                    llm_prompt=risk_data.get("llm_prompt"),
                    enriched_context=enriched_context,
                    enrichment_result=enrichment_result,
                )
                session.add(audit)
                await session.commit()
            except Exception as e:
                logger.warning(f"Failed to create audit for event {event.id}: {e}")
```

**Step 2: Also add to `analyze_detection_fast_path()` method (~line 585)**

Same pattern after event creation.

**Step 3: Commit**

```bash
git add backend/services/nemotron_analyzer.py
git commit -m "feat(audit): create partial audit records inline with events"
```

---

## Phase 4: Frontend Implementation

### Task 4.1: Create Audit API Client

**Files:**

- Create: `frontend/src/services/auditApi.ts`

**Step 1: Write the API client**

```typescript
// frontend/src/services/auditApi.ts
/**
 * API client for AI audit endpoints
 */

const API_BASE = "/api/audit";

export interface ModelContributions {
  rtdetr: boolean;
  florence: boolean;
  clip: boolean;
  violence: boolean;
  clothing: boolean;
  vehicle: boolean;
  pet: boolean;
  weather: boolean;
  image_quality: boolean;
  zones: boolean;
  baseline: boolean;
  cross_camera: boolean;
}

export interface QualityScores {
  context_usage: number | null;
  reasoning_coherence: number | null;
  risk_justification: number | null;
  consistency: number | null;
  overall: number | null;
}

export interface PromptImprovements {
  missing_context: string[];
  confusing_sections: string[];
  unused_data: string[];
  format_suggestions: string[];
  model_gaps: string[];
}

export interface EventAudit {
  id: number;
  event_id: number;
  audited_at: string;
  is_fully_evaluated: boolean;
  contributions: ModelContributions;
  prompt_length: number;
  prompt_token_estimate: number;
  enrichment_utilization: number;
  scores: QualityScores;
  consistency_risk_score: number | null;
  consistency_diff: number | null;
  self_eval_critique: string | null;
  improvements: PromptImprovements;
}

export interface AuditStats {
  total_events: number;
  audited_events: number;
  fully_evaluated_events: number;
  avg_quality_score: number | null;
  avg_consistency_rate: number | null;
  avg_enrichment_utilization: number | null;
  model_contribution_rates: Record<string, number>;
  audits_by_day: Array<{ date: string; count: number }>;
}

export interface LeaderboardEntry {
  model_name: string;
  contribution_rate: number;
  quality_correlation: number | null;
  event_count: number;
}

export interface Recommendation {
  category: string;
  suggestion: string;
  frequency: number;
  priority: "high" | "medium" | "low";
}

export async function fetchEventAudit(eventId: number): Promise<EventAudit> {
  const response = await fetch(`${API_BASE}/events/${eventId}`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("No audit found for this event");
    }
    throw new Error("Failed to fetch audit");
  }
  return response.json();
}

export async function triggerEvaluation(
  eventId: number,
  force = false,
): Promise<EventAudit> {
  const response = await fetch(
    `${API_BASE}/events/${eventId}/evaluate?force=${force}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw new Error("Failed to trigger evaluation");
  }
  return response.json();
}

export async function fetchAuditStats(
  days = 7,
  cameraId?: string,
): Promise<AuditStats> {
  const params = new URLSearchParams({ days: days.toString() });
  if (cameraId) params.set("camera_id", cameraId);

  const response = await fetch(`${API_BASE}/stats?${params}`);
  if (!response.ok) {
    throw new Error("Failed to fetch audit stats");
  }
  return response.json();
}

export async function fetchLeaderboard(days = 7): Promise<{
  entries: LeaderboardEntry[];
  period_days: number;
}> {
  const response = await fetch(`${API_BASE}/leaderboard?days=${days}`);
  if (!response.ok) {
    throw new Error("Failed to fetch leaderboard");
  }
  return response.json();
}

export async function fetchRecommendations(days = 7): Promise<{
  recommendations: Recommendation[];
  total_events_analyzed: number;
}> {
  const response = await fetch(`${API_BASE}/recommendations?days=${days}`);
  if (!response.ok) {
    throw new Error("Failed to fetch recommendations");
  }
  return response.json();
}

export async function triggerBatchAudit(
  limit = 100,
  minRiskScore?: number,
): Promise<{ queued_count: number; message: string }> {
  const response = await fetch(`${API_BASE}/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      limit,
      min_risk_score: minRiskScore,
      force_reevaluate: false,
    }),
  });
  if (!response.ok) {
    throw new Error("Failed to trigger batch audit");
  }
  return response.json();
}
```

**Step 2: Commit**

```bash
git add frontend/src/services/auditApi.ts
git commit -m "feat(audit): add frontend API client for audit endpoints"
```

---

### Task 4.2: Create AI Performance Page

**Files:**

- Create: `frontend/src/components/audit/AIPerformancePage.tsx`
- Create: `frontend/src/components/audit/index.ts`

**Step 1: Create the page component**

```typescript
// frontend/src/components/audit/AIPerformancePage.tsx
import { useEffect, useState } from 'react';
import { Activity, AlertTriangle, BarChart3, Lightbulb, RefreshCw } from 'lucide-react';

import {
  fetchAuditStats,
  fetchLeaderboard,
  fetchRecommendations,
  triggerBatchAudit,
  type AuditStats,
  type LeaderboardEntry,
  type Recommendation,
} from '../../services/auditApi';

export default function AIPerformancePage() {
  const [days, setDays] = useState(7);
  const [stats, setStats] = useState<AuditStats | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [batchRunning, setBatchRunning] = useState(false);

  useEffect(() => {
    loadData();
  }, [days]);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [statsData, leaderboardData, recsData] = await Promise.all([
        fetchAuditStats(days),
        fetchLeaderboard(days),
        fetchRecommendations(days),
      ]);
      setStats(statsData);
      setLeaderboard(leaderboardData.entries);
      setRecommendations(recsData.recommendations);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }

  async function handleBatchAudit() {
    setBatchRunning(true);
    try {
      const result = await triggerBatchAudit(50, 50);
      alert(result.message);
      loadData();
    } catch (e) {
      alert('Batch audit failed');
    } finally {
      setBatchRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
        <p className="text-red-600 dark:text-red-400">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            AI Performance
          </h1>
          <p className="text-gray-500 dark:text-gray-400">
            Monitor and improve AI pipeline quality
          </p>
        </div>
        <div className="flex items-center gap-4">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="px-3 py-2 border rounded-md dark:bg-gray-800 dark:border-gray-700"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
          </select>
          <button
            onClick={handleBatchAudit}
            disabled={batchRunning}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {batchRunning ? 'Running...' : 'Run Batch Audit'}
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <StatCard
            icon={<Activity className="w-5 h-5" />}
            label="Events Audited"
            value={stats.audited_events.toString()}
          />
          <StatCard
            icon={<BarChart3 className="w-5 h-5" />}
            label="Avg Quality"
            value={stats.avg_quality_score?.toFixed(1) ?? 'N/A'}
            suffix="/5"
          />
          <StatCard
            icon={<Activity className="w-5 h-5" />}
            label="Consistency"
            value={
              stats.avg_consistency_rate
                ? `${(stats.avg_consistency_rate * 20).toFixed(0)}%`
                : 'N/A'
            }
          />
          <StatCard
            icon={<BarChart3 className="w-5 h-5" />}
            label="Enrichment Util"
            value={`${(stats.avg_enrichment_utilization * 100).toFixed(0)}%`}
          />
          <StatCard
            icon={<Activity className="w-5 h-5" />}
            label="Fully Evaluated"
            value={stats.fully_evaluated_events.toString()}
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Model Leaderboard */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            Model Contributions
          </h2>
          <div className="space-y-3">
            {leaderboard.map((entry, i) => (
              <div key={entry.model_name} className="flex items-center gap-3">
                <span className="w-6 text-gray-500">{i + 1}.</span>
                <span className="w-28 font-medium">{entry.model_name}</span>
                <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{ width: `${entry.contribution_rate * 100}%` }}
                  />
                </div>
                <span className="w-12 text-right text-gray-500">
                  {(entry.contribution_rate * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Recommendations */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Lightbulb className="w-5 h-5" />
            Top Recommendations
          </h2>
          <div className="space-y-3">
            {recommendations.slice(0, 8).map((rec, i) => (
              <div
                key={i}
                className="flex items-start gap-3 p-2 rounded bg-gray-50 dark:bg-gray-700"
              >
                <span
                  className={`px-2 py-0.5 text-xs rounded ${
                    rec.priority === 'high'
                      ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                      : rec.priority === 'medium'
                        ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                        : 'bg-gray-100 text-gray-700 dark:bg-gray-600 dark:text-gray-300'
                  }`}
                >
                  {rec.category.replace('_', ' ')}
                </span>
                <span className="flex-1 text-sm">{rec.suggestion}</span>
                <span className="text-xs text-gray-500">×{rec.frequency}</span>
              </div>
            ))}
            {recommendations.length === 0 && (
              <p className="text-gray-500 text-center py-4">
                No recommendations yet. Run batch audit to generate.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  suffix,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  suffix?: string;
}) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <div className="flex items-center gap-2 text-gray-500 mb-1">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <div className="text-2xl font-bold">
        {value}
        {suffix && <span className="text-sm font-normal text-gray-500">{suffix}</span>}
      </div>
    </div>
  );
}
```

**Step 2: Create index export**

```typescript
// frontend/src/components/audit/index.ts
export { default as AIPerformancePage } from "./AIPerformancePage";
```

**Step 3: Commit**

```bash
git add frontend/src/components/audit/
git commit -m "feat(audit): add AI Performance dashboard page"
```

---

### Task 4.3: Add Route and Navigation

**Files:**

- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/layout/Sidebar.tsx`

**Step 1: Add route to App.tsx**

```typescript
import { AIPerformancePage } from './components/audit';

// In Routes:
<Route path="/ai-performance" element={<AIPerformancePage />} />
```

**Step 2: Add nav item to Sidebar.tsx**

Add to navigation items:

```typescript
{ name: 'AI Performance', href: '/ai-performance', icon: Brain },
```

Import Brain icon from lucide-react.

**Step 3: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/layout/Sidebar.tsx
git commit -m "feat(audit): add AI Performance route and navigation"
```

---

### Task 4.4: Add Event Audit Detail Component

**Files:**

- Create: `frontend/src/components/audit/EventAuditDetail.tsx`

**Step 1: Write the component**

```typescript
// frontend/src/components/audit/EventAuditDetail.tsx
import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle, RefreshCw, XCircle } from 'lucide-react';

import {
  fetchEventAudit,
  triggerEvaluation,
  type EventAudit,
} from '../../services/auditApi';

interface EventAuditDetailProps {
  eventId: number;
}

export default function EventAuditDetail({ eventId }: EventAuditDetailProps) {
  const [audit, setAudit] = useState<EventAudit | null>(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAudit();
  }, [eventId]);

  async function loadAudit() {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchEventAudit(eventId);
      setAudit(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load audit');
    } finally {
      setLoading(false);
    }
  }

  async function handleEvaluate() {
    setEvaluating(true);
    try {
      const data = await triggerEvaluation(eventId, true);
      setAudit(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Evaluation failed');
    } finally {
      setEvaluating(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error && !audit) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500 mb-4">{error}</p>
        <button
          onClick={handleEvaluate}
          disabled={evaluating}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          {evaluating ? 'Running...' : 'Run Evaluation'}
        </button>
      </div>
    );
  }

  if (!audit) return null;

  const models = [
    { name: 'RT-DETR', active: audit.contributions.rtdetr },
    { name: 'Florence', active: audit.contributions.florence },
    { name: 'CLIP', active: audit.contributions.clip },
    { name: 'Violence', active: audit.contributions.violence },
    { name: 'Clothing', active: audit.contributions.clothing },
    { name: 'Vehicle', active: audit.contributions.vehicle },
    { name: 'Pet', active: audit.contributions.pet },
    { name: 'Weather', active: audit.contributions.weather },
    { name: 'Quality', active: audit.contributions.image_quality },
    { name: 'Zones', active: audit.contributions.zones },
    { name: 'Baseline', active: audit.contributions.baseline },
    { name: 'Cross-cam', active: audit.contributions.cross_camera },
  ];

  return (
    <div className="space-y-6">
      {/* Quality Scores */}
      <div>
        <h3 className="font-semibold mb-3">Quality Scores</h3>
        {audit.is_fully_evaluated ? (
          <div className="space-y-2">
            <ScoreBar label="Context Usage" score={audit.scores.context_usage} />
            <ScoreBar label="Reasoning" score={audit.scores.reasoning_coherence} />
            <ScoreBar label="Justification" score={audit.scores.risk_justification} />
            <ScoreBar label="Consistency" score={audit.scores.consistency} />
            <div className="border-t pt-2 mt-2">
              <ScoreBar label="Overall" score={audit.scores.overall} highlight />
            </div>
          </div>
        ) : (
          <div className="text-center py-4">
            <p className="text-gray-500 mb-2">Not yet evaluated</p>
            <button
              onClick={handleEvaluate}
              disabled={evaluating}
              className="px-3 py-1 bg-blue-600 text-white text-sm rounded"
            >
              {evaluating ? 'Running...' : 'Run Evaluation'}
            </button>
          </div>
        )}
      </div>

      {/* Model Contributions */}
      <div>
        <h3 className="font-semibold mb-3">Model Contributions</h3>
        <div className="grid grid-cols-3 gap-2">
          {models.map((m) => (
            <div
              key={m.name}
              className={`flex items-center gap-2 text-sm ${
                m.active ? 'text-green-600' : 'text-gray-400'
              }`}
            >
              {m.active ? (
                <CheckCircle className="w-4 h-4" />
              ) : (
                <XCircle className="w-4 h-4" />
              )}
              {m.name}
            </div>
          ))}
        </div>
        <div className="mt-2 text-sm text-gray-500">
          Utilization: {(audit.enrichment_utilization * 100).toFixed(0)}%
        </div>
      </div>

      {/* Self Critique */}
      {audit.self_eval_critique && (
        <div>
          <h3 className="font-semibold mb-2">Self-Critique</h3>
          <p className="text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap">
            {audit.self_eval_critique}
          </p>
        </div>
      )}

      {/* Improvements */}
      {audit.is_fully_evaluated && (
        <div>
          <h3 className="font-semibold mb-2">Suggested Improvements</h3>
          <div className="space-y-2 text-sm">
            {audit.improvements.missing_context.length > 0 && (
              <ImprovementList
                label="Missing Context"
                items={audit.improvements.missing_context}
              />
            )}
            {audit.improvements.unused_data.length > 0 && (
              <ImprovementList
                label="Unused Data"
                items={audit.improvements.unused_data}
              />
            )}
            {audit.improvements.model_gaps.length > 0 && (
              <ImprovementList
                label="Model Gaps"
                items={audit.improvements.model_gaps}
              />
            )}
          </div>
        </div>
      )}

      {/* Re-evaluate button */}
      {audit.is_fully_evaluated && (
        <button
          onClick={handleEvaluate}
          disabled={evaluating}
          className="w-full py-2 border rounded text-sm hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          {evaluating ? 'Re-evaluating...' : 'Re-run Evaluation'}
        </button>
      )}
    </div>
  );
}

function ScoreBar({
  label,
  score,
  highlight,
}: {
  label: string;
  score: number | null;
  highlight?: boolean;
}) {
  const pct = score ? (score / 5) * 100 : 0;
  const color =
    score === null
      ? 'bg-gray-300'
      : score >= 4
        ? 'bg-green-500'
        : score >= 3
          ? 'bg-yellow-500'
          : 'bg-red-500';

  return (
    <div className="flex items-center gap-3">
      <span className={`w-24 text-sm ${highlight ? 'font-semibold' : ''}`}>
        {label}
      </span>
      <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
        <div className={`${color} h-2 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right text-sm">
        {score?.toFixed(1) ?? 'N/A'}
      </span>
    </div>
  );
}

function ImprovementList({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <span className="text-gray-500">{label}:</span>
      <ul className="ml-4 list-disc">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
```

**Step 2: Export from index**

Add to `frontend/src/components/audit/index.ts`:

```typescript
export { default as EventAuditDetail } from "./EventAuditDetail";
```

**Step 3: Commit**

```bash
git add frontend/src/components/audit/EventAuditDetail.tsx frontend/src/components/audit/index.ts
git commit -m "feat(audit): add EventAuditDetail component for drill-down"
```

---

### Task 4.5: Integrate into EventDetailModal

**Files:**

- Modify: `frontend/src/components/events/EventDetailModal.tsx`

**Step 1: Add AI Audit tab**

Import EventAuditDetail and add a tab to the modal. Look for existing tab structure or add one:

```typescript
import { EventAuditDetail } from '../audit';

// Add state for active tab
const [activeTab, setActiveTab] = useState<'details' | 'audit'>('details');

// In the modal content, add tab buttons and conditionally render:
<div className="flex border-b mb-4">
  <button
    onClick={() => setActiveTab('details')}
    className={`px-4 py-2 ${activeTab === 'details' ? 'border-b-2 border-blue-500' : ''}`}
  >
    Details
  </button>
  <button
    onClick={() => setActiveTab('audit')}
    className={`px-4 py-2 ${activeTab === 'audit' ? 'border-b-2 border-blue-500' : ''}`}
  >
    AI Audit
  </button>
</div>

{activeTab === 'details' ? (
  // existing content
) : (
  <EventAuditDetail eventId={Number(event.id)} />
)}
```

**Step 2: Commit**

```bash
git add frontend/src/components/events/EventDetailModal.tsx
git commit -m "feat(audit): integrate AI Audit tab into EventDetailModal"
```

---

## Phase 5: Testing

### Task 5.1: Backend Unit Tests

**Files:**

- Create: `backend/tests/unit/services/test_audit_service.py`

**Step 1: Write tests**

```python
# backend/tests/unit/services/test_audit_service.py
"""Unit tests for AuditService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.audit_service import AuditService, get_audit_service


class TestAuditService:
    """Tests for AuditService."""

    def test_create_partial_audit_basic(self):
        """Test creating partial audit with no enrichment."""
        service = AuditService()

        audit = service.create_partial_audit(
            event_id=123,
            llm_prompt="test prompt",
            enriched_context=None,
            enrichment_result=None,
        )

        assert audit.event_id == 123
        assert audit.prompt_length == len("test prompt")
        assert audit.has_rtdetr is True
        assert audit.has_florence is False
        assert audit.has_zones is False

    def test_estimate_tokens(self):
        """Test token estimation."""
        service = AuditService()

        assert service._estimate_tokens(None) == 0
        assert service._estimate_tokens("") == 0
        assert service._estimate_tokens("test") == 1
        assert service._estimate_tokens("a" * 100) == 25

    def test_calc_utilization(self):
        """Test enrichment utilization calculation."""
        service = AuditService()

        # No enrichment = 1/12 (just rtdetr)
        util = service._calc_utilization(None, None)
        assert util == pytest.approx(1/12)

    def test_singleton(self):
        """Test service singleton."""
        s1 = get_audit_service()
        s2 = get_audit_service()
        assert s1 is s2
```

**Step 2: Run tests**

```bash
uv run pytest backend/tests/unit/services/test_audit_service.py -v
```

**Step 3: Commit**

```bash
git add backend/tests/unit/services/test_audit_service.py
git commit -m "test(audit): add unit tests for AuditService"
```

---

### Task 5.2: API Integration Tests

**Files:**

- Create: `backend/tests/integration/test_audit_api.py`

**Step 1: Write integration tests**

```python
# backend/tests/integration/test_audit_api.py
"""Integration tests for audit API endpoints."""

import pytest
from httpx import AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_get_audit_stats(async_client: AsyncClient):
    """Test fetching audit statistics."""
    response = await async_client.get("/api/audit/stats?days=7")
    assert response.status_code == 200
    data = response.json()
    assert "total_events" in data
    assert "model_contribution_rates" in data


@pytest.mark.asyncio
async def test_get_leaderboard(async_client: AsyncClient):
    """Test fetching model leaderboard."""
    response = await async_client.get("/api/audit/leaderboard?days=7")
    assert response.status_code == 200
    data = response.json()
    assert "entries" in data
    assert "period_days" in data


@pytest.mark.asyncio
async def test_get_event_audit_not_found(async_client: AsyncClient):
    """Test 404 for non-existent audit."""
    response = await async_client.get("/api/audit/events/999999")
    assert response.status_code == 404
```

**Step 2: Run tests**

```bash
uv run pytest backend/tests/integration/test_audit_api.py -v
```

**Step 3: Commit**

```bash
git add backend/tests/integration/test_audit_api.py
git commit -m "test(audit): add integration tests for audit API"
```

---

## Final Steps

### Task 6.1: Rebuild and Deploy

**Step 1: Rebuild containers**

```bash
podman-compose -p dev-1 -f docker-compose.prod.yml build --no-cache backend frontend
```

**Step 2: Run migrations**

```bash
podman exec dev-1_backend_1 bash -c 'cd /app && PYTHONPATH=/app alembic -c backend/alembic.ini upgrade head'
```

**Step 3: Restart services**

```bash
podman-compose -p dev-1 -f docker-compose.prod.yml up -d backend frontend
```

**Step 4: Verify deployment**

- Visit http://localhost:5173/ai-performance
- Check API: `curl http://localhost:8000/api/audit/stats`

---

**Plan complete and saved to `docs/plans/2026-01-02-ai-performance-audit-implementation.md`.**

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session in worktree with executing-plans, batch execution with checkpoints

**Which approach?**
