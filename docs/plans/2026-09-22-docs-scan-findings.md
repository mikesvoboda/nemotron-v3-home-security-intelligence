# Documentation full-scan — findings ledger (2026-09-22)

Two workflow rounds swept every documentation zone for outdated facts, missing
content, and unclear prose. Agents had authority to fix in-zone issues directly;
everything **outside** an agent's zone, or needing an owner ruling, is recorded
here instead of being half-edited. Round 1: 10 zone auditors + verify/fix wave.
Round 2: 4 targeted sweeps (closing ~125 zones round 1's map missed) + a judge
panel (first-timer / returning-agent / ops-oncall personas) + a nav-integrity
verifier.

Flags below are **leads with evidence**, not confirmed defects — each names its
file:line and the ground-truth source it was checked against. Items marked
"owner decision" are behavioral/code choices docs merely describe.

## Round 1 — cross-zone flag queue (79)

#### audit:decisions-mkdocs — 6 flags

- **docs/operations/README.md:415 and docs/architecture/security/biometric-privacy.md instruct 'open .env' / edit .env for biometric retention and VLM settings, but the repo uses Docker secrets (docs/operator/secrets-management.md) — direct .env edits do not reach containers.**
  - MISSING/OUTDATED doc contradiction, but both files are outside this zone (docs/operations/**, docs/architecture/**). Flagging for the docs-owning zone; compose/.env win per ground rules.
- _*25 markdown files under docs/ still document /api/v1/* endpoint paths._\*
  - OUTDATED: no router with a /api/v1 prefix exists in backend/api/routes/_.py (all are /api/_). Only this zone's decisions/grafana-integration.md falls in my edit authority and it is a historical record, so the rest must be fixed by the owning zone.
- **Entity-Detection ADR 'Mitigations' promise a periodic orphaned-primary_detection_id cleanup job, alerting metrics (orphans > 100, validation failures > 10/hr), and a monitoring query.**
  - MISSING implementation: no cleanup_orphaned_entity\* code in backend/ or scripts/, no orphan metric in backend/core/metrics.py. The ADR body is historical (plan-as-written, not false), so it was left intact; someone should either implement the cleanup job or add a clearly-marked status note in a future pass.
- **mkdocs.yml nav excludes docs/decisions/AGENTS.md.**
  - Intentional, not a bug: the repo-wide pattern never navs AGENTS.md files; they are agent-facing guides, not site pages.
- **ROADMAP 'Implemented Features' item 4 cites a 30-day baseline window and item 6 a 0-300s pre/post-roll.**
  - Verified accurate (backend/services/baseline.py:79 window_days=30; clip_generator.py:81-83 0-300s bound) and consistent with the 30-day retention ruling — kept as-is, listed so the orchestrator knows they were measured, not assumed.
- **docs/ROADMAP.md Future-Enhancement items 'NIM / Standardized Inference Deployment' and 'Digital Twin Reconstruction'.**
  - Checked and kept: llama.cpp process management is still what docker-compose.prod.yml runs (ai-llm service), Depth Anything V2 still listed in docs/ai/model-zoo.md:487. Strategic content left untouched per zone rules.

#### audit:README — 5 flags

- **Frontend port drift outside my zone: AGENTS.md:342/371, llms.txt:41/121/129, docker-compose.prod.yml:28 header comment, and setup.py:136-169/457 all still present host port 5173 as the production HTTP port and 'SSL enabled by default', but prod compose exposes 8444 (HTTPS) and 8080 (HTTP) and defaults SSL_ENABLED=false; setup.py even writes SSL_ENABLED=true into generated .env. Those files belong to other zones — owner should reconcile compose header + setup.py + llms.txt + AGENTS.md against the compose frontend block.**
  - Zone ownership: README.md only; compose/.env are ground truth per rules but their comments/setup.py are other agents' files
- **Model manifest disagreement: ai/download_models.sh fetches Florence-2-large + CLIP-ViT-L + Fashion-CLIP ('~42GB'), while models.yml (its declared single source of truth) declares florence-2-base + siglip2-base-patch16-224 and sums to ~34GB size_mb; llms.txt's model table follows the shell script. README now attributes each number to its own source (script header for ~42GB, models.yml for the model list) but the two download paths should be reconciled by whoever owns ai/ and models.yml.**
  - Cannot fix by editing docs alone — substantive config disagreement between two live sources
- **MISSING: no doc anywhere walks the first-admin registration flow end to end (first GET returns 503 except /api/auth/setup-status|register|health/docs whitelist; frontend authApi.register posts to /api/auth/register). docs/getting-started/quick-start.md and docs/user/README.md only link a 'tour'. A short 'First run: register the admin' section belongs in docs/getting-started/.**
  - Needed gap found while verifying README Security Model; file creation not permitted in this zone
- **MISSING: README (and no other human doc) lists the monitoring URLs an operator needs after install (Grafana http://localhost:3002 behind /grafana proxy at the frontend, Prometheus 9090, Alertmanager 9093 — compose comment block lines ~833-838). A one-line 'Observability' pointer in README pointing at docs/operator/monitoring/ would help first-time readers; deferred because the README already points to the Operator Hub and I avoided duplicating hub content.**
  - Structural suggestion for the docs/operator zone, not a README-only fix
- **git diff on this branch shows ~32 other files modified concurrently by parallel zone agents (backend/**/AGENTS.md, docs/architecture/**, frontend docs, mkdocs.yml). I touched only /agents/agent-veranda/workspace/README.md. Nothing was committed; no branch/checkout/reset performed per ground rules.**
  - Orchestrator should confirm concurrent agents are done before the commit/PR step

#### audit:backend — 5 flags

- **backend/api/routes/AGENTS.md - 5 measured prefix mismatches + 1 false non-inclusion claim, DISCOVERED BUT NOT YET EDITED (cutoff hit after measuring)**
  - Router-prefix cross-check vs code: notification_preferences doc '/api/notifications/preferences' vs code '/api/notification-preferences'; services doc '/api/services' vs '/api/system/services'; prompt_management doc '/api/ai-audit/prompts' vs '/api/prompts' AND its note 'currently NOT included in main.py' is false (main.py:1496 include_router); hierarchy doc '/api/v1' vs '/api/v1/households'; settings_api doc '/api/settings' vs '/api/v1/settings'. Every endpoint row in those sections carries the wrong mount path. Also note main.py mounts hierarchy.property_router and hierarchy.area_router beyond the main router.
- **~24 zone files still use bare 'pytest' in code blocks (backend/api/middleware/_, core/_, models/_, tests/benchmarks, e2e, gpu, load, security, integration/_, unit/\*)**
  - Works via pytest ini but bypasses uv-managed venv; repo commands are standardized as 'uv run pytest'. Left untouched to avoid churning dozens of blocks; mechanical sed candidate if the owner wants strict consistency.
- **MISSING: no backend/tests/AGENTS.md-level mention that the chaos suite hangs serially**
  - Measured: 'uv run pytest backend/tests/chaos/ -n0' never completed within 10min (pytest-timeout stack dump). validate.sh documents xdist-unsafety but the serial hang itself is only noted in my chaos README. If the suite is meant to be runnable, an owner issue should exist; I did not change test code (out of doc scope).
- **backend/tests/chaos README '84 tests' and 'run serially' guidance is a 2026-09-22 measurement**
  - If chaos test files are added later the count/table needs re-measure; date stamped in the file.
- **backend/AGENTS.md env sample is an excerpt of .env.example, not exhaustive**
  - FLORENCE_URL/CLIP_URL/ENRICHMENT_URL/ENRICHMENT_LIGHT_URL (also gateway-pointed in .env.example) omitted for brevity; full truth is .env.example per project rule.

#### audit:nav — 6 flags

- **README.md (another agent's file): Quick Start 'Verify' says 'open http://localhost:5173' — prod compose does not map host 5173 (FRONTEND_HTTP_PORT=8080, FRONTEND_HTTPS_PORT=8444); correct URL is https://localhost:8444**
  - Contradiction confirmed against docker-compose.prod.yml ports block; README is outside my zone so I only record it
- **README.md: AI Model Zoo claims 'Nemotron size 23 GB' and 'Download all models (~15GB total)' and '~23 GB / 24 GB' GPU usage**
  - measured: models.yml size_mb 15073 (~14.7GB) for the Q4_K_M GGUF actually downloaded; download_models.sh header says ~42GB total; README is another agent's file
- **setup.py .env generation writes FLORENCE_URL=http://ai-florence:8092, CLIP_URL=http://ai-clip:8093, ENRICHMENT_URL=http://ai-enrichment:8094 (container names that no longer exist)**
  - Code drift vs compose (all point at http://ai-gateway:8090/... now); compose env overrides it at runtime, but generated .env is misleading — needs a code fix, not a doc fix
- **docker-compose.ghcr.yml still runs jaeger (16686) + elasticsearch and maps frontend '${FRONTEND_HTTPS_PORT:-8443}:8443', and defines no ai-gateway service**
  - prod compose replaced Jaeger with Tempo (bc-era consolidation) and made the gateway the only AI path; ghcr stack is stale — infra file outside my zone
- **docs/archive/README.md does not exist**
  - docs/AGENTS.md previously pointed at it (I repointed to archive/AGENTS.md); if owners want a human-facing archive entry doc, that's a MISSING doc they'd have to create — I cannot add files
- **scripts/test-docker.sh checks frontend at http://localhost:5173**
  - stale expectation vs prod port mapping (8080/8444); script outside doc zone

#### audit:guides-ai — 4 flags

- **backend/api/routes/model_management.py lines 87-88**
  - CODE BUG outside my zone (not edited): ENRICHMENT_URL='http://ai-enrichment:8094' and ENRICHMENT_LIGHT_URL='http://ai-enrichment-light:8096' are hardcoded module constants used for the /api/system/models status fan-out (lines 362-363) and unload-all (706, 722). Those containers are not services in docker-compose.prod.yml, so runtime model status / vram-summary report those services unreachable in the gateway deployment. enrichment_client.py does it correctly via settings.get_enrichment_url_for_model; model_management.py should follow the same path. Docs now point users at these endpoints (face-recognition, video-analytics, ai/AGENTS.md), so the dead data is user-visible.
- **docs/operator/services/ai-gateway.md**
  - MISSING (cannot create files per task rules): docs/operator/services/ contains only ai-enrichment-light.md. The current production AI service (ai-gateway) has no operator service page; ai/gateway/AGENTS.md is the only narrative doc. The legacy ai-enrichment-light.md is fine but describes a non-prod container.
- **ai-gateway profiling gap**
  - OBSERVABILITY GAP: the ai-gateway container carries no pyroscope.profile label (only ai-llm does; backend uses SDK+py-spy), so the single container now hosting all inference models produces no continuous profiles. Documented as fact in profiling.md, but worth an owner decision on whether to add an eBPF or SDK target.
- **models.yml xclip-base vs gateway wiring**
  - DOC-CODE TENSION (documented in model-zoo.md Action Recognition rather than 'fixed'): models.yml marks xclip-base enabled:false 'replaced by stgcn-plus-plus', but ai/gateway/adapters/enrichment.py /action-classify still calls the xclip_action Triton model and ALL_MODELS waits for it, while stgcn_action exists in the repository dir but is in neither ALL_MODELS nor any router. Either the gateway should move to stgcn_action or the models.yml note is aspirational — needs an owner call.

#### audit:dev-docs — 8 flags

- **docs/developer/api/coverage.md per-endpoint mapping tables (all domain tables)**
  - MISSING-equivalent, needs regeneration not editing: most listed endpoints (/api/zones CRUD, /api/detections/aggregate, /api/analytics/\*, /api/metrics/slis, /api/notifications, /api/alerts GET/DELETE-instance) are absent from docs/openapi.json and many named consumers (RiskGauge.tsx, SLIMonitor.tsx, DLQMonitor.tsx, etc.) are not frontend files. A truthful rewrite means re-running ./scripts/check-api-coverage.sh + scanning frontend/src; I added a prominent stale-status banner instead of inventing 100+ rows.
- **docker-compose.deploy.yml / deploy pipeline**
  - OUT-OF-ZONE drift: deploy.yml still builds per-model images (ai-yolo26, ai-llm, ai-florence, ai-clip, ai-enrichment) although production compose runs the single consolidated ai-gateway; docs in my zone now describe the gateway reality — infra side may need reconciliation.
- **.env.example vestigial variables**
  - OUT-OF-ZONE: per-model ports (FLORENCE*PORT 8092, CLIP_PORT 8093, ENRICHMENT_PORT 8094, ENRICHMENT_LIGHT_PORT 8096, YOLO26_PORT 8095), GPU_FLORENCE/GPU_YOLO26/GPU_CLIP/GPU_ENRICHMENT\*/GPU_LLM-legacy and JAEGER*\* vars survive but are not consumed by docker-compose.prod.yml (tracing is Tempo via alloy; GPU vars in compose are GPU_LLM + GPU_AI_SERVICES). Docs now say 'vestigial' rather than documenting them as live.
- **backend/services/gpu_config.py service-name registry**
  - OUT-OF-ZONE: GPU Config API/UI still tracks legacy per-model service names (ai-llm/ai-yolo26/ai-florence/ai-clip/ai-enrichment) with AI_SERVICE_VRAM_REQUIREMENTS_MB, inconsistent with the consolidated ai-gateway deployment; noted in multi-gpu.md rather than papered over.
- **scripts/test-runner.sh COVERAGE_THRESHOLD=93**
  - OUT-OF-ZONE: hard-coded 93 matches no documented gate (80 absolute / 84,37 tiers / 85 relative / 80-90 codecov) — likely stale; script owner should reconcile.
- **docs/development vs docs/developer duplication**
  - Structural: testing.md vs testing-workflow.md, contributing.md vs developer/contributing/README.md, setup.md vs developer local-setup guidance, hooks.md vs contributing hook tables — near-duplicate content maintained in parallel (this scan had to fix the same claims in 3-4 places). Recommend consolidation to single sources with cross-links.
- **frontend floors in scripts or docs drift risk**
  - MISSING doc note candidate: R-1 measured floors (80/74.6/78.4/80.9) live in vite.config.ts and frontend/scripts/merge-shard-coverage.mjs FLOORS; docs mirror them and will silently drift on the next measurement — a generated doc or link would prevent recurrence.
- **pre-existing prettier failures fixed in files I touched**
  - 5 files failed `prettier --check` at HEAD (ai-pipeline.md, prompt-management.md, PORT_STANDARDIZATION.md, hooks.md, multi-gpu.md); I ran the hook-pinned prettier@3.2.4 --write so the whole zone now passes prettier@3.2.4 --check.

#### audit:getting-started — 10 flags

- **monitoring/prometheus.yml blackbox probe targets still point at retired hosts (http://ai-florence:8092, ai-clip:8093, ai-enrichment:8094, ai-yolo26:8095 /health, lines ~366-371)**
  - Measured infrastructure drift — those probes fail permanently since commit bc7d6101; fix is a monitoring/ config change (out of my docs zone and out of authority: content edits only). Should retarget to ai-gateway:8090/health + existing ai-llm probe.
- **monitoring/profiling-recording-rules.yml + profiling-regression-alerts.yml: ALERT-REG-005 chain (job:yolo26_inference_latency:p95_5m etc.) keys on yolo26_inference_latency_seconds_bucket exported only by the retired standalone server; same for florence/clip rules**
  - Dead alert rules with no data source in the current topology. Needs retarget to nv_inference_request_duration_seconds{model=...} from triton-metrics — monitoring code change, out of docs zone.
- **setup.py compose-override generator emits port blocks for retired services (YOLO26_PORT 8095 etc.)**
  - Code fix out of zone; docs now avoid propagating those ports as live, but generated override.yml still references dead services.
- **FRONTEND_PORT=5173 is a dead variable (compose header + .env.example only; nothing consumes it — frontend serves 8080/8444)**
  - Claimed live in docs/reference/\* and root README.md (both other agents' zones). Root README matters: the user explicitly asked for special attention there.
- _\*JAEGER\_\_ vars in .env.example + compose*parser 'jaeger' category prefix + OrchestratorSettings.jaeger_port (JAEGER_UI_PORT 16686)*_
  - No Jaeger container exists (Tempo replaced it). Legacy cleanup is code-side; I documented absence in container-orchestration.md rather than pretending vars work.
- **Grafana alerting contact-points/dashboard URLs lack the /grafana/ sub-path (monitoring/grafana provisioning + alert dashboard_urls)**
  - Grafana serves from /grafana/ (GF_SERVER_SERVE_FROM_SUB_PATH=true), so absolute /d/... and /api/... URLs from alerts 404. Monitoring zone fix.
- **Grafana Pyroscope datasource not provisioned (provisioning/datasources/ has only prometheus.yml) while hsi-profiling.json dashboards reference uid 'pyroscope'**
  - Dashboards silently depend on a manually-created datasource; MAINT-PROF-003 now documents the fix, but the provisioning file itself should be added (monitoring zone).
- **YOLO26_MODEL_PATH appears to have no consumer in the gateway path (no hits in backend config, gateway, or detector_client)**
  - Likely legacy var for the standalone dev server only; docs describe it as dev-server-scoped. Needs owner decision whether to remove from .env.example.
- **DETECTION_CONFIDENCE_THRESHOLD divergence: code default 0.40 (config.py) vs .env.example ships 0.5**
  - Deliberately noted inline in yolo26-migration.md rather than picking a winner; owner may want the two aligned.
- \_\*ai-llm/ai-gateway declare PYROSCOPE\_\_ env + pyroscope.profile label but neither image runs a profiler (llama.cpp native; gateway Triton)\_\_
  - Placeholder wiring that misleads operators into expecting profiles for those services. Flagged in profiling-runbook.md topology note; code cleanup is out of zone.

#### audit:components-misc — 6 flags

- **docs/../README.md (project root)**
  - MISSING attention, out of my zone: the user's explicit priority ('pay special attention to the project README.md'). My spot-checks found its VRAM tiers (README.md:183-185) and AI-service references accurate against compose/models.yml, but it needs a dedicated full audit by another wave.
- **docs/reference/models.md**
  - OUTDATED, out of my zone: still cites CLIP ViT-L/14 on port 8093 (retired ai-clip container). Now conflicts with the corrected docs/\_includes/vram-requirements.md (ai-gateway:8090 consolidation, SigLIP-2-base). Needs the architecture-zone agent.
- **docs/ai/model-zoo.md**
  - OUTDATED, out of my zone: references retired endpoints 'ai-yolo26:8095' and 'ai-florence:8092'; compose now runs a single ai-gateway (AI_GATEWAY_PORT 8090) with /yolo26 /florence /clip /enrichment /enrich-lt routers plus ai-llm:8091.
- **docs/user/components/** or any second copy of component docs\*\*
  - Checked: no duplicate component doc trees exist; component docs are only under docs/components/ — no further citation-drift surface for the props fixed here.
- **No standalone toasts doc page**
  - MISSING candidate (recorded, not created per ground rules): ToastProvider/useToast are documented inline in docs/components/common/notifications.md; if the docs team wants a hooks reference page, docs/reference/hooks.md would be the natural home for useToast/useConnectionStatus/useInfiniteScroll.
- **git operations**
  - Performed none (no commit/checkout/add/push) per ground rules — branch/push/PR belong to the orchestrator. Zone files are prettier-formatted with the repo's own frontend/node_modules/.bin/prettier so pre-commit should pass.

#### audit:frontend-ai-scripts — 5 flags

- **/agents/agent-veranda/workspace/.env.example lines 515-519: GPU_FLORENCE, GPU_YOLO26, GPU_CLIP, GPU_ENRICHMENT, GPU_ENRICHMENT_LIGHT**
  - Declared (with a comment claiming 'the compose file will fail without them') but consumed by no compose file - production uses only GPU_LLM and GPU_AI_SERVICES. .env.example is outside my zone; owner should prune or wire them.
- **/agents/agent-veranda/workspace/backend/services/gpu_config_service.py**
  - Docstring/generation logic for docker-compose.gpu-override.yml still targets the retired ai-yolo26/ai-enrichment services and has no ai-gateway awareness. Backend is outside my zone; docs updated to describe measured reality instead.
- **/agents/agent-veranda/workspace/ai/triton/client.py (TritonClient)**
  - No production consumer (asserted by backend/tests/contracts/ai_providers/test_conformance_vocabulary.py). Kept as dev/direct-gRPC tooling and documented as such in ai/triton/AGENTS.md; consider a disposition ruling.
- **ai/\*/Dockerfile standalone AI images (clip, florence, enrichment, enrichment-light, yolo26)**
  - Dockerfiles exist but no compose service builds them; they are dev-only one-off builds. Documented in each AGENTS.md; whether to archive them (per the archive/ owner ruling) is a call for the owner - I only edit docs.
- **docs/plans/triton-migration.md still frames Triton as 'Phase 1: infrastructure setup'**
  - Stale relative to Triton being the production path, but docs/\*\* is outside my zone and plans are treated as historical records; left untouched.

#### audit:api-arch — 9 flags

- **docs/images/architecture/dataflows/flow-event-lifecycle.png and concept-event-states.png**
  - Images depict the removed acknowledge/resolve/archive lifecycle; images cannot be edited here — staleness flagged with HTML comments at both embed sites in event-lifecycle.md
- **backend/services/enrichment_pipeline.py**
  - Module docstring still names ai-enrichment:8094 (pre-consolidation service). Code change, outside the docs zone
- **docs/images/architecture/overview-deployment-topology.svg**
  - Predates AI-gateway consolidation (shows five separate AI containers); alt-text staleness note added, image itself not editable
- **docs/images/arch-system-overview.png**
  - Pre-consolidation topology; not editable
- **docs/images/architecture/monitoring-stack.png**
  - Shows Jaeger + five AI services; stale; not editable (also noted inline in observability/README.md)
- **backend/core/config.py florence/clip/enrichment URL fields**
  - Field defaults still point at localhost:8092-8096 although those containers no longer exist; code fix candidate, out of docs zone
- **scripts/init-elasticsearch.sh**
  - Legacy leftover — no Elasticsearch anywhere in compose or backend; quarantine/archive candidate
- **backend/api/middleware/request_timing.py + request_logging.py standalone classes**
  - No longer registered by the app (NEM-5558 unified them into ObservabilityMiddleware) though still exported/tested; docs now carry a note; dead-code cleanup is a code-zone decision
- **docs/architecture/decisions.md ADR-004 diagram + overview.md commented-out mermaid**
  - Intentionally preserved pre-consolidation topology as historical record per the historical-immutability rule; both are annotated as as-recorded

#### fix:chunk-2 — 7 flags

- **docs/development/ci-cd.md changed mid-session (parallel wave)**
  - The file's 'Coverage Requirements' section was rewritten between my first and second read — the diff-gate framing the auditor asked for was already in place, apparently from a concurrent agent on the same branch. My own contribution is the corrected label column (85/85/85/80 + Hooks row) matching scripts/check-test-coverage-gate.py. Whoever orchestrates the commit should re-diff this file at commit time.
- **Auditor item 4 targets a nonexistent doc mismatch**
  - Item 4's problem text (llms.txt 'default 35') and correction text (ci-cd.md retitling) are for different files, and the llms.txt half is already fixed in the tree while the ci-cd.md half was fixed concurrently. No action remained beyond the label-value correction above.
- **Auditor item 3's stated 'blocker' does not exist**
  - llms.txt nowhere says 'Florence-2-Large ~1.5 GB' or 'CLIP ViT-L ~800 MB'. The actual ~3GB/~1.7GB rows are correct for the download script (verified against ai/download_models.sh:443-462), so applying the literal correction would have introduced a new error in a table explicitly headed 'The download script fetches…'. Applied the substance (Florence-2-base/SigLIP 2 gateway reality) as annotations instead.
- **Auditor item 5 cites wrong file**
  - Root AGENTS.md has no start_detector.sh line at :96 or anywhere; the claim is real but lives in ai/AGENTS.md (:96, :169, :410). All three fixed.
- **README:212-217 hardware table keeps 32GB RAM / 8-core min**
  - Auditor's item-8 correction text names only prerequisites.md (option A: revert prerequisites), and README's 32GB/64GB figures predate this branch (git show main:README.md). Left consistent with its own measured-usage table; the two-tier framing in prerequisites' sizing note (floor vs comfortable 32GB+) is the honest reconciliation. Owner may still want one table to rule.
- **scripts/dev.sh:106,175 print wrong dev URL (5173 vs real 8444)**
  - Code bug, explicitly out of scope for this docs pass ('that is a code fix worth its own fix'). Documented the discrepancy in README so users aren't misled; a follow-up code PR should fix the echoes.
- **docs/operator/README.md:45 still says GPU min 8GB VRAM**
  - Sibling docs' minimum-VRAM rows (operator/README, reference/getting-started, operator/deployment 'GPU VRAM 8GB min') predate this branch and are ambiguous about whether they mean detection-only or full-stack; not in this branch's diff and not on the auditor list, so left untouched to avoid unreviewed scope creep.

#### fix:chunk-1 — 8 flags

- **Item 6 (testing.md hooks.md#parallel-tests anchor)**
  - Auditor claim false — hooks.md:1216 has the '### parallel-tests' heading; the link resolves. No change made.
- **Items 7, 9, 10, 11 had correction text swapped between problems (probably a pipeline mis-zip)**
  - Item 7's correction described profiling.md (item 15's file); item 9's correction described llms.txt while its problem described contributing.md; item 10's correction described README's table while its file is model-zoo.md; item 11's correction described PORT_STANDARDIZATION links while its problem described a mermaid. I applied each item's ACTUAL file problem (corrections that matched the named file's content) rather than the mismatched correction text.
- **llms.txt:213 (referenced by item 9's correction)**
  - Already in the target state on disk: 'GPU_LAYERS=30' with comment '# In .env: reduce LLM GPU layers (default: auto = fit to VRAM)' — the 'from default 35' framing was already removed by this diff. No change needed. (Separate pre-existing 'Lower from 35' comment lives in docs/reference/troubleshooting/README.md:594, untouched — not in the audit list.)
- **Concurrent editing during this task**
  - Another wave edited README.md, llms.txt, ai/AGENTS.md:96/:169, docs/\_includes/vram-requirements.md and the ci-cd.md gate table (min_coverage 85/85/85/80 — which matches scripts/check-test-coverage-gate.py REQUIREMENTS better than my initial values) mid-flight. All preserved and built on; no checkout/reset was run (a stray pathspec-less 'git checkout --' restored nothing).
- **docs/\_includes/vram-requirements.md Florence row**
  - Says Florence-2-base ~1.5GB — that figure is the old Large value; the resident base model is ~460MB FP16 in VRAM (models.yml size_mb 1024 is the download size). Not in my task list; recommend a follow-up wave reconcile it with multi-gpu.md/model-zoo.md.
- **docs/development/multi-gpu.md YOLO26 row '~5 MB'**
  - Carried over unchanged from the old table, but model-zoo.md:188 and README both say YOLO26 ~2GB with the TensorRT engine (~650MB per model_zoo.py). Pre-existing, outside the audited rows; needs a follow-up ruling on which measure to publish.
- **monitoring/grafana/dashboards/hsi-request-profiling.json**
  - Dashboard link is titled 'Jaeger Traces' and its URL preselects datasource 'Jaeger' (:43-46), which the datasource provisioning no longer defines — the link is broken in the real product, not just stale prose. Fix is in monitoring JSON, outside this docs-only task's scope.
- **README.md:237 'Containers | 21 (19 run by default; ai-llm-vllm and dcgm-exporter need a profile)'**
  - docker-compose.prod.yml has exactly 19 services, two profiled (vllm, gpu-rootful), and no service named dcgm-exporter — the arithmetic (21/19) does not match the compose file. Pre-existing row, not in the audit list; worth a follow-up check of what the dcgm-exporter reference means.

## Round 2 — sweep flag queue (72)

#### sweep:reference-user — keys:['edits', 'flags', 'summary'] flags:35

- **env-reference.md L20-26 anchor block — NOT VERIFIED, needs re-check before edit**
  - Not in config.py field extractor. Also L24 says 'Container environment (docker-compose.yml)' but this repo uses docker-compose.prod.yml + podman, and priority order 'Environment > .env > Defaults' was not confirmed against pydantic SettingsConfigDict.
- **env-reference.md L102 YOLO26_URL default `http://localhost:8095`**
  - CONFIRMED OUTDATED. config.py: yolo26_url = "http://ai-gateway:8090/yolo26"; .env.example:206 YOLO26_URL=http://localhost:8090/yolo26. Port 8095 appears in NO compose port mapping (compose has only ${AI_GATEWAY_PORT:-8090}). YOLO26 is a router on ai-gateway:8090, not a standalone :8095 service.
- **env-reference.md L104-106 FLORENCE_URL/CLIP_URL/ENRICHMENT_URL defaults 8092/8093/8094**
  - LEFT DELIBERATELY — these DO match config.py (florence_url=8092, clip_url=8093, enrichment_url=8094). Changing them would be churn. But note .env.example:217-232 ships gateway paths for all three, so add a one-line note that the deployed values route via ai-gateway:8090 rather than rewriting the Default column.
- **env-reference.md L106 — ENRICHMENT_LIGHT_URL row MISSING**
  - Table has 5 AI URL rows; config.py has a 6th: enrichment_light_url = "http://localhost:8096". Add row + gateway path http://localhost:8090/enrich-lt (ai/gateway/main.py:185 prefix="/enrich-lt").
- **env-reference.md L117 '### Service Timeouts' — EMPTY SECTION (structural)**
  - Heading has no table. The AI timeout table (L181-189) is orphaned under '### Florence Circuit Breakers' (L172). Fix by moving the table under L117. No fact change.
- **env-reference.md L188 CLIP_READ_TIMEOUT default 15.0**
  - CONFIRMED WRONG. config.py: clip_read_timeout = 5.0.
- **env-reference.md L209 NEMOTRON_CONTEXT_WINDOW default 3900**
  - CONFIRMED WRONG. config.py: nemotron_context_window = 32768. Also compose sets CTX_SIZE=${CTX_SIZE:-262144}. Range column '1000-128000' now contradicts 32768..262144 and must be re-derived.
- **env-reference.md L247 DETECTION_CONFIDENCE_THRESHOLD default 0.5**
  - CONFIRMED WRONG. config.py: detection_confidence_threshold = 0.40. (0.5 belongs to a different var, yolo26_confidence = 0.5 — likely the source of the drift.)
- **env-reference.md L257 FAST_PATH_CONFIDENCE_THRESHOLD default 0.90**
  - CONFIRMED WRONG. config.py: fast_path_confidence_threshold = 2.0, i.e. the fast path is effectively DISABLED by default. The prose at L253 ('High-confidence detections can bypass batching for immediate alerts') reads as if it is on — needs a status sentence, this is a behaviour claim not just a number.
- **env-reference.md L365 RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE default 10**
  - CONFIRMED WRONG. config.py: rate_limit_websocket_connections_per_minute = 100.
- **env-reference.md L489/L491 VIDEO_FRAME_INTERVAL_SECONDS 2.0, VIDEO_MAX_FRAMES 30**
  - CONFIRMED WRONG, both. config.py: video_frame_interval_seconds = 4.0, video_max_frames = 20.
- **env-reference.md L520 ADMIN_ENABLED default `false`**
  - CONFIRMED WRONG. config.py: admin_enabled = True. The note at L523 ('require BOTH DEBUG=true AND ADMIN_ENABLED=true') was NOT verified — verify before rewriting, since the table's own Default now contradicts it.
- **env-reference.md L583-584 DEFAULT_PAGE_SIZE 50 / MAX_PAGE_SIZE 100**
  - SUSPECT NAME+VALUE MISMATCH. config.py has pagination_default_limit = 50 and pagination_max_limit = 1000. Neither DEFAULT_PAGE_SIZE nor MAX_PAGE_SIZE appears in the field list. Grep for an env alias before editing; if none, the rows name variables that do not exist.
- **env-reference.md L592 TRANSCODE_CACHE_DIR default `data/cache`**
  - CONFIRMED WRONG. TranscodeCacheSettings uses env*prefix TRANSCODE_CACHE* with cache_dir default "data/transcode_cache".
- **env-reference.md L593 TRANSCODE_CACHE_MAX_SIZE 1073741824**
  - NOT VERIFIED — extractor surfaced max_cache_size_gb = 10.0 nearby, which suggests the knob may be GB-denominated, not bytes. Resolve the exact field before writing.
- **env-reference.md L612-613 HARDWARE_ACCEL_ENABLED / HARDWARE_ACCEL_DEVICE**
  - SUSPECT WRONG NAMES. config.py field is hardware_acceleration_enabled -> env HARDWARE_ACCELERATION_ENABLED. No HARDWARE_ACCEL_DEVICE field found. Grep for validation_alias before keeping.
- **env-reference.md L622-623 PROFILING_SAMPLE_RATE 0.1, SLOW_REQUEST_THRESHOLD_MS 1000**
  - SLOW_REQUEST_THRESHOLD_MS CONFIRMED WRONG: config.py slow_request_threshold_ms = 500. PROFILING_SAMPLE_RATE not in the field list at all — suspect nonexistent (profiling_enabled and profiling_output_dir exist).
- **env-reference.md L641-642 REQUEST_LOGGING_BODY / REQUEST_LOGGING_HEADERS**
  - SUSPECT FABRICATED. Neither appears in config.py; only request_logging_enabled does. Must grep for a separate logging settings class before deleting.
- **env-reference.md L651 REQUEST_RECORDING_DIR**
  - SUSPECT FABRICATED. config.py has request_recording_enabled, request_recording_max_body_size, request_recording_sample_rate — no request_recording_dir.
- **env-reference.md L659-661 HSTS_ENABLED / HSTS_MAX_AGE / HSTS_INCLUDE_SUBDOMAINS**
  - NOT VERIFIED. Only hsts_preload = False is in the field list, so 3 of the 4 rows in this section are unconfirmed. Whole section needs a grep.
- **env-reference.md L679-680 BACKGROUND_EVAL_ENABLED / BACKGROUND_EVAL_INTERVAL**
  - SUSPECT WRONG NAMES. config.py has background_evaluation_enabled = True and background_evaluation_poll_interval = 5.0 — note the documented interval (3600) is off by ~700x if these are the same knob.
- **env-reference.md L704 MODEL_ZOO_PATH default /models/model-zoo**
  - NOT VERIFIED — absent from the field list. Grep backend/services/model_zoo.py, which models.yml names as a consumer.
- **env-reference.md L716 '~1,650 MB VRAM budget'**
  - NOT VERIFIED concrete number. Grep model_zoo.py / models.yml vram_mb sum. Zone rule: every row grepable or flagged.
- **env-reference.md L728 FRONTEND_PORT 5173 'Host port for frontend container'**
  - CONFIRMED DEAD + MISLEADING. docker-compose.prod.yml frontend maps FRONTEND_HTTP_PORT 8080->8080 and FRONTEND_HTTPS_PORT 8444->8443 with FRONTEND_INTERNAL_PORT 8080; it never references FRONTEND_PORT. 5173 survives only as frontend/Dockerfile dev-target EXPOSE and a setup.py/port_scanner table entry. Replace the row with FRONTEND_HTTP_PORT=8080 / FRONTEND_HTTPS_PORT=8444 / FRONTEND_INTERNAL_PORT=8080.
- **env-reference.md L144-145 REID_MAX_CONCURRENT 4, REID_TIMEOUT_SECONDS 5.0**
  - CONFIRMED WRONG name+value both. config.py: reid_max_concurrent_requests = 10 (env REID_MAX_CONCURRENT_REQUESTS) and reid_embedding_timeout = 30.0.
- **env-reference.md L152 IMAGE_QUALITY_MIN_THRESHOLD 0.3**
  - SUSPECT FABRICATED. Only image_quality_enabled = True found in config.py.
- _\_env-reference.md L158-161, L167-170, L176-179 circuit-breaker FAILURE_THRESHOLD=5 and all _\_SUCCESS\*THRESHOLD rows\*\*
  - CONFIRMED WRONG. config.py has *\_cb*failure*threshold = 10 for enrichment/clip/florence (not 5), and NO success-threshold field — only failure/half_open/recovery exist, which match at 3 and 60.0. Also the documented names are \*\_CIRCUIT*\_, not \_\*CB\*\_: confirm the env alias before renaming.
- **env-reference.md L134-136 FLORENCE_OCR_ENABLED / FLORENCE_DENSE_CAPTION_ENABLED / FLORENCE_DETAILED_CAPTION**
  - SUSPECT STALE NAMES. config.py's florence toggles are florence_detection_captions_enabled, florence_scene_captions_enabled, florence_vqa_enabled — none of the three documented names appear.
- **env-reference.md L203 AI_MAX_CONCURRENT_INFERENCES flat default 4**
  - INCOMPLETE. config.py resolves it via \_get_default_inference_limit(): 20 on free-threaded Python (3.13t/3.14t, GIL disabled), 4 with GIL. Worth a clause since python-freethreaded.yml is a real workflow.
- **env-reference.md L12 image ../../images/architecture/env-variable-cascade.png**
  - LINK TARGET NOT VERIFIED. Same for L741-747 ../../operator/ai-configuration.md, ../../developer/batching-logic.md, ../../developer/local-setup.md, ../../operator/README.md, ../../developer/README.md. Some of these may have been quarantined by commits fe0141b8/fdb7d4a5 — ls each path before keeping.
- _\*env-reference.md L35-38 DATABASE_POOL\_\_ ranges, L62 REDIS*POOL_SIZE range 10-500, L361-366 rate-limit ranges column*_
  - Defaults verified (20/30/30/1800, 50, all matching); the Range column was NOT verified — those bounds live in validators/ge/le, not in the default. Not a correctness defect I can confirm either way.
- **19 UNREAD ZONE FILES — audit incomplete, do NOT mark this zone done**
  - Only env-reference.md was read in full. Still unexamined: docs/reference/models.md (1016 L), nvidia-technology-inventory.md (818), troubleshooting/index.md (721), troubleshooting/README.md (687), ai-issues.md (550), connection-issues.md (403), glossary.md (402), database-issues.md (385), user/notification-setup.md (373), performance/LOAD_PROFILES.md (315), reference/README.md (338), accessibility.md (303), benchmarks/yolo26-performance.md (283, HISTORICAL: status-note + link fixes only), getting-started.md (224), config/risk-levels.md (215), troubleshooting/AGENTS.md (262), triton-rootless-cuda.md (183), keyboard-shortcuts.md (182), reference/AGENTS.md (186), config/AGENTS.md (153), user/README.md (128), user/AGENTS.md (110), performance/AGENTS.md (49), stability.md (33), templates/AGENTS.md (26).
- **MISSING (do not create, flag only): docs/reference/config/ service-name reference**
  - Compose service is `ai-llm` (docker-compose.prod.yml:120) but no doc in the zone names it; docs say 'Nemotron llama.cpp :8091'. A short table mapping compose service -> host port would kill the recurring drift. Belongs in docs/reference/config/.
- **Ground truth for the '21 services' count — CONFIRMED, safe to keep**
  - awk over the services: block yields exactly 21 keys; 2 are profiled (ai-llm-vllm -> vllm at L220-221, dcgm-exporter -> gpu-rootful at L1246-1247), so 19 default + 2 profiled. triton-kernel-cache/triton-tmp-cache/llama-cache/llama-nv-cache are VOLUMES and security-net is a NETWORK — reject any doc that counts them as services.
- **Anchor corrections for other agents**
  - models.yml lives at REPO ROOT (/models.yml, 581 L), NOT ai/models.yml — any zone doc citing ai/models.yml is wrong; ai/download_models.sh is the stale twin. Its header names 4 consumers: setup_lib/model_downloader.py, backend/services/model_zoo.py, ai/gateway/entrypoint.sh, ai/gateway/patch_triton_configs.py. Also .env.example:871-873 still ships JAEGER_UI_PORT/JAEGER_OTLP_GRPC_PORT/JAEGER_OTLP_HTTP_PORT although Jaeger is retired and compose has only `tempo:` (:3200, OTLP gRPC :4317) — that is a .env.example fix, outside my zone.

#### sweep:vss-style — keys:['edits', 'flags', 'summary'] flags:5

- **scripts/benchmark_yolo26_accuracy.py (outside zone)**
  - The RT-DETR->YOLO26 mechanical rename mangled this script too: its docstring says 'Benchmark YOLO26 vs YOLO26', and lines 154-155 define DEFAULT_YOLO26_PATH twice (the second silently overwrites the RT-DETR baseline path). The accuracy-comparison generator is therefore currently broken-by-rename; needs an owner/code fix, not a docs fix.
- **docs/benchmarks/yolo26-vs-yolo26.md (MISSING, do not create)**
  - The accuracy-comparison benchmark output file referenced by AGENTS.md and written by benchmark_yolo26_accuracy.py does not exist in any tree state (its predecessor yolo26-vs-rtdetr.md was deleted in #4442). Flagged rather than created per MISSING rule; AGENTS.md now states this explicitly and preserves the run's data as a labeled historical record.
- **docs/benchmarks/model-zoo-benchmark.md registry table**
  - Its 'Source: backend/services/model_zoo.py' model registry lists names that no longer match the live manifest (clip-vit-l, osnet-x0-25, depth-anything-v2-small; xclip-base shown Enabled where models.yml marks it DEPRECATED/disabled). Historical substance held immutable per the benchmarks rule; the README status note now tells readers models.yml is the current truth and to re-run before citing.
- **docs/benchmarks/yolo26-export-formats.md:269 absolute link /export/ai_models/.../VALIDATION_REPORT.md**
  - Machine-local absolute path outside the repo, unresolvable. Left per historical-record rule (run metadata); flagged for awareness.
- **vss-integration [V] citations into the external VSS repo (path:line, e.g. sizing.md, real-time-vlm.mdx, dev-profile.sh:1161-1165)**
  - Cannot be verified from this sandbox - the VSS clone path is machine-local and the repo is not in the working tree. The directory's own convention states these need re-verification against the upstream repo; none were altered.

#### sweep:research-plans-status — keys:['edits', 'flags', 'summary'] flags:8

- **docs/plans/2026-01-19-model-zoo-prompt-improvements-design.md (6 dead paths: backend/services/model_manager.py, model_loaders.py, enhanced_enrichment_pipeline.py, ai/enrichment/model_loaders.py, scripts/download_ondemand_models.sh)**
  - Paths do not exist AND are not in the pass-1/pass-2 rename map — they predate the archive moves (never created or removed in earlier work). No groundable replacement; out of the (a) dead-path-from-moves rule. Left as historical design prose.
- _*docs/plans/2026-01-18-dashboard-summaries-design.md, 2026-01-20-orphaned-infrastructure-integration-design.md, 2026-02-04-scene-ocr-design.md (backend/data/service_providers.json), 2026-01-18-docs-drift-detection-design.md (docs/developer/api/system-advanced.md), interfaces/* (_.test.ts paths, enrichment_service.py)\*\*
  - Dead paths that were planned-but-never-created files or removed in non-archive commits — not created by the archive moves, so per zone rules left untouched; noted here for the orchestrator.
- **docs/plans/2026-09-12-context-map-doc-updates.md refs to .github/workflows/gpu-tests.yml and .github/workflows/flake-allowlist.yml**
  - Not archive moves: gpu-tests.yml was deleted in 978bb04c and flake-allowlist.yml was intentionally relocated to .github/flake-allowlist.yml by a decision recorded INSIDE the plan itself. The prose is a historical record; editing it would falsify the ledger.
- **docs/plans/2026-09-12-context-map-doc-updates.md refs to docs/superpowers/plans/... and docs/superpowers/staged/...**
  - docs/superpowers/\*\* still exists and nothing was moved there; forbidden-edit zone and not a move casualty.
- **docs/plans/2026-01-18-contextual-docs-link-implementation.md link table (dashboard.md, timeline.md, ... settings.md) and docs/plans/2026-01-24-architecture-documentation-design.md directory links (system-overview/, api-reference/, ...)**
  - Illustrative 'planned future docs' tables and a design-time directory sketch — not archive-move casualties; feature shipped as PageDocsLink.tsx (status note added). Rewriting them would churn historical design content.
- _*Plans left WITHOUT status notes (tree not unambiguous): docs/plans/2026-02-02-setup-ux-redesign.md, 2026-01-21-nemo-data-designer-integration-design.md, 2025-01-23-multi-gpu-support-design.md, 2025-01-30-rtsp-camera-configuration-ui-design.md, 2025-01-31-face-recognition-ui-design.md, 2025-01-31-model-zoo-management-design.md, triton-migration.md, 2026-01-21-documentation-audit-plan.md, 2026-01-25-synthetic-data-generation-design.md, 2026-01-21-zone-intelligence-design.md, 2026-01-29-ai-pipeline-accuracy-improvements-design.md, 2026-02-01-platform-enhancement-strategy-design.md, executive-summary-slides.md, redeploy/other image-validation-* and image-revalidation-_ (14 files)\*\*
  - Partial or conflicting implementation signals (e.g. ai/triton exists but compose has no Triton server service; FaceRecognitionPage exists but plan predates it by a year and was never re-dated; image-\* files are already-dated generated validation reports). Per the 'obvious one-line only when the tree makes it unambiguous' rule, no note added.
- **docs/plans/README.md and docs/plans/AGENTS.md**
  - Index files list only 6 plans of 77; all links in them verify alive, and pre-existing prettier table drift is not in this zone's (a)/(b) rules. Flagging as MISSING content for the orchestrator: an index entry for the ~70 plans added 2026-01-20 onward would belong in README.md.
- **Prettier --check warnings on 4 touched files (2026-01-17-grafana-ai-audit-panels-design.md, 2026-09-12-context-map-doc-updates.md, ai-gateway-centralized-config-unit-tests.md, docs/research/06-model-type-comparison.md)**
  - Verified the same warnings exist at HEAD (checked pristine copies via git show) — pre-existing formatting drift, not introduced by these edits; running prettier --write would reformat historical prose and violate the minimal-churn rule.

#### sweep:operator-ui — keys:['edits', 'flags', 'summary'] flags:24

- **scripts/restart-all.sh AI_SERVICES list**
  - Names retired per-model AI containers that no longer exist in docker-compose.prod.yml after gateway consolidation; restarts would fail for those names.
- **backend service_managers.py ALLOWED_RESTART_SCRIPTS**
  - References restart scripts that do not exist in scripts/ — the allow-list admits nonexistent files.
- **CADVISOR_PORT 8083 vs cadvisor scrape target :8088**
  - Prometheus scrape config and .env variable disagree on the cadvisor port.
- **ai/download_models.sh '~42GB' claim**
  - models.yml enabled-model VRAM/size math measures ~33.3GB; the script's stated download size appears stale.
- **monitoring/prometheus.yml blackbox-http-2xx targets**
  - Still probes legacy per-model AI endpoints retired by the gateway consolidation — permanently failing synthetic probes.
- **.env.example CTX_SIZE=262144 vs backend validation le=131072**
  - Backend field caps context at 131072; the shipped .env.example default would be rejected/clamped.
- **.github/workflows/deploy.yml image builds**
  - Still builds ai-yolo26/ai-florence/ai-clip/ai-enrichment images for services that no longer ship.
- **docker-compose.ghcr.yml**
  - Predates the ai-gateway consolidation; service set diverges from docker-compose.prod.yml.
- **docs/ui/getting-started.md pointer**
  - Intentional moved-page stub (kept as-is); ui/README.md previously did not link it or understanding-alerts.md — README now links understanding-alerts and accessibility; the getting-started pointer stays unlinked on purpose.
- **Alembic-era images/screenshots**
  - Historical images reference a migration tool the project no longer uses (no Alembic); substantive historical content left immutable.
- **FAST_PATH_ENABLED env var**
  - Documented in some places but has no backend reader; FAST_PATH_ENABLED=false claim in docs matches compose env but nothing consumes it.
- **compose FAST_PATH_CONFIDENCE_THRESHOLD=0.90**
  - Overrides the code default 2.0 which is a deliberate 'disabled' sentinel — needs owner ruling on intended fast-path state.
- **ai/start_detector.sh YOLO26_PORT default 8090**
  - .env.example defines YOLO26_PORT=8095; script fallback silently uses 8090 (the gateway port).
- **ai-tls doc-vs-code gaps**
  - Doc fixed to match code, but underlying TLS provisioning gaps (documented in ai-tls.md) remain implementation decisions.
- **prometheus.yml rule_files: 7 listed, 5 mounted**
  - profiling-recording-rules.yml, profiling-regression-alerts.yml and ai-pipeline-alerts.yml are referenced but never mounted into the container, so they never load.
- **backend container_discovery.py fallback names**
  - Hardcoded fallback container list uses dead AI container names; discovery silently targets nonexistent services.
- \_\*.env.example ALERTMANAGER_SMTP\_\_ vars\_\_
  - No consumer in alertmanager config (webhook-only; no envsubst); Grafana GF*SMTP*\* is the only wired SMTP alert path.
- **GPU benchmark workflow gap**
  - gpu-tests.yml deleted (commit 978bb04c) and nightly extended-benchmarks removed 2026-09-15; no workflow now targets the GPU runner. Doc banner added; restoring coverage is an owner decision.
- **TracingPage.tsx 'Open Jaeger' link**
  - Shipped code links to localhost:16686 (Jaeger UI) which does not run; Tempo is the actual backend. Code fix is an owner decision; docs describe Tempo.
- **frontend CommandPalette 'System' entry + g y chord**
  - Both navigate to /system, which is not a route in App.tsx — lands on NotFound. keyboard-shortcuts.md now carries a Known-issue note; fixing the palette/chord target (likely /operations or /operations-dashboard) is an owner decision.
- **frontend/public/manifest.json PWA shortcut '/events'**
  - Shortcut URL /events is not a route in App.tsx; installed-app shortcut lands on NotFound. Likely intended /timeline or /alerts — owner decision.
- **FRONTEND_PORT=5173 in .env.example + compose header comment**
  - Presented as the frontend host port but docker-compose.prod.yml never consumes it; real host ports are FRONTEND_HTTP_PORT 8080 / FRONTEND_HTTPS_PORT 8444. 5173 is only the Vite dev-server port.
- **backend job-type catalogue drift**
  - GET /api/jobs/types advertises backup/import (never created) while real types (orphan_cleanup, orphaned_file_cleanup, data_cleanup, evaluation/background_evaluation) are absent; frontend Type dropdown's re_evaluation option matches nothing. jobs.md records reality; catalogue fix is an owner decision.
- **frontend dual risk-band constants (severityColors.ts vs risk.ts)**
  - severityColors.ts styles Critical at >=80 while risk.ts and backend use >=85; scores 80-84 render with critical card styling but a High RiskBadge label. timeline.md documents the mismatch; reconciling the constants is an owner decision.

## Round 2 — integrity verifier (nav/links/anchors/mermaid)

- **[minor] /agents/agent-veranda/workspace/docs/architecture/overview.md**
  - CHECK 1 — BLOCKER: none. All 101 nav leaf entries in mkdocs.yml resolve to an existing file (verified by YAML parse + filesystem check AND independently by `mkdocs build`, which emitted 0 nav `not_found` warnings). `extra_css: stylesheets/custom.css` also resolves. This branch added 5 nav entries (the Decisions section, lines 190-194); all 5 targets exist. Note (not a blocker): mkdocs reports 397 docs files not in nav — 234 are real docs and 163 are legitimately excluded (plans 77, archive 34, superpowers 10, discoveries 1, AGENTS.md 34, \_includes 5, images 2). All 234 are pre-existing: none of them is a file this branch created or moved. Largest clusters: architecture/\*\* 99, development/ 35, developer/ 20, research/ 17, ui/ 11, vss-integration/ 9.
  - **Action:** No change required. Leave nav as is.
- **[major] docs/architecture/overview.md, docs/architecture/decisions.md, docs/architecture/ai-pipeli**
  - ADJACENT TO CHECK 2 (found while resolving the 14 "BROKEN" paths my link scanner reported — they were NOT markdown links but pymdownx.snippets directives, and the real defect is behind them). 15 of the repo's 16 `--8<--` snippet directives write the include path as "docs/\_includes/<file>.md". pymdownx.snippets treats `\` as a literal path character — its only escape mechanism is a leading `;` (pymdownx/snippets.py lines 267-268) — so the path is looked up verbatim as `docs/\_includes/...`, does not exist, and is SILENTLY skipped because mkdocs.yml leaves `check_paths` at its default of false. Proven in two ways: (a) isolated repro with the repo's own pymdownx 12.0 — the unescaped form injects the content, the escaped form renders the empty string, and with check_paths=True it raises SnippetMissingError for path 'docs/\_includes/probe.md'; (b) the actual `mkdocs build` of this branch — docs/architecture/overview/index.html contains ZERO occurrences of "SetupGuardMiddleware" (the string lives only in \_includes/auth-model.md), and its '## Security Model' section renders with no body, jumping straight to '### Production Hardening'. Only 1 of the 16 directives is correct (docs/architecture/overview.md:289, unescaped) and it is the only one that injects. These 15 are NOT introduced by this branch (all predate it, from commit 85c93939, 2026-02-07) but 13 of the 15 occurrences sit in files this branch modified, and round-3 content changes land directly next to them.
  - **Action:** Drop the backslash from the include path in all 15 occurrences, e.g. `--8<-- "docs/\_includes/auth-model.md"` -> `--8<-- "docs/_includes/auth-model.md"` (match the one correct existing form at overview.md:289). Additionally set `check_paths: true` under the pymdownx.snippets config in mkdocs.yml so a bad include fails the build instead of silently vanishing. Because the escaping is almost certainly Prettier's doing (pre-commit runs prettier on markdown; .prettierignore already contains a comment about Prettier rewriting mid-word underscores into emphasis pairs), add a prettier-ignore guard or an include-path lint, or the fix will re-break on the next format pass.
- **[minor] /agents/agent-veranda/workspace/docs/architecture/system-overview/configuration.md**
  - CHECK 2 — site-root link. `:369` `[Environment Reference](/docs/reference/config/env-reference.md)`. mkdocs resolves absolute links against docs_dir, so it looks for docs/docs/reference/config/env-reference.md. `mkdocs build` logs: "contains an absolute link '/docs/reference/config/env-reference.md', it was left as is" — i.e. emitted verbatim, and it 404s at the deployed site root. The target itself is fine (docs/reference/config/env-reference.md exists and is in nav). Verified pre-existing (byte-identical at HEAD). Same defect at docs/architecture/system-overview/deployment-topology.md:293 -> /docs/architecture/overview.md. Both pages are nav-included, so both are live on the published site.
  - **Action:** Use a docs-rooted absolute link (drop the redundant `docs/` segment) or a relative link: `](/reference/config/env-reference.md)` or from system-overview/ `](../../reference/config/env-reference.md)`.
- **[minor] /agents/agent-veranda/workspace/docs/benchmarks/README.md**
  - CHECK 2 — four links point at docs/README.md, which mkdocs EXCLUDES from the built site because it collides with docs/index.md (`WARNING - Excluding 'README.md' from the site because it conflicts with 'index.md'`). They therefore resolve to nothing on the built site: benchmarks/README.md:111 `](../README.md)`, decisions/README.md:89 `](../README.md)`, developer/README.md:163 `](../README.md)`, developer/contributing/README.md:326 `](../../README.md)`. All four verified pre-existing. docs/README.md and docs/index.md are two genuinely different documents — index.md is the landing-page card grid (nav "Home"), README.md is a documentation hub with its own mermaid architecture diagram — so the losers' content is currently unreachable from the site.
  - **Action:** Retarget the four links to `](../index.md)` (or `/`), and separately decide whether docs/README.md should keep existing under docs_dir at all, since mkdocs will always silently drop it (content-relocation decision, not a link fix).
- **[minor] /agents/agent-veranda/workspace/docs/ai/model-zoo.md**
  - CHECK 2 — 45 occurrences across 20 changed files where a relative markdown link resolves on disk but to a target OUTSIDE docs_dir, which mkdocs can never link (it logs "is not found among documentation files"). Every one of these files exists on disk — this is a path-space error, not dead content. 9 occurrences were ADDED by this branch: docs/ai/model-zoo.md:12 and :1216 -> ../../ai/gateway/AGENTS.md; docs/ai/AGENTS.md:34/:42/:76 -> ../../ai/gateway/AGENTS.md; docs/developer/contributing/README.md:308 and docs/developer/contributing/AGENTS.md:104 -> ../../../AGENTS.md (both rewritten this branch from ../../../CLAUDE.md, which the branch deleted — so these were actively touched, not dormant); docs/development/AGENT_COORDINATION.md:657 -> ../../AGENTS.md (same CLAUDE.md rewrite); CONTRIBUTING.md:100 -> AGENTS.md (outside docs/, so only a GitHub-side issue). Of the pre-existing occurrences, 10 sit in nav-included published pages and do render as dead links on the built site: model-zoo.md:1215-1220 (../../ai/AGENTS.md, ai/enrichment, ai/yolo26, ai/florence, ai/clip), decisions/2026-01-31-risk-score-validation-suite.md:236 (../../backend/tests/integration/test_risk_score_validation.py), decisions/python-314-adoption.md:288 (../../scripts/benchmark_py314.py), getting-started/upgrading.md:316 (../../CHANGELOG.md). The remainder sit in files already off-nav (architecture/data-model/README.md, architecture/testing/README.md, development/model-testing.md, development/multi-gpu.md, docs/\*/AGENTS.md) or outside docs/ entirely (README.md, frontend/README-TESTING.md, backend/tests/integration/STATEFUL_TESTING.md, ai/AGENTS.md) where mkdocs never sees them.
  - **Action:** For links that must work on the built site, add the target to the mkdocs site (e.g. mirror the ai/\*/AGENTS.md service docs under docs/, or link a hosted URL via the repo_url/edit_uri pattern) rather than pointing at repo paths. For links that are meant for GitHub readers only, either accept the mkdocs warning deliberately or move them into the repo-root/AGENTS.md tree where mkdocs does not process them. Do not leave them as-is in nav-included pages: 10 of them are live 404s on the published site today.
- **[minor] /agents/agent-veranda/workspace/docs (131 anchors across 276 changed files)**
  - CHECK 3 — NO violations. Every `#heading` anchor in every changed file resolves to a heading that exists in the same file after the edit, and every cross-file `path.md#anchor` resolves in the target. 131 anchors checked. Confirmed twice, independently: (a) my own check, re-run with a STRICT heading-only index after I found and removed a looseness in it (a global `id=` regex catch-all that could have masked real misses) — strict pass also returned 0; (b) `mkdocs build` with validation level INFO, which runs `page.validate_anchor_links()` over every built page — it emitted zero anchor warnings. I also ran a positive control (a throwaway tree in /tmp with 1 planted broken same-file anchor, 1 planted broken cross-file anchor, 1 planted bad path, plus 3 valid links): all 3 violations detected, zero false positives, so the zero result is real rather than a checker that never fires. The branch's heading rewrites (round-1 style) did NOT strand any anchor.
  - **Action:** No change required.
- **[minor] /agents/agent-veranda/workspace/docs/style-guides/diagrams.md**
  - CHECK 4 — NO violations. 190 mermaid blocks across the 276 changed .md files scanned fence-aware (correctly handling the 4-backtick nesting this branch introduced); all balanced. Per-block checks: even double-quote count per line outside strings, even single-quote count outside strings and `%%` comments, and balanced `()`/`[]`/`{}` with quoted spans, `%%` comments, multi-line `%%{init:...}%%` frontmatter directives and ER cardinality tokens (`||--o{` etc.) removed first. Two apparent-balance classes are legitimate mermaid and were excluded deliberately, not overlooked: multi-line `%%{init: {...}}%%` directives (comment material, not graph syntax) and erDiagram relationship glyphs, which use `{`/`}` as crow's-foot cardinality. `<>` deliberately not balance-checked — arrows (`-->`, `<-->`, `-->>`), `A[text]` flag shapes and `<br/>` make raw counting meaningless. Cross-check: grep counted exactly 190 mermaid fence-open lines, matching the extractor's block count. Eyeball pass on the diff: only two files had mermaid blocks removed (docs/architecture/dataflows/event-lifecycle.md, docs/operator/ai-installation.md) and both deletions are clean with balanced fences; docs/ai/model-zoo.md and docs/operator/ai-installation.md content edits inside blocks stay balanced. This branch actually FIXED a long-standing fence-nesting bug in this file: the "Sequence Diagram / State Diagram / ER Diagram / Architecture Flowchart" examples used a spurious bare ` ` ``line to separate a closing fence from the next opener, which left the following `### ...` heading swallowed inside a code block; they now nest as `````markdown` + inner`` `mermaid ```` + ```` ` ` + ````` ` ````, verified structurally correct. Note my own scanner initially reported `#diagram-type-guidelines`as a dead anchor here — that was a bug in MY fence matcher (I wrote`fence[0]`, which grabs one character instead of the full marker, so a 4-backtick close never closed a 3-backtick block and the heading got swallowed). Fixed, re-run, gone. It is not a repo defect.
  - **Action:** No change required.
- **[minor] /agents/agent-veranda/workspace/docs/plans/2026-09-12-context-map-doc-updates.md**
  - CHECK 2 — 2 of the 14 "broken" hits my first pass reported are FALSE POSITIVES in my scanner, not repo defects. Lines 1627 and 1654 read `[VERIFIED deterministic repro]: poison plugin caching a bare-MagicMock client ...` — prose in a quarantine plan file. My reference-definition regex (`^ {0,3}\[label\]:\s*\S+`) matched the bracketed label followed by a colon and treated "poison" / "leak-sim" as link destinations. Real Python-Markdown would need a matching `[poison]` usage elsewhere, which does not exist. Recorded only so the finding is not mistaken for a broken link.
  - **Action:** No repo change. (If anything, tighten the ref-def regex to require a following destination and no trailing prose, as done in the corrected checker.)
- **[minor] /agents/agent-veranda/workspace/docs/templates/AGENTS.md**
  - CHECK 1 — near-miss worth knowing, because it looks like an mkdocs config bug and is not. docs/AGENTS.md:18 links to `templates/AGENTS.md` and mkdocs reports it "excluded from the built site", with no `exclude_docs` set in mkdocs.yml and no `docs/templates/.pages` file. Cause: mkdocs' hard-coded default exclusion is `pathspec.from_lines(['.*', '/templates/'])` (mkdocs/structure/files.py:524) — any directory named `templates` at docs root is dropped by mkdocs itself, always. Pre-existing, unrelated to this branch. No broken nav entry results (nothing in nav points there).
  - **Action:** No action for the nav audit. If those templates should ever be reachable from the site, they must move out of a docs-root directory named `templates` (mkdocs.yml cannot re-include them); otherwise leave as is and treat docs/AGENTS.md:18 as an intentional repo-path link.

## Round 2 — judge: first-timer (12 README findings)

- **[blocker]** The Development Setup block ("Runs backend and frontend as host processes... Redis comes from a container") never mentions PostgreSQL, and the host-run backend cannot start as written. Step 1's `python setup.py` writes `.env` with `DATABASE_URL=postgresql+asyncpg://security:...@postgres:{PORT}/secur...
  - **Fix:** Add a Postgres step to the Development Setup block (e.g. `podman run -d --name dev-postgres -e POSTGRES_PASSWORD=... -e POSTGRES_DB=security -p 127.0.0.1:5432:5432 postgres:16` or a `scripts/dev.sh db` pointer) and an explicit host-run env override shown before `dev.sh start`, e.g. `export DATABASE\_...
- **[blocker]** "Host-run AI servers" section says "Then point the backend at them by overriding the AI URL env vars, e.g. `export YOLO26_URL=http://host.docker.internal:8090` / `export NEMOTRON_URL=http://host.docker.internal:8091`". `host.docker.internal` does not resolve for processes running on a Linux host (it...
  - **Fix:** Replace the two exports in that section with `export YOLO26_URL=http://localhost:8090` / `export NEMOTRON_URL=http://localhost:8091` for the host-run backend, and add one sentence: if instead the backend runs in a container, you must add `extra_hosts: ["host.docker.internal:host-gateway"]` (docker) ...
- **[major]** Quick Start step 3 is literally `docker compose -f docker-compose.prod.yml up -d` with the aside "(this project uses Podman; plain `docker compose` works too)" — but for a Podman-first reader (the project's own documented runtime) `docker` is not on PATH at all without the optional podman-docker pac...
  - **Fix:** Invert the parenthetical: primary command `podman compose -f docker-compose.prod.yml up -d` (matching AGENTS.md/CLAUDE.md and the compose file's own assumptions), and either drop "plain docker compose works too" or qualify it (Docker requires a CDI spec, and the keep-id/`:U`/label=disable keys are P...
- **[major]** Nothing in the README mentions `PODMAN_SOCKET`, but docker-compose.prod.yml hard-requires it: `- ${PODMAN_SOCKET:?PODMAN_SOCKET must be set}` at lines 396 and 1295. `.env.example` ships it only commented out (lines 54, 656), and `setup.py`'s `generate_env_content()` never writes it — it is appended ...
  - **Fix:** Add one Quick Start bullet or a note under step 3: podman users need `export PODMAN_SOCKET=/run/user/$(id -u)/podman/podman.sock` (and `systemctl --user enable --now podman.socket`) unless setup.py's deploy phase ran; setup.py appends it to .env automatically only when it completes a deploy....
- **[major]** Quick Start step 2 `./ai/download_models.sh` has two traps for a fresh laptop: (a) it defaults to `AI_MODELS_PATH=/export/ai_models` and does bare `mkdir -p "${AI_MODELS_PATH}/..."` (lines 267–268) under `set -e` — creating `/export` requires root, so run before/without setup.py's sudo'd storage_con...
  - **Fix:** Amend step 2 to `AI_MODELS_PATH=$(grep -m1 ^AI_MODELS_PATH .env | cut -d= -f2-) ./ai/download_models.sh` (or note that setup.py already prompts for the model download and path, and that re-running the script needs the same AI_MODELS_PATH), and note the /export default needs the directory to already ...
- **[major]** MISSING prerequisites for the Development Setup path: the Quick Start "Prerequisites:" line ("Linux host + NVIDIA GPU + Docker/Podman with GPU passthrough") never applies to the dev collapsible, which silently requires `uv` (not installed by anything; `uv sync` → command not found on a fresh laptop)...
  - **Fix:** Add a one-line prerequisite to the Development Setup block: "needs `uv` (curl -LsSf https://astral.sh/uv/install.sh | sh), Node 24+ (nvm install 24), and Python 3.14 available to uv" — before the `python setup.py` step....
- **[major]** "Start Redis + backend (uvicorn :8000) + frontend" — but `scripts/dev.sh` starts Redis exclusively with `docker` (falls back to `sudo docker`), and on the Podman-first laptop the project recommends, `docker info` fails, it prints "Could not start Redis. Docker not available." and returns 1 — which u...
  - **Fix:** Note in the dev section: dev.sh's Redis bootstrap needs the docker CLI or the podman docker-compatible socket (`systemctl --user enable --now podman.socket` + podman-docker, or `DOCKER_HOST=unix:///run/user/$UID/podman/podman.sock`), or a system redis (`sudo systemctl start redis`), and mention `./s...
- **[minor]** Line 286 comment claims "bun.lock exists but no bun config" — grep fails: `frontend/bunfig.toml` exists, and it carries a load-bearing rule for newcomers ("DO NOT USE: bun test"; use `bun run test`, because the repo uses Vitest, not Bun's runner). A contributor reading "no bun config" may conclude b...
  - **Fix:** Change the parenthetical to "(CI uses npm; bun.lock + bunfig.toml exist — if you use bun, run `bun run test`, never `bun test` — see frontend/bunfig.toml)"....
- **[minor]** Line 286 comment "uv sync --extra dev # Python deps (backend/.venv)" — there is no `backend/pyproject.toml`; `uv sync` at the repo root creates `./.venv`, which is exactly what `scripts/dev.sh` sources (`source .venv/bin/activate` after `cd "$PROJECT_ROOT"`). The "backend/.venv" label can...
  - **Fix:** Fix the label to "(root `.venv`, which scripts/dev.sh activates)"....
- **[minor]** Quick Start "Verify" shows `open http://localhost:8080    # Dashboard (HTTP)` as the primary URL and treats HTTPS as opt-in ("enable with SSL_ENABLED=true") — but setup.py's generated .env hard-writes `SSL_ENABLED=true` (generate_env_content), and with SSL enabled the frontend nginx HTTP listener (F...
  - **Fix:** Swap the Verify block to `open https://localhost:8444  # Dashboard (self-signed cert — accept the warning)` as primary, since setup.py enables SSL by default, and keep 8080 as the redirect/HTTP-only alternative....
- **[minor]** "Model Status API" block presents four `curl http://localhost:8000/api/system/models...` commands with no caveat, but those routes (backend/api/routes/model_management.py, prefix /api/system/models) are NOT in SetupGuardMiddleware's whitelist (setup_guard.py whitelists only /api/auth/setup-status, /...
  - **Fix:** Add "(after the first admin registration; before it, these return 503 — see Quick Start)" to the Model Status API intro line....
- **[minor]** The Verify block implies `curl http://localhost:8000/api/system/health` succeeds right after `up -d`. In compose, backend has `depends_on: ... ai-llm: condition: service_healthy; ai-gateway: condition: service_healthy; go2rtc: service_healthy` (docker-compose.prod.yml ~lines 498-513), and ai-llm mus...
  - **Fix:** Under Verify, add: "first boot can take 5-10 min — ai-llm loads a 15GB model before backend starts; watch with `podman compose -f docker-compose.prod.yml ps` / `logs -f ai-llm` until healthy"....

## Round 2 — judge: returning-agent (12 README findings)

- **[blocker]** Quick Start step 3 (`docker compose -f docker-compose.prod.yml up -d`) cannot run immediately after step 1 as written. `backend` and `alloy` hard-require PODMAN_SOCKET (`${PODMAN_SOCKET:?PODMAN_SOCKET must be set}`, compose lines 396 and 1295) and it is only ever written into .env by the `deploy` phase (`_ensure_podman_socket`, setup_lib/deploy_phases.py:336-356, called from `phase_build`:379), which `python setup.py` does not reach when a reboot is required (setup.py:1528-1583 stops at 'Then run: python3 setup.py deploy'). Even a clean setup only appends PODMAN_SOCKET if setup.py's own deploy phase ran. I reproduced the failure: `docker compose -f docker-compose.prod.yml config` → 'required variable PODMAN_SOCKET is missing a value: PODMAN_SOCKET must be set'. .env.example ships it commented out (lines 54, 656). Also, the compose file is Podman-only (PODMAN_SOCKET is mounted as the docker.sock and alloy receives `PODMAN_SOCKET=${PODMAN_SOCKET}` as DOCKER_HOST), which contradicts the comment '(this project uses Podman; plain `docker compose` works too)' — and AGENTS.md:346 says 'Podman Compose (podman-compose), not docker compose'.
  - **Fix:** Make step 3 `python setup.py deploy` (or `podman compose -f docker-compose.prod.yml up -d`) and state the precondition explicitly: PODMAN_SOCKET must be present and uncommented in .env (setup.py deploy writes it; otherwise `systemctl --user enable --now podman.socket` and `echo "PODMAN_SOCKET=/run/user/$(id -u)/podman/podman.sock" >> .env`). Drop the 'plain docker compose works too' claim or scope it to Docker hosts where PODMAN_SOCKET is set to the Docker socket.
- **[blocker]** 'Host-run AI servers' (lines 312-314): `export YOLO26_URL=http://host.docker.internal:8090` / `export NEMOTRON_URL=http://host.docker.internal:8091` has no effect on the compose deployment, and the YOLO26 value is missing the router suffix. Those four URLs are **literal** in the compose file (`NEMOTRON_URL=http://ai-llm:8091`, `YOLO26_URL=http://ai-gateway:8090/yolo26`, `FLORENCE_URL=...`, `CLIP_URL=...` at docker-compose.prod.yml:454-460) with no `env_file:` anywhere in the file, so a shell export never reaches the backend container — it keeps calling `http://ai-gateway:8090`, which the README's own warning says is down. Worse, the backend appends paths to this base (`f"{settings.yolo26_url}/health"`, backend/services/gpu_monitor.py:805, performance_collector.py:178), so a suffix-less URL hits `/health` instead of `/yolo26/health` and 404s. docs/operator/ai-configuration.md:234-235 has the correct shape (`.../yolo26`) and notes `host.docker.internal` is macOS/Docker-Desktop only (Podman on Linux needs `host.containers.internal`/host IP). Also, with the gateway stopped, FLORENCE_URL/CLIP_URL/ENRICHMENT_URL are not overridden at all, so those routers silently fall back to config defaults 8092/8093/8094 — services that no longer exist.
  - **Fix:** Replace with the working recipe: override per-service in a compose override file (or `podman compose ... -e`-equivalent environment entries) using `YOLO26_URL=http://host.docker.internal:8090/yolo26`, `NEMOTRON_URL=http://host.docker.internal:8091`, plus `FLORENCE_URL`, `CLIP_URL`, `ENRICHMENT_URL`, `ENRICHMENT_LIGHT_URL` pointed at the still-running gateway, and link docs/operator/ai-configuration.md for the platform-specific hostname.
- **[blocker]** Model-downloading block: `python scripts/download_models.py` is presented as a supported alternative to `./ai/download_models.sh` ('supports --force and --models-dir'), but its default target is `./models` (`default=Path(os.environ.get("MODELS_DIR", "./models"))`, scripts/download_models.py:163-165) while compose mounts `${AI_MODELS_PATH:-/export/ai_models}` (docker-compose.prod.yml:144, 308-310) — so a reader who runs it as written and then starts the stack gets an empty model dir. Its `MODELS` dict is a 10-model subset (no Nemotron GGUF, no YOLO26, no Florence) and uses stale repos (fashion-clip → `patrickjohncyh/fashion-clip`, which models.yml:336-337 says was replaced by `Marqo/marqo-fashionSigLIP`; smoke-fire → `luminous0219/...` vs models.yml's `SHOU-ISD/fire-and-smoke`). Separately, both commands hard-default to `/export/ai_models` and ignore the AI_MODELS_PATH that `python setup.py`'s storage step writes to .env, and neither has a writability preflight — the `mkdir -p` at ai/download_models.sh:267 aborts under `set -e` (line 28) on a permission error, at line 267 of a 600-line script that starts a ~42GB download.
  - **Fix:** Delete the `python scripts/download_models.py` line (or label it 'subset only, targets ./models — not the container paths'). Add a preflight note for ./ai/download_models.sh: run `./scripts/... ` no — state `sudo mkdir -p "$AI_MODELS_PATH" && sudo chown "$USER" "$AI_MODELS_PATH"` first, and that the script reads only the AI_MODELS_PATH shell variable, not .env.
- **[major]** Camera Ingestion says 'Use the vsftpd container kept in the archive: see [`archive/vsftpd/README.md`]' — that README is itself a dead end and an agent will run its first command verbatim. Its 'Using Docker Compose' section says 'The vsftpd service is included in the main `docker-compose.yml`' and tells the reader `docker compose up -d vsftpd`; there is no root `docker-compose.yml` (only docker-compose.{prod,ci,test,ghcr}.yml) and no `vsftpd` service in any of them. archive/README.md confirms it: '`vsftpd/` … README targets a `docker-compose.yml` that no longer exists'. Worse, archive/README.md:4 states 'Nothing here is referenced by code, CI, or compose' — the README is the only live reference to it.
  - **Fix:** Point the bullet at the concrete artifacts that still work in that directory (`archive/vsftpd/vsftpd.conf`, `Dockerfile`, `docker-compose-wrapper.sh`, `install-systemd.sh`) and add 'not wired into any compose file — the README inside is stale', or drop the link and keep only 'bring your own FTP server pointed at /export/foscam'.
- **[major]** 'Containers | 21 (19 run by default; `ai-llm-vllm` and `dcgm-exporter` need a profile)' miscounts: `docker compose -f docker-compose.prod.yml config --services` returns **19** services and `ls -d docker-compose.prod.yml` … the two profiled ones are included in that file, so the split is 17 default + 2 profiled, not 19 + 2. The 19 includes `foscam-init`, a short-lived chown helper that exits (compose line 355). The adjacent RAM row is off in the other direction: '~49 GB (sum of `deploy.resources.limits.memory` in `docker-compose.prod.yml`…)' — summing the limits gives 72.9 GB total / **48.9 GB** for the 17 default services (reservations sum to 34.5 GB); ~49 GB is the real A5500 observation, and attributing it to an arithmetic operation on the compose file is a claim the next agent will re-derive and 'fix'.
  - **Fix:** State '19 services defined (17 start by default; `ai-llm-vllm` needs `--profile vllm`, `dcgm-exporter` needs `--profile gpu-rootful`; `foscam-init` exits after chown)' and reword the RAM row to 'observed ~49 GB with all services running; compose `deploy.resources.limits` sum to ~49 GB across the default services (~73 GB including profiled)', or drop the parenthetical derivation.
- **[major]** 'Configuration' presents these variables as the knobs a deployer turns ('**Source of truth:** [Environment Variable Reference]' + 'Common settings'), but three of them never reach the backend container in the production deployment: `RETENTION_DAYS`, `BATCH_WINDOW_SECONDS` and `API_KEY_ENABLED` appear nowhere in docker-compose.prod.yml (verified by grep; only `FILE_WATCHER_POLLING=${FILE_WATCHER_POLLING:-false}` at line 447 is interpolated), and there is no `env_file:` in the compose file — backend/core/config.py's `env_file=".env"` resolves to the path _inside_ the container. So editing RETENTION_DAYS in .env silently keeps the built-in default while the reader believes retention changed. `YOLO26_URL`/`FLORENCE_URL`/`CLIP_URL` are the mirror image: the table's '(port 8090)' is right for a host process but the container values are hardcoded literals (see the host-run finding).
  - **Fix:** Annotate the table: mark RETENTION_DAYS / BATCH_WINDOW_SECONDS / API_KEY_ENABLED as 'backend process env — not passed to the backend container by docker-compose.prod.yml; add an environment entry or override file to change them in a containerized deploy', and note the container values for the \*\_URL rows are set by compose.
- **[major]** '**Also included:**' bullets plus the four feature tables (Detection and Analysis / Zone Intelligence / Person and Vehicle Identification / Analytics and Reporting) describe only capabilities. The single most load-bearing operational fact in the project — that on a fresh install SetupGuardMiddleware returns 503 for everything except setup/health until you register the first admin — first appears 200 lines later, on line 270. An agent that lands here, then curls anything before registering, gets 503 with no clue it is a feature. The tables also carry no status, so the next agent assumes every listed capability is live: every row in three of the four tables links to the same one or two guides (docs/guides/video-analytics.md ×7, docs/guides/zone-configuration.md ×4, docs/guides/face-recognition.md ×3), which reads as a stub link farm rather than navigation.
  - **Fix:** Add a 'First run' line to the 'Also included' list ('first run: API returns 503 until you register the first admin in the dashboard') so the fact is stated once next to the capabilities, and either de-duplicate the repeated guide links or split the tables by status (implemented / partial / planned) so a reader can tell what they can exercise.
- **[major]** 'Download all models the gateway needs (**~42GB** with the full zoo)' is only the script's own header comment (ai/download_models.sh:9); `models.yml`, which the README declares 'the single source of truth ... The tables below are drawn from it', sums `size_mb` to **34.1 GB**. The README's VRAM Budget table also contradicts its own hardware table two sections later and AGENTS.md:456's legacy note: 'Minimum | 8–12GB | LLM partially offloaded … + YOLO26 + embeddings' and the GPU-compatibility row '16GB | RTX 4080, A4000, **Tesla T4**' — Tesla T4 is Turing (sm_75) with no bf16/NVFP4 support, so it cannot run this llama.cpp/Triton stack. The YOLO26 '~650MB' also can't be grepped from models.yml: the `yolo26` entry has `size_mb: 67`, `vram_mb: 0`, `enabled: false` (lines 74-88), and 650 appears only as `size_mb` of the unrelated `yolo11-license-plate`.
  - **Fix:** Split the storage number ('~34GB in `models.yml`; ~42GB as downloaded, incl. legacy CLIP-ViT-L/FashionCLIP clones the script still pulls'), replace the Tesla T4 example with a card that can actually run the stack (or state Turing is unsupported), and source the YOLO26 VRAM figure (docs/\_includes/vram-requirements.md says ~2GB) or mark it 'measured, not in models.yml'.
- **[major]** The README is the repo's declared navigation index but never mentions `AGENTS.md` or `llms.txt` (grep: zero hits for 'AGENTS' in README.md). For a returning agent this is the only crossroads: AGENTS.md:364 states 'Read this file (AGENTS.md) — the single root instruction file; `CLAUDE.md` was deliberately retired (owner ruling 2026-09), don't look for it', and every subdirectory has one, yet an agent following README → docs/developer/README.md never learns that, and may waste a cycle looking for the deleted CLAUDE.md.
  - **Fix:** Add one line under the 'I want to…' table: 'Work on the codebase as an AI agent → [`AGENTS.md`](AGENTS.md) (single root instruction file; per-directory `AGENTS.md` indexes; `llms.txt` is the condensed machine-readable map)'.
- **[minor]** 'Then open the dashboard: first run requires you to register the first admin account (the API returns 503 for everything except setup and health until you do)' — 'everything' and 'health' are both too loose. backend/api/middleware/setup_guard.py:49-79 whitelists `/`, `/health`, `/ready`, `/docs`, `/redoc`, `/openapi.json`, `/api/auth/setup-status`, `/api/auth/register`, `/api/system/gpu`, `/api/system/stats`, `/api/system/telemetry`, `/api/metrics`, prefix `/api/system/health`, and prefix `/ws/`. An agent testing 'the API returns 503' against `/api/system/gpu`, `/api/metrics` or a `/ws/` channel will conclude the guard is broken.
  - **Fix:** Reword to '503 except the setup endpoints (`/api/auth/setup-status`, `/api/auth/register`), the health/metrics endpoints and WebSocket channels — see the whitelist in `backend/api/middleware/setup_guard.py`'.
- **[minor]** 'On-Demand Models … Representative entries (VRAM from `models.yml`)' — three rows do not exist in models.yml and one is named after a retired model. `Smoke/Fire-YOLOv8n` is there as `smoke-fire-yolov8n`; `ViT age + gender` is two entries (`vit-age-classifier`, `vit-gender-classifier`, 200MB each); `X-CLIP Base / ST-GCN++` is two entries (`xclip-base` vram*mb: 0, `stgcn-plus-plus` vram_mb: 20, not 'Triton'). 'FashionCLIP' was replaced by Marqo/marqo-fashionSigLIP per models.yml:336-337. And 'Full list: `models.yml` (grouped by `download_phase`: 0 required, 1 core enrichment, 2 extended, 3 optional)' is misleading as worded — the phase is a \_download-order* integer (models.yml:16), not a grouping key, and 16 of 30 models are phase 3 (optional), so 'these load when a detection needs them' overstates readiness for half the zoo.
  - **Fix:** Rename rows to the exact `name:` values in models.yml (or drop the '(VRAM from models.yml)' attribution), split the paired entries with their real vram_mb, rename FashionCLIP → FashionSigLIP, and reword the last line to 'ordered by `download_phase` (0 required → 3 optional)'.
- **[minor]** Missing section — the README has no 'Where to look when something is wrong' step, which is exactly what a context-free returning agent needs after a verification command fails. Its whole verification surface is `curl http://localhost:8000/api/system/health` (works — whitelisted) and `open http://localhost:8080`. There is no pointer to container logs (`podman compose -f docker-compose.prod.yml logs`, and `podman ps -a`), to the repo's own health gate (`/platform-healthcheck` skill, referenced AGENTS.md:26/103), or to the troubleshooting hubs that exist and would answer the top three first-run failures this README itself creates: PODMAN_SOCKET/POSTGRES_PASSWORD interpolation (docs/operator/deployment-modes.md), models-missing/VRAM (docs/operator/ai-troubleshooting.md), and SSL (docs/development/ssl-https.md).
  - **Fix:** Add a '### If something fails' block under Quick Start: `podman ps -a` → `podman compose -f docker-compose.prod.yml logs --tail=50 <svc>` → `/platform-healthcheck`; then a 4-row 'symptom → doc' table (503 everywhere = register admin; compose 'required variable … is missing' = .env; model/VRAM errors = docs/operator/ai-troubleshooting.md; HTTPS/cert = docs/development/ssl-https.md).

> Lens notes: Lens: returning AI agent, six months out, zero context, using README.md (/agents/agent-veranda/workspace/README.md) as the navigation index and executing every command it gives. Read top to bottom as that reader; grounded every claim against docker-compose.prod.yml, .env.example, setup.py/setup*lib, models.yml, ai/*.sh, scripts/\_, frontend/vite.config.ts + docker-entrypoint.sh, and backend/api/routes + middleware. Nothing edited. What works for this reader (verified, don't churn it): all 31 file/dir links and all 12 image paths resolve, including docs/api/analytics-endpoints.md, docs/benchmar

## Round 2 — judge: ops-oncall (7 README findings)

- **[blocker]** Lines 189-203 "Model Status API" — "Check which models are currently loaded" and "Load or unload a specific model on demand" — instruct curls that fail or lie in the gateway-consolidated deployment the README itself describes (lines 124-126). backend/api/routes/model_management.py hardcodes ENRICHMENT_URL = "http://ai-enrichment:8094" and ENRICHMENT_LIGHT_URL = "http://ai-enrichment-light:8096" (lines 87-88), but `grep -n "ai-enrichment\|8094\|8096" docker-compose.prod.yml` finds zero matches — those hostnames no longer exist and there are no network aliases. Consequences at 2am: `POST /api/system/models/<name>/load` always fails (connect error → 502/503, "Cannot connect to http://ai-enrichment:8094"), and `GET /api/system/models` returns HTTP 200 but reports EVERY model with runtime.loaded=False and ai-enrichment/ai-enrichment-light services unhealthy (the fetch-fails-soft path), i.e. the on-call reader is shown a phantom "all models unloaded" outage and the fix command cannot work. The gateway adapter (ai/gateway/adapters/enrichment.py) exposes no /models/preload route either, and .env.example's ENRICHMENT_URL=http://localhost:8090/enrichment (line 227) is ignored by the hardcoded constants.
  - **Fix:** Either rewire model_management.py to the gateway URLs from .env.example (http://ai-gateway:8090/enrichment and /enrich-lt — which needs gateway-side /models/preload endpoints), or, in the README, keep GET /api/system/models with a caveat block ("runtime state is reported as unloaded until the status API is repointed at the gateway — trust ai-gateway /health and http://localhost:8090/metrics instead") and delete the load/unload curl block until those routes work.
- **[major]** MISSING — no monitoring/observability quick-links anywhere in the README. The screenshot table (lines 14-20) advertises Analytics / AI Performance / Operations dashboards, and the compose stack ships Grafana (host 3002, sub-path /grafana/ via the frontend nginx proxy — docker-compose.prod.yml lines 930-953: GF_SERVER_ROOT_URL=/grafana/, comment "Access Grafana via the frontend nginx proxy at /grafana/ for production use"), Prometheus :9090, Alertmanager :9093, Loki :3100, Tempo :3200, Pyroscope :4040 (docker-compose.prod.yml lines 854-1168) — yet an on-call reader gets zero URLs. The only entry point is the generic "Operator Hub" row (line 39); the port table with Grafana is buried in docs/operator/README.md:232. docs/operator/monitoring.md exists but README never links it.
  - **Fix:** Add an "Operations & Monitoring" section directly after Quick Start with a quick-link table: Dashboard http://localhost:8080 / https://localhost:8444, Grafana http://localhost:3002 or https://<host>:8444/grafana/ (anonymous Admin on by default, GF_AUTH_ANONYMOUS_ENABLED=true), Prometheus http://localhost:9090, Alertmanager http://localhost:9093, Loki http://localhost:3100, Tempo http://localhost:3200, Pyroscope http://localhost:4040, API docs http://localhost:8000/docs — all 127.0.0.1-bound — plus a link to docs/operator/monitoring.md.
- **[major]** MISSING — no log locations and no restart/service-control commands. `grep -n "logs" README.md` yields only the dev-mode line "./scripts/dev.sh status # Also: stop | restart | logs" (line 290); there is no `docker compose logs`/`podman logs` anywhere and no compose restart command anywhere. The 2am reader who finds a sick backend cannot, from this README alone, learn to run `docker compose -f docker-compose.prod.yml logs -f backend` / `podman logs backend`, or `docker compose -f docker-compose.prod.yml restart backend`, or that host-run dev logs land in logs/backend.log (scripts/dev.sh line 91), or that there are cheap health endpoints beyond the one curl — /api/system/health/live and /health/full exist (backend/api/routes/system.py lines 320-321), and AI health is at http://localhost:8090/health and http://localhost:8091/health (the compose healthchecks).
  - **Fix:** Add a "First five minutes at 2am" block: status (`podman ps -a` / `docker compose -f docker-compose.prod.yml ps`), logs (`docker compose -f docker-compose.prod.yml logs --tail=50 <service>`; per-container `podman logs <name>`), restart (`docker compose -f docker-compose.prod.yml restart <service>`), and a health-URL list (backend /api/system/health/live, /health/full; gateway :8090/health; LLM :8091/health), with a pointer to docs/operator/service-control.md.
- **[minor]** The only port map in the README is the line "| **Open Ports** | 8444/8080 (UI HTTPS/HTTP), 8000 (API), 8090/8091 (AI gateway/Nemotron) |" (line 237) — buried inside the collapsed `<details> Hardware Requirements` block (opens line 208), invisible until expanded, and incomplete: it omits Grafana 3002, Prometheus 9090, Alertmanager 9093, Loki 3100, Tempo 3200, Pyroscope 4040, go2rtc 1984/8555, Postgres 5432, Redis 6379, gateway metrics 8002, and never says which ports are 127.0.0.1-bound vs the UI's 0.0.0.0 (docker-compose.prod.yml lines 779-780) — a distinction the Security Model section's "trusted LAN" claim depends on.
  - **Fix:** Move a complete port table out of the collapsed hardware details into the proposed Operations & Monitoring section (or link docs/operator/README.md's port table, line 232), marking bind addresses explicitly.
- **[minor]** Lines 264-266 Verify block: "open http://localhost:8080 # Dashboard (HTTP)" and "# Or: open https://localhost:8444 # Dashboard (HTTPS; enable with SSL_ENABLED=true)" — after Quick Start step 1, setup.py writes SSL_ENABLED=true into .env (setup.py line 469), so on the standard path nginx replaces the HTTP locations with a 301 to https://<host>:8444 (frontend/docker-entrypoint.sh lines 291-293, 392-399) using an auto-generated self-signed cert — a warning the README gives only for the dev Vite cert (line 293-294), not here. Conversely "enable with SSL_ENABLED=true" describes it as opt-in while the just-generated .env already enables it.
  - **Fix:** Reword to: after setup.py HTTPS is on by default (self-signed cert — accept the browser warning); http://:8080 301-redirects to https://:8444; set SSL_ENABLED=false to serve HTTP only.
- **[minor]** Line 270 "(the API returns 503 for everything except setup and health until you do)" and line 395-396 restate SetupGuard as absolute, but backend/api/middleware/setup_guard.py (lines 49-79) also whitelists /docs, /redoc, /openapi.json, /api/metrics, /api/system/gpu, /api/system/stats, /api/system/telemetry and /ws/\* — so "everything except setup and health" misleads a reader debugging, e.g., why Prometheus still scrapes or WebSockets still connect pre-registration, or why /docs answers.
  - **Fix:** Change to "503 for everything except setup, health/metrics probes, API docs (/docs, /openapi.json) and WebSockets — see SetupGuardMiddleware's whitelist".
- **[minor]** Line 257 comment "# 3. Start everything (this project uses Podman; plain `docker compose` works too)" — docker-compose.prod.yml relies on Podman-isms: CDI devices `devices: nvidia.com/gpu=all` / `nvidia.com/gpu=${GPU_LLM:-0}` (lines 139, 303, 1251) and the `:U` volume flag (line 383). Plain Docker needs Docker ≥25/Compose ≥2.24 with an nvidia CDI spec present; on an older host `docker compose up -d` fails at ai-llm/ai-gateway with a device error — exactly the wall a panicked 2am operator hits.
  - **Fix:** Qualify: "plain docker compose works on Docker ≥25 with the NVIDIA CDI spec (nvidia-ctk cdi generate); podman-compose is the tested path."

> Lens notes: Lens: ops on-call at 2am. I attempted every command and URL the README offers and grep-checked all concrete claims. What HOLDS UP: all 34 referenced file paths exist; /api/system/health, /api/system/models(/<name>/status|load|unload) route prefixes are real (backend/api/routes/model_management.py prefix /api/system/models); the four /api/analytics/\* endpoints exist; the \"core services\" up command names are all valid compose services; \"21 (19 run by default; ai-llm-vllm and dcgm-exporter need a profile)\" is exactly right; \"~49 GB (sum of deploy.resources.limits.memory...)\" sums to 48.9 GB

## Round 2 — fix wave (2 agents, 20 edits) — flagged / declined items

### r2fix:1

- **Audit item 9 ('Host-run AI servers', blocker) — partially wrong; applied only its verified core**
  (a) 'the YOLO26 value is missing the router suffix' is false for this section's target: the host-run detector (ai/yolo26/model.py) serves /health and /detect at root; the /yolo26 prefix exists only on the gateway, whose adapter has no /health route — adding the suffix as instructed would break the host-run recipe the section documents (correct shape is docs' `.../yolo26` only for the gateway hostname). (b) 'FLORENCE_URL/CLIP_URL/ENRICHMENT_URL silently fall back to config defaults for services that no longer exist' is wrong under compose: docker-compose.prod.yml hardcodes all of them to ai-gateway routes (lines 454-460); the dead-defaults failure only applies to a shell-exported (host-run) backend, which the corrected text now covers explicitly. (c) enrichment_light_url default is localhost:8096, not 8094. The valid core (host.docker.internal doesn't resolve on Linux hosts; exports never reach the backend container) was applied.
- **Audit item 12 (Containers/RAM miscount) — auditor's numbers wrong; text left**
  Re-measured from the compose file: 21 services defined (not 19); the two profiled ones are ai-llm-vllm and dcgm-exporter, so 19 start by default — the README's existing 21/19/2 is right and the suggested '19 defined / 17 default' would introduce an error. deploy.resources.limits.memory sums to exactly 49.0 GB across default services (73.0 GB including profiled), so the '~49 GB (sum of limits...)' parenthetical is accurate and was kept; only a verified foscam-init clarification was added.
- **Audit items 3/8 and 4/8 were duplicate pairs**
  Each pair applied once against the live file: step 3 inverted to podman compose with the podman-only-keys caveat (3+8) and the PODMAN_SOCKET note with the socket-enable recipe (4+8). Kept `podman compose ... up -d` rather than `python setup.py deploy` as step 3 since a reader who completed setup.py never needs step 3 — the note now says so.
- **README.md was concurrently modified on disk mid-task**
  A parallel doc pass landed while I was editing (new Operations/Model-Status-API sections, reworked Configuration table). I re-read the current file before content-dependent edits; all listed corrections were applied against the live content, and the Operations block's `docker compose` usages were converted to podman as part of item 3. No git operations performed.

### r2fix:2

- **README 'Tesla T4' GPU-compatibility row — auditor is WRONG, text left as-is**
  Repo ground truth says Turing IS a supported target: ai/nemotron/Dockerfile:44,46 documents building llama.cpp for CUDA arch 75 (T4/RTX 2080) and defaults to 75,80,86,89; docs/operator/gpu-setup.md lists RTX 20xx and Tesla cards as supported at CUDA CC 7.0+; ai/yolo26/build_engine.py maps sm_75: RTX 2080 / T4. No bf16/NVFP4 requirement exists in the tree — bf16 is an optional guarded fallback (is_bf16_supported() in ai/torch_optimizations.py:544 and the florence2 Triton model). Caveat I could not verify locally: whether Triton 26.01 (ai/gateway/Dockerfile) still supports sm_75 at runtime.
- **README 'VRAM Budget table contradicts its own hardware table / AGENTS.md:456' sub-claim**
  No actual contradiction found: the 8–12GB minimum, 16GB recommended and 24GB optimal tiers match docs/\_includes/vram-requirements.md verbatim and the hardware/GPU-compatibility rows describe the same degraded modes; AGENTS.md:456 is the legacy-port note, unrelated. Left as-is.
- **~42GB attribution in the finding**
  Partially wrong: the finding attributed the extra ~8GB to 'legacy CLIP-ViT-L/FashionCLIP clones the script still pulls', but fashion-clip IS in models.yml (size_mb 4400) and florence-2-large too (3000, disabled). Only clip-vit-large-patch14 (~1.7GB) is pulled outside models.yml; the remainder of the script header's ~42GB is Git-LFS working-tree overhead/rounding. README wording reflects the corrected attribution.
- **Feature-table status split (implemented/partial/planned) — not applied**
  The correction offered de-dup OR status-split. De-dup applied (verified anchors). A status split would require per-row implementation status I could not establish from the tree without guessing — inventing statuses would be worse drift.
- **Concurrent workspace activity during the task**
  README.md and several docs were modified/staged by another process mid-task (e.g., ~33GB download figures, TIP rewording, docs/plans/2026-09-22-docs-scan-findings.md which contains this finding list). All findings were re-verified against the live tree and all my edits coexist with the concurrent changes; final state passes both Prettier versions and the mkdocs build. No git operations performed by me (read-only status/diff/show only).

## Round 2 — closing notes (verifier-checked)

- **`check_paths: true` is now enabled and the strict build passes.** (Measured at round-2 close the
  warning set was identical to `HEAD` — 69 vs 69, both diff directions empty; the final
  post-wave-3 delta is recorded below.) The warnings are three
  pre-existing structural classes, each needing an owner decision rather than a link edit:
  (1) links out of the docs site to repo paths (`../../ai/gateway/AGENTS.md`,
  `../../../backend/services/AGENTS.md`, `../../CHANGELOG.md`, `.py`/`.ts` sources) that resolve on
  GitHub but can never resolve inside the site; (2) `README.md`-vs-`index.md` exclusion collisions
  (`docs/README.md`, `reference/troubleshooting/README.md`); (3) `architecture/templates/*`
  placeholder links, which are template examples by design.
- **Final mkdocs warning delta (branch vs main, verified via parallel worktree builds):** 69 → 66.
  **9 fixed** — all four `../README.md` "Back to Docs Index" collisions (now `../index.md`) and the
  three `CLAUDE.md` dead-link warnings (repointed to `AGENTS.md`, which resolves on GitHub).
  **6 new, same class:** agents documenting the consolidated gateway honestly added repo-path links
  (`../../ai/gateway/AGENTS.md` ×4, and `../../AGENTS.md`/`../../../AGENTS.md` root-file links from
  `developer/contributing/*` and `AGENT_COORDINATION.md` after the CLAUDE.md repoint) — these
  resolve on GitHub and can never resolve inside the docs site; they join the standing structural
  class above rather than being churned away.
- **`docs/reference/` was NOT fully swept.** The reference-user auditor exhausted its budget after
  verifying anchors and fully auditing `reference/config/env-reference.md`; **19 of 27 files in the
  zone remain unread** (its flag list names them). Its 35 flags for `env-reference.md` are exact and
  mechanical to apply — ~20 wrong defaults, ~10 variables that do not exist in
  `backend/core/config.py` at all, a dead `YOLO26_URL:8095` row, a dead `FRONTEND_PORT` row, the
  empty `Service Timeouts` heading whose table is misparented under `Florence Circuit Breakers`,
  and a missing `ENRICHMENT_LIGHT_URL` row. **Follow up here first** — it is the largest known
  unfinished area and needs no re-derivation.
- **`models.yml` lives at the repo root, not `ai/models.yml`** — flagged as a trap likely to bite
  other doc zones.

## Wave 3 — reference-zone closeout (5 agents)

Applied all 35 `sweep:reference-user` flags to `env-reference.md` (fabricated vars replaced or deleted with honest notes; every value re-grepped against config.py validation_alias/env_prefix) and completed the first-ever audit of the 19 files that auditor never reached.

### fix:env-reference — flagged / owner-queue items

- **Admin gating code-comment drift: backend/core/config.py comment says 'Admin endpoints require BOTH debug=True AND admin_enabled=True' but require_admin_access (backend/api/routes/admin.py) checks admin_enabled only; docs annotated honestly per the wrong-in-code rule**
  Docs must not pretend the DEBUG pairing is enforced; the code comment is misleading and the effective default is ADMIN_ENABLED=true with 127.0.0.1 binding as the boundary — owner should reconcile the comment (and possibly the posture) with the dependency
- **CTX_SIZE split-brain: compose passes CTX_SIZE=262144 only to the ai-llm container; the backend never receives it (no env var, no .env mount in the compose backend block), so backend nemotron_context_window stays 32768 while llama.cpp actually runs 262144**
  The validation_alias makes CTX_SIZE the 'single source of truth', but the two consumers disagree in deployment; whether the backend's truncation budget should track llama.cpp's real context is a design ruling, not a docs fix
- **docker-compose.prod.yml:28 header comment still documents FRONTEND_PORT as 'Host port for frontend HTTP (default: 5173)' while the ports block uses FRONTEND_HTTP_PORT/FRONTEND_HTTPS_PORT; .env.example:1012 likewise still ships FRONTEND_PORT=5173**
  Dead-but-documented variable outside this task's file set; code-side fix needed so the compose header comment and .env.example stop resurrecting the var the docs just marked dead
- **Prior-flag carry-over: docs/reference zone still has 19 unread files flagged by sweep:reference-user (models.md, troubleshooting/\*, glossary.md, LOAD_PROFILES.md etc.) — not assigned to this fix pass**
  Zone cannot be marked done until those are read; listing preserved for the orchestrator
  _(ERRATA, wave-3 close: this flag was stale — the fix agent read only its own assignment brief,
  not the orchestrator's plan. All 19 files WERE read and audited by the four parallel wave-3 sweep
  agents dispatched in the same workflow; the zone is closed. Cross-agent flags naming specific
  files (e.g. troubleshooting README `start-ai.sh` / retired-service drift) were fixed in place by
  the sweep that owned each file — spot-verified clean after all sweeps landed.)_
- **MISSING (flag only, not created): a compose-service -> host-port mapping table in docs/reference/config/ (compose service ai-llm vs 'Nemotron llama.cpp :8091' prose)**
  Per MISSING rule: flag, do not create
- **.env.example:871-873 still ships JAEGER_UI_PORT/JAEGER_OTLP_GRPC_PORT/JAEGER_OTLP_HTTP_PORT although Jaeger is retired (prior anchor: Tempo :3200/:4317)**
  Outside assigned file; recorded in the findings file already — owner queue for .env.example cleanup

### sweep:config-triage — flags

- _\*Severity thresholds: cross-field ordering (low<medium<high) is validated only when SeverityService is first constructed (lazy, @lru_cache — first classification or /api/system/severity), not at startup; a misordered SEVERITY\_\_ config passes get*settings() and Settings construction and blows up later as a ValueError at an arbitrary request site*_
  Doc (risk-levels.md) claimed startup failure; code is arguably the broken side — config.py has no model_validator for the ordering constraint (it does have the pattern: validate_violence_thresholds). Docs now describe actual behavior; owner may want to add a Settings model_validator so the original fail-fast intent holds
- **docs/reference/troubleshooting/index.md (not mine) still instructs 'Run alembic migrations: docker compose -f docker-compose.prod.yml exec backend alembic upgrade head' and similar in ~3 places**
  Dead procedure — no alembic.ini or migrations tree exists in the repo (removed PR #4465); following it fails. Needs the index.md-zone agent
- **docs/reference/troubleshooting/README.md (not mine) still shows YOLO26 :8092, Florence :8093, CLIP :8094 and tells readers to use ./scripts/start-ai.sh and 'optional' standalone services**
  Ports belong to standalone dev servers that compose never starts; start-ai.sh wrapper was removed (docs/operator/ai-services.md:18). Zone owner should align with ai-issues.md
- **docs/reference/troubleshooting/AGENTS.md (not mine) still cites curl http://localhost:8095/health (lines ~66, ~217) and ./scripts/start-ai.sh (line ~63)**
  8095 was the retired standalone YOLO26 service port (start_detector.sh uses 8090; gateway serves YOLO26 at :8090/yolo26); wrapper removed
- **docs/reference/README.md, docs/reference/models.md, docs/reference/getting-started.md (not mine) still document port 8095 as live YOLO26 and YOLO26_URL=http://ai-yolo26:8095**
  8095 exists nowhere in docker-compose.prod.yml or config defaults (.env.example ships YOLO26_PORT=8095 but the compose stack routes YOLO26_URL=http://ai-gateway:8090/yolo26)
- **backend/services/service_managers.py ALLOWED_RESTART_SCRIPTS includes scripts/restart_yolo26.sh and scripts/restart_nemotron.sh, but neither file exists on disk**
  AI_RESTART_ENABLED auto-recovery would invoke allowlisted-but-missing scripts and fail — dead code path; owner decision whether to restore scripts or drop the entries
- **Host-run fallback ./ai/start_llm.sh expects ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf, which ai/download_models.sh never downloads and which is absent from the working tree**
  The documented dev-fallback LLM path is unusable without the manual wget documented only in docs/operator/ai-installation.md:230-236; either download_models.sh should cover it (optional flag) or docs should stop presenting start_llm.sh as ready-to-run

### sweep:user-ref — flags

- **frontend/src/components/common/CommandPalette.tsx:93 and frontend/src/hooks/useKeyboardShortcuts.ts:28 both navigate to /system, which no longer exists in the app router (page now at /operations, sidebar 'Pipeline'). Docs describe the code faithfully; the code is the broken side — one-line fixes in both files, then remove the two 'Known issue' notes added to keyboard-shortcuts.md and accessibility.md.**
  Wrong-in-code: user-visible dead navigation from two shipped features (command palette entry and g y chord); not a docs-only fix
- **docs/reference/stability.md Entities 'WIP' rating itself looks stale: the page renders no WIP badge and docs/ui/entities.md documents a fully featured page (grid, filters, trust statuses, detail modal). Owner should decide whether to promote it to Beta/Stable rather than keep the WIP rating that no longer matches the UI.**
  Doc claim may be outdated in a judgment direction I cannot make unilaterally — stability ratings are an owner call
- **frontend/src/components/layout/AGENTS.md:286 still says 'Badge rendering (WIP on Entities)' referencing a badge that no longer exists in the sidebar.**
  Stale claim found while verifying, but outside my assigned files — flagging for whoever owns frontend AGENTS.md files
- **docs/developer/redis-key-conventions.md still documents hsi:queue:detection_queue (Redis list) as the main processing queue, while the pipeline actually runs on streams (detections:stream / analysis:stream). The list API survives for degradation-fallback and admin paths, so the doc is half-true; worth a pass by the developer-docs owner.**
  Related inconsistency noticed during verification; outside my assigned file set

### sweep:hubs-nav — flags

- **backend/api/routes/system.py:3085 get_telemetry (and queue_status_service) report queue depths via LLEN on raw 'detection_queue'/'analysis_queue' list keys, but the pipeline writes to Redis Streams 'detections:stream'/'analysis:stream' by default (use_redis_streams=True default in backend/core/config.py:2104, never overridden in compose).**
  WRONG IN CODE: /api/system/telemetry almost certainly returns 0/0 on a default streams-mode deployment even under heavy backlog, while every troubleshooting doc tells operators to use it as the primary backlog check. Docs now note the streams keys explicitly, but the endpoint itself should be fixed to XLEN the stream keys (or the code change coordinated); docs left describing the endpoint as designed rather than rewritten to hide the defect.
- **YOLO26_PORT is inconsistent across three owners: ai/start_detector.sh defaults to 8090, .env.example ships YOLO26_PORT=8095, and backend config health-check default is 8095.**
  Code-level inconsistency (flagged in docs/operator/ai-configuration.md:22 too). Docs now annotate both spellings where operators would hit the mismatch, but one canonical value should be chosen by the owner.
- **scripts/smoke-test.sh:162 and :510 still instruct './scripts/start-ai.sh start/status'; docs/operator/ai-services.md:182 mentions /tmp/yolo26-detector.log 'when launched via the old wrapper'.**
  The wrapper script was removed (confirmed absent from scripts/); these references live outside my assigned files (scripts/ and docs/operator/), so I fixed only my six files and am queueing the rest.
- **.env.example:1012 still ships FRONTEND_PORT=5173 although docker-compose.prod.yml never reads it.**
  Already flagged as dead in docs/reference/config/env-reference.md:753 (another agent owns that file). My README/troubleshooting edits consistently treat 8080/8444 as the real host ports; the .env.example line itself needs an owner decision to remove or repurpose.
- **docs/reference/troubleshooting/README.md 'GPU Not Detected' still uses `docker run nvidia/cuda:11.8.0-base-ubuntu22.04` as the container-GPU smoke test.**
  Left as-is deliberately: the project targets CUDA 12.0+ and Podman-first (CDI specs), and a correct rewrite duplicates docs/operator/gpu-setup.md; a modernization would be nice but nothing in the six files is factually wrong from it. Owner may want to bump the image tag.

### sweep:models-nvidia — flags

- **models.yml `depth-anything-v2-tiny`: name/local_path say Tiny, hf_repo points at Depth-Anything-V2-Small**
  Manifest self-contradiction — owner must pick the real repo; doc now annotates the mismatch in both files.
- **ai/download_models.sh still fetches first-generation models (florence-2-large, clip-vit-l, patrickjohncyh/fashion-clip, lxyuan vehicle) that models.yml replaced (Base, SigLIP 2, Marqo FashionSigLIP, AventIQ vehicle)**
  Two download paths disagree; outside assigned files, docs now label the script as legacy.
- **ai/clip/AGENTS.md line 73 says base image tensorrt:26.01-py3 while ai/clip/Dockerfile line 12 builds 26.08-py3 (likely same drift in ai/yolo26 docs)**
  26.01->26.08 bump (commit c1128110) missed those AGENTS.md files; they are outside my assignment.
- **docker-compose.prod.yml line 337 health comment "Triton loads 13 models" vs 15 model directories actually loaded**
  Stale comment in compose; doc notes it, fix belongs to compose owner.
- **ai/triton/model_repository/xclip_action ships and loads at startup (model-control-mode=none) despite models.yml enabled:false (X-CLIP deprecated)**
  Disabled model consumes A400 VRAM in production; needs owner decision to remove dir or gate it.
- **monitoring/prometheus.yml.template still targets removed standalone containers (ai-yolo26:8095, ai-florence:8092, ai-clip:8093, ai-enrichment:8094, ai-enrichment-light:8096) for metrics and health probes**
  Live prometheus.yml removed them; the template would reintroduce dead probes — outside my files.
- **inference-api.nvidia.com exists only as a literal in scripts/generate_videos.py and scripts/synthetic/media_generator.py; docs previously credited it to generate_architecture_images.sh, which actually invokes a local nvidia-image-gen Claude skill**
  Doc-only endpoint claim corrected here; script/doc split may confuse owners.
- **docs/reference/benchmarks/yolo26-performance.md tables (5-6ms class numbers, FPS 170-200, multi-GPU scaling) are not reproducible with the scripts the page itself lists**
  Curated TensorRT-era results vs current .pt-based tooling; provenance note added, but a re-run on the GPU box (currently offline for CI) is the real fix.
- **Q4_K_M GGUF size "~9.5 GB" appeared in multiple docs; models.yml size_mb: 15073 (~15 GB) is authoritative**
  Fixed in both my files; any occurrence elsewhere needs the same correction.
- **setup_lib/nvidia_detect.py comments still say 'CUDA 13.1'/'13.1.1' while ai-llm builds on CUDA 13.3.1**
  Code-comment drift; driver minimum 580 covers 13.x so behavior is fine — doc wording generalized, code comment fix is outside my files.
