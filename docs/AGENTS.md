# Documentation Directory - Agent Guide

## Purpose

This directory contains all project documentation organized into role-based hubs. Each hub has its own README.md for human navigation and AGENTS.md for AI assistant navigation.

## Quick Navigation

| Directory          | Purpose                                    | Entry Point                            |
| ------------------ | ------------------------------------------ | -------------------------------------- |
| `ai/`              | AI model zoo and pipeline architecture     | [AGENTS.md](ai/AGENTS.md)              |
| `archive/`         | Archived working documents (historical)    | [AGENTS.md](archive/AGENTS.md)         |
| `getting-started/` | Installation and first-run setup           | [README](getting-started/README.md)    |
| `developer/`       | Architecture, API, patterns, contributing  | [README](developer/README.md)          |
| `guides/`          | Feature guides (video analytics, zones)    | [AGENTS.md](guides/AGENTS.md)          |
| `operations/`      | Operational runbooks for production        | [AGENTS.md](operations/AGENTS.md)      |
| `operator/`        | Deployment, monitoring, administration     | [README](operator/README.md)           |
| `templates/`       | Document templates (AGENTS.md, etc.)       | [AGENTS.md](templates/AGENTS.md)       |
| `user/`            | End-user dashboard documentation           | [README](user/README.md)               |
| `reference/`       | Env vars, glossary, troubleshooting        | [README](reference/README.md)          |
| `deployment/`      | Container orchestration documentation      | [AGENTS.md](deployment/AGENTS.md)      |
| `style-guides/`    | Documentation style guides                 | [AGENTS.md](style-guides/AGENTS.md)    |
| `vss-integration/` | NVIDIA VSS pipeline research (in progress) | [AGENTS.md](vss-integration/AGENTS.md) |

## Directory Structure

```
docs/
├── README.md                    # Human navigation hub
├── AGENTS.md                    # This file - AI navigation
├── ROADMAP.md                   # Post-MVP features and direction
├── openapi.json                 # OpenAPI specification
│
├── ai/                          # AI model zoo documentation
│   ├── AGENTS.md                # AI docs navigation
│   └── model-zoo.md             # Model zoo architecture
│
├── api/                         # API governance documentation
│   ├── AGENTS.md                # API docs navigation
│   └── migrations/              # Migration guides
│
├── archive/                     # Archived working documents
│   ├── AGENTS.md                # Archive navigation
│   └── *.md                     # Historical documents
│
├── architecture/                # System design documentation
│   ├── AGENTS.md                # Architecture navigation
│   ├── overview.md              # High-level architecture
│   ├── ai-pipeline.md           # AI pipeline details
│   ├── data-model.md            # Database schema
│   ├── decisions.md             # Architecture decisions
│   ├── frontend-hooks.md        # Frontend hooks architecture
│   ├── real-time.md             # WebSocket and pub/sub
│   ├── resilience.md            # Circuit breakers, retries
│   └── system-page-pipeline-visualization.md
│
├── benchmarks/                  # Performance benchmarks
│   ├── AGENTS.md                # Benchmarks navigation
│   ├── README.md                # Benchmarks overview
│   └── model-zoo-benchmark.md   # Model zoo benchmarks
│
├── decisions/                   # Architectural Decision Records
│   ├── AGENTS.md                # Decisions navigation
│   └── *.md                     # Individual ADRs
│
├── developer/                   # Developer documentation
│   ├── README.md                # Hub: Architecture, API, patterns
│   ├── AGENTS.md                # Developer docs navigation
│   ├── api/                     # API guides
│   ├── architecture/            # Architecture guides
│   ├── contributing/            # Contribution guide + tool guides
│   ├── patterns/                # Code patterns
│   └── *.md                     # Topic-specific docs (testing, git workflow,
│                                #   code quality, hooks, multi-GPU, ...)
│
├── development/                 # Redirect stubs (consolidated into developer/)
│
├── getting-started/             # Installation and setup
│   ├── AGENTS.md                # Getting started navigation
│   ├── prerequisites.md         # System requirements
│   ├── installation.md          # Installation guide
│   ├── first-run.md             # First run guide
│   └── upgrading.md             # Upgrade guide
│
├── guides/                      # Feature guides
│   ├── AGENTS.md                # Guides navigation
│   ├── video-analytics.md       # AI pipeline and detection features
│   ├── zone-configuration.md    # Detection zone setup
│   ├── face-recognition.md      # Face detection and re-ID
│   └── profiling.md             # Continuous profiling guide
│
├── images/                      # Diagrams and screenshots
│   ├── AGENTS.md                # Images navigation
│   ├── style-guide.md           # Visual style guide
│   ├── SCREENSHOT_GUIDE.md      # Screenshot capture guide
│   └── */                       # Organized subdirectories
│
├── operations/                  # Operational runbooks
│   ├── AGENTS.md                # Operations navigation
│   └── profiling-runbook.md     # Pyroscope profiling operations
│
├── style-guides/                # Documentation style guides
│   ├── AGENTS.md                # Style guides navigation
│   └── diagrams.md              # Mermaid diagram style guide
│
├── vss-integration/             # NVIDIA VSS pipeline research (in progress)
│   ├── AGENTS.md                # VSS research navigation
│   ├── README.md                # Human entry point
│   ├── 00-context.md            # Goal, repos, decision this feeds
│   ├── 01-vss-architecture.md   # VSS service map and pipeline mapping
│   ├── 02-model-inventory.md    # Models, slots, consumer-GPU sizing
│   ├── 03-open-questions.md     # Open question register
│   ├── 04-fp4-and-deployment.md # FP4, local paths, verified consumer fit
│   ├── 05-hardware-profiles.md  # Hardware tiering strategy
│   ├── 06-repo-a-readiness.md   # Repo-A defects blocking a swap
│   └── 07-lean-backend.md       # Storage/bus abstraction; overlay play
│
├── operator/                    # Operator documentation
│   ├── README.md                # Hub: Deployment, monitoring, admin
│   ├── AGENTS.md                # Operator navigation
│   ├── admin/                   # Administration guides
│   ├── deployment/              # Deployment guides
│   ├── monitoring/              # Monitoring guides
│   └── *.md                     # Topic-specific docs
│
├── performance/                 # Performance documentation
│   ├── AGENTS.md                # Performance navigation
│   └── LOAD_PROFILES.md         # Load testing profiles
│
├── plans/                       # Implementation plans
│   ├── README.md                # Plans overview
│   └── *.md                     # Individual design plans
│
├── reference/                   # Reference material
│   ├── AGENTS.md                # Reference navigation
│   ├── README.md                # Reference hub
│   ├── glossary.md              # Terms and definitions
│   ├── accessibility.md         # Accessibility guide
│   ├── models.md                # Model reference
│   ├── stability.md             # API stability
│   ├── config/                  # Configuration reference
│   └── troubleshooting/         # Troubleshooting guides
│
├── templates/                   # Document templates
│   ├── AGENTS.md                # Templates navigation
│   └── AGENTS.md.template       # AGENTS.md file template
│
├── testing/                     # Testing documentation
│
├── ui/                          # Page-by-page UI documentation
│   ├── AGENTS.md                # UI docs navigation
│   ├── README.md                # UI pages index
│   └── *.md                     # Page-specific docs
│
├── deployment/                  # Container orchestration docs
│   └── container-orchestration.md  # Startup, health checks, recovery
│
└── user/                        # End-user documentation hub
    ├── AGENTS.md                # User docs navigation
    └── README.md                # Hub: Dashboard, alerts, features

# Support/asset directories (no hub role):
├── _includes/                   # MkDocs snippet includes (auth-model, risk-scoring)
├── components/                  # UI component documentation (see components/AGENTS.md)
├── diagrams/                    # Diagram sources
├── discoveries/                 # NEM-tagged discovery notes
├── examples/                    # Prompt-engineering examples
├── archive/                     # Historical point-in-time reports, snapshots &
│                                #   NEM investigations (see archive/AGENTS.md)
├── research/                    # Numbered research studies
├── stylesheets/                 # MkDocs custom CSS
└── superpowers/                 # Agent handoff/plan documents
```

## Key Entry Points

### For Understanding the System

- **Architecture overview**: `architecture/overview.md`
- **AI model zoo**: `ai/model-zoo.md`
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
- **Container orchestration**: `deployment/container-orchestration.md` - Startup sequences, health checks, recovery
- **Monitoring setup**: `operator/monitoring/README.md`
- **Configuration**: `operator/admin/README.md`

### For Troubleshooting

- **Troubleshooting hub**: `reference/troubleshooting/README.md`
- **AI issues**: `reference/troubleshooting/ai-issues.md`
- **Database issues**: `reference/troubleshooting/database-issues.md`

## AGENTS.md Index

Each major directory has its own AGENTS.md:

| Path                                  | Purpose                        |
| ------------------------------------- | ------------------------------ |
| `docs/AGENTS.md`                      | This file - documentation root |
| `archive/AGENTS.md`                   | Archived working documents     |
| `ai/AGENTS.md`                        | AI model zoo documentation     |
| `api/AGENTS.md`                       | API governance documentation   |
| `guides/AGENTS.md`                    | Feature guides documentation   |
| `architecture/AGENTS.md`              | System design documents        |
| `benchmarks/AGENTS.md`                | Performance benchmarks         |
| `decisions/AGENTS.md`                 | Architectural Decision Records |
| `deployment/AGENTS.md`                | Container orchestration docs   |
| `developer/AGENTS.md`                 | Developer documentation        |
| `developer/api/AGENTS.md`             | API endpoint documentation     |
| `developer/architecture/AGENTS.md`    | Developer architecture guides  |
| `developer/contributing/AGENTS.md`    | Contribution guidelines        |
| `developer/patterns/AGENTS.md`        | Code and testing patterns      |
| `getting-started/AGENTS.md`           | Installation navigation        |
| `images/AGENTS.md`                    | Visual assets                  |
| `operations/AGENTS.md`                | Operational runbooks           |
| `operator/AGENTS.md`                  | Operator documentation         |
| `operator/admin/AGENTS.md`            | Administration guides          |
| `operator/deployment/AGENTS.md`       | Deployment guides              |
| `operator/monitoring/AGENTS.md`       | Monitoring guides              |
| `performance/AGENTS.md`               | Performance documentation      |
| `reference/AGENTS.md`                 | Reference material             |
| `reference/config/AGENTS.md`          | Configuration reference        |
| `reference/troubleshooting/AGENTS.md` | Troubleshooting guides         |
| `ui/AGENTS.md`                        | UI page documentation          |
| `user/AGENTS.md`                      | End-user documentation         |
| `style-guides/AGENTS.md`              | Documentation style guides     |
| `templates/AGENTS.md`                 | Document templates             |
| `vss-integration/AGENTS.md`           | NVIDIA VSS pipeline research   |

## Visual Assets

SVG diagrams are organized by topic in `images/`:

- `images/admin/` - Admin guide diagrams
- `images/ai-pipeline/` - AI processing flow diagrams
- `images/architecture/` - System architecture diagrams
- `images/data-model/` - Entity relationship diagrams
- `images/real-time/` - WebSocket and event flow diagrams
- `images/resilience/` - Circuit breaker and recovery diagrams
- `images/screenshots/` - Application screenshots
- `images/user-guide/` - User guide images

See `images/style-guide.md` for diagram creation guidelines and `images/SCREENSHOT_GUIDE.md` for screenshot capture instructions.

## Related Resources

- **Project root AGENTS.md**: `../AGENTS.md`
- **Backend AGENTS.md**: `../backend/AGENTS.md`
- **Frontend AGENTS.md**: `../frontend/AGENTS.md`
- **AI AGENTS.md**: `../ai/AGENTS.md`
