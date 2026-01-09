# Risk Levels Reference

> Canonical definition of risk score ranges and severity levels.

**Time to read:** ~3 min
**Prerequisites:** None

---

## Overview

Every security event is assigned a **risk score** from 0 to 100, which maps to one of four **severity levels**. This document is the single source of truth for these definitions.

## Risk Score Ranges

| Level    | Score Range | Color  | Description                       |
| -------- | ----------- | ------ | --------------------------------- |
| Low      | 0-29        | Green  | Routine activity, no concern      |
| Medium   | 30-59       | Yellow | Notable activity, worth reviewing |
| High     | 60-84       | Orange | Concerning activity, review soon  |
| Critical | 85-100      | Red    | Immediate attention required      |

### Boundary Details

The thresholds are **inclusive** on the upper bound:

- A score of **29** is Low (the maximum Low score)
- A score of **30** is Medium (the minimum Medium score)
- A score of **59** is Medium (the maximum Medium score)
- A score of **60** is High (the minimum High score)
- A score of **84** is High (the maximum High score)
- A score of **85** is Critical (the minimum Critical score)

## What Each Level Means

### Low (0-29)

Normal, expected activity that requires no action.

**Examples:**

- Family members arriving home
- Expected deliveries (mail, packages)
- Pets or wildlife in the yard
- Neighbors walking past on the sidewalk
- Scheduled service workers (landscapers, utility meter readers)

**Action:** None required. These events are logged for reference but do not need review.

### Medium (30-59)

Unusual activity that may warrant a quick look but is not immediately alarming.

**Examples:**

- Unknown vehicle briefly parked in or near your driveway
- Unrecognized person approaching your door but leaving without interaction
- Motion detected at an unusual hour that could be a neighbor
- Someone walking slowly past your property, looking at houses

**Action:** Review when convenient. If the same activity repeats, pay closer attention.

### High (60-84)

Concerning activity that deserves prompt attention.

**Examples:**

- Someone checking door handles on parked vehicles
- A person wearing concealing clothing (hood, mask) lingering near entry points
- Multiple unknown individuals approaching your property from different directions
- Someone photographing your house and security features

**Action:** Review promptly. Consider securing your home and contacting a neighbor or local police non-emergency line if warranted.

### Critical (85-100)

Potentially dangerous situation requiring immediate attention.

**Examples:**

- Signs of forced entry attempt
- Multiple unknown individuals at night with no clear legitimate purpose
- Someone attempting to disable or avoid cameras
- Aggressive or threatening behavior

**Action:** Take immediate action. If home, stay inside and call 911 if there is an active threat. If away, call a trusted neighbor or police for a welfare check.

## Configuration

The default thresholds are:

```
Low:      0-29   (SEVERITY_LOW_MAX=29)
Medium:   30-59  (SEVERITY_MEDIUM_MAX=59)
High:     60-84  (SEVERITY_HIGH_MAX=84)
Critical: 85-100 (derived from high_max + 1)
```

### Environment Variables

You can customize these thresholds via environment variables:

| Variable              | Default | Description                       |
| --------------------- | ------- | --------------------------------- |
| `SEVERITY_LOW_MAX`    | 29      | Maximum score for Low severity    |
| `SEVERITY_MEDIUM_MAX` | 59      | Maximum score for Medium severity |
| `SEVERITY_HIGH_MAX`   | 84      | Maximum score for High severity   |

**Constraint:** Values must satisfy: `0 <= low_max < medium_max < high_max <= 100`

### Threshold Validation

The system validates severity thresholds at startup. If the constraint is violated, the application will fail to start with a validation error.

**Constraint Requirements:**

- All values must be non-negative integers
- `SEVERITY_LOW_MAX` must be less than `SEVERITY_MEDIUM_MAX`
- `SEVERITY_MEDIUM_MAX` must be less than `SEVERITY_HIGH_MAX`
- `SEVERITY_HIGH_MAX` must be less than or equal to 100

**Invalid Configuration Example:**

```bash
# INVALID - medium_max is not greater than low_max
export SEVERITY_LOW_MAX=50
export SEVERITY_MEDIUM_MAX=40
export SEVERITY_HIGH_MAX=84
```

**Expected Error:**

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
  Value error, Severity thresholds must satisfy: 0 <= low_max (50) < medium_max (40) < high_max (84) <= 100
```

**Valid Configuration Example:**

```bash
# VALID - thresholds are properly ordered
export SEVERITY_LOW_MAX=29
export SEVERITY_MEDIUM_MAX=59
export SEVERITY_HIGH_MAX=84
```

### Example: Stricter Thresholds

To escalate more events to higher severity:

```bash
export SEVERITY_LOW_MAX=19
export SEVERITY_MEDIUM_MAX=39
export SEVERITY_HIGH_MAX=69
```

This configuration would classify:

- Low: 0-19
- Medium: 20-39
- High: 40-69
- Critical: 70-100

## Color Scheme

The UI uses these colors (Tailwind-inspired):

| Level    | Hex Code  | Tailwind Class |
| -------- | --------- | -------------- |
| Low      | `#22c55e` | green-500      |
| Medium   | `#eab308` | yellow-500     |
| High     | `#f97316` | orange-500     |
| Critical | `#ef4444` | red-500        |

## Technical Reference

The severity logic is implemented in:

- **Enum definition:** `backend/models/enums.py` - `Severity` enum
- **Service:** `backend/services/severity.py` - `SeverityService` class
- **Configuration:** `backend/core/config.py` - `Settings.severity_*` fields

The `SeverityService.risk_score_to_severity()` method converts scores to levels:

```python
def risk_score_to_severity(self, score: int) -> Severity:
    if score <= self.low_max:      # 0-29
        return Severity.LOW
    elif score <= self.medium_max:  # 30-59
        return Severity.MEDIUM
    elif score <= self.high_max:    # 60-84
        return Severity.HIGH
    else:                           # 85-100
        return Severity.CRITICAL
```

---

## Next Steps

- [Understanding Alerts](../../user-guide/understanding-alerts.md) - How to interpret and respond to alerts
- [Environment Variable Reference](env-reference.md) - Severity configuration variables

---

## See Also

- [Risk Analysis](../../developer/risk-analysis.md) - How Nemotron generates risk scores
- [Alerts](../../developer/alerts.md) - How alert rules use risk levels
- [Dashboard Basics](../../user-guide/dashboard-basics.md) - Reading the risk gauge

---

[Back to User Hub](../../user-hub.md) | [Operator Hub](../../operator-hub.md) | [Developer Hub](../../developer-hub.md)
