# Background Services

> Async tasks, workers, and scheduled jobs

## Overview

This hub documents the background services that perform asynchronous work outside the request-response cycle. It covers the retention cleanup service, health monitoring tasks, and other background workers.

Background services handle tasks like cleaning up old data (30-day retention), periodic health checks, and other maintenance operations that shouldn't block user requests.

## Planned Documents

- [ ] retention-service.md - Data retention and cleanup
- [ ] health-monitor.md - Background health checking
- [ ] task-scheduling.md - Scheduled task patterns
- [ ] worker-patterns.md - Async worker implementation
- [ ] startup-shutdown.md - Service lifecycle management

## Key Services

| Service          | Schedule   | Description                     |
| ---------------- | ---------- | ------------------------------- |
| RetentionService | Daily      | Cleanup data older than 30 days |
| HealthMonitor    | Periodic   | Check component health          |
| MetricsCollector | Continuous | Collect and expose metrics      |

## Status

Ready for documentation

## Related Hubs

- [Resilience Patterns](../resilience-patterns/README.md) - Worker resilience
- [Observability](../observability/README.md) - Service monitoring
- [Data Model](../data-model/README.md) - Retention policies
