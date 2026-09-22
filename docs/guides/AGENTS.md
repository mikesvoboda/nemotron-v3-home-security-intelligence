# Guides Directory - Agent Guide

## Purpose

This directory contains comprehensive feature guides for video analytics, zone
configuration, face recognition, household registration, and observability
capabilities in Home Security Intelligence.

## Directory Contents

```
docs/guides/
  AGENTS.md                        # This file - directory guide
  video-analytics.md               # AI pipeline overview, detection, scene understanding
  zone-configuration.md            # Zone setup, dwell time, line crossing, household integration
  face-recognition.md              # Face detection, person re-ID, household matching
  household-registration.md        # Household member and vehicle registration workflow
  profiling.md                     # Pyroscope continuous profiling guide
  metrics-coverage.md              # Prometheus metric to Grafana panel mapping
  detection-validation-coverage.md # Synthetic-scenario coverage for detection validation
```

## Guide Overview

| Guide                                                             | Purpose                                                       | Audience              |
| ----------------------------------------------------------------- | ------------------------------------------------------------- | --------------------- |
| [Video Analytics](video-analytics.md)                             | Complete AI pipeline documentation                            | Developers, operators |
| [Zone Configuration](zone-configuration.md)                       | Detection zone setup and intelligence features                | Users, operators      |
| [Face Recognition](face-recognition.md)                           | Face detection and person identification                      | Users, operators      |
| [Household Registration](household-registration.md)               | Register members and vehicles for trust and alert suppression | Users, operators      |
| [Profiling](profiling.md)                                         | Continuous profiling with Pyroscope                           | Developers, operators |
| [Metrics Coverage](metrics-coverage.md)                           | Prometheus metrics mapped to Grafana panels                   | Developers, operators |
| [Detection Validation Coverage](detection-validation-coverage.md) | Improve synthetic-scenario coverage of the detection pipeline | Developers            |

## Key Topics by Guide

### Video Analytics Guide

- Object detection with YOLO26
- Scene understanding with Florence-2
- Anomaly detection using CLIP baselines
- Threat detection (weapons, dangerous items)
- Person analysis (pose, demographics, clothing, re-ID)
- Vehicle analysis (classification, plates)
- Risk assessment with Nemotron LLM
- Analytics API reference

### Zone Configuration Guide

- CameraZone types (entry_point, driveway, sidewalk, yard, other) and the
  separate PolygonZone types (monitored, excluded, restricted)
- Drawing rectangle and polygon zones
- Dwell time tracking
- Line crossing detection
- Approach vector calculation
- Household integration and trust levels
- Schedule-based access rules
- Zone API reference

### Face Recognition Guide

- Face detection pipeline
- Person re-identification embeddings
- Demographics (age, gender) estimation
- Household member registration
- Cross-camera entity tracking
- Alert integration for unknown persons
- Privacy considerations

## Related Documentation

| Resource              | Location                                                                                     |
| --------------------- | -------------------------------------------------------------------------------------------- |
| Analytics API         | [../api/analytics-endpoints.md](../api/analytics-endpoints.md)                               |
| Cameras API           | [../architecture/api-reference/cameras-api.md](../architecture/api-reference/cameras-api.md) |
| UI Zone Documentation | [../ui/zones.md](../ui/zones.md)                                                             |
| UI Analytics          | [../ui/analytics.md](../ui/analytics.md)                                                     |
| Backend Services      | [../../backend/services/AGENTS.md](../../backend/services/AGENTS.md)                         |
| AI Enrichment         | [../../ai/enrichment/AGENTS.md](../../ai/enrichment/AGENTS.md)                               |

## Entry Points

1. **New users**: Start with [Video Analytics Guide](video-analytics.md) for system overview
2. **Zone setup**: See [Zone Configuration Guide](zone-configuration.md)
3. **Household setup**: See [Face Recognition Guide](face-recognition.md)
4. **API integration**: See [Analytics API](../api/analytics-endpoints.md)
5. **RTSP/ONVIF cameras**: See [Cameras API](../architecture/api-reference/cameras-api.md) for RTSP configuration and ONVIF device management
