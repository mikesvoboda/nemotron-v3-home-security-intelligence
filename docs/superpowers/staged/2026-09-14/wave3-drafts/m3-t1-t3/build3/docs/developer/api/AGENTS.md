# API Documentation - Agent Guide

## Purpose

This directory is the API documentation hub for the Home Security Intelligence system. It contains consolidated API documentation organized by domain, providing developers with comprehensive reference material for all REST and WebSocket endpoints.

## Directory Contents

```
docs/developer/api/
  AGENTS.md              # This file
  README.md              # API overview, authentication, pagination, error handling
  core-resources.md      # Cameras, events, detections, zones, entities, analytics
  ai-pipeline.md         # Enrichment, batches, AI audit, dead letter queue
  system-ops.md          # Health checks, config, alerts, logs, notifications
  system-monitoring.md   # System monitoring endpoints
  realtime.md            # WebSocket streams for events and system status
  calibration.md         # Camera calibration API
  coverage.md            # API endpoint coverage tracking
  webhooks.md            # Webhook configuration and delivery
  websocket-contracts.md # WebSocket message formats and contracts
```

## Quick Navigation

| Guide                                     | Description                                               |
| ----------------------------------------- | --------------------------------------------------------- |
| [README.md](README.md)                    | API overview, authentication, pagination, error handling  |
| [Core Resources](core-resources.md)       | Cameras, events, detections, zones, entities, analytics   |
| [AI Pipeline](ai-pipeline.md)             | Enrichment, batches, AI audit, dead letter queue          |
| [System Operations](system-ops.md)        | Health checks, configuration, alerts, logs, notifications |
| [System Monitoring](system-monitoring.md) | System monitoring and telemetry endpoints                 |
| [Real-time](realtime.md)                  | WebSocket streams for events and system status            |
| [Calibration](calibration.md)             | Camera calibration API endpoints                          |
| [Webhooks](webhooks.md)                   | Inbound (Alertmanager) and outbound webhook configuration |

## Supporting Documentation

| Document                                         | Purpose                                 |
| ------------------------------------------------ | --------------------------------------- |
| [coverage.md](coverage.md)                       | API endpoint implementation coverage    |
| [websocket-contracts.md](websocket-contracts.md) | WebSocket message formats and contracts |

## Related Resources

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs) - Interactive API documentation
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc) - Alternative API documentation view
- **OpenAPI Spec:** `GET /openapi.json` - Machine-readable API specification

## Entry Points for Agents

### Getting Started with the API

1. Start with [README.md](README.md) for API overview, authentication, and conventions
2. Review [Core Resources](core-resources.md) for primary data endpoints
3. Check [AI Pipeline](ai-pipeline.md) for processing pipeline endpoints
4. Explore [System Operations](system-ops.md) for health and configuration
5. Reference [Real-time](realtime.md) for WebSocket integration

### Implementing API Clients

1. Review authentication patterns in [README.md](README.md)
2. Understand pagination (cursor-based preferred)
3. Check error handling and HTTP status codes
4. Use Swagger UI for interactive testing

### Debugging API Issues

1. Check endpoint exists in the appropriate guide
2. Verify authentication headers if API key is enabled
3. Review error response format (RFC 7807)
4. Test with Swagger UI at http://localhost:8000/docs

## API Organization

The API is organized into four functional domains:

1. **Core Resources** - Primary data entities (cameras, events, detections, zones, entities)
2. **AI Pipeline** - Processing pipeline operations (enrichment, batches, DLQ)
3. **System Operations** - Infrastructure and monitoring (health, config, alerts, logs)
4. **Real-time** - WebSocket streams for live updates

## Related Documentation

- **docs/developer/AGENTS.md** - Developer documentation overview
- **docs/architecture/real-time.md** - WebSocket architecture details
- **docs/api/AGENTS.md** - API governance and deprecation policies
- **backend/api/routes/AGENTS.md** - Route implementation details
