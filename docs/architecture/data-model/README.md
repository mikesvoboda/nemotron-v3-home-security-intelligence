# Data Model Hub

> Documentation hub for the Home Security Intelligence System database architecture.

This directory contains comprehensive documentation for the data model, including PostgreSQL tables, Redis data structures, indexes, and migration patterns.

## Quick Navigation

| Document                                                | Description                                   |
| ------------------------------------------------------- | --------------------------------------------- |
| [Core Entities](./core-entities.md)                     | Camera, Detection, Event models               |
| [Auxiliary Tables](./auxiliary-tables.md)               | GPUStats, AuditLog, Jobs, Baselines           |
| [Indexes and Performance](./indexes-and-performance.md) | GIN indexes, BRIN indexes, query optimization |
| [Migrations](./migrations.md)                           | Alembic patterns and examples                 |
| [Redis Data Structures](./redis-data-structures.md)     | Queues, batch state, pub/sub channels         |

## Entity Relationship Overview

```mermaid
erDiagram
    cameras ||--o{ detections : "has many"
    cameras ||--o{ events : "has many"
    cameras ||--o{ camera_zones : "has many"
    cameras ||--o{ activity_baselines : "has many"
    cameras ||--o{ class_baselines : "has many"
    cameras ||--o{ scene_changes : "has many"
    events ||--o{ event_detections : "links"
    detections ||--o{ event_detections : "links"
    events ||--o{ alerts : "triggers"
    events ||--o{ event_feedback : "has one"
    events ||--o{ event_audits : "has one"
    alert_rules ||--o{ alerts : "generates"
    detections ||--o{ pose_results : "has one"
    detections ||--o{ threat_detections : "has many"
    detections ||--o{ demographics_results : "has one"
    detections ||--o{ reid_embeddings : "has one"
    detections ||--o{ action_results : "has one"
    household_members ||--o{ registered_vehicles : "owns"
    household_members ||--o{ person_embeddings : "has many"

    cameras {
        string id PK
        string name
        string folder_path
        string status
        datetime created_at
        datetime last_seen_at
        datetime deleted_at
    }

    detections {
        int id PK
        string camera_id FK
        string file_path
        datetime detected_at
        string object_type
        float confidence
        jsonb enrichment_data
    }

    events {
        int id PK
        string batch_id
        string camera_id FK
        datetime started_at
        int risk_score
        string risk_level
        text summary
        tsvector search_vector
    }

    alerts {
        uuid id PK
        int event_id FK
        uuid rule_id FK
        enum severity
        enum status
        string dedup_key
    }
```

## Storage Architecture

The system uses a dual-storage architecture optimized for different workloads:

| Storage        | Technology | Purpose                                     | Persistence           |
| -------------- | ---------- | ------------------------------------------- | --------------------- |
| **Primary DB** | PostgreSQL | Permanent records, audit trail, analytics   | Durable               |
| **Cache/MQ**   | Redis      | Queues, pub/sub, batch state, deduplication | Ephemeral (TTL-based) |

### Data Flow

```mermaid
flowchart LR
    subgraph Input
        FTP[Camera FTP Upload]
    end

    subgraph Processing
        FW[FileWatcher]
        DQ[(detection_queue)]
        DQW[DetectionWorker]
        BA[BatchAggregator]
        AQ[(analysis_queue)]
        AQW[AnalysisWorker]
    end

    subgraph Storage
        PG[(PostgreSQL)]
        Redis[(Redis)]
    end

    subgraph Output
        WS[WebSocket Broadcast]
    end

    FTP --> FW
    FW --> DQ
    DQ --> DQW
    DQW --> PG
    DQW --> BA
    BA --> Redis
    BA --> AQ
    AQ --> AQW
    AQW --> PG
    AQW --> WS
```

## Key Design Decisions

### Junction Table for Event-Detection Relationships

Events and Detections have a many-to-many relationship managed through the `event_detections` junction table (`backend/models/event_detection.py:10-30`). This provides:

- Proper foreign key constraints with cascade deletes
- Efficient querying of detections per event
- Database-enforced referential integrity

### Soft Deletes

Camera and Event models support soft deletion via `deleted_at` timestamp columns:

- Preserves referential integrity with related records
- Enables audit trail and potential recovery
- See `backend/models/camera.py:102-104` and `backend/models/event.py:64-67`

### Full-Text Search

Events support PostgreSQL full-text search via `search_vector` TSVECTOR column:

- Combines summary, reasoning, and object_types
- GIN-indexed for efficient searching
- See `backend/models/event.py:61-62`

## Table Summary

### Core Tables

| Table              | Purpose                    | Primary Key | Source                                 |
| ------------------ | -------------------------- | ----------- | -------------------------------------- |
| `cameras`          | Camera configuration       | `id` (str)  | `backend/models/camera.py:63-92`       |
| `detections`       | Object detection results   | `id` (int)  | `backend/models/detection.py:28-141`   |
| `events`           | Aggregated security events | `id` (int)  | `backend/models/event.py:21-155`       |
| `event_detections` | Event-Detection junction   | composite   | `backend/models/event_detection.py:10` |

### Alerting Tables

| Table         | Purpose                     | Primary Key | Source                    |
| ------------- | --------------------------- | ----------- | ------------------------- |
| `alerts`      | Generated notifications     | `id` (uuid) | `backend/models/alert.py` |
| `alert_rules` | Alert condition definitions | `id` (uuid) | `backend/models/alert.py` |

### Enrichment Tables

| Table                  | Purpose                  | Primary Key | Source                         |
| ---------------------- | ------------------------ | ----------- | ------------------------------ |
| `pose_results`         | Body posture detection   | `id` (int)  | `backend/models/enrichment.py` |
| `threat_detections`    | Weapon detection         | `id` (int)  | `backend/models/enrichment.py` |
| `demographics_results` | Age/gender estimation    | `id` (int)  | `backend/models/enrichment.py` |
| `reid_embeddings`      | Person re-identification | `id` (int)  | `backend/models/enrichment.py` |
| `action_results`       | Action recognition       | `id` (int)  | `backend/models/enrichment.py` |

### System Tables

| Table        | Purpose                 | Primary Key | Source                        |
| ------------ | ----------------------- | ----------- | ----------------------------- |
| `gpu_stats`  | GPU performance metrics | `id` (int)  | `backend/models/gpu_stats.py` |
| `audit_logs` | Security audit trail    | `id` (int)  | `backend/models/audit.py`     |
| `logs`       | Application logs        | `id` (int)  | `backend/models/log.py`       |
| `jobs`       | Background job tracking | `id` (str)  | `backend/models/job.py`       |

## Related Documentation

- [Database Configuration](../../../backend/core/database.py) - Connection pooling, async setup
- [Redis Configuration](../../../backend/core/redis.py) - Queue management, pub/sub
- [Existing Data Model Reference](../data-model.md) - Legacy comprehensive reference

## Related Hubs

- [Detection Pipeline](../detection-pipeline/README.md) - Detection creation
- [AI Orchestration](../ai-orchestration/README.md) - Event creation
- [API Reference](../api-reference/README.md) - Data access endpoints
