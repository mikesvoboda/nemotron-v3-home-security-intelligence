# Understanding Alerts

> What risk levels mean and how to respond to security events.

**Time to read:** ~8 min
**Prerequisites:** [Dashboard Basics](dashboard-basics.md)

---

## Risk Scoring Overview

The AI system assigns a risk score (0-100) to every event based on:

- **What** was detected (person, vehicle, animal)
- **When** it happened (day vs. night)
- **How** the subject behaved (walking past vs. lingering)
- **Where** on the property (front door vs. street)

---

## Risk Levels

### Low Risk (Green, 0-29)

**What it means:** Normal activity, nothing concerning.

**Examples:**

- Family members coming and going
- Expected deliveries
- Pets and wildlife
- Normal neighborhood traffic

**What to do:** No action needed. These are informational only.

---

### Medium Risk (Yellow, 30-59)

**What it means:** Something unusual worth noting, but probably okay.

**Examples:**

- Unfamiliar people near property
- Activity at unusual hours
- Longer-than-normal presence
- Vehicles stopping briefly

**What to do:** Quick review when convenient. Likely nothing to worry about.

---

### High Risk (Orange, 60-84)

**What it means:** Concerning activity detected.

**Examples:**

- Unknown individuals approaching doors/windows
- Activity late at night
- Multiple people acting together
- Repeated visits by same unknown person

**What to do:** Review promptly. Consider whether action is needed.

---

### Critical Risk (Red, 85-100)

**What it means:** Potential security threat requiring immediate attention.

**Examples:**

- Attempted unauthorized entry
- Suspicious behavior near entry points
- Known threat indicators
- Emergency situations

**What to do:** Check immediately. Consider contacting authorities if warranted.

---

## Alerts Page

The Alerts page focuses only on events needing attention.

### Accessing Alerts

Click **Alerts** in the left sidebar. A warning triangle icon appears next to the title.

### What You See

The Alerts page shows the same event cards as Timeline, but automatically filtered to show only:

- **High risk** events (score 60-84)
- **Critical risk** events (score 85-100)

### Filtering Alerts

Use the dropdown to narrow down:

- **All Alerts** - Shows both high and critical
- **Critical Only** - Shows only the most urgent
- **High Only** - Shows only high-risk (not critical)

### Refreshing

Click **Refresh** to check for new alerts. The button spins while refreshing.

### When There Are No Alerts

If no high-risk events exist, you see: "No Alerts at This Time" - your system is secure.

---

## Color Guide

| Color  | Meaning               | Action            |
| ------ | --------------------- | ----------------- |
| Green  | Normal / Low Risk     | No action needed  |
| Yellow | Caution / Medium Risk | Worth monitoring  |
| Orange | Warning / High Risk   | Check soon        |
| Red    | Critical / Urgent     | Check immediately |

---

## Why Did I Get This Alert?

The AI considers multiple factors when assigning risk:

### Time of Day

- Daytime activity: Lower risk
- Evening activity: Slightly higher risk
- Late night (11pm-5am): Higher risk

### Detection Type

- Known family/vehicles: Lower risk
- Unknown people: Higher risk
- Multiple unknowns: Much higher risk

### Behavior Patterns

- Walking past: Lower risk
- Approaching property: Medium risk
- Lingering at doors/windows: Higher risk
- Examining locks/entry points: Critical risk

### Location

- Street/sidewalk: Lower risk
- Driveway: Medium risk
- Near doors/windows: Higher risk

---

## Common False Alarms

No system is perfect. Common causes of false alerts:

| Cause            | Typical Level | Why It Happens                   |
| ---------------- | ------------- | -------------------------------- |
| Delivery drivers | Medium        | Unknown person approaching       |
| Neighbors        | Low-Medium    | Unknown to the AI                |
| Service workers  | Medium        | Unfamiliar, may inspect property |
| Weather/shadows  | Low           | Motion triggers detection        |
| Animals          | Low           | Movement detected                |

**What to do:** Review, mark as reviewed, and add notes if helpful.

---

## Responding to Alerts

### For Medium Risk

1. Review the event when convenient
2. Check the AI summary and reasoning
3. Mark as reviewed
4. Add notes if relevant

### For High Risk

1. Review promptly
2. Check multiple images in the sequence
3. Verify nothing concerning is happening
4. Mark as reviewed
5. Consider if any follow-up needed

### For Critical Risk

1. Check immediately
2. View all available images
3. Assess whether threat is real
4. If real threat: Contact authorities
5. If false alarm: Mark reviewed, add notes

---

## Emergency Reminder

This system is a monitoring tool - it does NOT automatically contact emergency services.

- **Active emergency:** Call 911 immediately
- **Suspicious activity:** Contact local police non-emergency line
- **Technical problems:** Contact whoever maintains your system

---

## Next Steps

- [Viewing Events](viewing-events.md) - How to view event details
- [Dashboard Settings](dashboard-settings.md) - Configure notifications
- [Back to User Hub](../user-hub.md)
