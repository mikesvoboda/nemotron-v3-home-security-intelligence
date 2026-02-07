# Documentation Improvement Design

**Date:** 2026-02-07
**Status:** Approved
**Goal:** Make documentation community/contributor-ready with a professional docs portal, visual storytelling, and interactive API reference.

---

## Context

A comprehensive documentation audit (see `docs/DOCUMENTATION_REVIEW_2026-02-07.md`) revealed that while the project has extensive documentation (~456 markdown files, 231 AGENTS.md files, role-based hubs), the content was drifting from the codebase and lacked the visual polish and onboarding experience needed for community adoption. A two-team fix/validation effort resolved ~230 issues across ~80 files.

This design addresses the next level: transforming raw markdown into a professional documentation experience that converts visitors into contributors.

---

## Phase 1: MkDocs Material Site + Architecture Walkthrough

### 1.1 MkDocs Material Setup

Set up a documentation site powered by MkDocs Material, deployed to GitHub Pages.

**Site hierarchy:**

```
Home (hero image + animated architecture walkthrough)
├── Getting Started
│   ├── Prerequisites & Hardware
│   ├── Quick Start
│   ├── First Run Tour
│   └── Configuration Reference
├── User Guide (docs/user/)
│   ├── Dashboard, Alerts, Timeline, Analytics...
│   └── Notification Setup
├── Operator Guide (docs/operator/)
│   ├── Deployment, Monitoring, Admin...
│   └── GPU Setup, AI Services
├── Developer Guide (docs/developer/)
│   ├── Architecture, API Reference, Patterns...
│   └── Contributing Guide (NEW)
├── Architecture (docs/architecture/)
│   ├── System Overview, Data Model, AI Pipeline...
│   └── ADRs
├── AI Model Zoo (docs/ai/)
└── API Reference (Swagger/ReDoc - Phase 3)
```

**Key decisions:**

- Existing markdown files stay in place -- `mkdocs.yml` nav config maps them into the site hierarchy
- Mermaid diagrams render natively (no pre-rendering to SVG)
- GitHub Actions deploys to GitHub Pages on every push to main
- Search, dark mode, version selector come free with Material theme

**Configuration:**

- `mkdocs.yml` at project root
- Material theme with `pymdownx.superfences` for Mermaid
- `snippets` extension for content deduplication (see 1.3)
- `.github/workflows/docs.yml` for automated deployment

### 1.2 Animated Architecture Walkthrough

A visual storytelling sequence on the docs homepage that walks visitors through the camera-to-alert pipeline in 6 panels. This is the "aha moment" -- within 30 seconds a visitor understands what the system does.

**The story in 6 panels:**

1. **Camera Capture** - Security camera uploads image via FTP to the watched directory
2. **Object Detection** - YOLO26 identifies person, vehicle, or animal with bounding boxes
3. **Enrichment** - Florence captions the scene, CLIP checks anomaly baseline, enrichment models add face/clothing/vehicle context
4. **Batching** - 90-second window aggregates related detections into a coherent event
5. **AI Reasoning** - Nemotron analyzes the full context, assigns 0-100 risk score with natural language explanation
6. **Dashboard Alert** - Real-time WebSocket pushes the event to the dashboard with risk gauge, timeline entry, and entity tracking

**Each panel consists of:**

- An AI-generated hero image (Google Nano Banana Pro) showing the concept visually in a stylized technical illustration style
- A Mermaid sequence or flow diagram below showing the actual technical flow
- 2-3 sentences of explanation
- Link to the relevant architecture deep-dive

**Additional Mermaid diagrams (8 missing from audit):**

- Auth flow (SetupGuard -> registration -> normal access)
- MQTT integration (broker, publishers, command handlers)
- Webhook flow (event -> dispatch -> retry logic)
- Household matching (detection -> face/vehicle match -> member identification)
- Model zoo VRAM management (LRU eviction, priority tiers, budget allocation)
- Zone types comparison (CameraZone vs PolygonZone)
- Enrichment pipeline split (heavy on 8094 vs light on 8096)
- go2rtc integration (camera -> go2rtc -> WebRTC -> frontend)

### 1.3 Content Deduplication

Extract duplicated content into reusable snippets using MkDocs `snippets` extension.

**Canonical content in `docs/_includes/`:**

```
docs/_includes/
├── risk-scoring-levels.md
├── batching-config.md
├── websocket-channels.md
├── pipeline-stages.md
├── vram-requirements.md
└── auth-model.md
```

**Usage in markdown files:**

```markdown
--8<-- "docs/\_includes/risk-scoring-levels.md"
```

The `_includes/` directory is excluded from nav. Single source of truth -- edit once, reflected everywhere. Raw GitHub viewing loses the includes, but the docs site is the primary consumer.

### 1.4 Contributing Guide

**CONTRIBUTING.md at project root (~100 lines):**

- Welcome message and project philosophy (local-first, privacy-focused)
- Hardware requirements (direct about the GPU need)
- Quick setup: `python setup.py && docker compose -f docker-compose.prod.yml up -d`
- How to run tests: `./scripts/validate.sh`
- PR workflow: branch naming, commit conventions, TDD requirement
- Link to developer hub for deep dives
- Code of Conduct reference

**Good first issues:**

- Label system in GitHub Issues: `good-first-issue`, `help-wanted`, `documentation`, `frontend`, `backend`, `ai`
- Curate 5-10 starter issues that don't require understanding the full AI pipeline
- GitHub Issues is the public interface; Linear syncs automatically for internal triage

---

## Phase 2: Demo Video

A 2-3 minute screen recording of the live system, embedded in README and docs homepage.

**Script:**

1. Cold open (10s) - Dashboard with camera grid, quiet state. Text overlay: "AI-powered home security -- 100% local, no cloud."
2. Detection happens (30s) - Person appears on camera. Activity feed lights up. Bounding box visible.
3. AI reasoning (30s) - Event detail with Nemotron risk analysis and natural language explanation.
4. Multi-camera tracking (20s) - Same person on second camera. Entity view shows re-identification.
5. Analytics & timeline (20s) - Timeline view, analytics charts, detection trends.
6. Model zoo (20s) - AI performance page with loaded models, VRAM usage, inference times.
7. Close (10s) - Dashboard overview. Text overlay: "Open source. Local-first. GPU-accelerated."

**Production:**

- Record with OBS, 1080p
- Text overlays, no voiceover
- Host on YouTube, embed in README via image link
- Done when real camera activity makes for a compelling demo

---

## Phase 3: API Playground

Interactive Swagger UI embedded in the MkDocs docs site.

**Approach:**

- Dedicated API Reference page with full Swagger UI loading `docs/openapi.json`
- CI step auto-generates updated OpenAPI spec from FastAPI and commits if changed
- Pairs with existing narrative API docs in `docs/developer/api/`

**CI integration:**

```bash
python -c "from backend.api.app import app; import json; print(json.dumps(app.openapi()))" > docs/openapi.json
```

---

## What Stays As-Is

- **231 AGENTS.md files** - Maintained manually with periodic audits (the two-team audit/fix/validate approach works well)
- **Role-based hub structure** - user/operator/developer entry points remain the primary navigation
- **GitHub Issues + Linear sync** - Public contributor interface via GitHub Issues, internal planning via Linear

---

## Implementation Order

| Phase | Deliverable                                      | Effort | Dependency                  |
| ----- | ------------------------------------------------ | ------ | --------------------------- |
| 1.1   | MkDocs Material site + GitHub Pages deployment   | Medium | None                        |
| 1.3   | Content deduplication into `_includes/`          | Medium | 1.1                         |
| 1.4   | CONTRIBUTING.md + good first issues              | Small  | None                        |
| 1.2   | Architecture walkthrough (6 panels + 8 diagrams) | Large  | 1.1, AI image generation    |
| 2     | Demo video                                       | Medium | Running system with cameras |
| 3     | API playground (Swagger UI)                      | Small  | 1.1                         |
