# Prompt Playground

> Edit, test, and refine AI model prompts and configurations with A/B testing and version history.

**Time to read:** ~15 min
**Prerequisites:** [AI Audit Dashboard](../user-guide/ai-audit.md), [Dashboard Basics](../user-guide/dashboard-basics.md)

---

## Overview

The Prompt Playground is a powerful tool for customizing how the AI analyzes security events. It allows you to edit the prompts and configurations used by each AI model, test changes against real events before applying them, and compare different versions side-by-side using A/B testing.

This tool is designed for power users who want to:

- Fine-tune AI risk assessments for their specific environment
- Reduce false positives by adjusting detection classes
- Improve risk scoring accuracy with better prompts
- Test changes safely before deploying them

---

## Who Should Use This

The Prompt Playground is intended for:

- **Power users** who want to customize AI behavior for their specific needs
- **System administrators** who need to optimize detection accuracy
- **Advanced users** comfortable with prompt engineering concepts

If you are new to the system, start with the [AI Audit Dashboard](../user-guide/ai-audit.md) to understand how the AI performs before making changes.

---

## Opening the Prompt Playground

There are two ways to access the Prompt Playground:

### From the AI Audit Dashboard

1. Navigate to **AI Audit** in the left sidebar
2. In the **Recommendations Panel**, find a recommendation you want to implement
3. Click **Apply Suggestion** on any recommendation
4. The Prompt Playground slides in from the right with the recommendation context

### From the Settings Page

1. Navigate to **Settings** in the left sidebar
2. Find the **Prompt Management** section
3. Click **Open Prompt Playground**

---

## Understanding the Interface

The Prompt Playground is a slide-out panel that takes up 80% of the screen width. It contains several sections:

### Header Section

The header shows:

- **Title:** "Prompt Playground"
- **Description:** Brief explanation of the tool's purpose
- **Recommendation context** (if opened from a recommendation): Shows the category, priority, and suggestion text

### Model Editors

Below the header, you will find expandable accordion panels for each AI model:

| Model            | Purpose                          | What You Can Edit                          |
| ---------------- | -------------------------------- | ------------------------------------------ |
| **Nemotron**     | Primary LLM for risk analysis    | System prompt, temperature, max tokens     |
| **Florence-2**   | Visual question-answering        | VQA queries for scene analysis             |
| **YOLO-World**   | Open-vocabulary object detection | Object classes, confidence threshold       |
| **X-CLIP**       | Action recognition               | Action classes to recognize                |
| **Fashion-CLIP** | Clothing and appearance analysis | Clothing categories, suspicious indicators |

Click any model accordion to expand and view its editor.

### Test Area

At the bottom of the panel, you will find the test area where you can:

- Enter an **Event ID** to test against
- **Run Test** to compare before/after results
- View test results with score comparison

### Footer Actions

The footer contains:

- **Import JSON** - Load configurations from a file
- **Export JSON** - Save current configurations to a file

---

## Editing Model Configurations

### Nemotron System Prompt

The Nemotron model uses a system prompt to analyze detection context and provide risk assessments. The editor provides:

1. **Available Variables** - Highlighted variables you can use:

   - `{detections}` - RT-DETR object detections
   - `{cross_camera_data}` - Related detections from other cameras
   - `{weather}` - Current weather conditions
   - `{time_context}` - Time of day and day of week

2. **System Prompt Editor** - A syntax-highlighted textarea with:

   - Line numbers for easy reference
   - Variable highlighting (variables shown in green)
   - Synchronized scrolling between line numbers and content

3. **Temperature Slider** - Controls response randomness (0.0 to 2.0):

   - Lower values (0.3-0.5): More deterministic, consistent responses
   - Higher values (0.7-1.0): More creative, varied responses

4. **Max Tokens** - Maximum response length (100-8192)

### Florence-2 VQA Queries

Enter one visual question-answering query per line. These are the questions asked about each captured image:

```
What is the person doing?
What objects are they carrying?
Describe the environment
Is there anything unusual in this scene?
```

### YOLO-World Object Classes

Define custom objects to detect. Enter one class per line:

```
person
vehicle
package
knife
suspicious bag
```

You can also adjust the **Confidence Threshold** (0.0-1.0) - higher values reduce false positives but may miss detections.

### X-CLIP Action Classes

Define actions to recognize in video clips:

```
walking
running
loitering
fighting
climbing fence
```

### Fashion-CLIP Settings

Configure clothing analysis with:

- **Clothing Categories** - Types of clothing to classify
- **Suspicious Indicators** - Patterns that may indicate suspicious activity (e.g., "all black", "face mask", "gloves at night")

---

## Testing Prompts

Before saving changes, you should test them against real events to see how they affect risk scoring.

### Running a Test

1. **Enter an Event ID** in the test area

   - You can find Event IDs on the Timeline page
   - Tip: Choose events with different risk levels to see varied results

2. **Click Run Test**

   - The system runs inference with both the original and modified configurations
   - This may take several seconds

3. **Review Results**
   - **Before** panel: Shows score with original configuration
   - **After** panel: Shows score with your changes
   - **Result indicator**: Shows if the change improved results

### Interpreting Test Results

| Indicator                     | Color  | Meaning                               |
| ----------------------------- | ------ | ------------------------------------- |
| Arrow pointing right (green)  | Green  | Configuration improved results        |
| Arrow pointing right (yellow) | Yellow | Configuration did not improve results |

The test compares risk scores before and after your changes. Generally:

- If the before and after scores are within 10 points, the change is considered successful
- Significant score changes may indicate the prompt needs adjustment

---

## A/B Testing

A/B testing allows you to compare your modified prompt against the original on multiple events to validate changes before deployment.

### What is A/B Testing?

A/B testing (also called split testing) compares two versions:

- **Version A (Control):** The current saved prompt
- **Version B (Treatment):** Your modified prompt

By testing both versions on the same events, you can see which performs better and make informed decisions about promoting changes.

### Running A/B Tests

When you apply a suggestion or make changes, the A/B Test section appears:

1. **Enter an Event ID** (optional) - If left blank, the system picks a random recent event

2. **Click "Run A/B Test"** to test both prompts on the event

3. **Review the results:**
   - Original (A) panel shows results from the current saved prompt
   - Modified (B) panel shows results from your changes
   - Delta indicator shows the score difference

### Understanding Delta Indicators

The delta indicator shows the score difference (B - A):

| Delta        | Color | Meaning                                                                   |
| ------------ | ----- | ------------------------------------------------------------------------- |
| -5 or lower  | Green | B is less alarming (potential improvement for false positives)            |
| +5 or higher | Red   | B is more alarming (may catch more threats but also more false positives) |
| -4 to +4     | Gray  | No significant difference                                                 |

### Promoting Your Changes

After running at least 3 A/B tests:

1. **Click "Promote B as Default"**
2. Review the test statistics in the confirmation dialog:
   - Average score change across all tests
   - Improvement rate (percentage of tests where B performed better)
3. **Click "Promote B"** to save your changes as the new default

The system requires at least 3 tests before promoting to ensure statistical validity.

---

## Version History

Every change to prompt configurations creates a new version. This allows you to:

- Track what changed and when
- Roll back to previous versions if needed
- See who made changes (if user tracking is enabled)

### Viewing Version History

The version number is displayed in each model accordion header (e.g., "v3").

To view full history, use the API:

```bash
curl http://localhost:8000/api/ai-audit/prompts/history
```

### Rolling Back to a Previous Version

If a change causes problems, you can restore a previous version:

1. Note the version ID from the history
2. Use the restore API:

```bash
curl -X POST http://localhost:8000/api/ai-audit/prompts/history/{version_id}
```

This creates a new version with the old configuration, preserving the complete history.

---

## Importing and Exporting Configurations

### Exporting Configurations

To save your current configurations:

1. Click **Export JSON** in the footer
2. A JSON file downloads with all model configurations
3. Store this file as a backup

The exported file includes:

- All model configurations
- Version numbers
- Export timestamp

### Importing Configurations

To restore or share configurations:

1. Click **Import JSON** in the footer
2. Select a previously exported JSON file
3. Configurations are validated and imported
4. New versions are created for each imported model

**Note:** Import creates new versions rather than overwriting, so you can always roll back.

---

## Best Practices

### Before Making Changes

1. **Export current configurations** as a backup
2. **Choose representative events** for testing - include low, medium, and high risk events
3. **Document your changes** using the change description field

### When Editing Prompts

1. **Make small, incremental changes** - It is easier to identify what works
2. **Use the variables provided** - They ensure the AI has the context it needs
3. **Be specific** - Clear instructions produce more consistent results
4. **Define output format** - Specify the exact structure you expect

### When Testing

1. **Test against multiple events** - At least 3-5 different scenarios
2. **Include edge cases** - Test with challenging events
3. **Compare scores** - Look for consistency, not just improvement
4. **Run A/B tests** before promoting major changes

### After Making Changes

1. **Monitor the AI Audit Dashboard** for quality changes
2. **Check the consistency rate** - It should remain stable
3. **Review new events** to ensure the changes work in production
4. **Roll back quickly** if you see problems

---

## Troubleshooting

### Test is timing out

- LLM inference can take up to 30 seconds
- Try a simpler event (fewer detections)
- Check that the AI services are running

### Changes not appearing after save

- Wait a few seconds and refresh the page
- Check the version number updated
- Verify the change in the version history

### Score changed dramatically

- Review the specific change you made
- Test with more events to verify
- Consider rolling back if results are worse

### Import failed

- Verify the JSON file format is correct
- Check that model names match expected values
- Review the error message for specific issues

---

## Keyboard Shortcuts

| Shortcut | Action                            |
| -------- | --------------------------------- |
| `Escape` | Close the Prompt Playground panel |

---

## Next Steps

- [AI Audit Dashboard](../user-guide/ai-audit.md) - Monitor AI quality metrics
- [Understanding Alerts](understanding-alerts.md) - Learn about risk levels
- [Settings](settings.md) - Configure other system options

---

## Technical Reference

For developers and advanced users, see:

- [Prompt Management API](../api-reference/prompts.md) - REST API documentation
- [Prompt Management Developer Guide](../developer/prompt-management.md) - Architecture and implementation details

---

[Back to User Hub](../user-hub.md)
