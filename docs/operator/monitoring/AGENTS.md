# Monitoring Documentation - Agent Guide

## Purpose

This directory contains monitoring documentation for operators, covering health checks, service level objectives (SLOs), GPU monitoring, circuit breakers, and alerting configuration.

## Quick Navigation

| File        | Description                                                            |
| ----------- | ---------------------------------------------------------------------- |
| `README.md` | Comprehensive monitoring guide (health, GPU, DLQ, Prometheus, Grafana) |
| `slos.md`   | SLI/SLO framework with error budgets and alerting rules                |

## Key Topics

### Health Checks (README.md)

- Liveness probe: `GET /health`
- Readiness probe: `GET /api/system/health/ready`
- Full health check: `GET /api/system/health/full`

### GPU Monitoring (README.md)

- Metrics: utilization, memory, temperature, power usage
- API: `GET /api/system/gpu`, `GET /api/system/gpu/history`
- WebSocket: `/ws/system` stream for real-time updates

### Circuit Breakers (README.md)

- States: closed, open, half_open
- WebSocket broadcasting for state changes
- Configuration parameters and recovery behavior

### Dead Letter Queue (README.md)

- DLQ stats: `GET /api/dlq/stats`
- Job listing: `GET /api/dlq/jobs/{queue_name}`
- Recovery: `POST /api/dlq/requeue-all/{queue_name}`

### Service Level Objectives (slos.md)

- 5 defined SLOs: API availability, event processing, detection latency, analysis latency, WebSocket availability
- Error budget policy with consumption thresholds
- Multi-window burn rate alerting
- Prometheus recording rules and alert configurations

## API Reference Summary

| Category | Endpoints                                                                   |
| -------- | --------------------------------------------------------------------------- |
| Health   | `/api/system/health`, `/api/system/health/ready`, `/api/system/health/full` |
| GPU      | `/api/system/gpu`, `/api/system/gpu/history`                                |
| DLQ      | `/api/dlq/stats`, `/api/dlq/jobs/{queue}`, `/api/dlq/requeue-all/{queue}`   |
| Storage  | `/api/system/storage`, `/api/system/cleanup`                                |

## Related Resources

- **Parent**: [Operator Documentation](../AGENTS.md)
- **Deployment**: [Deployment Guide](../deployment/)
- **Administration**: [Admin Guide](../admin/)
- **Architecture**: [System Architecture](../../architecture/)
- **Prometheus Stack**: Enable with `docker compose --profile monitoring`
