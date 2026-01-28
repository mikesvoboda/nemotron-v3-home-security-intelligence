# Shared Diagram Library

> Reusable Mermaid diagram snippets and templates for consistent documentation

This directory contains copy-paste ready diagram components. Use these snippets as building blocks when creating new diagrams in documentation.

## Quick Reference

| Snippet                                         | Description                        |
| ----------------------------------------------- | ---------------------------------- |
| [Theme Configuration](#theme-configuration)     | Standard dark theme init block     |
| [Service Components](#service-components)       | Common service node definitions    |
| [Data Flow Patterns](#data-flow-patterns)       | Pipeline and queue patterns        |
| [Architecture Diagrams](#architecture-diagrams) | Full system architecture templates |

## Related Resources

- [Diagram Style Guide](../style-guides/diagrams.md) - Conventions and best practices
- [Visual Style Guide](../images/style-guide.md) - Colors and design principles

---

## Theme Configuration

### Standard Dark Theme

Copy this init block to the top of every Mermaid diagram:

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'primaryColor': '#3B82F6',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#60A5FA',
    'secondaryColor': '#A855F7',
    'tertiaryColor': '#009688',
    'background': '#121212',
    'mainBkg': '#1a1a2e',
    'lineColor': '#666666'
  }
}}%%
```

### Theme Color Reference

| Variable             | Hex Code  | Purpose                       |
| -------------------- | --------- | ----------------------------- |
| `primaryColor`       | `#3B82F6` | Frontend/React components     |
| `primaryTextColor`   | `#FFFFFF` | Text on primary backgrounds   |
| `primaryBorderColor` | `#60A5FA` | Borders on primary components |
| `secondaryColor`     | `#A855F7` | AI/ML components              |
| `tertiaryColor`      | `#009688` | Backend/FastAPI components    |
| `background`         | `#121212` | Diagram background            |
| `mainBkg`            | `#1a1a2e` | Subgraph backgrounds          |
| `lineColor`          | `#666666` | Default connection lines      |

---

## Service Components

### AI Services

```mermaid
%%{init: {'theme': 'dark'}}%%
flowchart LR
    YOLO["YOLO26<br/>Port 8095<br/>Object Detection"]
    NEM["Nemotron<br/>Port 8091<br/>Risk Analysis"]
    FLOR["Florence-2<br/>Port 8092<br/>Captioning"]
    CLIP["CLIP<br/>Port 8093<br/>Embeddings"]
    ENR["Enrichment<br/>Port 8094<br/>Model Zoo"]
```

### Core Services

```mermaid
%%{init: {'theme': 'dark'}}%%
flowchart LR
    API["FastAPI<br/>Port 8000"]
    DB[(PostgreSQL<br/>Port 5432)]
    REDIS[(Redis<br/>Port 6379)]
    UI["React Frontend<br/>Port 5173/8443"]
```

### Backend Services

```mermaid
%%{init: {'theme': 'dark'}}%%
flowchart TB
    FW[FileWatcher<br/>backend/services/file_watcher.py]
    BA[BatchAggregator<br/>90s window]
    EB[EventBroadcaster<br/>WebSocket]
    DC[DetectorClient<br/>YOLO26 HTTP]
    NA[NemotronAnalyzer<br/>LLM Analysis]
```

---

## Data Flow Patterns

### Detection Pipeline

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'primaryColor': '#3B82F6',
    'secondaryColor': '#A855F7',
    'tertiaryColor': '#009688'
  }
}}%%
flowchart LR
    subgraph Input["Image Input"]
        FTP[FTP Server]
        CAM[Camera Feed]
    end

    subgraph Detection["Detection Stage"]
        FW[FileWatcher]
        DQ[detection_queue]
        YOLO[YOLO26]
    end

    subgraph Analysis["Analysis Stage"]
        BA[BatchAggregator]
        AQ[analysis_queue]
        NEM[Nemotron]
    end

    subgraph Output["Output"]
        DB[(Events DB)]
        WS[WebSocket]
        UI[Dashboard]
    end

    FTP --> FW
    CAM --> FW
    FW --> DQ
    DQ --> YOLO
    YOLO --> BA
    BA --> AQ
    AQ --> NEM
    NEM --> DB
    NEM --> WS
    WS --> UI
```

### Queue Processing Pattern

```mermaid
%%{init: {'theme': 'dark'}}%%
flowchart LR
    Producer --> Queue[(Redis Queue)]
    Queue --> Worker1[Worker 1]
    Queue --> Worker2[Worker 2]
    Worker1 --> Result[(Result Store)]
    Worker2 --> Result
    Worker1 -.-> DLQ[(Dead Letter Queue)]
    Worker2 -.-> DLQ
```

### Circuit Breaker Pattern

```mermaid
%%{init: {'theme': 'dark'}}%%
stateDiagram-v2
    [*] --> Closed
    Closed --> Open : failures >= threshold
    Open --> HalfOpen : timeout elapsed
    HalfOpen --> Closed : success
    HalfOpen --> Open : failure
    Closed --> Closed : success
```

---

## Architecture Diagrams

### Full System Overview

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'primaryColor': '#3B82F6',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#60A5FA',
    'secondaryColor': '#A855F7',
    'tertiaryColor': '#009688',
    'background': '#121212',
    'mainBkg': '#1a1a2e',
    'lineColor': '#666666'
  }
}}%%
flowchart TB
    subgraph Frontend["Frontend Layer"]
        UI["React Dashboard<br/>:5173 / :8443"]
    end

    subgraph Backend["Backend Layer"]
        API["FastAPI<br/>:8000"]
        FW[FileWatcher]
        BA[BatchAggregator]
    end

    subgraph AI["AI Services"]
        YOLO["YOLO26<br/>:8095"]
        NEM["Nemotron<br/>:8091"]
        FLOR["Florence-2<br/>:8092"]
        CLIP["CLIP<br/>:8093"]
        ENR["Enrichment<br/>:8094"]
    end

    subgraph Storage["Data Layer"]
        DB[(PostgreSQL<br/>:5432)]
        REDIS[(Redis<br/>:6379)]
    end

    UI <--> API
    API --> FW
    FW --> REDIS
    REDIS --> YOLO
    YOLO --> BA
    BA --> NEM
    NEM --> FLOR
    NEM --> CLIP
    NEM --> ENR
    NEM --> DB
    API <--> DB
    API <--> REDIS
```

### Sequence Diagram Template

```mermaid
%%{init: {'theme': 'dark'}}%%
sequenceDiagram
    participant FW as FileWatcher
    participant DQ as detection_queue
    participant YOLO as YOLO26 (8095)
    participant BA as BatchAggregator
    participant NEM as Nemotron (8091)
    participant DB as PostgreSQL

    FW->>DQ: queue image
    DQ->>YOLO: process
    YOLO-->>BA: detections
    BA->>NEM: analyze batch
    NEM-->>DB: save event
```

---

## Standard Abbreviations

Use these consistent abbreviations across all diagrams:

| Abbreviation | Full Name        | Component Type |
| ------------ | ---------------- | -------------- |
| `FW`         | FileWatcher      | Service        |
| `DQ`         | detection_queue  | Redis Queue    |
| `AQ`         | analysis_queue   | Redis Queue    |
| `YOLO`       | YOLO26           | AI Model       |
| `NEM`        | Nemotron         | AI Model       |
| `FLOR`       | Florence-2       | AI Model       |
| `BA`         | BatchAggregator  | Service        |
| `EB`         | EventBroadcaster | Service        |
| `WS`         | WebSocket        | Communication  |
| `DB`         | PostgreSQL       | Database       |
| `REDIS`      | Redis            | Cache/Queue    |
| `API`        | FastAPI          | API Layer      |
| `UI`         | React Frontend   | Frontend       |
| `ENR`        | Enrichment       | AI Service     |

---

## Port Reference

Current standard ports for all services:

| Service            | Port | Container           |
| ------------------ | ---- | ------------------- |
| Frontend HTTP      | 5173 | frontend            |
| Frontend HTTPS     | 8443 | frontend            |
| Backend API        | 8000 | backend             |
| PostgreSQL         | 5432 | postgres            |
| Redis              | 6379 | redis               |
| Nemotron           | 8091 | ai-llm              |
| Florence-2         | 8092 | ai-florence         |
| CLIP               | 8093 | ai-clip             |
| Enrichment (Heavy) | 8094 | ai-enrichment       |
| YOLO26             | 8095 | ai-yolo26           |
| Enrichment (Light) | 8096 | ai-enrichment-light |

---

## Usage Examples

### Adding a New Diagram

1. Copy the theme configuration from [Theme Configuration](#theme-configuration)
2. Select appropriate components from this library
3. Customize labels and connections for your use case
4. Follow the [Diagram Style Guide](../style-guides/diagrams.md) for conventions

### Embedding in Documentation

```markdown
## System Architecture

The following diagram shows the data flow through the system:

\`\`\`mermaid
%%{init: {'theme': 'dark'}}%%
flowchart LR
A[Source] --> B[Processing] --> C[Output]
\`\`\`
```

---

## Contributing

When adding new diagram components:

1. Follow the [Diagram Style Guide](../style-guides/diagrams.md) conventions
2. Use standard abbreviations from this document
3. Include theme configuration in all examples
4. Test rendering in GitHub/GitLab before committing
