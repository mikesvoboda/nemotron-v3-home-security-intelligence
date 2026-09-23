# archive/

Staging area for artifacts judged **not load-bearing** by the 2026-09-21
directory-structure cleanup (audit + adversarial refutation, branch
`chore/artifact-cleanup`) that the owner has not yet signed off on deleting.
Nothing here is referenced by code, CI, or compose; items were moved with
plain `mv` and Git records the rename at commit (rename detection preserves
history). A later, deliberate pass deletes from here once each item is
confirmed dead-on-the-owner's-desk.

| Item                     | What it is                                                                                     | Pending ruling                        |
| ------------------------ | ---------------------------------------------------------------------------------------------- | ------------------------------------- |
| `wp25-feed/`             | Prior agent's WP4.3/4.4 handoff + memory + triage evidence (23M, incl. 20M wp44-triage output) | delete wholesale?                     |
| `vsftpd/`                | FTP decoy-server container config; README targets a `docker-compose.yml` that no longer exists | keep as demo asset, or delete?        |
| `test_setup*.py`         | Root-level setup-script tests; outside pytest `testpaths` (never runs in CI)                   | wire into testpaths or delete?        |
| `.eta.py` + 3 dot-files  | WP4.3/4.4 mutation-triage one-off scripts (were dot-prefixed in scripts/)                      | delete?                                |
| `docs-reports/`          | Three one-session reports (load-test, network-health, 2026-02 doc review)                      | delete?                                |

### Pass 2 additions (same audit, later session, 2026-09-21)

| Item | What it is | Pending ruling |
| --- | --- | --- |
| `package-lock.json` | Root JS lockfile — no CI job installs root deps (all `npm ci` run `working-directory: frontend`); stale vs package.json; legacy setup-hooks.sh path installs it | delete, or keep for local commitlint dev? |
| `Dockerfile.yolo26-benchmark` | Benchmark image build, base pinned tensorrt `24.09-py3` (two generations behind live 26.08); doc-prose citations only | delete, or refresh base? |
| `scripts/` (11 files) | One-off probes/migrations with zero consumers: deprecated e2e runner, GPU/context probes with hardcoded dev paths, superseded `download_models.sh` (live twin: `ai/download_models.sh`), NEM-3262/3339 one-time scripts, orphaned quickstart | delete? |
| `docs-media/` | VEO3 video-generation helpers (mascot/hype content, not security); live path is scripts/synthetic_data.py | delete? |
| `../docs/archive/` | 29 point-in-time docs (gap reports, TDD red-phase snapshots, NEM-numbered one-offs, metrics snapshots, 4.3MB unreferenced Grafana screenshots) | delete wholesale? |

### Gateway-consolidation follow-up additions (2026-09-22, PR-A)

| Item | What it is | Pending ruling |
| --- | --- | --- |
| `triton-model-repository/xclip_action/` | Retired X-CLIP action-recognition Triton config + model.py (migration to stgcn_action complete; models.yml keeps the provenance entry — runtime-default patch16-16-frames vs patch32 disk question still open) | delete with the provenance entry, or keep until provenance ruled? |
| `monitoring-elasticsearch/` (ilm-policy, index-template) + `scripts/init-elasticsearch.sh` | Elasticsearch log-backend leftovers; Tempo replaced the Jaeger+Elasticsearch tracing/logging stack (NEM-5545) and nothing mounts them | delete? |
| `prometheus.yml.template` | envsubst template with zero consumers (live configs are the compose-mounted files) | delete? |
| `scripts/download_models.py` | Superseded Python downloader; live twin `ai/download_models.sh` re-derived from the setup_lib rule | delete? |
| `scripts/setup_docker_override.py` | `generate_docker_override_content()` extracted from setup.py: setup.py no longer writes docker-compose.override.yml (.env is sole config truth) and the table targeted pre-consolidation containers/ports. NOTE: `test_setup.py` (this tree) imports it and stays ImportError-stale either way | delete with `test_setup*.py`? |

### PR-C additions (2026-09-23) — monitoring round-2 + X-CLIP retirement

| Item | What it is | Pending ruling |
| --- | --- | --- |
| `ai-enrichment/` (`action_recognizer.py` + `test_action_recognizer.py`) | The X-CLIP `ActionRecognizer` (537 lines) and its test suite (8 classes / 29 tests), retired by the NEM-5563 migration to skeleton-based Triton `stgcn_action`, which the gateway's `/action-classify` adapter serves today. Both files are byte-identical to the removed `ai/enrichment/` originals, so Git rename-detects them at commit and history survives the move. Nothing collects them: pytest `testpaths` is `backend/tests`, `ai/*/tests`, `ai/*/test_*.py`, `setup_lib/tests` — `archive/` matches none. Live references swept 2026-09-23 (docs-and-critic-misses repair pass): the `action_recognizer` entries in `backend/core/security.py` `ALLOWED_PRELOAD_MODELS` and `backend/evaluation/combined_dataset.py` removed with archive-pointer comments, and `ai/enrichment/tests/AGENTS.md` annotates the moved suite. `models.yml` keeps the `xclip-base` entry (`enabled: false`, `triton_name: xclip_action`) — owner-owned, untouched | delete with the `xclip-base` provenance entry? |
| `prometheus_rules.yml.template` | Rules-template clone with zero consumers (grep: nothing reads, mounts, or envsubsts it; compose bind-mounts the live `monitoring/prometheus_rules.yml` directly). Its own header lied: "processed by envsubst at container startup, do not edit the live file" — no launcher ever did. Content is a byte-identical clone of the live `monitoring/prometheus_rules.yml` except one stale `${GRAFANA_PORT}` placeholder, so it invites silent drift; retire, don't repair. Both files carry 20 literal `- alert:` lines but 18 active alerts (`promtool check rules` on each: SUCCESS, 18 rules — `AINemotronTimeout`/`AIDetectorSlow` are commented out in both) | delete? |

### Backend X-CLIP chain retirement (owner ruling 2026-09-23, full removal)

| Path | Original location | Why archived | Date |
| --- | --- | --- | --- |
| `xclip-backend-chain/xclip_loader.py` | `backend/services/xclip_loader.py` | Backend X-CLIP model loader (HF load + process batch) — the NEM-5563 ST-GCN++ skeleton path (gateway `/action-classify` adapter) replaced inference; its two label heuristics (`is_suspicious_action`, `get_action_risk_weight`) were relocated verbatim into `backend/services/enrichment_pipeline.py` because they score ST-GCN++ and remote-service labels too | 2026-09-23 |
| `xclip-backend-chain/action_recognition_service.py` | `backend/services/action_recognition_service.py` | X-CLIP recognition service + the CRUD helpers its `analyze_frames` entrypoint wrapped; route CRUD was inlined into `backend/api/routes/action_events.py` as plain DB queries. Side effect a monitoring pass should note: it defined and emitted the `hsi_action_detections_total`/`hsi_action_confidence`/`hsi_action_corrections_total` FED family, and its retirement leaves those with zero emitters (dashboard feed gaps already annotated in PR-B) | 2026-09-23 |
| `xclip-backend-chain/test_action_recognition_service.py` | `backend/tests/unit/services/test_action_recognition_service.py` | Unit suite for the archived service; route behavior is covered in place by `backend/tests/integration/test_action_events.py` (which now pins the removed analyze endpoint at 405), model behavior by the surviving `backend/tests/integration/test_action_event_model.py` | 2026-09-23 |
| `xclip-backend-chain/test_xclip_loader.py` | `backend/tests/unit/services/test_xclip_loader.py` | Loader/keyword-heuristic unit tests; the heuristics' contracts are exercised transitively through the pipeline tests they moved with | 2026-09-23 |

The consumer half of this chain went the same day: the
`POST /api/action-events/analyze` endpoint (owner ruling: "Full removal, API
change included" — an approved breaking change, label the PR
`breaking-change-approved` for `api-compatibility.yml`), the `ActionAnalyze*`
schemas, the `model_zoo.py` `xclip-base` loader entry, the `xclip-base`
`HEAVY_MODELS` lane and model-category row, and the deprecated pipeline
fallback (`_recognize_actions`/`_safe_recognize_actions`). `models.yml` keeps
the `xclip-base` provenance entry (`enabled: false`) — owner-owned, untouched.

### Standalone yolo26 GPU image retirement (owner ruling 2026-09-23)

| Path | Original location | Why archived | Date |
| --- | --- | --- | --- |
| `ai-yolo26-image/Dockerfile` | `ai/yolo26/Dockerfile` | Owner ruling "Retire image fully": Triton on ai-gateway serves yolo26 (one of the 14 models) and the compose stack has no yolo26 service; deploy.yml build/merge/sbom/provenance matrices and the dependabot docker entry removed the same day. Recipe kept for reference (header annotated with the retirement) | 2026-09-23 |
| `ai-yolo26-image/requirements.txt` | `ai/yolo26/requirements.txt` | Image-only dependency manifest — the sole consumer was the Dockerfile's `uv pip install -r`; the kept repo-side modules resolve through the root project env, not this file | 2026-09-23 |
| `ai-yolo26-image/export_tensorrt.py` | `ai/yolo26/export_tensorrt.py` | INT8/FP16 engine-export CLI for the image era; nothing imports it (its only invocations were prose in the also-archived `ai/yolo26/README.md`). The live export path is `ai/gateway/export/export_yolo26.py` + `export_all.sh` (gateway-era, models.yml-driven) and `ai/yolo26/build_engine.py` stays for `scripts/prebuild-tensorrt-engines.sh` | 2026-09-23 |
| `ai-yolo26-image/README.md` | `ai/yolo26/README.md` | Build/run/API documentation for the retired server (pip-install the image reqs, build the image, port 8095); production request shapes are owned by the gateway adapter contract. Kept as the historical runbook — `ai/yolo26/AGENTS.md` now points here | 2026-09-23 |

NOTE: `ai/yolo26/` itself is NOT archived. `contract.py` is the live pure leaf
`backend/services/prompts.py` imports at runtime, and `model.py` +
`pose_estimation.py` are AST-read by the AI-contract conformance tests in
`backend/tests/contracts/ai_providers/` (SECURITY_CLASSES, class thresholds,
KEYPOINT_NAMES, classify_pose, /track deletion markers) — they stay in place.

### Treatment of this tree (pass 2 ruling, 2026-09-22)

Archived artifacts are frozen content, not active source: the mutation-triage
evidence rule first written for `.wp25-feed/` was widened to the whole
`archive/` tree in `.pre-commit-config.yaml`, `.prettierignore`, and the ruff
`exclude` in `pyproject.toml`. Nothing here is linted, formatted, parsed, or
secret-scanned on commit — and nothing here is load-bearing for CI (the whole
point of the pass-2 CI run is to prove exactly that).
