# Documentation Directory - Agent Guide

## Purpose

This directory contains all project documentation organized into role-based hubs. Each hub has its own README.md for human navigation and AGENTS.md for AI assistant navigation.

## Quick Navigation

| Directory          | Purpose                                   | Entry Point                         |
| ------------------ | ----------------------------------------- | ----------------------------------- |
| `getting-started/` | Installation and first-run setup          | [README](getting-started/README.md) |
| `developer/`       | Architecture, API, patterns, contributing | [README](developer/README.md)       |
| `operator/`        | Deployment, monitoring, administration    | [README](operator/README.md)        |
| `user/`            | End-user dashboard documentation          | [README](user/README.md)            |
| `reference/`       | Env vars, glossary, troubleshooting       | [README](reference/README.md)       |

## Directory Structure

```
docs/
├── README.md                    # Human navigation hub
├── AGENTS.md                    # This file - AI navigation
├── ROADMAP.md                   # Post-MVP features and direction
│
├── getting-started/             # Installation and setup
│   ├── README.md                # Hub: Prerequisites → Install → First run
│   ├── prerequisites.md
│   ├── installation.md
│   ├── first-run.md
│   └── upgrading.md
│
├── developer/                   # Developer documentation
│   ├── README.md                # Hub: Architecture, API, patterns
│   ├── architecture/            # System design docs
│   │   └── README.md
│   ├── api/                     # Consolidated API guides
│   │   ├── README.md            # API overview, auth, pagination
│   │   ├── core-resources.md    # Cameras, Events, Detections, Zones
│   │   ├── ai-pipeline.md       # Enrichment, Batches, AI Audit
│   │   ├── system-ops.md        # System, Health, Alerts, Logs
│   │   └── realtime.md          # WebSocket, SSE
│   ├── patterns/                # Testing and code patterns
│   │   └── README.md
│   └── contributing/            # Git workflow, code quality
│       └── README.md
│
├── operator/                    # Operator documentation
│   ├── README.md                # Hub: Deployment, monitoring, admin
│   ├── deployment/              # Docker, GPU, AI setup
│   │   └── README.md
│   ├── monitoring/              # Health checks, SLOs, metrics
│   │   └── README.md
│   └── admin/                   # Configuration, secrets, security
│       └── README.md
│
├── user/                        # End-user documentation
│   └── README.md                # Hub: Dashboard, alerts, features
│
├── reference/                   # Shared reference material
│   ├── README.md                # Hub: Env vars, glossary
│   └── troubleshooting/         # Common issues and fixes
│       └── README.md
│
├── architecture/                # System design (existing)
├── user-guide/                  # Detailed user docs (existing)
├── admin-guide/                 # Admin guides (existing)
├── benchmarks/                  # Performance benchmarks
├── decisions/                   # Architectural Decision Records
└── images/                      # Diagrams and screenshots
    └── style-guide.md           # SVG diagram style guide
```

## Key Entry Points

### For Understanding the System

- **Architecture overview**: `architecture/overview.md`
- **AI pipeline**: `architecture/ai-pipeline.md`
- **Data model**: `architecture/data-model.md`
- **Real-time events**: `architecture/real-time.md`

### For API Integration

- **API overview**: `developer/api/README.md`
- **Core resources** (cameras, events, detections): `developer/api/core-resources.md`
- **AI pipeline APIs**: `developer/api/ai-pipeline.md`
- **System operations**: `developer/api/system-ops.md`
- **Real-time/WebSocket**: `developer/api/realtime.md`
- **Interactive docs**: http://localhost:8000/docs (Swagger UI)

### For Deployment

- **Deployment guide**: `operator/deployment/README.md`
- **Monitoring setup**: `operator/monitoring/README.md`
- **Configuration**: `operator/admin/README.md`

### For Troubleshooting

- **Troubleshooting hub**: `reference/troubleshooting/README.md`
- **AI issues**: `reference/troubleshooting/ai-issues.md`
- **Database issues**: `reference/troubleshooting/database-issues.md`

## AGENTS.md Index

Each major directory has its own AGENTS.md:

| Path                        | Purpose                        |
| --------------------------- | ------------------------------ |
| `docs/AGENTS.md`            | This file - documentation root |
| `getting-started/AGENTS.md` | Installation navigation        |
| `developer/AGENTS.md`       | Developer documentation        |
| `operator/AGENTS.md`        | Operator documentation         |
| `reference/AGENTS.md`       | Reference material             |
| `architecture/AGENTS.md`    | System design documents        |
| `user-guide/AGENTS.md`      | User documentation             |
| `admin-guide/AGENTS.md`     | Administrator guides           |
| `images/AGENTS.md`          | Visual assets                  |

## Visual Assets

SVG diagrams are organized by topic in `images/`:

- `images/ai-pipeline/` - AI processing flow diagrams
- `images/architecture/` - System architecture diagrams
- `images/data-model/` - Entity relationship diagrams
- `images/real-time/` - WebSocket and event flow diagrams
- `images/resilience/` - Circuit breaker and recovery diagrams

See `images/style-guide.md` for diagram creation guidelines.

## Related Resources

- **Project root AGENTS.md**: `../AGENTS.md`
- **Backend AGENTS.md**: `../backend/AGENTS.md`
- **Frontend AGENTS.md**: `../frontend/AGENTS.md`
- **AI AGENTS.md**: `../ai/AGENTS.md`
