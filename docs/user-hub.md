# User Hub

> Your guide to using Home Security Intelligence - everything you need to monitor and protect your home.

Welcome! This system watches your security cameras around the clock and alerts you when something needs your attention. You do not need to be technical to use it - this hub will help you understand what everything means and how to get the most from your security system.

> Curious what’s stable vs still evolving? See [Stability Levels](reference/stability.md).

---

**New to the system?** Follow this path to get started:

1. [Getting Started](user-guide/getting-started.md) - What the system does and how to open it (~5 min read)
2. [Dashboard Overview](user-guide/dashboard-overview.md) - Understanding what you see on screen (~8 min read)
3. [Understanding Alerts](user-guide/understanding-alerts.md) - What the risk levels mean and when to take action (~10 min read)

---

## Understanding Your Dashboard

These guides help you understand what you see when you open the app.

| Guide                                                    | Description                                                 | Time    |
| -------------------------------------------------------- | ----------------------------------------------------------- | ------- |
| [Getting Started](user-guide/getting-started.md)         | What the system does and how to access it                   | ~5 min  |
| [Dashboard Overview](user-guide/dashboard-overview.md)   | The main screen layout - risk gauge, cameras, activity feed | ~8 min  |
| [Using the Dashboard](user-guide/using-the-dashboard.md) | Complete walkthrough of every feature                       | ~20 min |

**Dashboard Deep Dives (Focused Guides):**

| Guide                                                | Description                                      | Time    |
| ---------------------------------------------------- | ------------------------------------------------ | ------- |
| [Dashboard Basics](user/dashboard-basics.md)         | Layout, header, sidebar, quick stats             | ~8 min  |
| [Viewing Events](user/viewing-events.md)             | Activity feed, timeline, event details           | ~10 min |
| [AI Enrichment Data](user/ai-enrichment.md)          | Advanced AI analysis in event details            | ~8 min  |
| [AI Audit Dashboard](user/ai-audit.md)               | AI quality metrics and recommendations           | ~8 min  |
| [Understanding Alerts](user/understanding-alerts.md) | Risk levels and how to respond                   | ~8 min  |
| [Dashboard Settings](user/dashboard-settings.md)     | Configuration and quick reference                | ~5 min  |
| [System Monitoring](user/system-monitoring.md)       | System health, circuit breakers, troubleshooting | ~12 min |

---

## Understanding Risk Scores

The system assigns a risk score (0-100) to every event. These guides explain what the numbers mean and how to respond.

| Guide                                                      | Description                                                | Time    |
| ---------------------------------------------------------- | ---------------------------------------------------------- | ------- |
| [Understanding Alerts](user-guide/understanding-alerts.md) | What each risk level means and recommended actions         | ~10 min |
| [Risk Levels Reference](reference/config/risk-levels.md)   | The official definition of Low, Medium, High, and Critical | ~3 min  |

### Quick Reference: Risk Levels

| Level        | Score  | Color  | What It Means                              | What To Do                         |
| ------------ | ------ | ------ | ------------------------------------------ | ---------------------------------- |
| **Low**      | 0-29   | Green  | Normal activity - family, deliveries, pets | Nothing - informational only       |
| **Medium**   | 30-59  | Yellow | Something unusual worth noting             | Quick review when convenient       |
| **High**     | 60-84  | Orange | Concerning activity detected               | Review promptly, consider response |
| **Critical** | 85-100 | Red    | Potential security threat                  | Immediate attention required       |

---

## Managing Alerts

When the system detects something important, you will want to know about it.

| Guide                                                        | Description                            | Time    |
| ------------------------------------------------------------ | -------------------------------------- | ------- |
| [Alerts & Notifications](user-guide/alerts-notifications.md) | The Alerts page and notification setup | ~8 min  |
| [Understanding Alerts](user-guide/understanding-alerts.md)   | What causes alerts and how to respond  | ~10 min |

### Common Questions About Alerts

**Why did I get an alert?**
The AI considers what it sees (person, vehicle, animal), when it happened (day vs. night), and how the subject behaved (walking past vs. lingering). See [Understanding Alerts](user-guide/understanding-alerts.md) for details.

**What about false alarms?**
No system is perfect. Pets, delivery drivers, and weather can sometimes trigger medium-risk alerts. The [Understanding Alerts](user-guide/understanding-alerts.md) guide explains common causes and what to do.

---

## Reviewing Events

All activity detected by your cameras is saved for 30 days. These guides help you find and review past events.

| Guide                                          | Description                           | Time   |
| ---------------------------------------------- | ------------------------------------- | ------ |
| [Event Timeline](user-guide/event-timeline.md) | Browse, filter, and review all events | ~8 min |
| [Full-Text Search](user-guide/search.md)       | Find specific events by keyword       | ~6 min |

### What You Can Do With Events

- **Filter by camera** - See events from just one camera
- **Filter by risk level** - Focus on high-priority events first
- **Filter by date** - Check what happened last night or last week
- **Search by keyword** - Find events mentioning "delivery" or "vehicle"
- **Mark as reviewed** - Track which events you have already checked
- **Add notes** - Record your own observations

---

## Settings

Customize how the system works for you.

| Guide                              | Description                                          | Time   |
| ---------------------------------- | ---------------------------------------------------- | ------ |
| [Settings](user-guide/settings.md) | Camera management, processing options, notifications | ~7 min |

### What You Can Configure

- **Cameras** - Add, edit, or remove cameras from monitoring
- **Processing** - Adjust how sensitive the detection is
- **Notifications** - Set up email or webhook alerts
- **Retention** - How long events are kept (default: 30 days)

---

## Quick Reference

### Color Guide

| Color  | Meaning               | Action            |
| ------ | --------------------- | ----------------- |
| Green  | Normal / Low risk     | No action needed  |
| Yellow | Caution / Medium risk | Worth monitoring  |
| Orange | Warning / High risk   | Check soon        |
| Red    | Critical / Urgent     | Check immediately |

### Status Indicators

| Indicator         | Meaning                       |
| ----------------- | ----------------------------- |
| Green pulsing dot | System is live and monitoring |
| Yellow dot        | Some features may be degraded |
| Red dot           | System needs attention        |
| Spinning icon     | Loading or refreshing         |

### Keyboard Shortcuts

When viewing event details:

| Key         | Action          |
| ----------- | --------------- |
| Left Arrow  | Previous event  |
| Right Arrow | Next event      |
| Escape      | Close the popup |

---

## Need Help?

### Something not working?

See our [Troubleshooting Guide](admin-guide/troubleshooting.md) for detailed solutions, or check these quick fixes:

1. **Dashboard not loading?** Try refreshing your browser (F5 or Cmd+R)
2. **Cameras showing offline?** Check that cameras are powered and connected
3. **No events appearing?** Make sure cameras have activity to detect
4. **System status showing red?** Contact whoever set up your system

### Emergency Situations

This system is a monitoring tool - it does NOT automatically contact emergency services.

- **Active emergency:** Call 911 immediately
- **Suspicious activity:** Contact your local police non-emergency line
- **Technical problems:** Contact whoever installed and maintains your system

### Understanding the AI

The AI is designed to help you, not replace your judgment:

- It watches your cameras 24/7 so you do not have to
- It highlights what might be important so you can focus your attention
- It is not perfect - sometimes it will flag normal activity as concerning
- Trust your instincts - if something feels wrong, investigate even if the AI scored it low

---

## All User Guides

Complete list of guides for using the system:

| Guide                                                        | Description                        |
| ------------------------------------------------------------ | ---------------------------------- |
| [Getting Started](user-guide/getting-started.md)             | Introduction and first steps       |
| [Dashboard Overview](user-guide/dashboard-overview.md)       | Main screen layout and components  |
| [Using the Dashboard](user-guide/using-the-dashboard.md)     | Complete feature walkthrough       |
| [Understanding Alerts](user-guide/understanding-alerts.md)   | Risk levels and how to respond     |
| [Alerts & Notifications](user-guide/alerts-notifications.md) | Alert page and notification setup  |
| [Event Timeline](user-guide/event-timeline.md)               | Browsing and filtering events      |
| [Full-Text Search](user-guide/search.md)                     | Finding specific events            |
| [Settings](user-guide/settings.md)                           | Configuring the system             |
| [AI Audit Dashboard](user/ai-audit.md)                       | AI quality metrics and auditing    |
| [System Monitoring](user/system-monitoring.md)               | System health and circuit breakers |
| [Risk Levels Reference](reference/config/risk-levels.md)     | Official risk score definitions    |

---

## Other Documentation

Looking for something else?

- **[Operator Hub](operator-hub.md)** - For system administrators who deploy and maintain the system
- **[Developer Hub](developer-hub.md)** - For developers who want to contribute or extend the system

---

_This system uses AI to help protect your home. The AI analyzes camera footage, identifies activity, and assesses potential risks - but you are always in control of how to respond._
