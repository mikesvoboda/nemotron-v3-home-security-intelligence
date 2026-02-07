# Understanding Alerts

Nemotron Home Security uses AI-driven risk scoring to generate and prioritize alerts. Each alert is assigned a risk score from 0 to 100 by the Nemotron LLM, reflecting the assessed severity of the detected event.

## Alert Levels

| Level    | Score Range | Description                                    |
| -------- | ----------- | ---------------------------------------------- |
| Critical | 80 - 100    | Immediate attention required (e.g., intrusion) |
| High     | 60 - 79     | Significant activity that warrants review      |
| Medium   | 30 - 59     | Notable but non-urgent observations            |
| Low      | 0 - 29      | Routine or informational detections            |

## How Risk Scores Are Determined

The Nemotron LLM evaluates each detection event against contextual factors such as time of day, zone sensitivity, entity history, and detection confidence. The resulting score determines the alert level and notification behavior.

## Further Reading

- [Risk Levels Reference](../reference/config/risk-levels.md) -- full configuration details for risk thresholds and scoring parameters
- [Alerts Panel](alerts.md) -- managing and filtering alerts in the dashboard
- [Dashboard Overview](dashboard.md) -- navigating the main interface
