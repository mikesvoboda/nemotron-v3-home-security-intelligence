# Reference Directory - Agent Guide

## Purpose

This directory contains authoritative reference documentation for the Home Security Intelligence system. Reference documentation provides definitive, lookup-style information about APIs, configuration, and troubleshooting.

## Directory Structure

```
reference/
  AGENTS.md                  # This file
  glossary.md                # Terms and definitions
  api/                       # API endpoint reference
    AGENTS.md                # API subdirectory guide
    overview.md              # API overview and conventions
    alerts.md                # Alert rules API
    cameras.md               # Cameras API
    detections.md            # Detections API
    events.md                # Events API
    system.md                # System API
    websocket.md             # WebSocket API
  config/                    # Configuration reference
    AGENTS.md                # Config subdirectory guide
    env-reference.md         # Environment variables
    risk-levels.md           # Risk score definitions
  troubleshooting/           # Problem-solving guides
    AGENTS.md                # Troubleshooting subdirectory guide
    index.md                 # Symptom-based quick reference
    ai-issues.md             # AI service troubleshooting
    connection-issues.md     # Network and connectivity
    database-issues.md       # PostgreSQL problems
    gpu-issues.md            # GPU and CUDA issues
```

## Key Files

### glossary.md

**Purpose:** Canonical definitions of terms used throughout documentation.

**Topics Covered:**

- Security system terminology (Alert, Detection, Event, Risk Score)
- AI/ML terms (Inference, Confidence Score, Batch, Pipeline)
- System components (Circuit Breaker, Dead Letter Queue, Worker)
- Configuration terms (Retention Period, Risk Level, Threshold)

**Format:** Alphabetically organized with cross-references between related terms.

**When to use:** Understanding unfamiliar terminology, consistent term definitions.

## Subdirectories

### api/

**Purpose:** Complete REST and WebSocket API documentation.

> **Note:** The `docs/api-reference/` directory is the **canonical/authoritative location** for API documentation. The `docs/reference/api/` directory is maintained for historical compatibility, but `docs/api-reference/` should be treated as the source of truth for all API documentation.

See `api/AGENTS.md` for detailed information.

**Key Files:**

- `overview.md` - Base URL, authentication, rate limiting
- `alerts.md` - Alert rule CRUD operations
- `cameras.md` - Camera management
- `detections.md` - Object detection results
- `events.md` - Security event queries
- `system.md` - Health, config, monitoring
- `websocket.md` - Real-time streaming

### config/

**Purpose:** Configuration reference for environment variables and settings.

See `config/AGENTS.md` for detailed information.

**Key Files:**

- `env-reference.md` - Complete environment variable reference
- `risk-levels.md` - Risk score ranges and severity definitions

### troubleshooting/

**Purpose:** Symptom-based problem-solving guides.

See `troubleshooting/AGENTS.md` for detailed information.

**Key Files:**

- `index.md` - Quick symptom lookup table
- `ai-issues.md` - RT-DETRv2, Nemotron, pipeline problems
- `connection-issues.md` - Network, containers, WebSocket
- `database-issues.md` - PostgreSQL connection, migrations
- `gpu-issues.md` - CUDA, VRAM, thermal issues

## Reference Documentation Standards

Reference documentation follows specific conventions:

### Format

- **Tables for structured data** - Quick lookup
- **Code examples** - Practical usage
- **Type annotations** - Parameter types and constraints
- **Default values** - What happens without configuration

### Tone

- **Factual and precise** - No marketing language
- **Complete** - All options documented
- **Authoritative** - Single source of truth

### Structure

Each reference document includes:

1. Brief description
2. Read time estimate
3. Prerequisites if any
4. Main content with examples
5. Related documentation links

## Target Audiences

| Audience       | Needs                       | Primary Documents         |
| -------------- | --------------------------- | ------------------------- |
| **Developers** | API integration, extensions | api/, glossary.md         |
| **Operators**  | Configuration, deployment   | config/, troubleshooting/ |
| **Support**    | Problem resolution          | troubleshooting/          |
| **All Users**  | Term definitions            | glossary.md               |

## Entry Points

### Looking Up API Details

1. Start with `api/overview.md` for conventions
2. Find specific endpoint in relevant API file
3. Check examples and response formats

### Configuring the System

1. Check `config/env-reference.md` for all variables
2. Review `config/risk-levels.md` for severity tuning
3. Apply changes to `.env` file

### Solving Problems

1. Start with `troubleshooting/index.md` symptom table
2. Follow link to specific issue guide
3. Try solutions in order (most likely first)

### Understanding Terms

1. Search `glossary.md` alphabetically
2. Follow cross-references to related terms
3. See "Related Resources" for deeper context

## Related Documentation

- **docs/AGENTS.md:** Documentation directory overview
- **docs/developer/:** Developer guides (how-to)
- **docs/operator/:** Operator guides (how-to)
- **docs/user-guide/:** End-user documentation
- **docs/architecture/:** Technical architecture (why decisions were made)
