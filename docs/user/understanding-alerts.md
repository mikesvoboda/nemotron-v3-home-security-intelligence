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

<!-- SCREENSHOT: Risk Level Color Guide
Location: N/A - composite infographic
Shows: Horizontal bar divided into four color-coded sections showing risk levels: Low (green, 0-29), Medium (yellow, 30-59), High (orange, 60-84), Critical (red, 85-100). Each section includes the level name, score range, and a simple icon
Size: 1000x200 pixels (5:1 aspect ratio)
Alt text: Risk level color guide showing four sections - green for Low (0-29), yellow for Medium (30-59), orange for High (60-84), and red for Critical (85-100)
-->
<!-- Screenshot: Risk level color guide showing Low (green), Medium (yellow), High (orange), Critical (red) sections -->

_Caption: Risk levels are color-coded for easy identification._

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

<!-- SCREENSHOT: Alerts Page Overview
Location: Alerts page (click Alerts in sidebar)
Shows: Alerts page with warning triangle icon in title, severity filter dropdown, refresh button, results summary showing alert counts, and event cards with orange and red left borders
Size: 1200x700 pixels (12:7 aspect ratio)
Alt text: Alerts page showing high and critical risk events with orange and red severity indicators, filter dropdown, and event cards
-->
<!-- Screenshot: Alerts page with severity filter, refresh button, and high/critical event cards -->

_Caption: The Alerts page shows only high-priority events that need your attention._

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

<!-- SCREENSHOT: Alert Card Examples by Risk Level
Location: N/A - composite showing 4 sample alert cards
Shows: Four event cards side by side, each representing a different risk level: Low (green left border), Medium (yellow left border), High (orange left border), Critical (red left border with glow). Each card shows camera name, timestamp, risk badge, and brief summary
Size: 1000x400 pixels (2.5:1 aspect ratio)
Alt text: Four example alert cards showing Low (green), Medium (yellow), High (orange), and Critical (red) risk levels with their distinctive border colors
-->
<!-- Screenshot: Four event cards showing Low, Medium, High, and Critical risk levels with color-coded borders -->

_Caption: Event cards are color-coded by risk level for easy identification._

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

---

## See Also

- [Risk Levels Reference](../reference/config/risk-levels.md) - Technical risk score definitions
- [Dashboard Basics](dashboard-basics.md) - Main dashboard overview
- [Alerts (Developer)](../developer/alerts.md) - Technical alert system details

---

[Back to User Hub](../user-hub.md)
