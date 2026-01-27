# Guides Directory - Agent Guide

## Purpose

This directory contains comprehensive feature guides for video analytics, zone configuration, and face recognition capabilities in Home Security Intelligence.

## Directory Contents

```
docs/guides/
  AGENTS.md              # This file - directory guide
  video-analytics.md     # AI pipeline overview, detection, scene understanding
  zone-configuration.md  # Zone setup, dwell time, line crossing, household integration
  face-recognition.md    # Face detection, person re-ID, household matching
```

## Guide Overview

| Guide                                       | Purpose                                        | Audience              |
| ------------------------------------------- | ---------------------------------------------- | --------------------- |
| [Video Analytics](video-analytics.md)       | Complete AI pipeline documentation             | Developers, operators |
| [Zone Configuration](zone-configuration.md) | Detection zone setup and intelligence features | Users, operators      |
| [Face Recognition](face-recognition.md)     | Face detection and person identification       | Users, operators      |

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

- Zone types (entry_point, exit_point, restricted, monitored)
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

| Resource              | Location                                                             |
| --------------------- | -------------------------------------------------------------------- |
| Analytics API         | [../api/analytics-endpoints.md](../api/analytics-endpoints.md)       |
| UI Zone Documentation | [../ui/zones.md](../ui/zones.md)                                     |
| UI Analytics          | [../ui/analytics.md](../ui/analytics.md)                             |
| Backend Services      | [../../backend/services/AGENTS.md](../../backend/services/AGENTS.md) |
| AI Enrichment         | [../../ai/enrichment/AGENTS.md](../../ai/enrichment/AGENTS.md)       |

## Entry Points

1. **New users**: Start with [Video Analytics Guide](video-analytics.md) for system overview
2. **Zone setup**: See [Zone Configuration Guide](zone-configuration.md)
3. **Household setup**: See [Face Recognition Guide](face-recognition.md)
4. **API integration**: See [Analytics API](../api/analytics-endpoints.md)
