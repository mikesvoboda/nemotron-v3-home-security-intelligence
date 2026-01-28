# Notification Setup Guide

This guide explains how to configure notifications so you stay informed about security events without being overwhelmed by alerts.

---

## Overview

The notification system keeps you informed about what is happening at your property. You can receive alerts through multiple channels and customize when and how you are notified based on risk levels, specific cameras, and time schedules.

### What You Can Be Notified About

| Notification Type        | Description                                         |
| ------------------------ | --------------------------------------------------- |
| **Security alerts**      | High-risk events like intruders or unusual activity |
| **Household arrivals**   | Family members arriving or departing                |
| **System health**        | Camera offline, AI service issues                   |
| **Daily/weekly digests** | Summary of activity (configurable via alert rules)  |

---

## Notification Types

### Real-Time Security Alerts

These are immediate notifications triggered when the AI detects concerning activity:

| Risk Level   | Score Range | When You Get Notified                            |
| ------------ | ----------- | ------------------------------------------------ |
| **Critical** | 85-100      | Potential intruder, break-in attempt             |
| **High**     | 60-84       | Suspicious person, unusual activity at odd hours |
| **Medium**   | 30-59       | Unfamiliar person, unexpected delivery           |
| **Low**      | 0-29        | Routine activity (optional notifications)        |

### System Health Notifications

Stay informed about your system status:

- **Camera offline** - A camera has stopped sending images
- **Camera back online** - A previously offline camera is working again
- **AI service issues** - Processing delays or errors
- **Storage warnings** - Disk space running low

### Household Arrivals and Departures

If you have registered household members (see [Household Registration](../guides/household-registration.md)), you can receive optional notifications when:

- A family member arrives home
- A family member leaves
- A recognized vehicle enters or exits the driveway

---

## Accessing Notification Settings

1. Click the **Settings** icon in the navigation menu
2. Select the **Notifications** tab
3. You will see four main sections:
   - Global Preferences
   - Camera Notifications
   - Quiet Hours
   - Channel Configuration

---

## Global Preferences

These settings apply to all notifications across the system.

### Master Toggle

The **Notifications** toggle at the top is the master switch:

- **Enabled** (green) - You will receive notifications based on your settings
- **Disabled** (gray) - All notifications are silenced

### Notification Sound

Choose what sound plays when a notification arrives:

| Option      | Description                           |
| ----------- | ------------------------------------- |
| **None**    | Silent notifications (visual only)    |
| **Default** | Standard notification sound           |
| **Alert**   | Attention-grabbing alert tone         |
| **Chime**   | Gentle, pleasant chime                |
| **Urgent**  | Loud, urgent tone for critical events |

### Risk Level Filters

Select which risk levels trigger notifications:

- **Critical** - Always recommended to keep enabled
- **High** - Recommended for security awareness
- **Medium** - Enable if you want to see unusual activity
- **Low** - Usually kept disabled to avoid noise

> **Tip:** Start with Critical and High enabled. Add Medium later if you want more visibility into routine activity.

---

## Camera Notifications

Customize notifications for each camera individually.

### Per-Camera Settings

For each camera, you can configure:

| Setting            | Description                                   |
| ------------------ | --------------------------------------------- |
| **Enable/Disable** | Toggle notifications for this specific camera |
| **Risk Threshold** | Minimum risk score (0-100%) to trigger alerts |

### Setting Camera Thresholds

The risk threshold slider sets the minimum risk score that triggers a notification from that camera:

- **0%** - Notify on all detections
- **50%** - Notify on medium risk and above
- **80%** - Only notify on high-risk events
- **100%** - Effectively disables notifications

### Avoiding Threshold Conflicts

If your camera threshold is lower than your global risk level filters, you may miss some alerts. The system will warn you about potential conflicts. For example:

- Global filter set to "High" only (60+ risk score)
- Camera threshold set to 40%
- Result: Events scoring 40-59 will be ignored despite camera setting

**Resolution:** Either lower your global filter to include Medium, or raise the camera threshold to match.

---

## Quiet Hours (Do Not Disturb)

Configure time periods when notifications are silenced.

### Creating a Quiet Hours Period

1. Click **Add Period** in the Quiet Hours section
2. Enter a **Label** (e.g., "Night Time", "Work Hours")
3. Set the **Start Time** and **End Time**
4. Select which **Days** of the week this applies to
5. Click **Save**

### Example Configurations

| Label         | Time               | Days      | Purpose                         |
| ------------- | ------------------ | --------- | ------------------------------- |
| Sleep Time    | 11:00 PM - 7:00 AM | Every day | No interruptions while sleeping |
| Work Hours    | 9:00 AM - 5:00 PM  | Mon-Fri   | Focus during work               |
| Weekend Sleep | 11:00 PM - 9:00 AM | Sat-Sun   | Extended weekend rest           |

### Managing Quiet Hours

- Each quiet hours period shows its label, time range, and active days
- Click the **Delete** (trash) icon to remove a period
- You can have multiple overlapping periods

> **Important:** Critical alerts may still break through quiet hours depending on your alert rule configuration. Review your alert rules to ensure truly urgent events can reach you.

---

## Notification Channels

The system supports multiple notification delivery methods.

### Available Channels

| Channel      | Description                             | Configuration         |
| ------------ | --------------------------------------- | --------------------- |
| **In-app**   | Notifications within the dashboard      | Always active         |
| **Desktop**  | Browser push notifications              | Requires permission   |
| **Email**    | Email alerts to configured addresses    | Environment variables |
| **Webhook**  | HTTP POST to external services          | Environment variables |
| **Pushover** | Push notifications via Pushover service | Alert rules           |

### Desktop Notifications

Desktop notifications appear as browser pop-ups even when the dashboard is in the background.

**To enable:**

1. Go to **Settings > Ambient**
2. Find **Desktop Notifications**
3. Click **Request Permission** if the status shows "Not Set"
4. Allow notifications when your browser prompts

**Permission states:**

- **Granted** - Desktop notifications are active
- **Blocked** - You previously denied; must enable in browser settings
- **Not Set** - You have not been asked yet

**Browser settings if blocked:**

- **Chrome:** Settings > Privacy and Security > Site Settings > Notifications
- **Firefox:** Settings > Privacy & Security > Permissions > Notifications
- **Safari:** Preferences > Websites > Notifications

> **Note:** Desktop notifications require HTTPS. If you see a "Secure Context Warning" banner, certain features may not work until you access the system over a secure connection.

### Email Notifications

Email configuration is set via environment variables and requires a backend restart to change.

**Current configuration is shown in the Notifications tab:**

- SMTP host and port
- From address
- TLS status
- Default recipients

**To test email:**

Click the **Send Test Email** button to verify your configuration is working.

### Webhook Notifications

Webhooks send HTTP POST requests to external services (e.g., Slack, Discord, custom integrations).

**Configuration shows:**

- Webhook URL
- Timeout setting

**To test:**

Click the **Send Test Webhook** button to verify connectivity.

---

## Alert Rules

For advanced notification control, configure alert rules in **Settings > Rules**.

Alert rules let you:

- Set specific triggers (risk threshold, object types, cameras)
- Define schedules (only active certain hours)
- Choose notification channels per rule
- Set cooldown periods between duplicate alerts

See the [Settings documentation](../ui/settings.md#rules-tab) for complete alert rule configuration options.

---

## Setup Checklist

Follow this checklist to configure your notifications:

| Step | Action                                             | Location                 |
| ---- | -------------------------------------------------- | ------------------------ |
| 1    | Enable master notification toggle                  | Settings > Notifications |
| 2    | Select risk level filters (Critical, High minimum) | Settings > Notifications |
| 3    | Choose notification sound                          | Settings > Notifications |
| 4    | Review per-camera settings and thresholds          | Settings > Notifications |
| 5    | Set up quiet hours for sleep/work                  | Settings > Notifications |
| 6    | Enable desktop notifications                       | Settings > Ambient       |
| 7    | Test email/webhook if configured                   | Settings > Notifications |
| 8    | Create alert rules for specific scenarios          | Settings > Rules         |

---

## Troubleshooting

### Not Receiving Any Notifications

**Check:**

1. Is the master notification toggle enabled?
2. Are risk level filters set to include the event severity?
3. Is the specific camera's notifications enabled?
4. Is the camera threshold lower than the event's risk score?
5. Are you currently in a quiet hours period?
6. Is the backend notification system enabled? (Check "System Notifications Status")

### Too Many Notifications

**Try:**

1. Increase camera risk thresholds to filter low-priority events
2. Disable low and medium risk level filters
3. Set up quiet hours for times you do not want interruptions
4. Review alert rules and increase cooldown periods
5. Register household members to reduce false positives for known people

### Desktop Notifications Not Working

**Check:**

1. Did you grant browser permission?
2. Is the permission status "Granted" in Settings > Ambient?
3. Are you accessing the system via HTTPS?
4. Is your browser's system-level notification permission enabled?
5. On macOS: System Preferences > Notifications > Browser

**If permission is "Blocked":**

You must enable notifications in your browser settings directly - the app cannot re-request permission once blocked.

### Email Notifications Not Arriving

**Check:**

1. Is SMTP configured? (Shows "Configured" badge)
2. Did the test email succeed?
3. Check spam/junk folders
4. Verify the from address is not being filtered
5. Check backend logs for SMTP errors

### Webhook Failures

**Check:**

1. Is the webhook URL accessible from your server?
2. Is the receiving endpoint accepting POST requests?
3. Check timeout settings if requests are slow
4. Verify any authentication requirements
5. Use "Send Test Webhook" to diagnose

### Notification Delays

**Possible causes:**

1. AI processing queue backlog
2. Network connectivity issues
3. Email server delays

**Check:**

1. Operations dashboard for queue health
2. AI performance dashboard for processing times
3. System health indicators

---

## Best Practices

### Start Conservative

Begin with fewer notifications and add more as needed:

1. Enable only Critical and High risk level filters initially
2. Set camera thresholds to 60-70% to start
3. Add quiet hours for sleep time
4. After a week, adjust based on what you are seeing

### Optimize Over Time

- Review notifications weekly - are you getting useful alerts?
- Adjust thresholds for cameras that generate too many alerts
- Add household members to reduce false positives
- Create specific alert rules for scenarios you care about

### Maintain Awareness

- Keep Critical alerts enabled always
- Ensure at least one notification channel works
- Test periodically to confirm delivery
- Review quiet hours to ensure critical alerts can still reach you

---

## Related Documentation

- [Settings Guide](../ui/settings.md) - Complete settings documentation
- [Alert Rules](../ui/settings.md#rules-tab) - Advanced alert rule configuration
- [Household Registration](../guides/household-registration.md) - Reduce false positives
- [Desktop Notifications](../ui/settings.md#ambient-tab) - Ambient status features
- [Understanding Alerts](../ui/alerts.md) - What risk levels mean
