# AI Audit

The AI Audit page provides transparency into how the AI models make decisions, allowing you to understand, evaluate, and improve the AI-powered security analysis.

## What You're Looking At

The AI Audit Dashboard helps you understand and improve the quality of AI-generated security assessments. It provides:

- **Quality Metrics** - How well the AI is performing (1-5 scale scores)
- **Model Contributions** - Which AI models contributed to analyses
- **Recommendations** - AI-generated suggestions for improving prompt templates
- **Prompt Playground** - Interactive environment for testing prompt modifications
- **Version History** - Track and restore previous prompt configurations

This page is essential for maintaining and improving AI accuracy over time. By analyzing the AI's self-evaluation, you can identify patterns where the AI struggles and make targeted improvements.

## Key Components

The AI Audit page uses a tabbed interface with four main sections. Note: The page title displays as "AI Audit Dashboard" and Model contribution rates are shown alongside quality metrics on the Dashboard tab.

### Dashboard Tab

The default view showing aggregate quality metrics and recommendations.

#### Quality Score Metrics

Four stat cards display aggregate performance over the selected time period:

| Metric                     | Description                                                                                                                                              |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Average Quality Score**  | Overall quality of AI analyses (1-5 scale, higher is better). Displayed as "X.X / 5" with a progress bar. Based on the number of fully evaluated events. |
| **Consistency Rate**       | How consistent the AI is when re-analyzing the same events (1-5 scale). Measures risk score consistency on re-evaluation.                                |
| **Enrichment Utilization** | Percentage of AI models contributing to analyses (0-100%). Indicates how many enrichment sources were available and used.                                |
| **Evaluation Coverage**    | Percentage of events that have been fully evaluated. Shows "X of Y events evaluated".                                                                    |

**Score Interpretation:**

- **4.0-5.0 (Green):** Excellent - AI is performing well
- **3.0-3.9 (Yellow):** Good - Room for improvement
- **1.0-2.9 (Red):** Needs attention - Consider prompt adjustments

#### Model Contribution Breakdown

A horizontal bar chart showing the contribution rate of each AI model to event analyses. Each bar shows:

- Model name with icon
- Number of events the model contributed to
- Percentage contribution rate (0-100%)

| Model              | Description                                 |
| ------------------ | ------------------------------------------- |
| RT-DETRv2          | Object detection (always active)            |
| Florence-2         | Visual question-answering for scene details |
| X-CLIP             | Action recognition (walking, running, etc.) |
| Violence Detection | Violence classifier for suspicious behavior |
| Clothing Analysis  | FashionCLIP clothing identification         |
| Vehicle Detection  | Vehicle type and color classification       |
| Pet Detection      | Pet vs. wildlife classification             |
| Weather Analysis   | Environmental condition assessment          |
| Image Quality      | Camera image quality scoring                |
| Zone Analysis      | Entry point and security zone context       |
| Baseline           | Historical activity pattern comparison      |
| Cross-Camera       | Correlation with other camera detections    |

Models are sorted by contribution rate in descending order. Higher contribution rates indicate the model data was available and used in analyses.

#### Prompt Improvement Recommendations

AI-generated suggestions for improving prompt templates, displayed in an accordion grouped by category. The panel header shows the total "High Priority" count and how many events were analyzed.

| Category               | Description                                                | Icon             |
| ---------------------- | ---------------------------------------------------------- | ---------------- |
| **Missing Context**    | Information that would help the AI make better assessments | Warning triangle |
| **Unused Data**        | Provided data that was not useful for analysis             | Info circle      |
| **Model Gaps**         | AI models that should have provided data but did not       | Warning triangle |
| **Format Suggestions** | Ways to improve the prompt structure                       | Lightbulb        |
| **Confusing Sections** | Parts of the prompt that were unclear or contradictory     | Info circle      |

Each category accordion shows:

- **Item count** - Number of suggestions in that category
- **High priority count** - If any suggestions are high priority

Each recommendation item shows:

- **Suggestion text** - What to improve
- **Category badge** - Color-coded by category type
- **Priority badge** - High (red), Medium (yellow), or Low (gray)
- **Frequency count** - How many events mentioned this (e.g., "5x")
- **Edit Prompt button** - Opens the Prompt Playground with that recommendation context

Recommendations are sorted by priority (high first), then by frequency within each category.

### Prompt Playground Tab

An interactive slide-out panel (80% viewport width) for editing, testing, and refining AI model prompts. Opens when you click "Open Prompt Playground". Press Escape to close.

#### Supported Models

Each model has an accordion-style editor. The first model (Nemotron) is expanded by default. A "(modified)" indicator with a pulsing dot appears when you have unsaved changes.

| Model        | Editor Type                               | What You Can Configure                                                                                                                                                                      |
| ------------ | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Nemotron     | Full text editor with syntax highlighting | System prompt with highlighted variables like `{detections}`, `{cross_camera_data}`, `{weather}`, `{time_context}`. Also includes Temperature slider (0-2) and Max Tokens input (100-8192). |
| Florence-2   | Multi-line text (one per line)            | VQA queries for visual scene analysis                                                                                                                                                       |
| YOLO-World   | Multi-line text + slider                  | Object classes (one per line) + confidence threshold slider (0-1)                                                                                                                           |
| X-CLIP       | Multi-line text                           | Action recognition classes (one per line)                                                                                                                                                   |
| Fashion-CLIP | Two text areas                            | Clothing categories + suspicious indicators (one per line each)                                                                                                                             |

**Syntax Highlighting:** The Nemotron editor highlights prompt variables like `{variable_name}` in green with a subtle background, and includes line numbers.

#### Diff Preview Flow

When opening from a recommendation with an enriched suggestion:

1. **Preview Changes** - See a side-by-side diff view showing original vs. modified prompt
2. **Suggestion Explanation** - View why this change is recommended with event links
3. **Apply or Dismiss** - Apply the suggestion to the editor or dismiss it
4. **Applied Banner** - After applying, shows "Suggestion applied. Test it or save to keep your changes."

#### A/B Testing Workflow

After applying a suggestion or making changes, the A/B Test section appears:

1. **Run A/B Test** - Tests the modified prompt against a real event (uses the Event ID field, or picks a random recent event)
2. **View Results** - Shows test count (e.g., "3 tests completed")
3. **Run More Tests** - Requires at least 3 tests before promoting
4. **Promote B as Default** - Opens a confirmation dialog showing:
   - Average score change (green if negative = improvement, red if positive = regression)
   - Improvement rate percentage
5. **Confirm Promote** - Saves the modified prompt as the new default

**Note:** The "Promote B" button shows a warning "Run at least 3 tests before promoting" if fewer than 3 tests have been run.

#### Test Configuration

A separate "Test Configuration" section at the bottom allows you to:

1. Enter an **Event ID** to test against
2. Click **Run Test** to compare before/after results
3. View side-by-side results showing:
   - Score and risk level (before and after)
   - Summary text
   - Whether the configuration "improved results" (green) or "did not improve results" (yellow)
   - Inference time in milliseconds

#### Save, Export, and Import

Each model has its own action buttons:

- **Reset** - Revert to the original saved configuration (shows toast notification)
- **Save** - Persist changes to the database (creates new version, shows "Saved!" with checkmark)

Footer buttons:

- **Import JSON** - Load configurations from a JSON file (validates format)
- **Export JSON** - Download all prompt configurations as JSON (filename: `prompt-configs-YYYY-MM-DD.json`)

**Toast Notifications:** Success, error, and info messages appear in the bottom-right corner and auto-dismiss after 3 seconds.

### Batch Audit Tab

Trigger batch evaluation of events to generate quality metrics and recommendations.

The tab shows summary stats:

- **Total Events** - Total events in the selected time period
- **Audited Events** - Events that have some audit data
- **Fully Evaluated** - Events that have completed full evaluation

#### Batch Audit Modal

Click "Trigger Batch Audit" to open the configuration modal:

| Option                 | Default | Range  | Description                                                |
| ---------------------- | ------- | ------ | ---------------------------------------------------------- |
| **Event Limit**        | 50      | 1-1000 | Maximum number of events to process                        |
| **Minimum Risk Score** | 50      | 0-100  | Only process events with risk score at or above this value |
| **Force Re-evaluate**  | Off     | On/Off | Re-process events that have already been evaluated         |

#### Batch Audit Process

1. Click "Trigger Batch Audit" button
2. Configure options in the modal
3. Click "Start Batch Audit" (button shows "Processing..." while submitting)
4. Modal closes and a success banner appears: "Queued X events for evaluation"
5. The batch runs asynchronously in the background
6. Use the `/api/ai-audit/batch/{job_id}` endpoint to track progress (see API Endpoints)
7. Refresh the Dashboard tab to see updated metrics

**Note:** If no events match the criteria, the job completes immediately with "No events found matching criteria".

#### Self-Evaluation Modes

The audit service runs 4 evaluation passes on each event:

| Mode                   | What It Does                                                                                    |
| ---------------------- | ----------------------------------------------------------------------------------------------- |
| **Self-Critique**      | AI critiques its own previous analysis                                                          |
| **Rubric Scoring**     | Scores on context usage, reasoning coherence, risk justification (1-5 scale each)               |
| **Consistency Check**  | Re-analyzes the event with a clean prompt and compares risk scores                              |
| **Prompt Improvement** | Identifies missing context, unused data, model gaps, format suggestions, and confusing sections |

### Version History Tab

View and restore previous prompt configurations.

#### Version History Features

- **Model Filter Dropdown** - Filter versions by specific model or view "All Models"
  - Available options: All Models, Nemotron, Florence-2, YOLO-World, X-CLIP, Fashion-CLIP
- **Refresh Button** - Reload the version history
- **Version Table** - Shows version number, model, date, changes, status, and actions

#### Version Table Columns

| Column  | Description                                                                             |
| ------- | --------------------------------------------------------------------------------------- |
| Version | Sequential version identifier displayed as "vX" (e.g., v1, v2)                          |
| Model   | Which model this version applies to (formatted display name)                            |
| Date    | When created, shown as relative time (e.g., "2h ago", "3d ago") with full date on hover |
| Changes | Description of what changed, or "No description" if none provided                       |
| Status  | "Active" (green badge) for current version, "Previous" (gray badge) for older versions  |
| Actions | "Restore" button (only shown for non-active versions)                                   |

#### Restore Process

1. Click "Restore" on a previous version
2. Button shows loading spinner during restore
3. On success, a green banner appears: "Restored [Model] to version X (new version: Y)"
4. The table refreshes to show the new active version
5. On error, a red banner appears with the error message

**Note:** Restoring a version creates a new version entry (it doesn't overwrite). The restored content becomes the new active version with an incremented version number.

## Settings & Configuration

### Period Selector

The time period dropdown in the header controls which data is displayed:

| Period       | Description            |
| ------------ | ---------------------- |
| Last 24h     | Yesterday's audit data |
| Last 7 days  | Rolling week (default) |
| Last 14 days | Two week window        |
| Last 30 days | Monthly view           |
| Last 90 days | Quarterly view         |

### Refresh

Click the Refresh button to reload all data without changing the page.

## Troubleshooting

### "No Events Have Been Audited Yet"

This appears when no events have been processed through the audit system.

**Solution:** Click "Trigger Batch Audit" to start evaluating events. The audit requires:

- Events exist in the database
- Events have AI analysis (risk scores)
- Nemotron LLM service is running

### Quality Scores Show "N/A"

Quality scores are only available for fully evaluated events.

**Possible causes:**

- Batch audit hasn't run yet
- Nemotron service was unavailable during evaluation
- Events don't have LLM prompts stored

**Solution:** Run a batch audit with "Force Re-evaluate" enabled.

### Model Contribution Rates Are Low

Low contribution rates indicate certain AI models aren't being used.

**Possible causes:**

- Model service is offline
- No relevant detections (e.g., no vehicles for vehicle classification)
- Model is disabled in configuration

**Check:** Go to AI Performance page to verify model health status.

### Recommendations Are Empty

Recommendations are generated from fully evaluated events.

**Solution:**

1. Verify events exist in the time period
2. Run a batch audit to evaluate events
3. Check that events have LLM prompts (older events may not)

### Prompt Playground Test Fails

Test failures can occur when running tests or A/B tests.

**Common causes:**

- Nemotron LLM service is offline
- Event no longer exists in database
- Network timeout during inference
- Invalid Event ID entered (must be a positive integer)
- No events available for A/B testing (when no Event ID is provided)

**Solution:**

1. Check AI Performance page for Nemotron health
2. Verify the Event ID exists in the Timeline page
3. Try a different event ID
4. Wait and retry (inference takes 2-5 seconds)
5. Check the error message displayed in the red error banner

**A/B Test Specific:**

- If no Event ID is entered, the system picks a random event from the 5 most recent events
- If no events exist at all, you'll see "No events available for A/B testing"

### Version Restore Failed

Restoring a previous version creates a new version entry.

**Possible causes:**

- Database connection issue
- Original version data is corrupted
- Network error during API call

**Solution:**

1. Try the restore again (click the Restore button)
2. Check the red error banner for the specific error message
3. If it persists, check backend logs for `PromptApiError` details
4. Verify the prompt management API is accessible

---

## Technical Deep Dive

For developers wanting to understand the underlying systems.

### Architecture

- **AI Pipeline**: [AI Pipeline Architecture](../architecture/ai-pipeline.md)
- **Self-Evaluation Service**: `backend/services/pipeline_quality_audit_service.py`
- **API Routes**: `backend/api/routes/ai_audit.py`
- **Prompt Management**: `backend/api/routes/prompt_management.py` (consolidated from ai_audit.py in NEM-2695)

### Self-Evaluation Modes

The audit service runs 4 evaluation passes on each event:

```
Mode 1: Self-Critique
  - Prompt: "Critique your own previous analysis"
  - Output: Text critique identifying strengths and weaknesses
  - Stored in: self_eval_critique field

Mode 2: Rubric Scoring (1-5 scale)
  - context_usage: Did analysis reference all relevant data?
  - reasoning_coherence: Is reasoning logical and well-structured?
  - risk_justification: Does evidence support the risk score?
  - Overall: Average of the three scores above

Mode 3: Consistency Check
  - Re-analyze the same event with clean prompt
  - Compare new risk score to original
  - Consistency score: 5 if diff <= 5, down to 1 if diff >= 25
  - Stored in: consistency_risk_score, consistency_diff

Mode 4: Prompt Improvement
  - Identify: missing_context, unused_data, model_gaps, format_suggestions, confusing_sections
  - Stored as JSON arrays
  - Aggregated across events into recommendations
```

### Quality Score Calculation

```
overall_quality = average(
  context_usage_score,
  reasoning_coherence_score,
  risk_justification_score
)

consistency_score = max(1.0, 5.0 - (risk_score_diff / 5))
```

**Note:** The consistency_score is separate from the overall_quality score. The UI displays them as separate metrics.

### API Endpoints

| Endpoint                             | Method | Description                               | Query Parameters                                    |
| ------------------------------------ | ------ | ----------------------------------------- | --------------------------------------------------- |
| `/api/ai-audit/stats`                | GET    | Aggregate audit statistics                | `days` (1-90, default 7), `camera_id` (optional)    |
| `/api/ai-audit/leaderboard`          | GET    | Model leaderboard by contribution         | `days` (1-90, default 7)                            |
| `/api/ai-audit/recommendations`      | GET    | Aggregated prompt improvement suggestions | `days` (1-90, default 7)                            |
| `/api/ai-audit/events/{id}`          | GET    | Get audit for specific event              | -                                                   |
| `/api/ai-audit/events/{id}/evaluate` | POST   | Trigger evaluation for specific event     | `force` (boolean, default false)                    |
| `/api/ai-audit/batch`                | POST   | Trigger batch audit processing (async)    | Body: `{ limit, min_risk_score, force_reevaluate }` |
| `/api/ai-audit/batch/{job_id}`       | GET    | Get batch audit job status and progress   | -                                                   |

**Batch Audit Response (202 Accepted):**

```json
{
  "job_id": "uuid-string",
  "status": "pending",
  "message": "Batch audit job created. Use GET /api/ai-audit/batch/{job_id} to track progress.",
  "total_events": 50
}
```

**Batch Job Status Response:**

```json
{
  "job_id": "uuid-string",
  "status": "running|completed|failed",
  "progress": 45,
  "message": "Processing event 23 of 50",
  "total_events": 50,
  "processed_events": 22,
  "failed_events": 1,
  "created_at": "2025-01-15T10:00:00Z",
  "started_at": "2025-01-15T10:00:01Z",
  "completed_at": null,
  "error": null
}
```

### Database Model

The `event_audits` table stores:

- **Model contribution flags**: `has_rtdetr`, `has_florence`, `has_clip`, `has_violence`, `has_clothing`, `has_vehicle`, `has_pet`, `has_weather`, `has_image_quality`, `has_zones`, `has_baseline`, `has_cross_camera`
- **Quality scores**: `context_usage_score`, `reasoning_coherence_score`, `risk_justification_score`, `consistency_score`, `overall_quality_score`
- **Consistency check results**: `consistency_risk_score`, `consistency_diff`
- **Prompt metadata**: `prompt_length`, `prompt_token_estimate`, `enrichment_utilization`
- **Prompt improvements (JSON)**: `missing_context`, `unused_data`, `model_gaps`, `format_suggestions`, `confusing_sections`
- **Self-evaluation text**: `self_eval_critique`
- **Status**: `is_fully_evaluated`, `audited_at`

### Related Code

| Component                    | Location                                                      |
| ---------------------------- | ------------------------------------------------------------- |
| **Main Page**                | `frontend/src/components/ai/AIAuditPage.tsx`                  |
| **Dashboard Component**      | `frontend/src/components/ai-audit/AIAuditDashboard.tsx`       |
| **Quality Score Trends**     | `frontend/src/components/ai/QualityScoreTrends.tsx`           |
| **Model Contribution Chart** | `frontend/src/components/ai-audit/ModelContributionChart.tsx` |
| **Recommendations Panel**    | `frontend/src/components/ai/RecommendationsPanel.tsx`         |
| **Prompt Playground**        | `frontend/src/components/ai/PromptPlayground.tsx`             |
| **Batch Audit Modal**        | `frontend/src/components/ai/BatchAuditModal.tsx`              |
| **Version History**          | `frontend/src/components/ai-audit/PromptVersionHistory.tsx`   |
| **Audit Progress Bar**       | `frontend/src/components/ai-audit/AuditProgressBar.tsx`       |
| **Audit Results Table**      | `frontend/src/components/ai-audit/AuditResultsTable.tsx`      |
| **Backend Service**          | `backend/services/pipeline_quality_audit_service.py`          |
| **API Routes**               | `backend/api/routes/ai_audit.py`                              |
| **API Schemas**              | `backend/api/schemas/ai_audit.py`                             |
| **Audit API (Frontend)**     | `frontend/src/services/auditApi.ts`                           |
