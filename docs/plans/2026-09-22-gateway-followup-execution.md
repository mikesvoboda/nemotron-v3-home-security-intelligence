# Gateway-consolidation follow-up — execution plan (PR-A / PR-B)

Status ledger for executing the owner rulings on the #6640 findings queue. Rulings
themselves are recorded in `docs/plans/2026-09-22-docs-scan-findings.md` (the queue)
and in agent memory (`docs-scan-followup-rulings-2026-09-22`). This file is the
**live checklist**: update the checkboxes as things land. Packaging ruling: PR-A =
all code/config, PR-B = all docs, sequential, each green before the next.

## PR-A — branch `fix/gateway-consolidation-exec` (off `gh/main` @ 5d2ed562)

### Workflow wave 1 (run wf_df282afc-ac4) — 10 fixers + adversarial verifiers

| item                          | what                                                                                                  | state                                                                                                                                                                                                                                                                                              |
| ----------------------------- | ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| fix:dead-code                 | request_timing.py deleted; allowlist trim; init-elasticsearch.sh → archive/; compose header 5173→8080 | ✅ verified sound                                                                                                                                                                                                                                                                                  |
| fix:backend-micro             | admin.py 7× docstring myth corrected (comment-only)                                                   | ✅ verified sound                                                                                                                                                                                                                                                                                  |
| fix:ghcr                      | compose + deploy.yml current (gateway/tempo/alloy/8444)                                               | ✅ verified sound                                                                                                                                                                                                                                                                                  |
| fix:config-env                | config.py gateway URLs + DEPRECATED marks; setup.py generator; .env.example prune; dev.sh 8444        | ⏳ verify pending                                                                                                                                                                                                                                                                                  |
| fix:monitoring                | probes/rules/dashboards retargeted; GPUOOMCritical deleted; ALERT-REG-005 chain repaired              | ⏳ verify pending                                                                                                                                                                                                                                                                                  |
| fix:stgcn                     | adapter = pose→stgcn skeleton pipeline; NTU-60 labels; repo dir added                                 | ✅ verify found top-person argmax defect → fixed inline (confidence now carried per detection + argmax + 2-person regression test; gateway suite 230 pass)                                                                                                                                         |
| fix:model-mgmt / fix:ctx-size | chain after config-env                                                                                | ✅ both closed (ctx-size verify sound; mm-health follow-up verify **sound** — root-/health union lands, siglip2/stgcn-plus-plus honest loaded=True, warn-on-drift, no ModelManager fallback for gateway-served, zero egress for backend-process models; 37 unit + 2758 dir + 17 integration green) |
| fix:catalogue                 | download_models.sh re-derived; scripts/download_models.py → archive/; README 3× ~29.3GB               | ✅ verify:catalogue **sound** (all HF URLs reachable, 29.34 GiB math re-derived, prettier@CI-version clean) — but **superseded by owner ruling** → re-derive to setup_lib rule (dispatched, below)                                                                                                 |
| fix:chaos                     | serial-hang repro + root cause                                                                        | ✅ verify:chaos issues = the two doc claims (xreadgroup=[] "fix", pytest-timeout "never fired") — **both already fixed inline** before the verdict landed; core fix re-verified green serial+parallel by the verifier independently                                                                |
| verify:ctx-size               | —                                                                                                     | ✅ **sound** — end-to-end (unset→32768, 262144→32768, PARALLEL=2→131072, clamps). New flag: **docker-compose.ghcr.yml:170 CTX_SIZE:-4096, zero PARALLEL, backend gets neither** → slot-budget 8× wrong on ghcr stack                                                                               |

Chaos pending OWNER decisions (kept out of agent scope): (a) defensive `asyncio.sleep(0)` at
pipeline_workers.py:414/:936 empty-read; (b) validate.sh R-T7-POISON-CASCADE + nightly
--ignore chaos now rest on a false "xdist-unsafe" premise — re-include or keep excluded.

Results live in the workflow journal:
`~/.claude/projects/-agents-agent-veranda-workspace/8bb05b15-*/subagents/workflows/wf_df282afc-ac4/journal.jsonl`
(label join via `started` lines).

### Held-batch wave (run wf_52e54ad2-86e) — unblocked once config.py/compose owners drained

6 fixers + adversarial verifiers, disjoint scopes: **mm-health** (model_management.py
root-/health union — siglip2 [clip,clip_text] + stgcn-plus-plus [stgcn_action] appear in NO
router payload → permanently loaded=False; union root+router readiness, warn on
found-nowhere, de-mask unit fixtures that omit both models), **config-severity** (severity
startup model_validator mirroring validate_violence_thresholds + admin-myth comment
reconciliation :863-864/:871-874 + two ctx-size comment nits), **compose-parity** (prod: 3
missing rule-file mounts; ghcr: CTX_SIZE/PARALLEL to backend matching its ai-llm pool),
**catalogue-r2** (setup_lib-rule re-derivation + README/llms.txt totals), **jaeger-smoke**
(tests/smoke TestJaeger → Tempo :3200 per platform-healthcheck.py:332).

### Follow-up batch (dispatch when the config.py chain fully drains — serial with chain owners to avoid edit races)

- [x] **compose parity (prod)** ✅ landed + verify **sound** (prod: 7/7 rule files mounted,
      `compose config` rc 0). **PARALLEL-default owner question RESOLVED by verify:compose-parity
      — NOT a divergence: ghcr ai-llm runs 2 slots by design (ai/nemotron/Dockerfile:100
      `ENV PARALLEL=2`, image-level; ghcr passes no override) and backend now derives
      4096//2=2048 correctly. No action.**
- [x] **compose parity (ghcr) + comment staleness** ✅ fixed inline after verify:compose-parity
      **issues**: ghcr prometheus mounted 4/7 rule files (same fatal-absent-file crash-loop as
      prod, pre-existing at HEAD) → 3 mounts added; monitoring/prometheus.yml RULE FILE MOUNTING
      comment updated to all-mounted. `compose config` rc 0 both files + rule-dir existence check.
- [x] **config.py severity startup validator** ✅ landed + verify **sound** (validator at
      config.py:3124-3160 mirrors the violence pattern; fail-fast reproduced; safety premise
      independently re-confirmed — zero SEVERITY*\* in any committed config AND both runtime
      writers pre-validate before persisting, so no stored state can trip it; 82+3804+338
      tests green). **New flag (PR-B / PR-body nuance): docker-compose.ci.yml:93 binds
      all-interfaces vs prod/ghcr loopback — the 127.0.0.1 network-boundary posture the admin
      comments now state is prod/ghcr-only; CI stack is exposed on the CI net (ephemeral;
      call out in the SECURITY-DOCS PR body, document in PR-B).** Original: mirror
      `validate_violence_thresholds`
      (config.py:2996 — ledger's "violation/~1757" both drifted). Fields :2288-2305.
      Real lazy check today: `SeverityService.__init__` services/severity.py:127-133 via
      lru_cache :385. No committed config sets SEVERITY*\* (verified) → fail-fast breaks
      nothing. Tests mirror violence-threshold tests in test_config.py.
- [x] **observability inline → delete request_logging.py** ✅ landed + verify **sound** (AST
      diff byte-identical inlined helpers; **init** trim was mandatory — it still re-exported
      the deleted request_timing; 15-of-18 test deaths authorized by ruling #7, 3 re-homed;
      717+23+3 green). Original text: inline `DEFAULT_EXCLUDED_PATHS` + `format_request_log` into observability.py:33-37 imports, trim `__init__` re-exports,
      delete module + its 18-test file. (Completes ruling #7a; request_timing already gone.)
- [x] **admin residual-myth sweep** ✅ landed + verify **sound** (live app.openapi() confirms
      7+7 new descriptions, 0 old strings; 401-unreachable premise swept exhaustively; three
      /users 401s correctly KEPT — auth.py:419-446 really raises; 165 tests green across the
      admin zones). New PR-B flags: **env-reference.md:527,529** also claims X-Admin-API-Key
      enforcement; **security.md:30** doubly-false (claims DEBUG=false closes admin endpoints).
      openapi.json/api.ts still carry the old strings until assembly regen (by design).
      Original: 403 `responses=`
      descriptions ×7 (admin.py:290,437,655,764,892,1056,1190 "Debug mode or admin not
      enabled"), sibling 401 "Admin API key required" descriptions (admin_api_key is never
      enforced), config.py:851-862 comments, tests/integration/test_http_error_codes.py:573.
- [x] **stgcn conformance re-shape** ✅ landed + verify **sound** (pins re-checked against
      adapter source incl. NTU index 42→falling→0.8; xclip_action dir archived byte-identical;
      ref sweep clean; re-shaped coverage, not deleted — anti-pin added). Two flagged reds
      dispositioned by orchestrator: (i) test_patch_triton_configs::TestModelsYamlConsistency
      (CI-RUN ai/gateway zone → **fixed inline**: name-pinned `deliberately_retired`
      exemption that still asserts the catalogue owner stays enabled:false — disabled-history
      is legal, silent drift is not; gateway suite 229 pass 1 skip); (ii) 5×
      ai/triton/tests/test_client.py KeyError:'output0' — HEAD-identical, zero xclip coupling,
      and ci.yml:1823-1827 records ai/triton as a **parked-red subtree excluded from CI run
      steps** (collect-only gate unaffected) → pre-existing ledger-classified state, no action.
      PR-B addition: docs/ai/model-zoo.md:622-628 claims router "still invokes xclip_action".
      Original: backend/tests/contracts/ai_providers/
      test_conformance_semantics.py:911-930 + test_conformance_ops.py:719,754 pin the xclip
      wire format → re-shape to pose→stgcn (these are RED right now by design). Then retire
      `ai/triton/model_repository/xclip_action/` (already weightless) + sweep stale refs:
      export_all.sh:213, entrypoint.sh:44 (XCLIP_DEVICE path), export/AGENTS.md:32,
      ai/triton/AGENTS.md:60,188. models.yml xclip-base entry stays (immutable history of
      a disabled model — owner call).
- [x] **client DEFAULT\_\*\_URL constants** ✅ landed + verify issues dispositioned (4 surviving
      X-CLIP-as-engine docstring lines in enrichment_client.py **fixed inline** — module/
      Result/classify_action → ST-GCN++ per gateway adapter truth; provisioning-side xclip
      refs correctly KEPT per ruling #2; 173 tests green). Verifier also corrected the fixer's
      flag evidence: the AST tripwire was PREDICTED-GREEN at HEAD (went red only vs the
      rewrite; already deleted by the aftermath agent; contracts suite 612 pass). Original:
      florence_client.py:259, scene_ocr_service.py:71,
      enrichment_client.py:63-64 point at retired containers (unreachable fallbacks) →
      gateway form + fix asserting tests (test_florence_client.py:220, test_enrichment_client.py:705-723).
- [x] **TracingPage → Tempo** ✅ landed + verify **sound** (Grafana-Explore URL shape proven
      against the shipped tracing.json dashboard link + GF_SERVER_ROOT_URL + entrypoint
      proxy; datasource uid `tempo` confirmed; 32 vitest, tsc/eslint/prettier clean; 5
      Jaeger tests re-shaped not deleted). Original: TracingPage.tsx:105 hard-codes
      localhost:16686 "Open Jaeger" + 5 asserting tests → Grafana explore /grafana/...datasource=tempo.
- [x] **verify-observability.sh:38-121** verifies Jaeger → Tempo :3200. ✅ fix landed + verify
      **sound** — empirically verified against a REAL pinned grafana/tempo:2.7.1 container
      (search query GREEN on an ingested synthetic span); also fixed a load-bearing latent
      `set -e` bug (HEAD died at first FAIL). New flags (small, PR-B/follow-up): config.py:330-335
      compat shim (intentional), scripts/test-docker.sh:28 FRONTEND_PORT=5173 (same agent's
      dead-compose-file item), compose:1327 alloy bare-4317 mapping vs tempo 127.0.0.1 binding.
- [ ] **archive batch**: ~~`monitoring/elasticsearch/`~~ ✅ DONE (→ archive/monitoring-elasticsearch/,
      README table row paired with the archived init-elasticsearch.sh). Remaining in this item:
      `container_discovery.py` golden table keyed on 5 retired containers **plus its dead
      'elasticsearch' ServiceConfig (:130,294-297,550-551)** — and the matching dead config
      surface `setup.py:156,185,233,506` + `.env.example:889,917-923` + `config.py:381-386`
      provisioning ELASTICSEARCH_PORT for a service no compose stack defines (discovery can
      never find it). Bigger surgery — decide: fix in PR-A follow-up or file to findings queue.
      Same call for scripts/restart-all.sh / seed-events.py / validate_synthetic_quality.py
      retired-container targets and scripts/test-docker.sh (COMPOSE_FILE points at a
      docker-compose.yml that no longer exists).
- [x] **model-mgmt aftermath** ✅ landed + verify issues dispositioned inline (integration
      rewrite real — 17 pass serially, verifier ran them; tripwire deletion correct). Verify
      found the evidence-cite refresh dead-on-arrival (numeric cites into a file the mm-health
      agent was editing live — 854→865 lines during the review; gen-ai-contract --check green
      only because both sides wrong identically) → **all 6 cites replaced with function-name
      anchors** (`_fetch_router_health`, `load_model/reload_model`, `unload_model`) in
      operations.py + gen-ai-contract.py mirror; gate green + 14/14 generator tests. False
      "503 never implemented" docstring claim corrected (HEAD implemented it, old suite was
      green). **Standing lesson for this repo: evidence strings must anchor on function/route
      names, never line numbers — check_phantoms only re-verifies paths.** Original: (i) rewrite
      `backend/tests/integration/api/routes/test_model_management_integration.py` (686 lines,
      dispatches on 8094/8096 + /models/status, asserts load/unload 200) to the gateway-health + 501 contract or archive it. (ii) delete the AST tripwire
      `test_client_conformance.py::TestTierAUnloadPathMismatch::test_backend_route_still_posts_the_wrong_shape`
      — its own text says delete-on-fix, and the fix landed (currently 1 red) — and refresh
      `backend/ai_contract/operations.py` evidence line numbers (486/560/646/186 stale).
      (iii) openapi regen happens at assembly anyway; api-compatibility.yml oasdiff will show
      the intentional 502/503→501 change — call it out in the PR body. (iv) Frontend:
      ModelZooPanel load/unload/reload buttons now surface 501 detail; lane labels say
      'ai-enrichment(-light)' — owner call: hide lifecycle buttons / relabel lanes
      ("gateway heavy/light router") in PR-B or a frontend ticket.
- [x] **catalogue amendment (owner ruling)** ✅ RE-DERIVED + verify issues dispositioned
      (verify core **sound**: 25/32.7920 GiB independently recomputed twice; yolo26 .pt files
      really downloaded + sha256-matched; every URL reachability-checked; stub run 25/25 steps
      exit 0; README/llms.txt consistent ~32.8GB). Only issue was ai/AGENTS.md:244 still
      linking the 401-gated nvidia/ Nemotron repo → **fixed inline** (unsloth mirror, models.yml
      named as source of truth). New flags: **docs/getting-started/prerequisites.md:51 ~42GB →
      PR-B pile**; xclip provenance = script provisions patch32 (catalogue row) but
      action_recognition_service.py:155/:586 defaults patch16-16-frames (runtime HF pull) —
      pre-existing known xclip item, ride-along for the xclip-retirement owner decision;
      test_deploy_phases systemctl failure = sandbox artifact, unmodified file. Original:
      re-derive `ai/download_models.sh` to the
      **setup_lib rule** — `download_method != skip AND (hf_repo OR download_method)` = 25
      entries / **32.79 GiB** — which re-adds `yolo26` (enabled:false but required:true; the
      gateway's export_yolo26.py:69 / export_all.sh:157 / prebuild-tensorrt-engines.sh:42-43
      all need model-zoo/yolo26/\*.pt) and also `xclip-base` + `florence-2-large` (enabled:false
      but still fed to live loaders: backend/services/action_recognition_service.py →
      xclip_loader.py defaults microsoft/xclip-base-patch16-16-frames; florence_extractor.py + model_zoo.py:387 loader map). Header must state the rule + total and note `enabled`
      governs backend VRAM slots, not provisioning. Old script's yolo26 section (git HEAD)
      downloaded n/s/m .pt from ultralytics/assets v8.4.0 — mirror setup_lib
      download_yolo26_models (setup_lib/model_downloader.py:445-485). Also fix README's 3 GB
      claims back to ~32.8GB and llms.txt:31,72 (~42GB → the rule's total).
- [ ] **monitoring round-2 (verify:monitoring findings)**: (i) 9 dead alerts still live in
      `alerting-rules.yml` (yolo26*model_loaded :955, florence_model_loaded :968, whole
      enrichment_model_zoo_alerts group :988-1065 — series exist only in retired ai/\*/metrics.py;
      file IS bind-mounted/loaded at compose:886) → delete-with-comment or Triton retarget per
      ruling (c). (ii) `prometheus.yml.template:245` duplicate `llama-cpp-metrics` job never
      actually removed as the edit report claimed (template has zero consumers — consider
      deleting the template outright, it was already flagged as consumerless with disagreeing
      placeholders). (iii) fix overstated comments: PromQL `sum(rate(empty))` = EMPTY not 0,
      so CLIPServiceDown/FlorenceServiceDown miss the model-absent scenario their new comment
      cites → add `or vector(0)` to the exprs or correct the comment; prometheus.yml:124-131
      claims hsi_ai_inference*\_ metrics survive the nv\_\_ drop, but GATEWAY_REQUEST_DURATION/
      ERRORS (ai/gateway/main.py:80-93) are defined and NEVER observed (zero call sites —
      separate small production gap: wire them into the request path or annotate honestly).
- [x] **setup.py `generate_docker_override_content()`** — resolved **option B (archived)**:
      the body is preserved verbatim in `archive/scripts/setup_docker_override.py` with a
      provenance header + README routing row; restoring it was rejected on evidence (its
      service map names only retired containers, so a revived override would break compose
      up; and `archive/test_setup.py` is stale _beyond_ the import — it asserts
      YOLO26_URL=http://ai-yolo26:8095 — so restoring would not have made it green either).
      setup.py quirk/HEAD ruff baseline preserved; bootstrap importlib path smoke-tested.
      NOTE for owner: `archive/test_setup.py` is doubly stale (ImportError + pre-consolidation
      asserts) — folds into the standing "wire archived tests into testpaths or delete?"
      ruling in archive/README.md.
- [x] **.env.example GPU comment honesty** — corrected: inline defaults `${GPU_LLM:-0}` /
      `${GPU_AI_SERVICES:-1}` apply silently (can misplace containers); file still parses
      via setup.py's loader (26 port keys, AI_GATEWAY_PORT=8090/TEMPO_PORT=3200 intact).
      Flag: docker-compose.ghcr.yml has no GPU_LLM usage at all (pins ai-llm's GPU itself) —
      PR-B docs nuance.

### Assembly (after batch; #6640 playbook)

- [ ] Generated artifacts MUST regenerate: `docs/openapi.json` + `frontend/src/types/generated/api.ts`
      — `generate-openapi.py --check` / `generate-types.sh --check` are exit 1 right now by
      design; the pre-commit hooks regenerate both. Do the admin sweep FIRST or they bake the myth again.
- [ ] `rm -rf site/` before agents_md_validator (gitignored build output false-positives).
- [x] Gate loop: landed via STAGED-set runs to rc=0 (never bypassed). Truth discovered
      2026-09-22: `--all-files` is red ON CLEAN HEAD (12 hooks fail — the baseline worktree
      proved it) so it is NOT the correct target; the commit-stage run IS. Fixes that made
      the staged gate pass are in commit `fix(gate):` (py3.14 hook env, ruff rev+^backend/
      scope mirroring CI, check-yaml gb300 exclusion, hadolint failure-threshold, secrets
      baseline). Hook drift on ~170 unowned files was reverted and re-reverted after each
      sweep — the ruff scope fix is what finally stops the bleed. Registry/census/baseline
      reconciled at 142 (ratchet + gen --check green).
- [ ] Commit trailer `Co-Authored-By: Claude Code <noreply@anthropic.com>`; push to remote
      **`gh`** (literal `origin` is the unpushable host mirror); `gh pr create --fill`;
      `gh pr merge N --auto --squash`; rebaser from `/tmp/rebaser-6635.sh` template
      (`sed s/6635/N/`), nohup; check-runs API watcher (neutral/skipped are non-blocking).
- [ ] CI red to expect-and-verify: chaos suite (fix:chaos result), stgcn conformance
      (post re-shape), image smoke jobs. ci.yml `ai-yolo26-image-smoke` still builds the
      retired ai/yolo26 image — owner call: retire job with Dockerfiles or keep.

- [ ] **SECURITY-DOCS (raised by fix:admin-myth; verified by orchestrator against tree)**:
      admin endpoints are gated by `admin_enabled` ALONE, which defaults **True**
      (config.py:866); `admin_api_key` is defined+redacted but enforced NOWHERE (Field desc
      :871-874 promises an X-Admin-API-Key check that exists nowhere — only a seed script
      sends the dead header); global AuthMiddleware disabled (NEM-5527, main.py:1353-1362).
      Stated posture (admin_enabled description): 127.0.0.1 network binding is the primary
      boundary — coherent for single-user local, but docs/operator/admin/security.md:17,187,190 + admin/README.md:94,281 + configuration.md:165 + config/AGENTS.md:68 +
      backend/core/AGENTS.md:969 + tests/load docs ADVISE an ADMIN_API_KEY protection that
      does not exist. Ruling #6 keeps posture unchanged (comment/doc reconciliation only);
      config.py:863-864/871-874 comments ✅ LANDED (config-severity agent; verify:admin-myth
      confirmed "resolved in current tree") + verify:config-severity **sound** (comments match
      require_admin_access exactly; ADMIN_API_KEY confirmed enforcement-free repo-wide);
      docs myth = PR-B (+ env-reference.md:527/529 and security.md:30 additions from
      verify:admin-myth). **PR-body nuance from verify:config-severity: the loopback-boundary
      posture is prod/ghcr-only — docker-compose.ci.yml:93 binds all-interfaces (ephemeral CI
      boxes).** If the owner ever WANTS key enforcement, that is a new
      posture decision with its own ticket — do not smuggle it in here. Call it out in the
      PR-A body so the posture is visible, not silent.

## PR-B — docs only (after PR-A merges)

- [ ] coverage.md real regeneration (./scripts/check-api-coverage.sh + frontend/src scan).
- [ ] docs/development → docs/developer consolidation (developer/ is nav-canonical;
      36 files vs 50; redirect stubs, nav+anchor surgery; LAST in PR-B).
- [ ] entity-ADR orphan-cleanup promise: annotate "unimplemented" in the STATUS section only
      (ADR body immutable).
- [ ] Flag pile from PR-A agents (each already has file:line evidence in the journal):
      middleware doc-drift (backend/AGENTS.md:520, backend/api/AGENTS.md:260,
      backend/api/middleware/AGENTS.md ×4, tests/.../AGENTS.md ×6, docs/architecture/middleware/_,
      api-request-flow.md:31-92); services/AGENTS.md:2686 restart example; ghcr operator doc
      (docs/operator/ai-ghcr-deployment.md:19-31,71); GPUOOMCritical→GPUInferenceFailures
      runbook rename (docs/operations/profiling-runbook.md; nvidia-technology-inventory.md:399);
      env-reference residual FRONTEND*PORT/JAEGER*_ rows (findings :237-238, :540);
      ai-gateway/Dockerfile:15 stale comment (findings :547); archive README git-mv wording.
      **Additions from the tracing-tempo fix**: frontend/src/components/tracing/AGENTS.md
      needs a full REWRITE (all-Jaeger AND describes never-built features: view-mode toggle,
      Compare Traces, SplitSquareHorizontal); docs/ui/tracing.md:59 Open-Jaeger table row;
      frontend/src/components/pyroscope/AGENTS.md:179 one-word drift.
- [x] **tests/smoke/test_monitoring_smoke.py TestJaeger → TestTempo** ✅ landed; verify found
      /api/echo asserts JSON but tempo:2.7.1 replies text/plain "echo" (hard-fails with stack
      up) → **fixed inline** (plain-text assertion, docstring corrected; 13 skip cleanly, ruff
      clean). Also landed: pre-existing missing skip-guard on test_prometheus_metrics_endpoint.
      Flag: tests/smoke/README.md:52 still says "Jaeger distributed tracing" → PR-B pile.
      Original: hits
      :16686 with skip-when-unreachable = false coverage that never validates Tempo. Convert
      TestJaeger -> Tempo :3200 checks (scripts/platform-healthcheck.py:332 already has the
      right probe shape to copy). Owner ruling implicit in ruling #1 (fix all of it); it
      skipped rather than failed so it was invisible.
- [ ] Grafana dashboard redesign (~40 panels across consolidated/ai-services/tracing/hsi-profiling
      dashboards — PR-A flagged exact nv\_\* mappings for the rate/error panels) — decide PR-B
      vs follow-up ticket.

## Standing traps (do not re-learn these the hard way)

- Compose service counting: grep swallows named volumes under `volumes:`; parse YAML or stop
  at top-level keys. **21/19/2 in README is CORRECT** — never "fix" it.
- models.yml is at REPO ROOT, not ai/models.yml; enabled set 25 / 29.3GB; full 30 / 33.3GB.
- `nv_inference_request_duration_seconds` does NOT exist — real: `nv_inference_request_duration_us`
  (cumulative); percentiles need `--metrics-config summary_latencies` (not set).
- pymdownx snippets: `docs/\_includes` backslash = silent no-render; live docs unescaped,
  dated plans `;`-escaped; check_paths:true must stay on.
- ruff formats fenced python inside .md in CI but the local hook only feeds .py — run
  `uv run ruff format` on touched .md files.
- Evidence strings (ai_contract operations.py + gen-ai-contract.py mirror) anchor on
  function/route NAMES, never line numbers — check_phantoms only re-verifies paths, numbers
  silently rot under concurrent edits, and --check stays green with both sides wrong.
- Squash-merge phantom conflicts: prove with `git diff <pre-branch> <main-squash>`, resolve --ours.
- Concurrent agents: no git mutations inside fixer scopes; archive moves are plain `mv`
  (git detects rename at commit); the archive README's git-mv prose loses to this rule.
- setup.py deliberately lacks top-level `import os` (bootstrap-gb300.sh injects it); its
  4 F821s are the accepted baseline — don't "fix" them.
