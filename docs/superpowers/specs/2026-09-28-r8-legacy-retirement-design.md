# R8 Legacy Retirement — Design

**Status:** picked up by owner instruction (2026-09-29); scope authorized, slices S0–S5 ordered.
**Date:** 2026-09-28
**Branch:** `chore/r8-legacy-retirement` (off `main` at `51f635e5`)
**Supersedes:** nothing. This is [`12-postponed-roadmap.md`](../../vss-integration/12-postponed-roadmap.md)
R8 moving from the deferred index into its own spec, which is that file's own convention at `:10`.

Evidence tags follow the repo convention ([`AGENTS.md`](../../vss-integration/AGENTS.md)):
**[V]** verified this session by source read at the named tip; **[C]** computed; **[O]** owner
statement; **[A]** agent-reported, not independently verified. Keep every marker when editing.

## 0. Why this is open now

R8's trigger in the index is _"Go-live holds 14 days"_. **That trigger is reversed by owner
instruction [O]** — the owner picked it up on 2026-09-29 with two rulings that set the shape of
the work:

- **"we do not have to support backwards compatability"** and **"we should hard raise"** [O].
  `PIPELINE_MODE=legacy` must RAISE at boot. No deprecation window, no alias, no compatibility
  shim, no one-release warning. The precedent is ledger item 20 on the re-ID swap, whose wording
  is nearly identical.
- **No A5500.** Repo + GB300 only. S1's 9,722 MiB and S4's 16.2 s belong to that box (ledger
  items 40–41) and are neither re-measured nor restated as repo claims here.

The reason the deletion matters functionally rather than cosmetically: **the legacy path is
reachable by environment variable today.** `backend/core/config.py:1084` accepts `"legacy"` and
`:1086` only logs a warning [V]. A deployment with a stale `.env` boots the unsupported pipeline.

The owner's stated motive is agent-experience, not code hygiene: _"so we dont confuse future
agents."_

## 1. What goes

Everything below verified **[V]** at `main` `51f635e5`, which is the tip this spec was written
against. The measured detail — every line number, importer and trap — lives in
[`docs/plans/2026-09-28-r8-legacy-retirement-scope.md`](../../plans/2026-09-28-r8-legacy-retirement-scope.md).

| target                                                                                  | size              | note                                    |
| --------------------------------------------------------------------------------------- | ----------------- | --------------------------------------- |
| `PIPELINE_MODE=legacy` as a value                                                       | —                 | becomes a raise; 13 branch sites delete |
| `ai-llm` service + `ai/nemotron` build context                                          | —                 | `prod.yml` profile `legacy`             |
| `backend/services/nemotron_analyzer.py`                                                 | 5,429 L           | **minus** the hoist in §2               |
| `enrichment_pipeline.py` / `enrichment_client.py`                                       | 7,662 / 3,334 L   | legacy-side                             |
| `nemotron_streaming` `analyzer_facade` `prompt_auto_tuner` `nemotron_latency_optimizer` | 575/266/205/650 L | legacy-side                             |
| `skeleton_action_service.py`                                                            | —                 | only importer is `enrichment_pipeline`  |
| `pose_analysis_service.py`                                                              | —                 | **zero** non-test importers already     |
| 19 of 22 `*_loader.py`                                                                  | —                 | see §3                                  |
| Florence-2 (loader, extractor, rows, Triton dir)                                        | —                 | legacy-reachable, not VLM-reachable     |
| legacy `FULL_MODEL_SET` Triton models (11)                                              | —                 | §4                                      |
| pose / demographics / action / `reid_embeddings` tables + `models.yml` rows             | —                 | §5                                      |
| R8's named frontend panels                                                              | —                 | §6                                      |

## 2. What stays — and the one extraction that must happen first

`nemotron_analyzer.py` is ~98% legacy, but **`:294-411` is imported by the shipped VLM path**
[V]: `vlm_client.py:65-69`, `vlm_analyzer.py:74`, `evaluation/vlm_replay.py:56`, and `main.py:773`
inside the live constrained-decoding startup gate. Symbols: `ConstrainedDecodingNotEnforced`,
`_is_length_truncated`, `build_probe_schema` (and `VerificationRowOutcome`, `PROBE_PROMPT`,
`_TRUNCATED_STOPS`, `_probe_completion`). They move to `backend/services/constrained_decoding.py`
**before** the file is deleted; deleting whole breaks vlm at import.

The three VLM-reachable loaders stay, with `model_loader_base.py`: `face_recognizer_loader`,
`osnet_loader`, `fast_alpr_loader` [V]. The other 19 are reachable only through
`enrichment_pipeline`, `model_zoo._LOADER_MAP`, or `prompts.py` under `if TYPE_CHECKING:` —
which erases at runtime and is therefore **not** evidence of life.

This is not a judgement call about capability. `core/container.py:508` builds the enrichment
collaborators **only when `pipeline_mode == "legacy"`**, and no API route constructs
`EnrichmentPipeline` [V]. Retiring legacy makes the tier unreachable by construction.

**Stays for a different reason than "it works":** the specialists are lookups against a store the
pixels cannot reach (face→`known_persons`, plate→registered vehicles, re-ID→`PersonEmbedding` via
`household_matcher.load_person_gallery`). The VLM receives the raw key frames as base64
(`vlm_client.py:499`) and perceives the scene itself, which is why Florence and the attribute zoo
are substitutions rather than additions. If more signal is wanted later, the category worth
adding is detection/lookup — the sanctioned optional threat specialist
(`GATEWAY_ENABLE_THREAT`, `residency.py:69`) — not a second perception model.

Other must-not-break [V]:

- `notification_filter.py:35 should_notify` — implemented, unwired. **M1's exit; a separate job.**
- `threat_detections` (`enrichment.py:100`) — read by `alert_engine.py`, `api/schemas/alerts.py`.
- `household.py:155 PersonEmbedding` — **LIVE**, while `enrichment.py:218 reid_embeddings` is legacy.
- The `llama-cache` named volume (`prod.yml:1621`) — mounted by **ai-vlm** at `:262`.
- `GPU_LLM`, and the `CTX_SIZE`/`PARALLEL` pair — shared with vlm's slot budget (32768/2).
- The `models.yml` row carrying `triton_name: reid` — one row feeds the CPU OSNet loader _and_
  the Triton repository. Keep the whole row.
- Triton `yolo26`, `reid`, and the opt-in `threat` — S1's PASS was measured against exactly
  `yolo26`+`reid` (`residency.py:65`, threat off by default).

## 3. Slices

One slice, one PR, TDD red-first. Order matters where noted.

| slice  | content                                                            | why here                         |
| ------ | ------------------------------------------------------------------ | -------------------------------- |
| **S0** | currency banners + this spec + the doc-12 mark                     | ships alone, before any deletion |
| **S1** | hard raise on non-`vlm`; delete the 13 branch sites                | makes legacy unreachable at boot |
| **S2** | hoist `:294-411`, then delete the analyzer + enrichment tier       | extract **before** delete        |
| **S3** | `ai_contract` providers, **one per slice**; prune 11 Triton models | PR-gated tier                    |
| **S4** | table retirements (model class + dated `DROP` SQL)                 | see ordering below               |
| **S5** | frontend panels + docs a future agent reads                        | last                             |

**Ordering argument for S4 early [V reasoning]:** `select_preload_candidates` (`main.py:644`)
preloads by `enabled AND preload` and is **not** keyed to mode, so `smoke-fire-yolov8n`'s 350 MB
preloads in shipped vlm mode today. S1's PASS was measured _with_ that dead weight inside the
budget, so retiring it moves S1 down — headroom, never risk. Table retirements are also smaller
and more reversible than deleting a module the DI graph still names.

## 4. Triton residency

`FULL_MODEL_SET` (`residency.py:46-60`) holds 14; `VLM_MODEL_BASE` is `("yolo26","reid")` (`:65`)
with `threat` opt-in (`:69`). The 11 others are legacy-only, so pruning them **cannot** move S1's
number. Face (SCRFD + w600k_r50) is CPU-side in the backend and is not in Triton at all. Tests
that pin the pair move with the change: `test_gateway_model_set_compose.py`,
`ai/gateway/tests/test_residency.py`, `test_entrypoint_residency.py`.

## 5. Schema

There is **no Alembic** in this repo. Schema comes from `backend/scripts/init_schema.py` +
`core/database.py`, with hand-authored dated SQL in `docs/api/migrations/`. So a table retires as:
delete the model class, add a dated `DROP` file. Precedents:
`2026-09-26-face-vector-provenance-model-id.sql`, `NEM-5051-convert-alert-json-to-jsonb.sql`.

## 6. Frontend

R8 `:108` names "their frontend panels" as in-scope, and they are real [V]:
`components/enrichment/EnrichmentViewer.tsx`, `components/events/EnrichmentBadges.tsx`,
`EnrichmentPanel.tsx`, `EventEnrichmentSummary.tsx`, `utils/poseVisualization.ts`. The tree is
`frontend/` — **not** `src/frontend/`, a path several scoping agents asserted and none exists.

## 7. Minefield

- Clear stale `__pycache__` before trusting a deletion guard (R8 `:118`: a stale
  `backend/api/helpers/__pycache__` false-reddened one on 2026-09-23).
- Coverage gates are the **merged floors — 84 unit (`ci.yml:613`), 37 integration (`ci.yml:1215`)**,
  not `pyproject.toml`'s 85. Report the direction; never lower a floor.
- Deleting test files moves the **suppression census** (`ci.yml:101-104` vs
  `.github/suppression-baseline.json`). Regenerate via `scripts/suppression-registry-gen.py`;
  never hand-edit a generated file.
- ~96 legacy-only test files go with their module; ~61 more merely mention legacy and are
  **edited**, not deleted.
- 66 of those 96 error at import in this sandbox (no `libxcb.so.1`/cv2). Environmental — judge by CI.
- Never rewrite frozen research prose, and never edit a spec's Status/rev line: owner-only.
- `docker-compose.ghcr.yml` has no `ai-vlm` service at all. Report it; do not fix it inside a
  retirement slice.

## 8. Open, owner's call

1. `models.yml`: delete legacy rows, or keep `enabled: false` as provenance?
2. Does R8 reach the `ai/enrichment` / `ai/enrichment-light` providers, or backend only?
3. Keep `full` as a Triton dev affordance? (Default: no — hard-raise `GATEWAY_MODEL_SET`.)
4. `nemotron_url` has **live, non-mode-gated callers** [V]: `summary_generator.py:84` (its
   scheduler at `main.py:1092` is gated on Redis only, not mode) and `prompt_service.py:938`
   (`POST`s `{_llm_url}/completion`; router registered at `main.py:1649`). Both already degrade to
   warnings because `ai-llm` is profile-`legacy` — so deleting makes an existing breakage
   permanent. Re-home them on the VLM, or retire the features explicitly.
5. Whether keeping the threat detector switched-on is wanted now (costs S1 VRAM — re-measure).
