# Deployment Documentation - Agent Guide

## Purpose

This directory contains documentation for container orchestration, startup sequences, health monitoring, and recovery procedures for the Home Security Intelligence system.

## Files

| File                         | Purpose                                            |
| ---------------------------- | -------------------------------------------------- |
| `container-orchestration.md` | Comprehensive container orchestrator documentation |
| `yolo26-migration.md`        | YOLO26 detector migration guide and configuration  |

## Key Topics

### YOLO26 Migration

The `yolo26-migration.md` file covers:

1. **Overview** - YOLO26 architecture and migration benefits (5.3x faster)
2. **Prerequisites** - Hardware, software, and model file requirements
3. **Configuration** - Environment variables and model selection
4. **Migration Steps** - Step-by-step deployment instructions
5. **Rollback Procedure** - How to revert to YOLO26
6. **Performance** - Benchmark results and latency comparisons
7. **Monitoring** - Prometheus metrics and Grafana integration
8. **Troubleshooting** - Common issues and solutions

### Container Orchestration

The `container-orchestration.md` file covers:

1. **Architecture** - Component interaction and data flow
2. **Startup Sequence** - Four-phase startup with dependencies
3. **Health Checks** - HTTP endpoints, commands, and fallbacks
4. **Dependency Graph** - Service dependencies and startup order
5. **Self-Healing Recovery** - Exponential backoff and auto-restart
6. **Service Categories** - Infrastructure, AI, and Monitoring services
7. **Configuration** - Environment variables and port settings
8. **API Endpoints** - Health and service management APIs
9. **Recovery Procedures** - Common failure scenarios and solutions
10. **Troubleshooting** - Diagnostic commands and issue resolution

### Related Backend Services

| Service                   | File                                              | Purpose             |
| ------------------------- | ------------------------------------------------- | ------------------- |
| ContainerOrchestrator     | `backend/services/container_orchestrator.py`      | Main coordinator    |
| ContainerDiscoveryService | `backend/services/container_discovery.py`         | Container discovery |
| HealthMonitor             | `backend/services/health_monitor_orchestrator.py` | Health check loop   |
| LifecycleManager          | `backend/services/lifecycle_manager.py`           | Restart logic       |
| ServiceRegistry           | `backend/services/orchestrator/registry.py`       | State management    |
| DockerClient              | `backend/core/docker_client.py`                   | Docker API wrapper  |

## Related Documentation

- [Deployment Guide](../operator/deployment/README.md) - Full deployment instructions
- [Monitoring Guide](../operator/monitoring/README.md) - Observability setup
- [AI Services](../operator/ai-services.md) - AI service configuration
- [Service Control](../operator/service-control.md) - Manual service management

## Quick Reference

### Health Endpoints

```bash
# Backend readiness
curl http://localhost:8000/api/system/health/ready

# AI services health
curl http://localhost:8000/api/health/ai-services

# Individual service health
curl http://localhost:8095/health  # ai-yolo26 (YOLO26)
curl http://localhost:8091/health  # ai-llm
curl http://localhost:8095/health  # ai-yolo26
```

### Service Management

```bash
# List all services
curl http://localhost:8000/api/system/services

# Restart a service
curl -X POST http://localhost:8000/api/system/services/ai-yolo26/restart

# Enable/disable auto-restart
curl -X POST http://localhost:8000/api/system/services/ai-yolo26/enable
curl -X POST http://localhost:8000/api/system/services/ai-yolo26/disable
```
