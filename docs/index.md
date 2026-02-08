---
hide:
  - navigation
  - toc
---

# Home Security Intelligence

**Turn "dumb" security cameras into an intelligent threat detection system -- 100% local, no cloud APIs required.**

<div class="grid cards" markdown>

-   :material-rocket-launch: **Getting Started**

    ---

    Prerequisites, installation, and your first run

    [:octicons-arrow-right-24: Get started](getting-started/README.md)

-   :material-monitor-dashboard: **User Guide**

    ---

    Dashboard, alerts, timeline, analytics, and features

    [:octicons-arrow-right-24: User Guide](user/README.md)

-   :material-server-network: **Operator Guide**

    ---

    Deployment, monitoring, GPU setup, and administration

    [:octicons-arrow-right-24: Operator Guide](operator/README.md)

-   :material-code-braces: **Developer Guide**

    ---

    Architecture, API reference, patterns, and contributing

    [:octicons-arrow-right-24: Developer Guide](developer/README.md)

</div>

---

## How It Works

The system processes security camera footage through a multi-stage AI pipeline, turning raw images into explained security events with risk scores.

### 1. Camera Capture

![Camera Capture](images/walkthrough/01-camera-capture.png)

Security cameras upload images via FTP. A file watcher detects new uploads and submits them for analysis.

```mermaid
sequenceDiagram
    participant Camera as IP Camera
    participant FTP as FTP Server
    participant Watcher as File Watcher
    participant Queue as Detection Queue
    Camera->>FTP: Upload image
    FTP->>Watcher: File system event
    Watcher->>Watcher: Validate file type & size
    Watcher->>Queue: Submit for detection
```

### 2. Object Detection

![Object Detection](images/walkthrough/02-object-detection.png)

YOLO26 identifies people, vehicles, animals, and objects in real-time with bounding boxes and confidence scores.

```mermaid
sequenceDiagram
    participant Queue as Detection Queue
    participant YOLO as YOLO26<br/>:8095
    participant DB as PostgreSQL
    Queue->>YOLO: POST /detect (image)
    YOLO-->>Queue: Detections (person, car, dog...)
    Queue->>DB: Store raw detections
```

### 3. AI Enrichment

![AI Enrichment](images/walkthrough/03-ai-enrichment.png)

Multiple specialized models add context: Florence-2 captions the scene, CLIP detects anomalies, and enrichment models identify faces, clothing, vehicles, and more.

```mermaid
flowchart LR
    D[Detection] --> F["Florence-2<br/>Scene Caption"]
    D --> C["CLIP<br/>Anomaly Score"]
    D --> E["Enrichment Models<br/>Face / Clothing / Vehicle"]
    F --> M[Merged Context]
    C --> M
    E --> M
```

### 4. Event Batching

![Event Batching](images/walkthrough/04-event-batching.png)

A 90-second window with 30-second idle timeout groups related detections into a single coherent event, preventing alert fatigue.

```mermaid
sequenceDiagram
    participant Det as Detections
    participant Agg as Batch Aggregator
    participant Event as Event
    Det->>Agg: Detection 1
    Det->>Agg: Detection 2
    Note over Agg: 90s window<br/>30s idle timeout
    Det->>Agg: Detection 3
    Agg->>Event: Window closes
    Note over Event: One explained event<br/>from many detections
```

### 5. AI Risk Reasoning

![AI Risk Reasoning](images/walkthrough/05-ai-reasoning.png)

Nemotron-3-Nano-30B analyzes the full context -- detections, enrichments, time of day, camera location -- and produces a 0-100 risk score with natural language explanation.

```mermaid
sequenceDiagram
    participant Event as Event + Context
    participant Nem as Nemotron-3-Nano-30B<br/>:8091
    participant DB as PostgreSQL
    Event->>Nem: Full context prompt
    Note over Nem: Reason about scene,<br/>entities, time, location
    Nem-->>Event: Risk: 73/100<br/>"Unknown person near<br/>garage at 2:34 AM..."
    Event->>DB: Store analysis
```

### 6. Real-Time Dashboard

![Real-Time Dashboard](images/walkthrough/06-dashboard-alert.png)

Events push to the React dashboard via WebSocket in real-time. The risk gauge updates, timeline entries appear, and entity tracking links detections across cameras.

```mermaid
sequenceDiagram
    participant DB as PostgreSQL
    participant Redis as Redis PubSub
    participant WS as WebSocket
    participant UI as React Dashboard
    DB->>Redis: Event published
    Redis->>WS: Broadcast to subscribers
    WS->>UI: Real-time push
    Note over UI: Risk gauge updates<br/>Timeline entry appears<br/>Entity tracking links
```

---

## Architecture Overview

```mermaid
flowchart TB
    subgraph Cameras["Camera Layer"]
        CAM[IP Cameras]
    end
    subgraph Frontend["Frontend Layer"]
        UI["React Dashboard<br/>:5173"]
    end
    subgraph Backend["Backend Layer"]
        API["FastAPI<br/>:8000"]
        WS["WebSocket"]
    end
    subgraph AI["AI Services"]
        YOLO["YOLO26<br/>:8095"]
        NEM["Nemotron LLM<br/>:8091"]
        FLO["Florence-2<br/>:8092"]
        CLIP["CLIP<br/>:8093"]
        ENR["Enrichment<br/>:8094 / :8096"]
    end
    subgraph Data["Data Layer"]
        DB[(PostgreSQL)]
        REDIS[(Redis)]
    end
    CAM -->|FTP Upload| API
    UI <-->|REST + WebSocket| API
    API --> YOLO & NEM & FLO & CLIP & ENR
    API <--> DB & REDIS
```

[:octicons-arrow-right-24: Full Architecture Documentation](architecture/README.md)

---

## AI Model Zoo

The system uses multiple AI models managed with VRAM-efficient on-demand loading. See the [complete Model Zoo documentation](ai/model-zoo.md).

| Model               | Purpose               | Always Loaded |
| ------------------- | --------------------- | :-----------: |
| YOLO26              | Object detection      |      Yes      |
| Florence-2          | Scene understanding   |      Yes      |
| CLIP ViT-L/14       | Anomaly detection     |      Yes      |
| Nemotron-3-Nano-30B | Risk reasoning (LLM)  |      Yes      |
| Threat Detection    | Weapon detection      |   On-demand   |
| Person Re-ID        | Cross-camera tracking |   On-demand   |
| FashionCLIP         | Clothing analysis     |   On-demand   |
| Demographics        | Age/gender estimation |   On-demand   |

---

## Quick Links

- [:fontawesome-brands-github: GitHub Repository](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence)
- [:material-api: Interactive API Docs](http://localhost:8000/docs) (when running locally)
- [:material-road-variant: Roadmap](ROADMAP.md)
- [:material-file-document: Contributing Guide](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/CONTRIBUTING.md)
