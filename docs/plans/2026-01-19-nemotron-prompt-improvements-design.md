# Nemotron Prompt Improvements Design

**Date:** 2026-01-19
**Status:** Draft
**Author:** Mike Svoboda + Claude

## Overview

This design addresses systemic issues in the Nemotron risk analysis prompts that cause excessive false positives and poor risk calibration. Analysis of production data revealed:

- **67% of events scored high/critical** (should be ~10-15%)
- **Florence-2 outputs are broken** (raw VQA tokens instead of answers)
- **Conflicting signals** confuse the model (e.g., "running" vs "sitting")
- **No household context** (can't distinguish residents from strangers)
- **No feedback loop** (false positives don't improve future analysis)

## Problem Analysis

### Current State Metrics

| Metric                     | Current | Target |
| -------------------------- | ------- | ------ |
| Low risk events (0-29)     | 8%      | 50-60% |
| Medium risk events (30-59) | 25%     | 25-30% |
| High risk events (60-84)   | 39%     | 10-15% |
| Critical events (85-100)   | 28%     | 2-5%   |

### Root Causes Identified

1. **Data Quality Issues**

   - Florence-2 VQA returns `VQA>question<loc_tokens>` instead of answers
   - Clothing model outputs impossible combinations ("pants, skirt, dress")
   - Pose detection says "running" while scene says "sitting"

2. **Missing Context**

   - No concept of household members vs strangers
   - No registered vehicles
   - Re-identification (seen 18x before) doesn't reduce risk

3. **Prompt Structure Problems**

   - Risk guidelines buried at bottom, often ignored
   - Empty sections included ("Violence analysis: Not performed")
   - No calibration examples to anchor scoring

4. **No Learning Loop**
   - EventFeedback table exists but unused
   - False positives don't improve future analysis

---

## Design: Four-Part Solution

### Part 1: Data Quality Fixes

#### 1.1 Florence-2 VQA Output Parsing

**Problem:** Raw VQA prompts passed to Nemotron instead of answers.

```python
# CURRENT (broken)
"Wearing: VQA>person wearing<loc_95><loc_86><loc_901><loc_918>"

# FIXED
"Wearing: dark hoodie and jeans"
```

**Implementation:**

1. Audit `ai/florence/` service response format
2. Fix parsing in enrichment pipeline to extract actual VQA answers
3. Add validation: if output contains `<loc_` tokens, log error and fallback
4. Fallback strategy: use scene captioning description instead

**Files to modify:**

- `ai/florence/` - Verify response format
- `backend/services/enrichment_pipeline.py` - Fix parsing
- `backend/services/prompts.py` - Add validation before interpolation

#### 1.2 Clothing Model Consistency

**Problem:** Impossible garment combinations.

**Solution:**

```python
def validate_clothing_items(items: list[str], confidence: dict) -> list[str]:
    """Apply mutual exclusion rules to clothing items."""

    MUTUALLY_EXCLUSIVE = [
        {"pants", "skirt", "dress", "shorts"},  # Lower body
        {"t-shirt", "dress", "jacket"},          # Upper body coverage
    ]

    validated = []
    for group in MUTUALLY_EXCLUSIVE:
        matches = [i for i in items if i in group]
        if len(matches) > 1:
            # Take highest confidence item
            best = max(matches, key=lambda x: confidence.get(x, 0))
            validated.append(best)
        elif matches:
            validated.append(matches[0])

    # Add non-exclusive items
    all_exclusive = set().union(*MUTUALLY_EXCLUSIVE)
    validated.extend(i for i in items if i not in all_exclusive)

    return validated
```

#### 1.3 Pose/Scene Contradiction Resolution

**Problem:** Conflicting signals between models.

**Solution:**

```python
def resolve_pose_scene_conflict(
    pose: str,
    pose_confidence: float,
    scene_description: str,
    has_motion_blur: bool
) -> dict:
    """Resolve conflicts between pose detection and scene analysis."""

    POSE_SCENE_CONFLICTS = {
        ("running", "sitting"): "scene",   # Prefer scene
        ("running", "standing"): "pose" if has_motion_blur else "scene",
        ("crouching", "walking"): "pose",  # Crouching is more specific
    }

    for (pose_val, scene_val), winner in POSE_SCENE_CONFLICTS.items():
        if pose == pose_val and scene_val in scene_description.lower():
            return {
                "resolved_pose": pose if winner == "pose" else "unknown",
                "conflict_detected": True,
                "resolution": f"Preferred {winner} interpretation"
            }

    return {"resolved_pose": pose, "conflict_detected": False}
```

**Prompt injection when conflict detected:**

```
⚠️ SIGNAL CONFLICT: Pose model detected "running" but scene shows "sitting".
Confidence is LOW for behavioral analysis. Weight other evidence.
```

---

### Part 2: Household Context System

#### 2.1 Database Schema

```python
# backend/models/household.py

class HouseholdMember(Base):
    """Known persons who should not trigger high-risk alerts."""

    __tablename__ = "household_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50))  # resident, family, service_worker, frequent_visitor
    trusted_level: Mapped[str] = mapped_column(String(20))  # full, partial, monitor

    # Schedule when this person is expected
    typical_schedule: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example: {"weekdays": "17:00-23:00", "weekends": "all_day"}

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    embeddings: Mapped[list["PersonEmbedding"]] = relationship(back_populates="member")


class PersonEmbedding(Base):
    """Re-ID embeddings for matching persons to household members."""

    __tablename__ = "person_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("household_members.id", ondelete="CASCADE"))
    embedding: Mapped[bytes] = mapped_column(LargeBinary)  # Serialized numpy array
    source_event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    confidence: Mapped[float] = mapped_column(default=1.0)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    member: Mapped["HouseholdMember"] = relationship(back_populates="embeddings")


class RegisteredVehicle(Base):
    """Known vehicles that should not trigger alerts."""

    __tablename__ = "registered_vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(String(200))  # "Silver Tesla Model 3"
    license_plate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vehicle_type: Mapped[str] = mapped_column(String(50))  # car, truck, motorcycle, golf_cart
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)

    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"),
        nullable=True
    )
    trusted: Mapped[bool] = mapped_column(default=True)

    # For visual matching
    reid_embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    owner: Mapped["HouseholdMember | None"] = relationship()
```

#### 2.2 Matching Service

```python
# backend/services/household_matcher.py

class HouseholdMatcher:
    """Match detections against known household members and vehicles."""

    SIMILARITY_THRESHOLD = 0.85

    async def match_person(
        self,
        embedding: np.ndarray,
        session: AsyncSession
    ) -> HouseholdMatch | None:
        """Find matching household member for a person embedding."""

        members = await self._get_all_member_embeddings(session)

        best_match = None
        best_similarity = 0.0

        for member_id, member_name, member_embedding in members:
            similarity = cosine_similarity(embedding, member_embedding)
            if similarity > self.SIMILARITY_THRESHOLD and similarity > best_similarity:
                best_match = HouseholdMatch(
                    member_id=member_id,
                    member_name=member_name,
                    similarity=similarity,
                    match_type="person"
                )
                best_similarity = similarity

        return best_match

    async def match_vehicle(
        self,
        license_plate: str | None,
        vehicle_embedding: np.ndarray | None,
        vehicle_type: str,
        color: str | None,
        session: AsyncSession
    ) -> HouseholdMatch | None:
        """Find matching registered vehicle."""

        # Try license plate match first (exact)
        if license_plate:
            vehicle = await self._find_by_plate(license_plate, session)
            if vehicle:
                return HouseholdMatch(
                    vehicle_id=vehicle.id,
                    vehicle_description=vehicle.description,
                    similarity=1.0,
                    match_type="license_plate"
                )

        # Fall back to visual matching
        if vehicle_embedding is not None:
            return await self._match_vehicle_visual(
                vehicle_embedding, vehicle_type, color, session
            )

        return None


@dataclass
class HouseholdMatch:
    """Result of household matching."""
    member_id: int | None = None
    member_name: str | None = None
    vehicle_id: int | None = None
    vehicle_description: str | None = None
    similarity: float = 0.0
    match_type: str = ""  # person, license_plate, vehicle_visual
```

#### 2.3 Prompt Integration

```python
# backend/services/prompts.py

def format_household_context(
    person_matches: list[HouseholdMatch],
    vehicle_matches: list[HouseholdMatch],
    current_time: datetime
) -> str:
    """Format household matching results for prompt injection."""

    lines = ["## RISK MODIFIERS (Apply These First)"]
    lines.append("┌" + "─" * 60 + "┐")

    base_risk = 50  # Default for unknown

    # Person matches
    if person_matches:
        for match in person_matches:
            member = match.member_name
            similarity = match.similarity * 100
            lines.append(f"│ KNOWN PERSON: {member} ({similarity:.0f}% match)")

            # Check schedule
            schedule_ok = check_schedule(match.member_id, current_time)
            if schedule_ok:
                lines.append(f"│   Schedule: ✓ Within expected hours")
                base_risk = 5
            else:
                lines.append(f"│   Schedule: ⚠ Outside normal hours")
                base_risk = 20
    else:
        lines.append("│ KNOWN PERSON MATCH: None (unknown individual)")

    # Vehicle matches
    if vehicle_matches:
        for match in vehicle_matches:
            lines.append(f"│ REGISTERED VEHICLE: {match.vehicle_description}")
            base_risk = min(base_risk, 10)
    else:
        lines.append("│ REGISTERED VEHICLE: None")

    lines.append("└" + "─" * 60 + "┘")
    lines.append(f"→ Calculated base risk: {base_risk}")
    lines.append("")

    return "\n".join(lines)
```

---

### Part 3: Improved Prompt Structure

#### 3.1 New System Prompt

```python
SYSTEM_PROMPT = """You are a home security analyst for a residential property.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

CALIBRATION: In a typical day, expect:
- 80% of events to be LOW risk (0-29): Normal activity
- 15% to be MEDIUM risk (30-59): Worth noting but not alarming
- 4% to be HIGH risk (60-84): Genuinely suspicious, warrants review
- 1% to be CRITICAL (85-100): Immediate threats only

If you're scoring >20% of events as HIGH or CRITICAL, you are miscalibrated.

Output ONLY valid JSON. No preamble, no explanation."""
```

#### 3.2 Restructured User Prompt Template

```python
ENHANCED_ANALYSIS_PROMPT = """
{household_context}

## EVENT CONTEXT
Camera: {camera_name}
Time: {timestamp} ({day_of_week}, {time_of_day})
Weather: {weather_summary}
Image Quality: {quality_summary}

## DETECTIONS
{formatted_detections}

{enrichment_sections}

## SCORING REFERENCE

| Scenario | Score | Reasoning |
|----------|-------|-----------|
| Resident arriving home | 5-15 | Expected activity |
| Delivery driver at door | 15-25 | Normal service visit |
| Unknown person on sidewalk | 20-35 | Public area, passive |
| Unknown person lingering | 45-60 | Warrants attention |
| Person testing door handles | 70-85 | Clear suspicious intent |
| Active break-in or violence | 85-100 | Immediate threat |

## YOUR TASK
1. Start from the base risk calculated above
2. Adjust based on specific threat indicators present
3. Provide clear reasoning for your score
4. Remember: most events should score LOW

{output_schema}
"""
```

#### 3.3 Conditional Section Inclusion

```python
def build_enrichment_sections(enrichment_result: EnrichmentResult) -> str:
    """Build enrichment sections, ONLY including those with actual data."""

    sections = []

    # Violence - only if detected
    if enrichment_result.violence_detection and enrichment_result.violence_detection.detected:
        sections.append(format_violence_alert(enrichment_result.violence_detection))

    # Clothing - only if meaningful results
    if enrichment_result.clothing_classifications:
        cleaned = validate_clothing_data(enrichment_result.clothing_classifications)
        if cleaned:
            sections.append(format_clothing_analysis(cleaned))

    # Pose - only if high confidence and no conflicts
    if enrichment_result.pose_results:
        resolved = resolve_pose_conflicts(enrichment_result)
        if resolved and resolved.confidence > 0.7:
            sections.append(format_pose_analysis(resolved))

    # Vehicle damage - only if detected
    if enrichment_result.vehicle_damage:
        damage = [d for d in enrichment_result.vehicle_damage.values() if d.damage_detected]
        if damage:
            sections.append(format_vehicle_damage(damage))

    # Pet detection - always include if pet found (helps reduce FPs)
    if enrichment_result.pet_classifications:
        high_conf_pets = [p for p in enrichment_result.pet_classifications.values()
                         if p.confidence > 0.85]
        if high_conf_pets:
            sections.append(format_pet_detection(high_conf_pets))

    # DON'T include sections like:
    # - "Violence analysis: Not performed"
    # - "Vehicle classification: No vehicles analyzed"
    # - Empty pose/action sections

    return "\n\n".join(sections) if sections else ""
```

---

### Part 4: Feedback Loop System

#### 4.1 Enhanced Feedback Model

```python
# backend/models/event_feedback.py (enhanced)

class EventFeedback(Base):
    """User feedback for calibrating risk analysis."""

    __tablename__ = "event_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), unique=True)

    # Existing fields
    accurate: Mapped[bool | None] = mapped_column(nullable=True)

    # Enhanced feedback
    feedback_type: Mapped[str] = mapped_column(String(30))
    # "correct", "false_positive", "missed_threat", "wrong_severity"

    actual_threat_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # "no_threat", "minor_concern", "genuine_threat"

    suggested_score: Mapped[int | None] = mapped_column(nullable=True)
    # What the user thinks the score should have been

    # Identity correction
    actual_identity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # "That was Mike" -> triggers household member creation

    # Learning data
    what_was_wrong: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_failures: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    # ["clothing_model", "pose_model", "florence_vqa"]

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    event: Mapped["Event"] = relationship()
```

#### 4.2 Camera Calibration Model

```python
# backend/models/camera_calibration.py

class CameraCalibration(Base):
    """Per-camera risk calibration learned from feedback."""

    __tablename__ = "camera_calibrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), unique=True)

    # Aggregate metrics
    total_feedback_count: Mapped[int] = mapped_column(default=0)
    false_positive_count: Mapped[int] = mapped_column(default=0)
    false_positive_rate: Mapped[float] = mapped_column(default=0.0)

    # Score adjustment
    risk_offset: Mapped[int] = mapped_column(default=0)  # -30 to +30
    # Negative = camera over-alerts, reduce scores
    # Positive = camera under-alerts, increase scores

    # Model-specific adjustments
    model_weights: Mapped[dict] = mapped_column(JSONB, default={})
    # {"pose_model": 0.5, "clothing_model": 0.8} = reduce pose weight

    # Pattern-specific suppression
    suppress_patterns: Mapped[list[dict]] = mapped_column(JSONB, default=[])
    # [{"pattern": "running", "time_range": "16:00-21:00", "reduction": 20}]

    # Computed stats
    avg_model_score: Mapped[float | None] = mapped_column(nullable=True)
    avg_user_suggested_score: Mapped[float | None] = mapped_column(nullable=True)

    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
```

#### 4.3 Feedback Processing Service

```python
# backend/services/feedback_processor.py

class FeedbackProcessor:
    """Process user feedback to improve future analysis."""

    async def process_feedback(
        self,
        feedback: EventFeedback,
        session: AsyncSession
    ) -> None:
        """Process a single feedback submission."""

        event = await self._get_event_with_detections(feedback.event_id, session)

        # 1. Update camera calibration
        await self._update_camera_calibration(event.camera_id, feedback, session)

        # 2. Handle identity correction
        if feedback.actual_identity:
            await self._create_or_update_household_member(
                feedback.actual_identity,
                event,
                session
            )

        # 3. Record model failures for analysis
        if feedback.model_failures:
            await self._record_model_failures(
                feedback.model_failures,
                event,
                session
            )

    async def _update_camera_calibration(
        self,
        camera_id: str,
        feedback: EventFeedback,
        session: AsyncSession
    ) -> None:
        """Update camera-specific calibration based on feedback."""

        calibration = await self._get_or_create_calibration(camera_id, session)

        calibration.total_feedback_count += 1

        if feedback.feedback_type == "false_positive":
            calibration.false_positive_count += 1

        # Recalculate FP rate
        calibration.false_positive_rate = (
            calibration.false_positive_count / calibration.total_feedback_count
        )

        # Auto-adjust offset if FP rate is high
        if calibration.total_feedback_count >= 20:
            if calibration.false_positive_rate > 0.5:
                # More than 50% FPs - reduce scores
                calibration.risk_offset = max(-30, calibration.risk_offset - 5)
            elif calibration.false_positive_rate < 0.1:
                # Very few FPs - might be under-alerting
                calibration.risk_offset = min(30, calibration.risk_offset + 2)

        # Update average suggested score
        if feedback.suggested_score is not None:
            await self._update_avg_suggested_score(calibration, feedback, session)

    async def _create_or_update_household_member(
        self,
        name: str,
        event: Event,
        session: AsyncSession
    ) -> None:
        """Create household member from identity feedback."""

        # Find or create member
        member = await self._find_member_by_name(name, session)
        if not member:
            member = HouseholdMember(
                name=name,
                role="resident",  # Default, user can update
                trusted_level="full"
            )
            session.add(member)
            await session.flush()

        # Extract and save person embedding from event
        embedding = await self._extract_person_embedding(event)
        if embedding is not None:
            person_embedding = PersonEmbedding(
                member_id=member.id,
                embedding=embedding.tobytes(),
                source_event_id=event.id,
                confidence=0.9  # High confidence since user confirmed
            )
            session.add(person_embedding)
```

#### 4.4 Calibration Prompt Injection

```python
def format_calibration_context(
    calibration: CameraCalibration | None,
    recent_feedback: list[EventFeedback]
) -> str:
    """Format calibration data for prompt injection."""

    if not calibration or calibration.total_feedback_count < 5:
        return ""  # Not enough data yet

    lines = ["## CALIBRATION ADJUSTMENTS (Learned from Feedback)"]

    if calibration.risk_offset != 0:
        direction = "over-alerts" if calibration.risk_offset < 0 else "under-alerts"
        lines.append(f"This camera historically {direction}.")
        lines.append(f"Apply offset: {calibration.risk_offset:+d} points to final score")

    if calibration.false_positive_rate > 0.3:
        lines.append(f"⚠️ High false positive rate ({calibration.false_positive_rate:.0%}) at this camera")
        lines.append("Be MORE conservative with high scores")

    # Recent false positive patterns
    fp_feedback = [f for f in recent_feedback if f.feedback_type == "false_positive"]
    if fp_feedback:
        lines.append("\nRecent false positives at this camera:")
        for fb in fp_feedback[:3]:
            lines.append(f"- Event {fb.event_id}: User said '{fb.what_was_wrong or 'Not a threat'}'")

    lines.append("")
    return "\n".join(lines)
```

---

### Part 5: Leveraging Existing Infrastructure

Research revealed significant **existing features that are implemented but underutilized**. These represent quick wins.

#### 5.1 X-CLIP Temporal Action Recognition (NEVER CALLED)

**Status:** Endpoint implemented, never invoked.

**Available Actions:**

- `loitering`, `approaching_door`, `running_away`
- `checking_car_doors`, `suspicious_behavior`
- `breaking_in`, `vandalism`

**Problem:** Pipeline processes single frames; X-CLIP needs frame sequences.

**Solution - Frame Buffer Service:**

```python
# backend/services/frame_buffer.py

class FrameBuffer:
    """Buffer recent frames for temporal analysis."""

    def __init__(self, buffer_size: int = 16, max_age_seconds: float = 30.0):
        self.buffer_size = buffer_size
        self.max_age = max_age_seconds
        self._buffers: dict[str, deque[FrameData]] = {}  # camera_id -> frames

    async def add_frame(self, camera_id: str, frame: bytes, timestamp: datetime) -> None:
        """Add frame to buffer, evicting old frames."""
        if camera_id not in self._buffers:
            self._buffers[camera_id] = deque(maxlen=self.buffer_size)

        buffer = self._buffers[camera_id]

        # Evict frames older than max_age
        cutoff = timestamp - timedelta(seconds=self.max_age)
        while buffer and buffer[0].timestamp < cutoff:
            buffer.popleft()

        buffer.append(FrameData(frame=frame, timestamp=timestamp))

    def get_sequence(self, camera_id: str, num_frames: int = 8) -> list[bytes] | None:
        """Get recent frame sequence for X-CLIP analysis."""
        buffer = self._buffers.get(camera_id)
        if not buffer or len(buffer) < num_frames:
            return None

        # Sample evenly across buffer
        indices = np.linspace(0, len(buffer) - 1, num_frames, dtype=int)
        return [buffer[i].frame for i in indices]
```

**Integration:**

```python
# In enrichment_pipeline.py
async def _run_action_recognition(self, camera_id: str) -> ActionResult | None:
    """Run X-CLIP on buffered frames."""
    frames = self.frame_buffer.get_sequence(camera_id, num_frames=8)
    if frames is None:
        return None  # Not enough frames yet

    return await self.enrichment_client.classify_action(frames)
```

**Prompt Integration:**

```
## BEHAVIORAL ANALYSIS (Temporal)
Action detected: loitering (78% confidence)
Duration: ~25 seconds across 8 frames
→ RISK MODIFIER: +15 points (suspicious lingering behavior)
```

#### 5.2 Scene Tampering Detection (COMPLETELY UNUSED)

**Status:** SSIM scores stored in `SceneChange` table, never included in prompts.

**Available Data:**

```python
SceneChange:
    similarity_score: float    # 0-1 SSIM score
    change_type: str           # view_blocked, angle_changed, tampered, unknown
    detected_at: datetime
    acknowledged: bool
```

**Solution - Add to Prompt Context:**

```python
def format_camera_health_context(
    camera_id: str,
    recent_scene_changes: list[SceneChange]
) -> str:
    """Format camera health/tampering alerts for prompt."""

    if not recent_scene_changes:
        return ""

    # Get most recent unacknowledged change
    recent = next((sc for sc in recent_scene_changes if not sc.acknowledged), None)
    if not recent:
        return ""

    lines = ["## ⚠️ CAMERA HEALTH ALERT"]

    if recent.change_type == "view_blocked":
        lines.append(f"Camera view may be BLOCKED (similarity: {recent.similarity_score:.0%})")
        lines.append("→ Detection confidence is DEGRADED")
    elif recent.change_type == "angle_changed":
        lines.append(f"Camera angle has CHANGED (similarity: {recent.similarity_score:.0%})")
        lines.append("→ Baseline patterns may not apply")
    elif recent.change_type == "tampered":
        lines.append(f"Possible TAMPERING detected (similarity: {recent.similarity_score:.0%})")
        lines.append("→ CRITICAL: Verify camera integrity")

    lines.append("")
    return "\n".join(lines)
```

**Risk Impact:**

- `view_blocked` during intrusion = **+30 points** (coordinated attack indicator)
- `tampered` + unknown person = **escalate to CRITICAL**

#### 5.3 Enhanced Re-ID Context (PARTIAL USE)

**Status:** Re-ID data appears in prompts but not properly weighted.

**Available but Underutilized:**

```python
Entity:
    detection_count: int       # Lifetime appearances (e.g., 47 times)
    first_seen_at: datetime    # When first detected
    last_seen_at: datetime     # Most recent detection
    trust_status: str          # trusted/untrusted/unknown
```

**Repository Methods Available:**

- `get_repeat_visitors()` - Entities seen multiple times
- `get_with_high_detection_count(threshold=10)` - Frequent visitors

**Enhanced Prompt Format:**

```python
def format_enhanced_reid_context(
    person_id: int,
    entity: Entity | None,
    matches: list[ReIDMatch]
) -> str:
    """Format re-identification with proper risk weighting."""

    if not entity:
        return f"Person {person_id}: FIRST TIME SEEN (unknown)\n→ Base risk: 50"

    lines = [f"## Person {person_id} Re-Identification"]

    # Calculate familiarity score
    days_known = (datetime.now() - entity.first_seen_at).days

    if entity.detection_count >= 20 and days_known >= 7:
        lines.append(f"FREQUENT VISITOR: Seen {entity.detection_count}x over {days_known} days")
        lines.append(f"Trust status: {entity.trust_status}")
        if entity.trust_status == "trusted":
            lines.append("→ RISK MODIFIER: -40 points (established trusted entity)")
        else:
            lines.append("→ RISK MODIFIER: -20 points (familiar but unverified)")
    elif entity.detection_count >= 5:
        lines.append(f"RETURNING VISITOR: Seen {entity.detection_count}x")
        lines.append("→ RISK MODIFIER: -10 points (repeat visitor)")
    else:
        lines.append(f"RECENT VISITOR: Seen {entity.detection_count}x (first: {days_known}d ago)")
        lines.append("→ No risk modifier (insufficient history)")

    return "\n".join(lines)
```

#### 5.4 Self-Evaluation Feedback Loop (EXISTS BUT NOT USED)

**Status:** `PipelineQualityAuditService` collects recommendations but doesn't feed them back.

**Available Infrastructure:**

```python
# Already exists in pipeline_quality_audit_service.py
get_recommendations() -> list[Recommendation]
    # Returns prioritized suggestions aggregated from all audits:
    # - missing_context (what data would help)
    # - format_suggestions (how to restructure prompts)
    # - model_gaps (what models should contribute)
```

**Solution - Auto-Improve Prompts:**

```python
# backend/services/prompt_auto_tuner.py

class PromptAutoTuner:
    """Use accumulated audit feedback to improve prompts."""

    async def get_tuning_context(self, camera_id: str) -> str:
        """Get auto-tuning recommendations for prompt injection."""

        recommendations = await self.audit_service.get_recommendations(
            camera_id=camera_id,
            days=14,
            min_priority="MEDIUM"
        )

        if not recommendations:
            return ""

        lines = ["## AUTO-TUNING (From Historical Analysis)"]

        # Group by category
        missing = [r for r in recommendations if r.category == "missing_context"]
        if missing:
            lines.append("Previously helpful context that was missing:")
            for r in missing[:3]:
                lines.append(f"  - {r.suggestion}")

        format_issues = [r for r in recommendations if r.category == "format_suggestions"]
        if format_issues:
            lines.append("Known prompt clarity issues:")
            for r in format_issues[:2]:
                lines.append(f"  - {r.suggestion}")

        return "\n".join(lines)
```

#### 5.5 Per-Class Baselines (MINIMAL USE)

**Status:** `ClassBaseline` tracks per-object-type frequency but barely used.

**Available Data:**

```python
ClassBaseline:
    camera_id: str
    hour: int              # 0-23
    detection_class: str   # "person", "car", "dog", etc.
    frequency: float       # EWMA of detections per hour
    sample_count: int
```

**Enhanced Anomaly Detection:**

```python
def format_class_anomaly_context(
    camera_id: str,
    current_hour: int,
    detections: dict[str, int],  # class -> count
    baselines: dict[str, ClassBaseline]
) -> str:
    """Format per-class anomaly detection."""

    anomalies = []

    for cls, count in detections.items():
        baseline = baselines.get(f"{camera_id}:{current_hour}:{cls}")
        if not baseline or baseline.sample_count < 10:
            continue

        expected = baseline.frequency
        if expected < 0.1:  # Rare class
            if count >= 1:
                anomalies.append({
                    "class": cls,
                    "message": f"{cls} RARE at this hour (expected: {expected:.1f}/hr, actual: {count})",
                    "severity": "high" if cls in ["person", "vehicle"] else "medium"
                })
        elif count > expected * 3:  # 3x normal
            anomalies.append({
                "class": cls,
                "message": f"{cls} UNUSUAL volume ({count} vs expected {expected:.1f})",
                "severity": "medium"
            })

    if not anomalies:
        return ""

    lines = ["## CLASS-SPECIFIC ANOMALIES"]
    for a in anomalies:
        icon = "🔴" if a["severity"] == "high" else "🟡"
        lines.append(f"{icon} {a['message']}")

    return "\n".join(lines)
```

**Example Output:**

```
## CLASS-SPECIFIC ANOMALIES
🔴 person RARE at 3am (expected: 0.1/hr, actual: 2)
🟡 vehicle UNUSUAL volume (5 vs expected 1.2)
→ RISK MODIFIER: +15 points (statistically anomalous activity)
```

#### 5.6 A/B Testing for Safe Rollout

**Status:** Infrastructure exists, ready to use.

**Available:**

```python
ABTestConfig       # Control/treatment prompt versions
ShadowModeConfig   # Run new prompts without affecting users
RollbackConfig     # Auto-rollback on performance degradation
```

**Usage for This Project:**

1. Deploy new prompts in **shadow mode** first
2. Compare risk distributions: old vs new
3. Validate FP rate reduction before switching
4. Auto-rollback if latency increases >50%

---

## Implementation Plan

### Phase 1: Data Quality Fixes (1-2 days)

1. Audit Florence-2 response format
2. Fix VQA parsing in enrichment pipeline
3. Add clothing validation logic
4. Implement pose/scene conflict resolution
5. Add unit tests for all validators

### Phase 2: Leverage Existing Infrastructure (2-3 days)

_Quick wins from underutilized features_

1. **Scene Tampering Integration**

   - Add `format_camera_health_context()` to prompts
   - Query recent `SceneChange` records for camera
   - Risk escalation rules for tampering + intrusion

2. **Enhanced Re-ID Weighting**

   - Implement `format_enhanced_reid_context()`
   - Query entity history (detection_count, first_seen_at)
   - Apply risk modifiers based on familiarity

3. **Per-Class Baseline Anomalies**

   - Implement `format_class_anomaly_context()`
   - Flag rare objects at unusual hours
   - Add to enriched prompt templates

4. **Self-Evaluation Feedback Loop**
   - Connect `get_recommendations()` to prompt builder
   - Inject historical improvement suggestions
   - Track which suggestions improve scores

### Phase 3: Household Context (2-3 days)

1. Create database migrations for new models
2. Implement HouseholdMatcher service
3. Build API endpoints for managing members/vehicles
4. Integrate matching into analysis pipeline
5. Add prompt formatting for household context

### Phase 4: Prompt Restructuring (1-2 days)

1. Update system prompt with calibration guidance
2. Restructure user prompt template
3. Implement conditional section inclusion
4. Add scoring reference table
5. Update all 5 template tiers

### Phase 5: Feedback Loop (2-3 days)

1. Enhance EventFeedback model
2. Create CameraCalibration model
3. Build FeedbackProcessor service
4. Add calibration prompt injection
5. Create UI for quick feedback actions

### Phase 6: X-CLIP Temporal Analysis (3-4 days)

_Requires architectural change for frame buffering_

1. Implement `FrameBuffer` service
2. Modify detection pipeline to buffer frames
3. Add X-CLIP invocation on sufficient frames
4. Implement `format_action_recognition_context()`
5. Test with loitering/suspicious behavior scenarios

### Phase 7: Testing & Validation (2-3 days)

1. **Shadow Mode Deployment**

   - Deploy new prompts in shadow mode
   - Compare risk distributions: old vs new
   - Validate no latency regression

2. **A/B Testing**

   - Run 50/50 split for 48 hours
   - Measure FP rate via user feedback
   - Auto-rollback if degradation detected

3. **Historical Replay**

   - Replay 500+ events through new pipeline
   - Compare scores: should shift toward LOW
   - Document edge cases that still score HIGH

4. **Load Testing**
   - Verify household matching latency <50ms
   - Test frame buffer memory usage
   - Validate concurrent inference limits

---

## Success Metrics

| Metric                       | Current | Target       | Measurement       |
| ---------------------------- | ------- | ------------ | ----------------- |
| Low risk events              | 8%      | 50-60%       | DB query          |
| High/Critical events         | 67%     | 15-20%       | DB query          |
| False positive rate          | ~60%\*  | <20%         | User feedback     |
| Household member recognition | 0%      | >90%         | Matching accuracy |
| User satisfaction            | Unknown | >80% correct | Feedback survey   |

\*Estimated from audit data showing most high-risk events were benign

---

## Risks and Mitigations

| Risk                                  | Impact | Mitigation                                         |
| ------------------------------------- | ------ | -------------------------------------------------- |
| Florence-2 fix breaks other features  | High   | Thorough integration testing                       |
| Household matching too slow           | Medium | Cache embeddings, async matching                   |
| Users don't provide feedback          | Medium | Make feedback UI frictionless                      |
| Over-correction causes missed threats | High   | Set minimum score floors, alert on violence always |
| Database migration issues             | Medium | Test migrations on staging first                   |

---

## Open Questions

1. **Household member onboarding**: Should we provide a "learn residents" mode that auto-captures frequent faces over 7 days?

2. **Vehicle matching accuracy**: License plate OCR vs visual matching - which is more reliable for this use case?

3. **Feedback incentives**: Should the UI gamify feedback ("Help improve detection accuracy")?

4. **Multi-property support**: Design assumes single household - need to consider multi-property deployments?

---

## Appendix: Sample Prompts

### Before (Current)

```
<|im_start|>system
You are an advanced home security risk analyzer...
<|im_start|>user
## Camera & Time Context
Camera: Beach Front Left
...
## Detections with Full Enrichment
### PERSON (ID: 2890)
Florence-2: Wearing: VQA>person wearing<loc_95><loc_86>...
...
## Risk Interpretation Guide
[Generic 40-line guide at the bottom]
```

### After (Proposed)

```
<|im_start|>system
You are a home security analyst for the Svoboda residence.
CRITICAL: Most detections are NOT threats...
<|im_start|>user
## RISK MODIFIERS (Apply First)
┌────────────────────────────────────────────┐
│ KNOWN PERSON: Mike (resident, 93% match)  │
│ Schedule: ✓ Within expected hours          │
│ → Base risk: 5                             │
└────────────────────────────────────────────┘

## EVENT CONTEXT
[Clean, relevant data only]

## SCORING REFERENCE
[Calibration examples inline]

## YOUR TASK
Start from base risk 5. Most events should score LOW.
```
