# Dataflows

> End-to-end data traces through the system

## Overview

This hub documents complete data flows through the system, tracing requests and events from trigger to completion. Each dataflow document provides a step-by-step trace with code citations.

Understanding dataflows helps developers see how components interact and debug issues by following the data path through the system.

## Planned Documents

- [ ] image-to-event.md - Camera image to security event flow
- [ ] event-broadcast.md - Event creation to WebSocket broadcast
- [ ] api-request.md - REST API request lifecycle
- [ ] websocket-connection.md - WebSocket connection establishment
- [ ] batch-processing.md - Detection batching and LLM analysis

## Key Flows

| Flow            | Trigger          | End State              |
| --------------- | ---------------- | ---------------------- |
| Image to Event  | New camera image | Security event created |
| Event Broadcast | Event created    | Frontend updated       |
| API Request     | HTTP request     | JSON response          |
| WebSocket       | Client connect   | Bidirectional channel  |

## Status

Ready for documentation

## Related Hubs

- [Detection Pipeline](../detection-pipeline/README.md) - Detection flow details
- [AI Orchestration](../ai-orchestration/README.md) - Batch flow details
- [Real-time System](../realtime-system/README.md) - Broadcast flow details
