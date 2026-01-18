# AI Audit Dashboard

> Monitor AI quality metrics and review prompt improvement recommendations.

**Time to read:** ~8 min
**Prerequisites:** [Dashboard Basics](dashboard-basics.md), [AI Enrichment Data](ai-enrichment.md)

---

## Overview

The AI Audit Dashboard helps you understand how well the AI system is performing. It shows quality metrics, consistency scores, and recommendations for improving the AI's analysis. This page is useful for power users who want to fine-tune their security system or verify the AI is working correctly.

<!-- SCREENSHOT: AI Audit Dashboard Overview
Location: AI Audit page (accessible from sidebar)
Shows: Complete AI Audit Dashboard with header, period selector, quality score cards, and recommendations panel
Size: 1400x900 pixels (16:9 aspect ratio)
Alt text: AI Audit Dashboard showing quality metrics cards and prompt improvement recommendations
-->
<!-- Screenshot: AI Audit Dashboard with quality metrics and recommendations -->

_Caption: The AI Audit Dashboard shows quality metrics and improvement suggestions._

---

## Accessing the AI Audit Dashboard

1. Click **AI Audit** in the left sidebar
2. The dashboard loads with data from the last 7 days by default
3. Use the period selector to change the time range

---

## Quality Score Metrics

The top section displays four metric cards showing how well the AI is performing:

<!-- SCREENSHOT: Quality Score Cards
Location: Top section of AI Audit Dashboard
Shows: Four metric cards in a row - Average Quality, Consistency Rate, Enrichment Utilization, Evaluation Coverage
Size: 1200x200 pixels (6:1 aspect ratio)
Alt text: Four quality metric cards showing scores with progress bars
-->
<!-- Screenshot: Quality score metric cards with progress bars -->

_Caption: Quality metrics give you a quick overview of AI performance._

### Average Quality Score

How well the AI is analyzing events, on a scale of 1 to 5.

| Score Range | Color  | Meaning                           |
| ----------- | ------ | --------------------------------- |
| 4.0 - 5.0   | Green  | Excellent - AI is performing well |
| 3.0 - 3.9   | Yellow | Good - Room for improvement       |
| Below 3.0   | Red    | Needs attention - Quality is low  |

The number below shows how many events were evaluated to calculate this score.

### Consistency Rate

How consistent the AI is when re-evaluating the same events. A high consistency rate means the AI gives similar risk scores when analyzing the same situation multiple times.

| Score Range | Color  | Meaning                         |
| ----------- | ------ | ------------------------------- |
| 4.0 - 5.0   | Green  | Highly consistent               |
| 3.0 - 3.9   | Yellow | Moderately consistent           |
| Below 3.0   | Red    | Inconsistent - results may vary |

### Enrichment Utilization

What percentage of AI models are contributing to event analysis. Higher utilization means more AI models are providing useful data.

| Percentage | Color  | Meaning                           |
| ---------- | ------ | --------------------------------- |
| 70%+       | Green  | Most models contributing          |
| 50-69%     | Yellow | Some models not providing data    |
| Below 50%  | Red    | Many models missing - investigate |

### Evaluation Coverage

What percentage of events have been fully evaluated by the AI audit system.

| Percentage | Color  | Meaning                       |
| ---------- | ------ | ----------------------------- |
| 80%+       | Green  | Most events evaluated         |
| 50-79%     | Yellow | Some events not yet evaluated |
| Below 50%  | Red    | Many events need evaluation   |

---

## Prompt Improvement Recommendations

The Recommendations Panel shows suggestions for improving the AI's analysis based on patterns found in evaluated events.

<!-- SCREENSHOT: Recommendations Panel
Location: Below quality score cards on AI Audit Dashboard
Shows: Recommendations panel with expandable accordion sections grouped by category, showing priority badges and frequency counts
Size: 1000x400 pixels (2.5:1 aspect ratio)
Alt text: Recommendations panel with expandable sections for Missing Context, Unused Data, and other categories
-->
<!-- Screenshot: Recommendations panel with expandable category sections -->

_Caption: Recommendations are grouped by category with priority indicators._

### Understanding Categories

Recommendations are grouped into categories:

| Category               | Icon    | Description                                                |
| ---------------------- | ------- | ---------------------------------------------------------- |
| **Missing Context**    | Warning | Information that would help the AI make better assessments |
| **Unused Data**        | Info    | Data that was provided but not useful for analysis         |
| **Model Gaps**         | Warning | AI models that should have contributed but did not         |
| **Format Suggestions** | Bulb    | Ways to improve the prompt structure                       |
| **Confusing Sections** | Info    | Parts of the prompt that were unclear                      |

### Reading Recommendations

Each recommendation shows:

1. **Suggestion text** - What could be improved
2. **Priority badge** - How important the change is:
   - **High** (Red) - Should be addressed soon
   - **Medium** (Yellow) - Worth considering
   - **Low** (Gray) - Minor improvement
3. **Frequency** - How often this issue was seen (e.g., "12x")

Click any category header to expand or collapse its recommendations.

---

## Changing the Time Period

Use the period selector in the top-right corner to view data from different time ranges:

| Option       | Shows Data From     |
| ------------ | ------------------- |
| Last 24h     | Past day only       |
| Last 7 days  | Past week (default) |
| Last 14 days | Past two weeks      |
| Last 30 days | Past month          |
| Last 90 days | Past three months   |

Longer periods give you more data for accurate trends but may take longer to load.

---

## Triggering a Batch Audit

You can manually trigger the AI to re-evaluate events for quality analysis.

<!-- SCREENSHOT: Batch Audit Modal
Location: Modal dialog triggered by "Trigger Batch Audit" button
Shows: Batch audit configuration modal with Event Limit, Minimum Risk Score, and Force Re-evaluate options
Size: 500x400 pixels (1.25:1 aspect ratio)
Alt text: Batch audit configuration dialog with limit and risk score inputs
-->
<!-- Screenshot: Batch audit modal with configuration options -->

_Caption: Configure batch audit settings before triggering evaluation._

### How to Trigger a Batch Audit

1. Click the **Trigger Batch Audit** button (green, top-right)
2. Configure the options:
   - **Event Limit** - Maximum events to process (1-1000, default 50)
   - **Minimum Risk Score** - Only process events at or above this score (0-100, default 50)
   - **Force Re-evaluate** - Check this to re-process events already evaluated
3. Click **Start Batch Audit**
4. A success message appears when events are queued

### When to Use Batch Audit

- After making changes to the AI configuration
- When you want to analyze high-risk events more thoroughly
- To generate fresh recommendations based on recent patterns
- To verify AI consistency by re-evaluating the same events

---

## Refreshing Data

Click the **Refresh** button (gray, top-right) to reload the latest metrics. The button shows a spinning icon while data is loading.

If an error occurs while refreshing, you will see a yellow banner explaining the issue. The page will continue showing the previously loaded data.

---

## Interpreting Your Results

### Good AI Performance

Signs that your AI system is healthy:

- **Average Quality Score:** 4.0 or higher
- **Consistency Rate:** 4.0 or higher
- **Enrichment Utilization:** 70% or higher
- **Evaluation Coverage:** 80% or higher
- **Recommendations:** Mostly low priority items

### Areas for Improvement

Watch for these warning signs:

- **Low quality scores** - The AI may need configuration adjustments
- **Low consistency** - Results vary too much; investigate why
- **Low enrichment** - Some AI models may not be contributing
- **High-priority recommendations** - Address these for better accuracy

---

## Next Steps

- [AI Enrichment Data](ai-enrichment.md) - Understand the AI analysis in event details
- [Dashboard Settings](dashboard-settings.md) - Configure AI processing options

---

## See Also

- [Dashboard Basics](dashboard-basics.md) - Main dashboard overview
- [Understanding Alerts](understanding-alerts.md) - How risk levels work
- [AI Pipeline Overview](../architecture/ai-pipeline.md) - Technical documentation

---

[Back to User Hub](../user/README.md)
