# R8 legacy retirement — measured scope (2026-09-28)

Scope notes for the retirement slices, written on the GB300 dev partition [V: this sandbox
is the agent partition per ledger E10]. **Nothing here has been executed** — no file has been
deleted, no test tier run. Every line reference was read at the tip of
`feat/vss-gaming-gpu-profile` (`1f2921a4`) and re-checked by hand; the parts a 7-agent
scoping pass asserted and I could not reproduce are marked as such. It is the detail layer
for the goal prompt at `docs/plans/2026-09-29-r8-legacy-retirement-goal-prompt.md`; that
prompt is the order of work, this file is the evidence.

**Owner rulings that set the scope (both 2026-09-29, recorded here before the work):**

- **"we do not have to support backwards compatability"** and **"we should hard raise"** —
  so `PIPELINE_MODE=legacy` must RAISE at boot, not warn. This matches ledger item 20's
  near-identical wording on the re-ID swap ("full swap. ignore previous architecture…").
- The **R8 trigger is reversed by instruction**: `12-postponed-roadmap.md:23` defers this
  deletion to "Go-live holds 14 days"; the owner is picking it up now, per that file's own
  convention at `:10` (a picked-up item gets its own dated spec and a mark here).
- **No A5500.** Everything below is repo + GB300 work. The pinned PASS numbers (S1 9,722 MiB
  of 20,890; S4 p95 16.2 s of 30 s, ledger items 40–41) belong to that box and must not be
  re-measured or re-stated as repo claims.

## 1. What is actually reachable today [V]

The legacy path is **live-by-environment-variable**, so its removal is a functional change,
not a cosmetic one.

- `backend/core/config.py:1061-1090` — the validator's own comment says `"legacy" parses
only because its code stays in the repo until R8 deletes it`. `:1084` accepts the two
  spellings, `:1086` logs a warning. It does **not** reject.
- Consequence: a deployment with a stale `PIPELINE_MODE=legacy` in its `.env` boots today and
  runs the unsupported pipeline. Under the hard-raise ruling it must crash at boot.

## 1a. Two shared config pairs that are NOT legacy-only [V]

- **`GPU_LLM`** is the LLM's _and_ the VLM's GPU: `docker-compose.prod.yml` passes it to
  `ai-llm` (:145,:159,:209) and to `ai-vlm` (:251,:266,:35x). Deleting the ai-llm block must
  not delete the variable or its `.env.example` row.
- **`CTX_SIZE` / `PARALLEL`** is one env pair feeding two different slot budgets:
  `config.py` binds `nemotron_context_window→CTX_SIZE` (legacy, 262144) and
  `llama_slot_count→PARALLEL`, while the shipped vlm slot uses 32768/2. Removing the legacy
  defaults must leave the vlm binding untouched — this pair is exactly where a careless
  deletion changes the measured slot ceiling behind S1's back.
- **`nemotron_url`** has live, non-mode-gated consumers beyond the legacy pipeline:
  `summary_generator.py:84`, `prompt_service.py:679`,
  `pipeline_quality_audit_service.py:136`, `performance_collector.py:475`. Whether those
  features are live under vlm mode is not established here — §11 item 5.

## 2. The `legacy` branch sites [V]

Instrument (wide grep — the narrow one is a trap, see below):

    grep -rn '"legacy"' backend/ --include=*.py | grep -v tests   # 13 lines at the tip

**Trap:** the narrower `grep -rn 'pipeline_mode == "legacy"\|pipeline_mode != "legacy"'`
returns **7** and silently misses `backend/services/pipeline_factory.py:52`, which branches
on a local `mode` variable assigned at `:51` (`mode = _settings_for_mode().pipeline_mode`).
An agent that enumerates with the narrow grep ships a live legacy branch.

Sites, all [V] at the tip: `main.py:733`, `main.py:1134`; `pipeline_factory.py:52`
(the module is 59 lines and is essentially the mode switch itself);
`system_broadcaster.py:1028`; `container_orchestrator.py:536`; `core/container.py:508`;
`api/routes/health_ai_services.py:111`; `api/routes/system.py:1164` (+ the legacy health body
it short-circuits); `api/schemas/enrichment_data.py:442,454`; `config.py:1084,1086`.

`pipeline_workers.py:800` is only a **comment** — its real coupling is the
`from backend.services.nemotron_analyzer import NemotronAnalyzer` at `:67`.

## 3. nemotron_analyzer.py is NOT wholly legacy [V — this was the pass's most important catch]

`backend/services/nemotron_analyzer.py` is 5,429 lines; ~98% is legacy. But **`:294-411` is
imported by the VLM path**, verified at each importer:

| symbol                           | imported by                                                                               |
| -------------------------------- | ----------------------------------------------------------------------------------------- |
| `ConstrainedDecodingNotEnforced` | `vlm_client.py:65-69`, `vlm_analyzer.py:74`, `evaluation/vlm_replay.py:56`, `main.py:773` |
| `_is_length_truncated`           | `vlm_client.py:65-69`                                                                     |
| `build_probe_schema`             | `vlm_client.py:65-69`                                                                     |

`main.py:773` is inside the **live constrained-decoding startup gate** — the comment at
`main.py:769` says the VLM mode's gate "shares the same shared
ConstrainedDecodingNotEnforced verdict vocabulary". Deleting the file whole therefore breaks
the shipped pipeline at import, and the S-1 enforcement verdict with it.

**Slice order:** 2a hoist `:294-411` (also carries `VerificationRowOutcome:294`,
`PROBE_PROMPT:323`, `_TRUNCATED_STOPS:335`, `_is_length_truncated:338`,
`_probe_completion:352`, `build_probe_schema:396`) into
`backend/services/constrained_decoding.py`, repoint the four importers, red-first with an
import test. 2b deletes the ~5,321 remaining lines.

Adjacent legacy-only modules — sizes now **wc-verified [V]**: `enrichment_pipeline.py` 7,662
(the pass's "3,334" was `enrichment_client.py`'s number, swapped), `enrichment_client.py` 3,334,
`nemotron_streaming.py` 575, `analyzer_facade.py` 266, `prompt_auto_tuner.py` 205,
`nemotron_latency_optimizer.py` 650, plus two the first pass missed: `skeleton_action_service.py`
(only importer: `enrichment_pipeline`) and `pose_analysis_service.py` (**zero** non-test
importers — already orphaned). DI/type bindings naming `NemotronAnalyzer` also live at
`ai_fallback.py:47,238` (+health use `:433`), `api/routes/events.py:100,105,2584`,
`pipeline_workers.py:67`, `api/dependencies.py:346,949,1430`, `core/dependencies.py:60,100` —
several are `TYPE_CHECKING`-only imports (`from backend.services... import` under
`if TYPE_CHECKING:`), which erase at runtime: they must be edited, but deleting the module does
not crash them at _import_ — distinguish those from the eager ones (`events.py:100` is a real
runtime import).

Safe to delete without touching M1: `nemotron_analyzer.py` has **zero** hits for
`should_notify|NotificationFilter|notification_filter` [V], so the unwired M1 rule at
`notification_filter.py:35` survives the deletion untouched.

## 4. Enrichment and the specialists do not overlap [V]

`backend/services/vlm_specialists.py` has **zero** references to `enrichment` — the face,
plate and re-ID legs are built from the module's own handles (`collect_face_text:499`,
`collect_plate_text:552`, `collect_reid_text:645`). Deleting `enrichment_client.py` (3,334 L)
and `enrichment_pipeline.py` cannot orphan the specialists.

**But the package init is the sever-most cut [V].** `backend/services/__init__.py` eagerly
re-exports both targets with no `try/except`: `EnrichmentPipeline` et al. at `:95` and
`NemotronAnalyzer` at `:245`. Deleting either module without first editing that file breaks
`import backend.services` **everywhere at once** — the whole tier, not one caller. Edit the
init in the same slice, ahead of the `rm`.

Other shared infra that is **not** legacy and must survive [V]:

- **`llama-cache` named volume** (`docker-compose.prod.yml:1621`) is mounted by **ai-vlm** at
  `:262` (and ai-llm at `:152`). Deleting the ai-llm service block must not delete the volume —
  that takes the VLM's CUDA/JIT caches with it.
- **The three specialist loaders stay:** `face_recognizer_loader.py`, `osnet_loader.py`, and the
  plate leg. `osnet_loader` reads its weights **and pin from the models.yml row that also
  carries `triton_name: reid`** — one row feeds the CPU in-process loader and the Triton
  repository. Keep the whole row; the row is entangled, not just the Triton half.
- **Florence is legacy-reachable, not VLM-reachable [V]** (this corrects an earlier, too-strong
  draft line that put `prompt_service.py` on the live list — its only Florence token is the
  docstring example at `:712`). The real Florence runtime importers are `services/__init__.py:136,145`
  (the eager re-export — the sever-most cut, above) and `model_zoo.py:66` (the `_LOADER_MAP`
  wiring). `florence-2-large` is already `enabled: false`; `florence-2-base` is the Triton row.
  Trace the wiring, don't trust R8's roadmap line — see the loader census below.
- **`ai/gateway/main.py:60,66`** builds `ALL_MODELS` from `list(FULL_MODEL_SET)`; pruning
  FULL_MODEL_SET must move that and the `/health` reporting together, or the gateway advertises
  models its repository no longer serves.
- **`api/routes/model_management.py:162`** `ROUTER_SUFFIXES = ("/enrichment", "/enrich-lt")` —
  the live model-readiness API is built on the two enrichment routers, so the frontend
  readiness surface breaks the moment those routers go. Re-scope the endpoint, don't just delete.
- **`models.yml` is one file, many readers** (`setup_lib/model_downloader`,
  `services/model_zoo`, gateway residency, the precheck) on three different filters. A row's
  removal has four blast radii; treat the file as the shared surface it is.

## 4a. The keeps/goes census: the enrichment tier is legacy-only _by construction_ [V]

Answering the owner's "we keep the VLM and the supplemental models, right?" — yes, but the
reason is stronger than a list of keepers, and it is what makes R8's `:109` phrase _"the
in-process loaders the VLM path no longer calls"_ true rather than hopeful.

**The construction gate.** `core/container.py:508` builds the analyzer's enrichment
collaborators only inside `if get_settings().pipeline_mode == "legacy":` — `context_enricher`
and `enrichment_pipeline` are passed as kwargs then and never otherwise (`vlm_analyzer` does
not take them). So once legacy is gone, `EnrichmentPipeline` has **no construction site** and
no API route reaches it (`grep enrichment_pipeline backend/api/routes/` = 0 hits [V]). The
whole enrichment tier is not "decided to be legacy" — it becomes unreachable the moment S1
lands. R8's _"What stays: the face, re-ID and plate specialists"_ (`:114`) is therefore an
accurate, not merely aspirational, line.

**The loader census** — all 22 `backend/services/*_loader.py`, classified by real (non-
docstring) importers, marking VLM-path reachability [V]:

| verdict                      | loaders                                                                                                                                                                                                                                                                                                                                                     |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **KEEP — VLM-reachable (3)** | `face_recognizer_loader` (`vlm_specialists.py:174,328,345,535`), `osnet_loader` (`vlm_specialists.py:705`, `reid_service.py`), `fast_alpr_loader` (`vlm_specialists.py:566` — the plate leg)                                                                                                                                                                |
| legacy-only (19)             | `age_classifier, clip, depth_anything, fashion_clip, florence, gender_classifier, image_quality, pet_classifier, segformer, smoke_fire, stgcn, threat_detection, vehicle_classifier, vehicle_damage, violence, weather, yolo_world, zero_dce, vitpose` — every one reachable only via `enrichment_pipeline` / `model_zoo._LOADER_MAP` / legacy `prompts.py` |
| shared base (1)              | `model_loader_base.py` — **KEEP**, it is the base class of the three survivors                                                                                                                                                                                                                                                                              |

**Two traps inside that census:**

1. **`prompts.py` is not evidence of life.** Its loader imports at `:674-691` sit under
   `if TYPE_CHECKING:` — type-only, erased at runtime. An import grep that doesn't exclude
   the `TYPE_CHECKING` block reads 15 legacy loaders as live consumers. `prompts.py`'s real
   importers (`nemotron_analyzer`, `nemotron_streaming`, `analyzer_facade`,
   `enrichment_pipeline`) are all legacy-side.
2. **`threat_detection_loader` is legacy but the Triton `threat` model is not.** Two different
   implementations, same word. Keep `residency.py:69` `VLM_THREAT_MODEL` and the
   `models.yml:309 triton_name: threat` row; `threat_detection_loader` goes with the tier.

**Preload residency, so the S1 number is understood [V]:** `BACKEND_MODEL_PRELOAD`
(`config.py:2886`, default `false`) makes `main.py:644 select_preload_candidates` load every
enabled row that declares `preload: true` — exactly four: `osnet-ain-x1-0` (100 MB, F11),
`face-detector-scrfd` (0), `face-recognizer` (0), and `smoke-fire-yolov8n` (**350 MB,
enrichment-only** — imported only by `enrichment_pipeline`/`model_zoo`/`nemotron_analyzer`).
So the shipped VLM path preloads **three** GPU legs, and the fourth preloaded model is dead in
vlm mode. Its row's comment even says "CRITICAL: never evict, preload at startup", which
`select_preload_candidates`' own docstring records as _"decorative"_ — `never_evict` has no
consumer. Retiring smoke-fire means removing that row's `preload: true` too, or a future agent
re-reads it as resident.

## 5. Triton residency — there is no S1 risk here [V]

This section exists because an earlier draft of this file asked the owner an ill-posed
question about "moving a Triton row". The facts dissolve it:

- `ai/gateway/residency.py:65` — `VLM_MODEL_BASE = ("yolo26", "reid")`; `:69` adds `threat`
  as an opt-in. Shipped state is `GATEWAY_ENABLE_THREAT=false`
  (`docker-compose.prod.yml:482`), so **the shipped set is exactly yolo26 + reid**, and that
  is the footprint S1's 9,722 MiB was measured against.
- `FULL_MODEL_SET` at `:46-60` holds **14** models; **11** are legacy-only —
  `clip, clip_text, florence2, vehicle, fashion_clip, demographics_age, demographics_gender,
pet, depth, pose, stgcn_action`. Pruning those cannot move S1's number.
- **`threat` is not legacy** — it is the vlm set's optional fourth. Keep it.
- **Face is not in Triton at all.** SCRFD + w600k_r50 run CPU-side in the backend, loaded by
  `face_recognizer_loader` (`vlm_specialists.py:328`). Do not look for them in the gateway.
- Tests that pin the pair and must move with the change:
  `backend/tests/unit/core/test_gateway_model_set_compose.py`,
  `ai/gateway/tests/test_residency.py`, `ai/gateway/tests/test_entrypoint_residency.py`.

Open, low-stakes: once legacy is gone, `get_model_set("full")` serves only a deliberate
"bring the whole repo up" dev run (`residency.py:26`). Default is to delete it and make
`GATEWAY_MODEL_SET` hard-raise on anything but `vlm`, consistent with the no-backcompat
ruling; keeping it as a dev affordance is the owner's call.

## 6. Tables — no Alembic, and two tables that look alike but are not [V]

There is **no Alembic in this repo**: schema comes from `backend/scripts/init_schema.py` +
`core/database.py`, with hand-authored dated SQL in `docs/api/migrations/` (precedents:
`2026-09-26-face-vector-provenance-model-id.sql`, `NEM-5051-convert-alert-json-to-jsonb.sql`).
So retiring a table = delete the model class + add a dated `DROP` SQL file.

- `backend/models/enrichment.py` is **not** a wholesale delete. `pose_results:47`,
  `demographics_results:160`, `action_results:265`, `reid_embeddings:218` are legacy-only —
  `reid_embeddings` is written _only_ by `enrichment_pipeline.py:5848`.
- **`threat_detections:100` stays** — read by `services/alert_engine.py` and
  `api/schemas/alerts.py`.
- **The name trap:** `enrichment.reid_embeddings` is legacy, but
  `backend/models/household.py:155` **`PersonEmbedding` is LIVE** — the VLM re-ID leg loads
  its gallery through `household_matcher.load_person_gallery:211`, which is deliberately the
  single reader so the one-embedding-space rule (F11/item 20) holds exactly once. Also live:
  `face_identity.py:80 known_persons`, `:139 face_embeddings`.

## 7. ai_contract is the real gate on deleting `ai/` [V]

The retired serving dirs (`ai/florence`, `ai/enrichment`, `ai/enrichment-light`, `ai/clip`,
`ai/triton`) are referenced from `backend/ai_contract/` (`operations.py`, `providers.py`,
`fake/generators.py`) and `backend/tests/contracts/ai_providers/*`. That contract tier is
PR-gated (`Contract Tests (API Schema)` runs
`uv run pytest backend/tests/contracts/ -n0 --timeout=30`, `.github/workflows/ci.yml:1363`).

Named first: `operations.py:380-391` declares an `llm_completion` Operation whose evidence
string cites `nemotron_analyzer.py:465`, with `schemas/llm_completion.{request,response}`.
That row must retire in the **same** slice that deletes the analyzer, or the tier goes red.
Conclusion: retire **one provider per slice**, never `rm -rf ai/<dir>`.

## 8. Test and CI blast radius [A where not marked V]

- **Coverage gates are the merged floors, not pyproject.** `ci.yml:613` fails under 84
  (unit), `ci.yml:1215` under 37 (integration) [V]. `pyproject.toml:636 fail_under = 85` is
  the local gate; the unit shards run `--cov-fail-under=0` and only _collect_
  (`ci.yml:430-467`) [V]. Deleting legacy code moves the denominator in a direction nobody
  has measured — measure per slice, report the sign, never lower a floor.
- **Legacy-only test mass:** ~96 files / 86,970 lines / 3,175 AST test defs (89 unit files /
  3,050 defs). ~61 further files merely _mention_ legacy and must be **edited**, not deleted
  (example given by the pass: `test_model_warmup.py`, 41 nemotron refs, subject is warmup).
- **The suppression census, not a "test-count mirror."** The `99→101` in PR 6698's own commit
  messages is category `pytest_skip_imperative` of the escape-hatch census, adjudicated by
  `ea79a858` and gated at `ci.yml:101-104` against `.github/suppression-baseline.json`,
  regenerated by `scripts/suppression-registry-gen.py` [V]. Deleting test files changes that
  count → **regenerate, never hand-edit**. (An earlier draft called this a test-count mirror;
  that was wrong and the pass corrected it.)
- **Environmental noise:** 66 of those 96 files error at import _in this sandbox_ for want of
  `libxcb.so.1` (cv2 is absent — reproduced). Judge deletions by CI, not local runs.
- **No test anywhere asserts a deleted module is absent** [A — the pass grepped for it and
  found only the stale-pycache scan at `scripts/a5500_precheck.py:36`]. So the grep-gate in
  S1 is a test the implementer must author.

## 9. Docs a future agent reads [V for path existence]

- Currency, ship alone: dated in-doc banners over `docs/vss-integration/README.md:6` and
  `AGENTS.md:6`, both claiming _"nothing implemented yet"_ — false since `4bfd6fa4` made vlm
  the shipped default (`docker-compose.prod.yml:578`). Precedent to imitate:
  `06-repo-a-readiness.md:11` "Retirement note — 2026-09-21 [V]". Also `00-context.md:5`
  ("Research in progress"), `README.md:18-19` (credits the Brev matrix with measurements that
  never ran, ledger `:148`), and ledger `:3`'s rev-5 cite (spec is **rev 7**).
  **Never** rewrite frozen research prose, and never edit a spec's Status/rev line — that is
  owner-only house convention, not drift.
- Post-deletion: root `README.md`/`AGENTS.md`, `ai/AGENTS.md`, `backend/AGENTS.md`,
  `mkdocs.yml` nav, `docs/developer/{moe-offloading,llm-inference-optimization,multi-gpu}.md`,
  `docs/reference/{models,nvidia-technology-inventory}.md`, `llms.txt`.
  (Two paths an earlier draft asserted do **not** exist: `docs/developer/nvidia-technology-inventory.md`
  is actually `docs/reference/…`, and there is no `ai/llm/` — the build context is
  `./ai/nemotron` at `prod.yml:139`.)
- `docker-compose.ghcr.yml` has **no `ai-vlm` service at all** — it cannot serve the shipped
  mode today. Report it; do not "fix" it inside a retirement slice.
- `docs/superpowers/plans/2026-09-27-a5500-vlm-bringup-checklist.md:42-44` is GENERATED and
  already stale. If a slice breaks a generator assertion, report it — never hand-edit a
  render (`scripts/a5500_precheck.py` is the authority).

## 10. Known-truth hazards carried forward

- Ledger items **39–41** cite commit hashes (`2fd5c54bc`, `d7b3fd3c6`, `cedac0a64`, …) that do
  **not** resolve as git objects at this tip — a branch rewrite, _not_ fabrication. A hash
  grep reads the newest evidence as invented; it isn't.
- The newest S4 number is **16.2 s** (item 41), superseding item 39's 21.7 s.
- `origin` in this sandbox is the dead host path `/home/msvoboda/github/…`; the real branch is
  on remote `github`, and `gh` needs `--repo mikesvoboda/nemotron-v3-home-security-intelligence`.
- **Do not** delete `notification_filter.py:35 should_notify`. All three verdict rules are
  implemented; only the wiring is missing. That is M1's exit, a separate job.

## 11. Not decided here (owner's call, with the recommended default)

1. `models.yml`: delete legacy LLM rows, or keep `enabled: false` as provenance? The X-CLIP
   precedent kept them and calls the file "owner-owned, untouched". _Default: ask before deleting._
2. Does R8 reach the **enrichment AI providers** (`ai/enrichment`, `ai/enrichment-light`) or
   only the backend client + pipeline + legacy LLM? R8's own text at `:108-115` reads wider
   than the ledger's description. _Default: backend first, providers as their own slice._
3. Keep `full` as a Triton dev affordance? _Default: no — hard-raise `GATEWAY_MODEL_SET`._
4. Whether R8's "(including the 0.3 changes)" imposes anything beyond deleting the file.
5. `nemotron_url` is read by `summary_generator.py:84`, `prompt_service.py:679`,
   `pipeline_quality_audit_service.py:136` and `performance_collector.py:475` — none of them
   mode-gated. **Two of the four are confirmed live callers, not just readers [V]:**
   `summary_generator.py:84` (the hourly dashboard summary — its scheduler start at
   `main.py:1092` is gated only on `redis_client is not None`, NOT on mode) and `prompt_service`
   which `POST`s `{_llm_url}/completion` at `:938` (registered router: `main.py:1649`). Because
   `ai-llm` is `profiles: [legacy]` (`prod.yml:125`), it is _already_ down in the shipped vlm
   mode, so both features degrade to warnings today (`summary_job.py:252-255` catches
   `TimeoutError`) — deleting the LLM makes a currently-incident breakage permanent. _Owner: is
   a vlm-backed summarizer wanted (point it at `ai_vlm_url`), or is the feature retired with the
   LLM?_ Decide before S2; do not silently orphan it.
6. ~~Florence's live non-mode-gated consumers~~ — **RESOLVED [V], see §4's census.** Florence is
   legacy-reachable, not VLM-reachable; the only runtime importers are the eager
   `services/__init__.py:136,145` re-export (a sever point, not evidence of life) and
   `model_zoo.py:66`. `prompt_service`'s only Florence token is a docstring example (`:712`).
   _Default: delete with the tier, after editing the `__init__` re-export._
7. **Does retiring the attribute zoo cost understanding the owner wants back?** (owner asked
   2026-09-29; recommendation here, decision is the owner's.) The VLM receives the raw key
   frames as base64 (`vlm_client.py:499`), so Florence-2 and the 19 attribute loaders _re-perceive
   what the 8B already sees_ — re-adding them (even "with a more modern version") is a weaker
   parallel perception, not new information. The three survivors stay for a different reason: they
   are **lookups against a store the pixels can't reach** (face→known*persons, plate→registered
   vehicles, re-ID→`PersonEmbedding` gallery via `load_person_gallery`). If the owner wants more
   signal, the category worth adding is \_more detection/lookup*, not more perception:
   (a) **switch on the already-sanctioned threat specialist** — `GATEWAY_ENABLE_THREAT`
   (`prod.yml:482`, default false), resident at `residency.py:69`, D3 rev-6's optional fourth;
   it is a precision/recall detector (not a describer) and the one legitimately worth modernizing
   off `threat-detection-yolov8n` (`models.yml:309`). Costs S1 VRAM — re-measure if enabled.
   (b) R11 glass-break audio is the other off-pixels signal, deferred (no consumer card fits the
   audio stack). Counter-evidence against re-bolting the zoo: **S3 already fails 90% in every arm
   for scoring reasons, and moves ~3/20 between identical runs** (ledger `:403`) — attribute text
   adds reconciliation surface below the noise floor, inside a 1024-token verdict budget
   (`vlm_client.py:91`). _Default: proceed with the R8 deletion; treat the threat detector as a
   separate opt-in decision._

## 12. Reconciliation of the 14-agent scoping workflow (`wf_5ccaa8ff-0c7`) [V]

Every line below was re-read at the tip after the workflow returned. The workflow's _claims_
were largely sound; a meaningful number of its _paths and line numbers_ were not, so nothing was
folded in without a re-read.

**Refuter claims I REJECTED — the refuter was wrong, my original [V] stands:**

- `model_management.py:162 ROUTER_SUFFIXES = ("/enrichment", "/enrich-lt")` **exists** (re-read
  verbatim; the two lanes are explained at `:106`/`:121`). §4 keeps it.
- `main.py:733 if settings.pipeline_mode == "legacy":` **exists** (re-read verbatim).
- `ai_fallback.py` is **line drift, not fabrication**: the `NemotronAnalyzer` binding is `:47` and
  `:238`; the health-check use is `:433` (the spine cites `:434`). Off by one, real symbol.

**Where BOTH sides had the wrong path (the signal is real; the citation was not):**

- The frontend is **`frontend/`**, not `src/frontend/`. Every workflow cite of the form
  `src/frontend/src/components/enrichment-panel.ts:19-31` is a hallucinated path; my own first
  grep of `src/frontend` came back empty for the same reason. On the real tree the enrichment
  surface is **106 files**, and the child-object renderers R8's `:108` ("their frontend panels")
  actually names are real: `components/enrichment/EnrichmentViewer.tsx`,
  `components/events/EnrichmentBadges.tsx`, `EnrichmentPanel.tsx`, `EventEnrichmentSummary.tsx`,
  plus `utils/poseVisualization.ts` (draws COCO-17 skeletons from the retired pose keypoints).
- Four enrichment config fields exist and are dead in vlm mode, but at the **real** lines
  `florence_url:1582, clip_url:1586, enrichment_light_url:1594` (+ `enrichment_url`, and the
  `:1831` validator list) — not the `:751-818` range the pass reported.

**NEW, confirmed, must be in scope (missed by my first pass):**

- `backend/services/skeleton_action_service.py` — imported only by `enrichment_pipeline.py`, zero
  VLM-path importers → legacy-side, retires with the tier.
- `backend/services/pose_analysis_service.py` — **zero non-test importers at all** (already
  orphaned) → retires with the tier.

**Also corrected:** `enrichment_pipeline.py` is **7,662** lines, not the 3,334 the scoping pass
reported (that is `enrichment_client.py`'s size — the two were swapped).

**A sequencing argument worth adopting — do the table/row retirements FIRST [V reasoning].**
`select_preload_candidates` (`main.py:644`) preloads by `enabled AND preload` from `models.yml`;
nothing in it is keyed to `pipeline_mode`, so **smoke-fire's 350 MB preload runs in shipped vlm
mode today.** S1's 9,722 MiB PASS was measured _with_ that dead 350 MB inside the budget, so
retiring smoke-fire moves S1 _down_ — freeing headroom, never risking the bar (an owner-asked
question this answers). The workflow's strongest single finding: it argues the table/row
retirements belong ahead of the code deletions, not after — retiring a table's model class +
dated `DROP` is a smaller, more reversible cut than deleting a module the DI graph still names.
The spine keeps its one-slice-one-PR rule either way; this only reorders which slice goes first.
