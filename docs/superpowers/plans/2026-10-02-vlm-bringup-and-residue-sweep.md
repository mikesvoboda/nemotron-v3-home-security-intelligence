# VLM bring-up + R8 residue sweep — plan (2026-10-02)

Companion to `docs/architecture/ai-pipeline-current-state.md`, which holds the measured facts.
This file holds the **decisions, the ordering, and the protection mechanism**. Nothing here is
implemented yet.

## The constraint that governs every step

The user's requirement is: bring the VLM stack up end to end, and **do not impact the path that
remains and works.** R8 was an intended refactor; the residue is expected. So the sweep is not
"delete what references dead things" — it is "delete only what is provably unreachable, and prove
it before deleting."

Three findings from the measurement pass set the rules:

1. **`export_all.sh` is NOT stale in whole.** `[V]` It builds the engines the shipped set needs —
   `yolo26` (`:155`), `threat` (`:145`), `reid` (`:196`) — and `setup_lib/deploy_phases.py:648`
   runs it during deploy. **A blanket delete of `ai/gateway/export/` would break VLM-era
   provisioning on a fresh host.** Only the retired-model rows inside it are residue.
2. **Deleting a stale probe can mask a real signal.** `monitoring/prometheus.yml` probes live and
   dead targets in the same job (`:412-448`). Removing the three dead targets is correct; removing
   the job is not.
3. **A gate that nothing runs is already broken.** `scripts/test_ai_surface_census.py` and
   `scripts/validate_docs` are invoked by **no** workflow [V]. The sweep's highest-value change is
   wiring gates that already exist, not writing new ones.

### Discipline

One change → verify → next change (`.claude/skills/incremental-fixes`). No stacked unverified
edits. `PIPELINE_MODE=vlm` must stay green after every step, and any step that cannot prove the
path is green **on the real box** stops rather than proceeds.

Baseline, measured before any change: **206 passed in 4.55s** over the seven VLM-path guard files
(`.venv/bin/python -m pytest <files> -p no:randomly --no-cov -o addopts=''`). The interpreter
matters: system `python3` has no pytest, and `timeout … | tail` reports *tail's* status, so a
silent `No module named pytest` once looked like exit 0. Use `.venv/bin/python` and read the
output, never just the exit code.

After each slice, run the **tripwire set** (§"tripwire set", bottom): the 7 guard files + the two
newly wired gates.

---

## Phase A — bring the VLM stack up (do this FIRST, before touching code)

Every item here is read-only or a restart. Nothing in Phase A edits the repo. Phase A is also what
makes Phase B safe: a running path is the only real proof a deletion was inert.

### A1. Is `ai-vlm` actually up, and can it see?

```bash
podman ps -a --filter name=ai-vlm --filter name=ai-gateway
curl -s http://127.0.0.1:8098/health | jq          # up ≠ multimodal, see A2
```

If `ai-vlm` is absent rather than stopped, the cause is likely §2.2 of the state doc:
`restart-all.sh:220` restarts `ai-gateway ai-vlm` with **no** `--profile vlm`, while `:222` passes
one for monitoring. Start it explicitly:

```bash
podman compose -f docker-compose.prod.yml --profile vlm up -d ai-vlm
```

### A2. Prove the serve is multimodal, not text-only

The healthcheck passes on a projector-less server (`prod.yml:238`, `Dockerfile:139`) — the state
doc §2.1. So:

```bash
podman exec ai-vlm sh -c 'echo "MODEL_PATH=$MODEL_PATH"; echo "MMPROJ_PATH=$MMPROJ_PATH"'
ls -l "$AI_MODELS_PATH/vlm/"                       # BOTH GGUFs must exist
podman logs ai-vlm 2>&1 | grep -i mmproj           # llama-server logs whether it loaded one
```

`download_models.sh:493-497` states the pair is operator-placed, not fetched, and that without the
mmproj "every `vlm_assess` call degrades silently". A text-only server returning 200s is the worst
failure mode available here because the events keep landing.

### A3. Did anything actually get analysed?

```sql
SELECT verdict, count(*), max(created_at)
FROM events e JOIN event_verifications ev ON ev.event_id = e.id
GROUP BY verdict ORDER BY max(created_at) DESC;
```

A run of `verification_failed` with NULL `risk_score` = VLM unreachable or blind (A1/A2), not an
empty camera. **Do not triage from the alerts table** — no event auto-creates an Alert (§2.4 of the
state doc), so "stalled" and "healthy and unnotified" are indistinguishable there.

### A4. Are the face and re-ID legs resident at all?

Residency is gated on `BACKEND_MODEL_PRELOAD`, which ships `false`, and both `get_reid_handle()`
and `get_face_leg_handles()` are membership reads that never load (state doc §2.3).

```bash
curl -s http://127.0.0.1:8000/metrics | grep hsi_specialist_unavailable_total
```

Non-zero and unbroken since boot ⇒ that leg has **never** run. The fix is host-specific:
>= 24 GB VRAM ⇒ `BACKEND_MODEL_PRELOAD=true` (`setup.py:461-464` auto-sets exactly this). Note the
shipped default is pinned by `test_ai_vlm_compose_service.py:402-409`, so **changing the shipped
default is a gate edit** — decide it explicitly or set it in the host `.env` only.

### A5. Decide whether the alert half is meant to run

`AlertRuleEngine.evaluate_event` / `create_alerts_for_event` have **zero** production call sites
[V]; the engine runs only from the rule-test endpoint (`alerts.py:434`), and the threat fast path
is dead-on-arrival (`batch_aggregator.py:1389-1391` passes `None, None` into a method that raises
`ValueError` by design, `threat_monitor_service.py:203-207`).

**This is the one finding that changes product behaviour, so it is an owner decision, not a
cleanup.** Options: (a) leave as-is and treat notifications as out of scope for the VLM path;
(b) wire `evaluate_event` into the analyzer's post-commit step; (c) delete the dead fast path and
leave the engine dormant explicitly. Recommended: **(a) for now, and record it in the ledger** —
wiring it changes what pages a human, which is not a refactor and deserves its own slice with its
own tests.

**Gate on A:** do not start Phase B until A1-A4 are green on the real box. Without a running path,
every Phase B "this is unreachable" claim is a guess.

---

## Phase B — the sweep, smallest blast radius first

Ordering rule: docs and comments (cannot break a boot) → unwired scripts (can break a deploy) →
config/env (can break a boot) → CI gates (can break a merge). One PR per slice.

### S1 — Docs that lie about the running stack (code risk: **none**)

**Owner ruling, 2026-10-02: clean slate, no backwards compatibility.** Pages whose subject is the
retired stack are **deleted**, not banner-ed or archived as "historical", so a future agent cannot
find a plausible-looking page that describes a stack which does not run. Surviving pages are
rewritten to describe the shipped shape in **present tense with no retirement narration** — no
"previously", no "removed in R8", no dead-name tables. Where an operator would otherwise hunt for a
dead knob, one pointer line is allowed ("ai-vlm is the only LLM service"); never more.

Two consequences worth stating, because they are the cost of the ruling:

1. The historical record is **not** duplicated into the docs tree. It already lives in the frozen
   execution record — `docs/plans/` (the VSS ledger, R8 scope docs) and git history. Correcting
   those is out of bounds except by dated addendum, and nothing needs to change there: they are
   correctly labelled as records.
2. `docs/architecture/ai-pipeline.md` and its exclusive image assets go away. Before deleting, the
   941 lines were **read for content that still transfers** (batch-aggregator timing rationale,
   queue/retry mechanics, the risk-band table) and that content was carried into
   `ai-pipeline-current-state.md` or the surviving pages. Deletion without that read would have
   destroyed the only prose on batching behaviour.

A guard follows in S5: `scripts/check-vss-docs-currency.py` (or a rule in
`scripts/docs-drift-rules.yml`, which is designed for pattern additions without Python changes)
makes the present-tense retired claims **unable to come back**. Without S5, S1 is a cleanup that
rots.

Executed as a fan-out (`docs-clean-slate-ai-stack`, six zones over `docs/operator/`,
`docs/architecture/` top level, `ai-orchestration/` + `dataflows/`, the remaining architecture
subdirs, `docs/developer/`, and `docs/reference/` + `getting-started/` + root README), with a
completeness critic over the post-edit tree and the deletions performed centrally afterwards.

| File | Defect | Action |
| --- | --- | --- |
| `docs/architecture/ai-pipeline.md` | `last_updated: 2026-01-04`; `source_refs` cite two deleted files; 49 retired-name mentions; 941 lines | banner at top → "pre-R8 historical", pointer to the current-state doc; **fix the 3 dead `source_refs`** so `validate_docs` is clean |
| `docs/operator/ai-overview.md` | `:19-22` present-tense "ai-gateway: YOLO26, Florence-2, CLIP, enrichment" and "ai-llm … Nemotron 30B" | rewrite to the two shipped services |
| `docs/operator/ai-services.md` | `:14` same table; `:111,121` tell an operator to `curl` `ai-llm` and `/florence/health` | rewrite |
| `docs/operator/ai-configuration.md` | `:124,129,140` documents `NEMOTRON_MODEL_PATH`, `LLM_MODEL_PATH` for `ai-llm` | rewrite |
| `docs/operator/deployment-modes.md` | `:14,25` "one container serves YOLO26, Florence-2, CLIP"; `:73` `FLORENCE_URL=` | rewrite |
| `docs/operator/ai-installation.md` | `:17` "Nemotron-3-Nano-30B + ai-gateway (Florence-2, SigLIP 2)"; `:85` mermaid with dead routers | rewrite |
| `docs/operator/ai-ghcr-deployment.md` | `:103,139,160` dead routers + `ai-llm` section | rewrite — **and** reconcile with `docker-compose.ghcr.yml` having **no `ai-vlm` service at all** (open question §9 of the state doc; may be "GHCR does not ship the VLM", which must be said out loud) |
| `docs/operator/ai-troubleshooting.md` | `:12` "two containers: ai-gateway and ai-llm"; `:17,37,104,109` tell you to `podman logs ai-llm` | rewrite |
| `docs/architecture/AGENTS.md` | `:84` advertises "Nemotron LLM risk analysis" | fix pointer |
| `docs/ROADMAP.md` | `:22` "Nemotron produces a risk score + summary + reasoning" | fix |
| `docs/ai/AGENTS.md` (already swept) + `README.md:334,466,532` | README still carries present-tense `ai-llm`/`NEMOTRON_URL` instructions `aabd7cd6` missed | fix README |
| `backend/evaluation/AGENTS.md` | describes the module as Nemotron prompt-template eval; omits all five modules the shipped replay runs | rewrite |
| `backend/ai_contract/AGENTS.md` | "38 operations", "45 schemas" (real: **9 ops, 15 files**), names three deleted client classes | fix counts |
| `backend/ai_contract/{operations,providers,provider}.py` | prose counts (38/31); `operations.py` evidence `file:line`s point at deleted files yet still satisfy `per_model_server: True` because the derivation greps the **string** | fix prose; **flag, do not silently fix** the evidence-string derivation — it is a doctrine gap (`gen-ai-contract.py:25-30` already names this hazard for Tier-A) |

**Verify S1:** `python3 -m scripts.validate_docs docs/architecture/ai-pipeline-current-state.md
--no-ast --no-code-match --no-cross-ref --no-staleness --errors-only` → 0 ERR (and the same on
every rewritten page). Then the
prettier hazard [memory `prettier-marks-up-underscores-in-markdown`]: prettier pairs mid-word
underscores into emphasis. Either add these pages to `.prettierignore` (precedent: the operator
handoffs already there) or run `--write` and grep the diff for `*`. Note: **prettier runs in no CI
workflow** [V], so formatting is a local habit here, not a gate.

### S2 — Monitoring that probes routers which no longer exist (code risk: **none**)

- Delete the three dead blackbox targets: `monitoring/prometheus.yml:430` (`/clip/health`), `:436`
  (`/florence/health`), `:442` (`/enrichment/health`). Keep `:412`, `:424`, `:448` — those are live.
- Delete `monitoring/grafana/dashboards/clip-florence-intelligence.json`; audit
  `enrichment-pipeline.json` and `nemotron-prompt-analytics.json` (same class, unmeasured).
- Add the positive coverage the state doc §8 says is missing: a scrape target/dashboard for
  `hsi_specialist_unavailable_total` and the pipeline counters, because that counter is the **only**
  signal for specialist degradation and nothing currently surfaces it.

**Verify S2:** `promtool check config monitoring/prometheus.yml`; blackbox `probe_success` for the
three surviving targets = 1.

### S3 — Unwired scripts (code risk: **medium** — two of these run in a deploy)

1. **`ai/gateway/export/`: prune rows, do NOT delete the directory.** Keep
   `export_yolo26.py`, `export_yolo_threat.py`, `export_reid.py`, `copy_yolo26_engine.py`,
   `export_all.sh`. Prune the retired rows `:113-142` (clip, clip_text, fashion_clip, pose) and the
   vehicle/demographics/pet/depth/florence2/stgcn_action entries at `:213`, plus the matching
   `check_file` lines. `[V]` `run_export` counts failures and skips cached outputs, and the script's
   exit behaviour is what `deploy_phases.py:648` inherits — **read what it returns on partial
   failure before pruning**, because today the retired rows may be the reason deploy logs look
   odd. This is the item most likely to look safe and not be.
2. **`scripts/download-model-zoo.py`** still provisions smoke-fire / yolo-world / vitpose /
   segformer / stgcn / fashion-clip [V] **and it is on the shipped installer path**: 
   `setup_lib/model_downloader.py:863` shells out to it with `--all` when `hf_hub` is unavailable
   [V]. Either prune it to the keeps or delete it and remove the fallback. Do not leave a fallback
   that materialises a retired zoo.
3. `setup_lib/model_downloader.py:93-129` — `DEPRECATED` specs (nemotron GGUF, florence-2-base,
   siglip2) and the nemotron path checks at `:328,:611`. (Row 73/slice 7 removed the dispatch
   branches at `:875` but left these lists.)
4. `scripts/seed-events.py:2581,2622` dial `CLIP_URL` → `/embed`, an endpoint deleted in S3. Dev
   script, never invoked by shipped code — fix or delete.
5. `scripts/benchmark_model_zoo.py:143-218` live branches for six retired models;
   `scripts/audit_grafana_queries.py:260` asserts action runs as Triton `stgcn_action` on
   ai-gateway, which the repository contradicts; `scripts/dataset_converters/kinetics_converter.py`
   serves the deleted action lane.
6. `ai/gateway/export/export_reid.py` has a **test** (`ai/gateway/tests/test_export_reid.py`) —
   check it is a keep-set test before touching anything.

**Verify S3:** a deploy run (or a dry-run of the export phase) still produces
`{yolo26,reid,threat}` engines; `test_r8_s3_florence_provider_retirement.py` + `test_export_reid.py`
green.

### S4 — Config/env that advertises dead knobs (code risk: **low**, but this slice touches the boot path)

- **`setup.py:433-435`** writes `FLORENCE_URL=` / `CLIP_URL=` / `ENRICHMENT_URL=` into every
  generated `.env` [V]. `Settings(extra="ignore")` (`config.py:369`) discards them, so this is
  cosmetic — **but it is already tested**: `test_r8_s3…:369-390` asserts no file injects those
  assignments and it passes only because the test scans `docker-compose*.yml`, `config/*.yml` and
  `.env.example` and **not** `setup.py`. Fix = delete the three lines **and add `setup.py` to that
  test's file list**, so the guarantee matches its name.
- `.env.example:383,394` — `ENRICHMENT_PRELOAD_MODELS` / `ENRICHMENT_LIGHT_PRELOAD_MODELS` ship
  values naming five retired models and **nothing reads either** (`security.py:264` validator has
  zero non-test callers). Delete vars + validator + its tests.
- `docker-compose.prod.yml:395-397` and `docker-compose.ghcr.yml:188-190` —
  `VEHICLE_QUANTIZED` / `DEMOGRAPHICS_QUANTIZED` / `QUANTIZED_MODEL_DIR` with no reader in `ai/`;
  their setup script died with `ai/enrichment` in `3b73b9b6`. Delete from both files.
- Present-tense retired-stack comments at `prod.yml:345,464`, `ghcr.yml:153-155`,
  `.env.example:21,168-179`.
- `backend/services/ai_fallback.py` — kept-and-dead, zero shipped importers, ledgered as
  flagged-not-deleted. Leave for the dead-code slice; do not fold it in here.

**Verify S4:** `python3 -c "from backend.core.config import Settings; Settings()"` boots;
`test_config.py`, `test_deploy.py`, `test_deploy_phases.py`, `test_r8_s3…` green; a fresh
`python3 setup.py` generates an env that still starts the stack.

### S5 — Wire the gates that already exist (code risk: **low**, CI surface only)

Highest value per unit of risk in the whole plan. All three tools already work.

1. `scripts/test_ai_surface_census.py` — pins the surviving-loads set to **exactly the three
   lookup loaders**, i.e. the guard against a specialist leg being quietly added or deleted. Run by
   **no** workflow [V], outside `testpaths`.
2. `scripts/validate_docs` — level-1 file-existence catches dead `source_refs`; found the 3 in
   `ai-pipeline.md`. Run by **no** workflow [V].
3. `ai/tests/test_module_hygiene.py` — its probes never execute (`ai-tests` runs `--collect-only`
   plus `ai/gateway` only).

Add all three to CI, and extend `scripts/check-vss-docs-currency.py` (or add a rule to
`scripts/docs-drift-rules.yml`, which is designed for pattern additions without Python changes) so
the present-tense retired claims that S1 fixes **cannot come back**. That is the difference between
one cleanup and a cleanup that holds. Note `scripts/test_ai_surface_census.py:176`'s module-count
floor is `>=170` where S2/S3 landed at 177 — floors are drift canaries, not equality pins; consider
tightening while wiring it.

**Verify S5:** the job passes on a clean tree **and** fails on a planted violation (a dead
`source_ref`, a fourth loader). A gate proven only green is not proven.

### S6 — Structural questions to settle (decisions, not deletions)

1. **Orphaned Triton `reid`.** Residency keeps `reid` in the shipped set
   (`residency.py:60-84`) and `model_repository/` holds `{yolo26,reid,threat}` [V], while
   `/enrich-lt`'s threat+reid routers have **no inference consumer** — the only non-test reader of
   `enrichment_light_url` is the readiness probe (`model_management.py:172`) [V]. So the shipped
   config pays GPU residency for a model nobody calls, and a pinned gate locks that in. Either drop
   `reid` from residency (frees VRAM for the VLM) or write the consumer. Both are legitimate; the
   current state is neither.
2. **`GATEWAY_ENABLE_THREAT` + the F12 ruling.** Threat stays off by ruling
   (`vlm_specialists.py:874-879`: identical 83.0% recall per class on an unnamed dataset; published
   CCTV weapon AP50 57.4 → 3.7 cross-dataset). Preserve the ruling. If weapon hints are wanted,
   that is the rev-7 YOLOE-26 feature gated on hand/arm overlap — not re-enabling this flag.
   **Precision for anyone tempted to "fix" this:** `run_threat` is a live parameter
   (`:891,926-927`) with one test caller, so `SPECIALIST_KEYS` is a **call-site default, not an
   invariant**. If the exclusion must be structural, say so and add a test that a `run_threat=True`
   caller cannot appear in production.
3. **`docker-compose.ghcr.yml` has no `ai-vlm` service.** Either the GHCR surface intentionally
   does not ship the VLM (then say it in `ai-ghcr-deployment.md` and add a guard) or it is a bug.
   Ledger rows 54/56 already carry this gap as close-pointer work.
4. **Second severity-band copy.** `api/schemas/events.py:21-23` hardcodes 29/59/84 while the bands
   are runtime-mutable (`system.py:3459`, `:3548`), so DB-stored and API-echoed `risk_level` can
   disagree. Small fix, genuinely user-visible.
5. **Eval cannot score a specialist change.** Replay feeds *stored* `specialist_outputs` and
   tierb-v0 declares none, and the only corpus that joined media + specialist context (38 items,
   ledger item 40) lives off-repo and is not reproducible [V]. **Any specialist-pipeline change is
   currently unmeasurable** — rebuilding that corpus should gate a specialist *change*, even though
   it does not gate this sweep. Also: nightly `prompt-evaluation.yml` scores the **retired**
   Nemotron harness in `--mock` mode and is green regardless — decide whether to retire it or
   repoint it at the VLM replay.

---

## Explicitly NOT touching

Things that look like residue and are not:

| Looks like | Actually | Evidence |
| --- | --- | --- |
| `ai/gateway/export/` | builds the shipped `{yolo26,reid,threat}` engines, runs in deploy | `export_all.sh:145,155,196` + `deploy_phases.py:648` |
| `ENRICHMENT_LIGHT_URL` / `/enrich-lt` | live readiness lane | `model_management.py:172`; `prod.yml:601`; `ghcr.yml:251` |
| `ai/yolo26/`, `ai/triton/` | pure-leaf contract + the repository Triton runs inside ai-gateway | `ai/AGENTS.md` |
| `osnet_loader`, `face_recognizer_loader`, `fast_alpr_loader` | the **live** specialists, in-process | `vlm_specialists.py:174,535,566,705` |
| `PIPELINE_MODE`/`GATEWAY_MODEL_SET` hard-raises | the guard itself | `config.py:1079-1083`; `residency.py:84` |
| `models.yml` + `download_models.sh` | already swept, provisions only the keeps | state doc §residue |
| `ai_fallback.py` | dead but ledgered as deliberately kept | `test_r8_s3…:396-400` |
| `docs/vss-integration/`, `docs/plans/`, `docs/superpowers/` | the frozen research/ledger record; correcting them is out of bounds except by dated addendum | `docs/vss-integration/AGENTS.md` |

## Ledger follow-ups this plan creates

The execution record lives in the ledger (`docs/plans/2026-09-23-vss-gaming-gpu-ledger.md`) — the
`docs/` pages are the explanation, the ledger is the record. Append, never rewrite:

1. A5 owner ruling on auto-alerting (dormant engine vs wired vs deleted fast path).
2. S6.1 ruling on Triton `reid` residency: drop or consume.
3. S6.3 ruling on `ai-vlm` in the GHCR surface.
4. S5 acceptance criterion: each newly wired gate must be proven to fail on a planted violation.
5. S6.5: specialist changes are unmeasurable until the joined corpus exists.

## Tripwire set

Run after **every** slice, and again at the end. Expect 206 passed on the guard files, unchanged.

```bash
.venv/bin/python -m pytest \
  backend/tests/unit/services/test_vlm_specialists.py \
  backend/tests/unit/services/test_vlm_analyzer.py \
  backend/tests/unit/core/test_config_pipeline_mode_hard_raise.py \
  backend/tests/unit/core/test_gateway_model_set_compose.py \
  backend/tests/unit/core/test_ai_vlm_compose_service.py \
  backend/tests/unit/test_no_legacy_pipeline_branches.py \
  backend/tests/unit/test_r8_s3_florence_provider_retirement.py \
  -p no:randomly -q --no-cov -o addopts=''
```

Then, per slice: `test_config.py` + `test_deploy*.py` (S3/S4), `ai/gateway/tests/test_export_reid.py`
(S3), `promtool check config` (S2), `scripts/validate_docs` (S1), and the two newly wired gates (S5).
On the real box after each deploy-affecting slice: **A1-A4 again**. A slice that cannot be shown
green stops; the next slice does not start on top of it.
