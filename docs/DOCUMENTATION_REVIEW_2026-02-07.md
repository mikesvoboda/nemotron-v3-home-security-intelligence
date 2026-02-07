# Comprehensive Documentation Review

**Date:** 2026-02-07
**Scope:** Full project documentation audit across 100+ markdown files
**Method:** 6 parallel agents audited different documentation domains, cross-referencing every path, link, port, class name, and command against the actual codebase.

---

## Executive Summary

The project has extensive documentation infrastructure (~100+ markdown files, 80+ AGENTS.md files, comprehensive architecture docs). However, the codebase has evolved significantly faster than the docs. The audit found **~140 issues** across all documentation, grouped into these themes:

1. **Pervasive port number errors** - YOLO26 port 8090/8091 documented everywhere, actual is 8095
2. **Stale file counts and module listings** - backend/AGENTS.md misses ~50% of routes, services, models
3. **Root-level work product clutter** - 4 one-off investigation reports sitting at project root
4. **Conflicting VRAM/model specs** - Different numbers in different docs for the same models
5. **Auth model confusion** - Three different descriptions of auth across README, CLAUDE.md, AGENTS.md
6. **Abandoned CHANGELOG** - No entries since Dec 2024 despite massive development
7. **Broken links** - CLAUDE.md links to non-existent container-rebuilds.md; setup.sh, docker-compose.yml (dev), start-ai.sh referenced but missing
8. **Version drift in CI configs** - Python 3.11 and React 18 referenced where 3.14 and 19 are actual
9. **Model name conflict** - ai-orchestration docs say "Nemotron 70B" (wrong) vs actual "Nemotron-3-Nano-30B"
10. **25 undocumented API routes** in developer hub out of ~58 total route files

---

## 1. FILES TO DELETE OR ARCHIVE

### Root-Level Work Products (Move to `docs/archive/`)

These are one-off investigation/task reports that clutter the project root:

| File                                     | Reason                                                                          | Action  |
| ---------------------------------------- | ------------------------------------------------------------------------------- | ------- |
| `CONTRACT_TESTS_VERIFICATION.md`         | Resolved CI investigation (2026-01-21)                                          | Archive |
| `FLAKY_TEST_DETECTION_IMPLEMENTATION.md` | Implementation summary; real docs at `docs/development/flaky-test-detection.md` | Archive |
| `NEM-3140-E2E-PARALLELIZATION-FIXES.md`  | Completed task report for NEM-3140                                              | Archive |
| `SKIPPED_TESTS_ANALYSIS.md`              | Point-in-time analysis (2026-01-20), counts already stale                       | Archive |

### Backend Test Docs to Rewrite or Remove

| File                                    | Reason                                                                                                    | Action             |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------ |
| `backend/tests/integration/COVERAGE.md` | Says "Total test files: 2" -- actual: 174 files. References SQLite (now PostgreSQL). Actively misleading. | Delete or rewrite  |
| `backend/tests/integration/README.md`   | Same -- only documents 2 of 174 test files, references SQLite and `requirements.txt`                      | Delete or rewrite  |
| `backend/tests/MATCHERS.md`             | Empty placeholder file (0 content)                                                                        | Delete or populate |

### Candidate for Review

| File                                                              | Reason                | Action             |
| ----------------------------------------------------------------- | --------------------- | ------------------ |
| `backend/tests/integration/TEST_NOTIFICATION_DELIVERY_SUMMARY.md` | NEM-2745 task summary | Consider archiving |
| `backend/tests/integration/RUM_TESTS.md`                          | NEM-2760 task summary | Consider archiving |
| `backend/tests/FIXTURE_CONSOLIDATION.md`                          | NEM-3152 task summary | Consider archiving |

---

## 2. CRITICAL FIXES NEEDED

### 2.1 YOLO26 Port Numbers (20+ files affected)

**Problem:** `.env.example` defines `YOLO26_PORT=8095`. Documentation pervasively uses port **8090** (old) or **8091** (Nemotron's port, completely wrong).

**Files needing port correction:**

Architecture docs (8090 -> 8095):

- `docs/architecture/overview.md` (7 references)
- `docs/architecture/ai-pipeline.md` (6 references)
- `docs/architecture/decisions.md` (2 references)
- `docs/architecture/resilience.md`
- `docs/architecture/system-overview/README.md`
- `docs/architecture/system-overview/deployment-topology.md`
- `docs/architecture/security/network-security.md`
- `docs/architecture/resilience-patterns/health-monitoring.md`
- `docs/deployment/container-orchestration.md` (2 references)

Video analytics guide (8091 -> 8095):

- `docs/guides/video-analytics.md` (4 references using 8091, which is the LLM port)

Hub docs (8090 -> 8095):

- `docs/developer/README.md` (line 113)
- `docs/reference/README.md` (line 29)

YOLO26 docs (8090 -> 8095):

- `ai/yolo26/README.md` (comparison table references 8090)

### 2.2 Nemotron Model Name Wrong in ai-orchestration/

**Problem:** The ai-orchestration subdirectory references a completely different model.

| File                                                      | Claims                           | Actual                         |
| --------------------------------------------------------- | -------------------------------- | ------------------------------ |
| `docs/architecture/ai-orchestration/README.md`            | "Nemotron 70B" at 21,700 MB VRAM | Nemotron-3-Nano-30B at ~14.7GB |
| `docs/architecture/ai-orchestration/nemotron-analyzer.md` | "Nemotron 70B LLM"               | Nemotron-3-Nano-30B-A3B        |

This is not a typo -- 70B and 30B are completely different models. Anyone referencing these docs would think a different model is running.

### 2.3 CLAUDE.md Broken Link + Wrong Endpoint

| Issue                                                   | Location          | Fix                                |
| ------------------------------------------------------- | ----------------- | ---------------------------------- |
| Broken link to `docs/development/container-rebuilds.md` | CLAUDE.md line 53 | Create the file or update the link |
| Health endpoint `/api/health` doesn't exist             | CLAUDE.md line 74 | Change to `/api/system/health`     |

### 2.4 AGENTS.md (Root) - Wrong License

| Issue                             | Location           | Fix                                    |
| --------------------------------- | ------------------ | -------------------------------------- |
| Says "Mozilla Public License 2.0" | AGENTS.md line 48  | Change to "Apache License 2.0"         |
| Coverage says 93%                 | AGENTS.md line 233 | Change to 85% (matches pyproject.toml) |

### 2.5 backend/AGENTS.md - Severely Outdated

The primary backend navigation document misses roughly **half the codebase**:

| Component  | Documented | Actual | Missing                          |
| ---------- | ---------- | ------ | -------------------------------- |
| API Routes | 28-34      | 62+    | ~30 routes undocumented          |
| Services   | 89-124     | 201    | ~80 services undocumented        |
| Models     | 25-35      | 54     | ~20 models undocumented          |
| Middleware | 20         | 25     | 5 missing (incl. setup_guard.py) |

Internal inconsistencies: the same file says "34 route modules" at top, "28 route modules" in details, and lists 27 in router registration.

### 2.6 AI Documentation - VRAM Conflicts

Same models have different VRAM specs across docs:

| Model          | ai/AGENTS.md | docs/ai/model-zoo.md | ai/enrichment/AGENTS.md | Actual (code)        |
| -------------- | ------------ | -------------------- | ----------------------- | -------------------- |
| YOLO26         | ~100 MB      | ~2 GB                | --                      | ~2 GB                |
| Demographics   | 500 MB       | ~400 MB              | ~500 MB                 | Verify               |
| FashionCLIP    | 800 MB       | ~500 MB              | ~800 MB                 | 800 MB               |
| VRAM_BUDGET_GB | 6.8          | --                   | --                      | 6.0 (docker-compose) |

### 2.7 docs/ai/model-zoo.md - Wrong Container Name + Path

| Issue                                              | Fix                                                    |
| -------------------------------------------------- | ------------------------------------------------------ |
| References container `ai-nemotron`                 | Should be `ai-llm`                                     |
| YOLO26 model path `/export/ai_models/yolo26v2/...` | Should be `/models/yolo26/exports/yolo26m_fp16.engine` |

---

## 3. AUTH MODEL CONFUSION

Three different descriptions exist across the codebase:

| Source    | Description                                                                                                                               |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| README.md | "Authentication is off by default"                                                                                                        |
| CLAUDE.md | "First-time admin registration required (SetupGuardMiddleware returns 503 until first user). After registration, API endpoints are open." |
| AGENTS.md | "No auth: Single-user local deployment (MVP)"                                                                                             |
| ADR-005   | "No authentication for MVP" (stale -- auth routes now exist)                                                                              |

**Recommendation:** Align all docs to the CLAUDE.md description, which most accurately reflects current behavior. Update ADR-005 to "Superseded" status.

---

## 4. VERSION DRIFT

| File                              | Claims                  | Actual                               |
| --------------------------------- | ----------------------- | ------------------------------------ |
| `.github/copilot-instructions.md` | Python 3.11, React 18   | Python 3.14, React 19.2.3            |
| `.github/workflows/AGENTS.md`     | Python 3.11, Node.js 20 | Python 3.14, Node.js 22              |
| `CHANGELOG.md`                    | Last entry 2024-12-21   | Effectively abandoned                |
| `ai/nemotron/AGENTS.md`           | CUDA 13.1.0             | CUDA 13.x doesn't exist; likely 12.x |

---

## 5. CONTENT DUPLICATION

The following content is duplicated across 3-6 files each, creating maintenance burden and drift risk:

| Content                           | Duplicated In                                                                                   |
| --------------------------------- | ----------------------------------------------------------------------------------------------- |
| AI pipeline sequence diagram      | overview.md, ai-pipeline.md, dataflows/                                                         |
| Database ER diagram               | overview.md, data-model.md, data-model/README.md                                                |
| Risk scoring levels (0-100 scale) | overview.md, ai-pipeline.md, decisions.md                                                       |
| Batching logic (90s/30s)          | overview.md, ai-pipeline.md, decisions.md, detection-pipeline/                                  |
| Circuit breaker state machine     | resilience.md, real-time.md, decisions.md                                                       |
| WebSocket channels table          | overview.md, real-time.md, frontend-hooks.md                                                    |
| Image generation prompts (DALL-E) | Bottom of overview.md, ai-pipeline.md, decisions.md, data-model.md, real-time.md, resilience.md |

**Recommendation:** Move canonical content to single-source files and reference them. Remove image generation prompts from architecture docs entirely (100-200 lines of bloat per file).

---

## 6. MISSING DOCUMENTATION

### Missing Documentation for New Features

| Feature                   | Code Exists                                          | Documentation              |
| ------------------------- | ---------------------------------------------------- | -------------------------- |
| 35+ new API routes        | `backend/api/routes/`                                | Not in backend/AGENTS.md   |
| 80+ new services          | `backend/services/`                                  | Not in backend/AGENTS.md   |
| Zustand stores (7+)       | `frontend/src/stores/`                               | Not in frontend/AGENTS.md  |
| 65+ undocumented hooks    | `frontend/src/hooks/`                                | Only ~15 of 80+ documented |
| ONVIF camera discovery    | `backend/api/routes/onvif.py`                        | No guide                   |
| MQTT integration          | `backend/services/mqtt_*.py`                         | No guide                   |
| Face recognition routes   | `backend/api/routes/face_recognition.py`             | Partial                    |
| Household management      | `backend/api/routes/household*.py`                   | None                       |
| Scheduled reports         | `backend/api/routes/scheduled_reports.py`            | None                       |
| Webhook system            | `backend/api/routes/*webhooks.py`                    | None                       |
| 8 AI optimization modules | `ai/*.py` (cpu_offloading, cuda_graph_manager, etc.) | Not in ai/AGENTS.md        |
| 5 enrichment model files  | `ai/enrichment/models/`                              | Only 3 of 8 documented     |
| enrichment-light service  | `ai/enrichment-light/`                               | No root AGENTS.md          |
| ai/shared/ module         | `ai/shared/gpu_profiler.py`                          | No AGENTS.md               |

### 25 Undocumented API Routes in Developer Hub

The `docs/developer/api/` directory covers cameras, events, detections, zones, entities, analytics, system, DLQ, calibration, and webhooks. But these route files have **no API documentation**:

`cost_analytics.py`, `gpu_config.py`, `tracks.py`, `reid.py`, `face_recognition.py`, `household.py`, `household_matcher.py`, `onvif.py`, `mqtt_config.py`, `scheduled_reports.py`, `trends.py`, `summaries.py`, `materialized_views.py`, `zone_anomalies.py`, `zone_baselines.py`, `zone_household.py`, `analytics_zones.py`, `entity_recognition.py`, `llm_reasoning.py`, `model_management.py`, `plate_reads.py`, `rum.py`, `settings_api.py`, `inbound_webhooks.py`, `outbound_webhooks.py`

### Missing Files Referenced in Docs

| Referenced Script                   | Referenced From                       | Status                                             |
| ----------------------------------- | ------------------------------------- | -------------------------------------------------- |
| `./setup.sh`                        | operator README, reference README     | Does not exist -- actual is `python setup.py`      |
| `docker-compose.yml` (dev)          | operator deployment, developer README | Does not exist -- only `.prod.yml` and `.ghcr.yml` |
| `./scripts/start-ai.sh`             | reference README                      | Does not exist                                     |
| `docs/developer/patterns/README.md` | developer hub                         | Directory exists but no README.md                  |

### Missing AGENTS.md Files

| Directory                     | Status                                       |
| ----------------------------- | -------------------------------------------- |
| `ai/enrichment-light/` (root) | Missing -- only models/ subdirectory has one |
| `ai/shared/`                  | Missing                                      |

### User Hub Gaps

The user hub (`docs/user/`) is thin -- only 1 substantive sub-document (`notification-setup.md`). Missing user-facing content for:

- Camera setup / first-time configuration
- Understanding AI analysis output
- Interpreting the event timeline
- Managing household members
- Video analytics features (linked only from operator/developer docs)
- Face recognition and zone configuration (no user-facing versions)

---

## 7. BROKEN OR BAD LINKS

| Source File                                                      | Broken Link                                                           | Issue                                                                              |
| ---------------------------------------------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| CLAUDE.md                                                        | `docs/development/container-rebuilds.md`                              | File does not exist                                                                |
| `docs/operator/README.md`, `docs/reference/README.md`            | `./setup.sh`                                                          | File does not exist (actual: `python setup.py`)                                    |
| `docs/operator/deployment/README.md`, `docs/developer/README.md` | `docker-compose.yml` (dev)                                            | File does not exist (only `docker-compose.prod.yml` and `docker-compose.ghcr.yml`) |
| `docs/reference/README.md`                                       | `./scripts/start-ai.sh`                                               | File does not exist                                                                |
| `docs/developer/README.md`                                       | `docs/developer/patterns/README.md`                                   | Directory exists but README.md is missing                                          |
| `backend/tests/integration/STATEFUL_TESTING.md`                  | Hardcoded worktree paths `/home/msvoboda/.claude-squad/worktrees/...` | Ephemeral paths, should be relative                                                |
| `docs/architecture/STANDARDS.md`                                 | `backend/services/detection_service.py`                               | File doesn't exist (actual: `detector_client.py`)                                  |
| `docs/architecture/overview.md`                                  | `backend/services/audit_service.py`                                   | File doesn't exist (actual: `audit.py` or `audit_logger.py`)                       |
| `docs/architecture/README.md`                                    | `python -m scripts.validate_docs docs/architecture/`                  | Script doesn't exist                                                               |
| `docs/architecture/STANDARDS.md`                                 | Same validate_docs reference                                          | Script doesn't exist                                                               |

---

## 8. INCONSISTENCIES ACROSS DOCS

### Zone Types (3 Different Enumerations)

| Source                              | Zone Types                                            |
| ----------------------------------- | ----------------------------------------------------- |
| `docs/architecture/data-model.md`   | entry_point, driveway, sidewalk, yard, other          |
| `docs/guides/zone-configuration.md` | entry_point, exit_point, restricted, monitored, other |
| `backend/models/analytics_zone.py`  | monitored, excluded, restricted                       |

**Recommendation:** Clarify that CameraZone and AnalyticsZone (PolygonZone) are different models with different type enums. Update zone-configuration.md to match actual CameraZoneType values.

### HTTPS Port

| Source                  | Port                                                     |
| ----------------------- | -------------------------------------------------------- |
| README.md               | 8443                                                     |
| `.env.example`          | FRONTEND_HTTPS_PORT=8444                                 |
| docker-compose.prod.yml | Conflicting defaults (8443 in port mapping, 8444 in env) |

### Model Download Scripts

| Source                               | Path                           |
| ------------------------------------ | ------------------------------ |
| README.md Quick Start                | `./ai/download_models.sh`      |
| README.md Downloading Models section | `./scripts/download_models.sh` |

Both exist -- should clarify which is canonical.

### Minimum RAM Requirements

| Source                               | Minimum RAM |
| ------------------------------------ | ----------- |
| `docs/operator/README.md`            | 8 GB        |
| `docs/operator/deployment/README.md` | 16 GB       |

### YOLO26 VRAM (4 different values)

| Source                                        | YOLO26 VRAM |
| --------------------------------------------- | ----------- |
| `docs/operator/README.md`                     | ~4 GB       |
| `docs/operator/deployment/README.md`          | ~1 GB       |
| `docs/guides/video-analytics.md`              | ~650 MB     |
| `ai/AGENTS.md`                                | ~100 MB     |
| `ai/yolo26/AGENTS.md`, `docs/ai/model-zoo.md` | ~2 GB       |

### Middleware Documentation Incomplete

`docs/architecture/middleware/README.md` lists 14 middleware classes but `backend/api/middleware/` contains 25 Python files. Missing from docs: `accept_header.py`, `content_negotiation.py`, `correlation.py`, `etag.py`, `exception_handler.py`, `file_validator.py`, `profiling.py`, `prometheus.py`, `websocket_auth.py`, `setup_guard.py`.

The critical `SetupGuardMiddleware` is completely absent from middleware documentation despite blocking all API access until initial admin setup.

### Security Hub Outdated

`docs/architecture/security/README.md` still says "the system does not require authentication by default" and "No role-based access control." Both are now inaccurate given SetupGuardMiddleware and per-route `verify_api_key`/`require_admin_access` dependencies.

### Operator Ports Table Missing Enrichment Light

The operator hub's ports reference table lists Enrichment on port 8094 but omits Enrichment Light (port 8096).

### Observability References Loki (May Not Be Deployed)

`docs/architecture/observability/README.md` mentions Loki for log aggregation, but no Loki service exists in `docker-compose.prod.yml`. May be aspirational documentation.

---

## 9. WHERE DIAGRAMS/IMAGES WOULD ADD VALUE

### Currently Missing (High Impact)

| Topic                         | Suggested Diagram                                                                          |
| ----------------------------- | ------------------------------------------------------------------------------------------ |
| **Auth flow**                 | Sequence diagram: first-visit -> SetupGuard 503 -> admin registration -> normal API access |
| **MQTT integration**          | Architecture diagram showing MQTT broker, publishers, command handlers                     |
| **Webhook flow**              | Sequence diagram: event -> webhook dispatch -> retry logic                                 |
| **Household matching**        | Flow diagram: detection -> face/vehicle match -> household member identification           |
| **Model zoo VRAM management** | Visual showing LRU eviction, priority tiers, VRAM budget allocation                        |
| **Zone types comparison**     | Diagram distinguishing CameraZone vs PolygonZone (AnalyticsZone)                           |
| **Enrichment pipeline split** | Diagram showing enrichment-heavy (8094) vs enrichment-light (8096) service split           |
| **go2rtc integration**        | Architecture diagram showing camera -> go2rtc -> WebRTC -> frontend                        |

### Screenshots Still Pending

Per `docs/images/SCREENSHOT_GUIDE.md`: 11 of 42 screenshots still need capture (74% complete).

---

## 10. IMPROVEMENT RECOMMENDATIONS

### Quick Wins (< 1 hour each)

1. **Fix all YOLO26 port references** - Global find/replace 8090->8095 in docs/ and ai/ markdown files
2. **Fix CLAUDE.md** - Health endpoint `/api/health` -> `/api/system/health`, fix or remove container-rebuilds.md link
3. **Fix root AGENTS.md** - License "Mozilla" -> "Apache", coverage 93% -> 85%
4. **Archive 4 root work products** - Move to `docs/archive/`
5. **Delete misleading test docs** - `backend/tests/integration/COVERAGE.md` and `README.md`
6. **Fix .github/copilot-instructions.md** - Python 3.14, React 19, Node 22
7. **Remove image generation prompts** from architecture docs (saves ~1000 lines total)
8. **Fix Nemotron model name** in ai-orchestration docs - "70B" -> "Nemotron-3-Nano-30B-A3B"
9. **Fix setup.sh references** - Change to `python setup.py` in operator and reference docs
10. **Fix docker-compose.yml references** - Change to `docker-compose.prod.yml` or note dev compose doesn't exist
11. **Create `docs/developer/patterns/README.md`** - Currently a broken link from developer hub

### Medium Effort (1-4 hours each)

8. **Rewrite backend/AGENTS.md** - Add all 62 routes, reconcile service/model counts
9. **Unify auth model description** - Single canonical description, update ADR-005 to superseded
10. **Resolve VRAM conflicts** - Single source of truth in model-zoo.md, reference from other docs
11. **Fix zone type documentation** - Clarify CameraZone vs PolygonZone distinction
12. **Update docs/ai/model-zoo.md** - Fix container name, model path, VRAM numbers
13. **Add missing AGENTS.md** - `ai/enrichment-light/`, `ai/shared/`
14. **Update frontend/AGENTS.md** - Add Zustand stores, complete route table

### Larger Efforts (4+ hours each)

15. **Consolidate duplicated content** - Move canonical versions to single-source files
16. **Document missing features** - ONVIF, MQTT, webhooks, household, scheduled reports
17. **Create missing architecture diagrams** - Auth flow, MQTT, webhook, household matching
18. **Revive CHANGELOG.md** - Backfill major milestones or adopt conventional-commits automation
19. **Complete screenshot capture** - 11 remaining screenshots per SCREENSHOT_GUIDE.md
20. **Audit all AGENTS.md files** (80+) for file listing accuracy -- many are missing newly added files

---

## Appendix: Files Audited

### By Agent

| Agent                        | Domain                                                       | Files Read          | Issues Found            |
| ---------------------------- | ------------------------------------------------------------ | ------------------- | ----------------------- |
| root-docs-auditor            | README, CHANGELOG, CLAUDE.md, root .md files                 | 8                   | 15                      |
| architecture-docs-auditor    | docs/architecture/, docs/guides/                             | 30+                 | 25 (incl. supplemental) |
| hubs-docs-auditor            | docs/user/, docs/operator/, docs/developer/, docs/reference/ | 100+                | 18                      |
| ai-docs-auditor              | ai/ directory, docs/ai/                                      | 23                  | 33                      |
| backend-docs-auditor         | backend/ READMEs, test docs                                  | 15+ AGENTS.md files | 21                      |
| frontend-docker-docs-auditor | frontend/, docker/, deployment, images, .github/             | 25+                 | 15                      |

### Issue Severity Distribution

| Severity | Count | Description                                                                                    |
| -------- | ----- | ---------------------------------------------------------------------------------------------- |
| CRITICAL | ~20   | Wrong ports, wrong license, wrong model name, broken links, missing scripts, misleading counts |
| HIGH     | ~25   | Stale auth model, missing features, version drift, VRAM conflicts, 25 undocumented API routes  |
| MEDIUM   | ~40   | Content duplication, partial outdatedness, missing AGENTS.md, incomplete hub listings          |
| LOW      | ~35   | Minor inconsistencies, cosmetic issues, archival candidates, thin user hub                     |
