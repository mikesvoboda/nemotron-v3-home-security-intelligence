# Understanding Alerts

This system assigns every analysed event a risk score from 0 to 100, reflecting the assessed
severity of what was detected. The score comes from the vision-language analyzer (`ai-vlm`), which
looks at up to four key frames from the event together with the detection list and the identity
lookups that ran.

## Alert Levels

| Level    | Score Range | Description                                    |
| -------- | ----------- | ---------------------------------------------- |
| Critical | 85 - 100    | Immediate attention required (e.g., intrusion) |
| High     | 60 - 84     | Significant activity that warrants review      |
| Medium   | 30 - 59     | Notable but non-urgent observations            |
| Low      | 0 - 29      | Routine or informational detections            |

The boundaries come from the severity settings `severity_low_max` (29), `severity_medium_max` (59)
and `severity_high_max` (84). They are runtime-editable (`GET/PUT /api/system/severity`), so an
operator can move the band edges without a redeploy; `computed_risk_level` in
`backend/models/event.py` and `frontend/src/utils/risk.ts` both read them.

## How Risk Scores Are Determined

The analyzer receives the key frames plus the detection classes and confidences, the camera and
its zones, the time of day, and whatever the face / plate / person re-ID lookups recognised. It
returns a verdict, a summary, its reasoning, and the score. The score is then checked against the
severity rules before it is stored — a rejected verdict is clamped into the low band, and the clamp
stays visible in the reasoning rather than being hidden.

## When an Event Has No Score

An event can carry **no score at all**. That happens when the analyzer could not be reached or
could not see: the event's verification row then reads `verdict = verification_failed` with
`risk_score` and `risk_level` NULL, and the event itself is still written. The UI renders that as
an absent badge — not a score of 0, and not a Low.

A run of such events is the signature of the analysis half of the pipeline being down (the
`ai-vlm` container not started, or started without its multimodal projector), not of a quiet
house. If you see it, open the [Operations](operations.md) page and check the AI services.

## Alerts Are Not Automatic

**A risk score never creates an alert by itself.** Alert rows are created by whatever posts to
the alert service; the rule engine that encodes your thresholds runs when you invoke it (the
rule-test endpoint), not on event arrival. Judge the pipeline from the event timeline, and read
the [Alerts page](alerts.md) note for what rules do today.

## Further Reading

- [Risk Levels Reference](../reference/config/risk-levels.md) -- full configuration details for risk thresholds and scoring parameters
- [Alerts Panel](alerts.md) -- managing and filtering alerts in the dashboard
- [Dashboard Overview](dashboard.md) -- navigating the main interface
