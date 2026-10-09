# synthbench — Agent Guide

## Purpose

Synthetic benchmark generation: spec `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md`.
Tier B generation is driven by a flagship agent beside the flagship: `docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md` (spec rev 3).
Phase plans live in `docs/superpowers/plans/*-synthbench-*.md`.

## Layout

| Path                                          | What                                                                                                                                      |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `generate/weights.py` + `generate/manifests/` | pinned, sha256-verified weights; ComfyUI symlink farm (`/export/models/comfyui`)                                                          |
| `generate/window.py`                          | GPU window: stops the flagship vLLM, ALWAYS restores it                                                                                   |
| `generate/podman.py`                          | the dedicated podman store (`SYNTHBENCH_PODMAN_ROOT`): argv prefix and `TMPDIR`                                                           |
| `generate/comfy/`                             | ComfyUI container (podman), HTTP client, graph validator, per-model graph builders                                                        |
| `contract/`                                   | event contract: spec/truth/provenance models, corpus records, append-only `CorpusStore`                                                   |
| `taxonomy/`                                   | committed Tier B taxonomy YAML, its coherence rules, the seeded quota sampler, the coverage model                                         |
| `cli.py` + `__main__.py`                      | `python -m synthbench <command>`; exit 0 done, 1 error, 2 stop and ask the owner                                                          |
| `commands/`                                   | one module per command, all listed in `docs/synthbench/command-reference.md`; `cli.py` dispatches                                         |
| `export/`                                     | exports of corpus events for other tools: `vss.py`, the VSS eval store's import layout (P5a)                                              |
| `audit/`                                      | the owner's audits: the 60-still sample and page (P5a); the blind clip draw and page (ISS-038)                                            |
| `run/`                                        | `replay`: served VLMs over the export, through the shipped `VlmClient`; imports `backend` (P5a)                                           |
| `score/`                                      | `score`: metrics and the report over replays, S2 and S3 from `s_metrics`; imports `backend` (P5a)                                         |
| `prompt/`                                     | the prompt rules and the content blocklist that `check` enforces                                                                          |
| `clips/`                                      | clip rounds: the settings recorded per round, the draw, the motion rules, the H3 fit/check/strip (clips design)                           |
| `status.py`                                   | the host status files the guard and corpus-snapshot write at runtime (status/flagship.json, status/snapshots.json — generated, untracked) |
| `generate/render.py`                          | ComfyUI discovery, yield to the flagship, the per-attempt FLUX.2 graph                                                                    |
| `generate/camera/`                            | the camera stage and its committed default parameters                                                                                     |
| `host/`                                       | host-only: the guard, the renderer unit's checks, the unit files, snapshots and pruning, the agent's sandbox                              |
| `spikes/p1_bakeoff/`                          | throwaway P1 bake-off harness (not a pattern to copy)                                                                                     |

## Rules

- Only `synthbench/score/` and `synthbench/run/` may import `backend` (spec §7.1; test: `backend/tests/unit/synthbench/test_import_rule.py`).
- Tests live in `backend/tests/unit/synthbench/` (CI runs only `backend/tests/unit/`); no GPU in tests.
- Storage: weights in `HF_HOME=/export/models`, outputs in `SYNTHBENCH_ROOT=/synthbench` (the ZFS dataset `primary/export/synthbench`; `/export/synthbench` is a host symlink to it); never the root fs.
- Only `uv run python -m synthbench.generate.window run -- ...` may stop the flagship; never `docker compose up` on the dgx-inference stack.
- Our containers are podman, in a dedicated store under `SYNTHBENCH_PODMAN_ROOT` (default `/export/models/containers`), never the default one. Code builds podman argv from `podman_argv()`; shell commands use `$(uv run python -m synthbench.generate.podman) ...`. The flagship is rootful docker.
- The corpus lives at `$SYNTHBENCH_ROOT/corpus` (the ZFS dataset `primary/export/synthbench/corpus`) and is append-only; tests write only under `tmp_path`.
- `synthbench/host/` runs only on the host, under systemd, from `/synthbench/host-checkout`; the sandbox agent never runs it. The exception is `host/agent.py`, which the owner runs from a checkout to retire and recreate the agent's sandbox. The agent's document is `docs/synthbench/agent-handoff.md`.

### `generate/` and `generate/comfy/`

- The manifest `generate/manifests/p1-slate.json` (42 rows, 35 unique files) is committed and never edited by hand.
- `generate/comfy/extra_model_paths.yaml` is generated: a test checks it equals `weights.extra_model_paths_yaml(...)` for `/export/models/comfyui`.
- Graph builders follow the official ComfyUI v0.37.0 templates; the committed `generate/comfy/object_info.v0.37.0.json` capture is the authority for input names and types.
- The renderer container binds 127.0.0.1 only and carries the `synthbench.gpu=1` label, so the GPU window stops it before the flagship restarts.
- Never let pip replace the NGC base image's torch, torchvision or triton, and never pip-install PyPI torchaudio here — it is built from source against the base torch (the `Containerfile`'s `TORCHAUDIO_REF` step; PyPI's aarch64 wheel is a CUDA 13.0 build that refuses the base torch).

### `taxonomy/`

- Editing the taxonomy YAML changes its sha256: `python -m synthbench sample` exits 2 for a corpus version built from the old file. A changed taxonomy needs a new corpus version.
- Quote times in `taxonomy/tier_b_v0.yaml`: YAML 1.1 reads an unquoted `16:30` as the base-60 integer 990.
- Terms are lowercase; `synthbench check` requires a prompt to use one term from each subject's and prop's class list.
- The draw order in `sampler._one`, `allocate`'s tie-break (earlier-listed scenario wins) and `compatible_cells`' sort order are part of the contract — changing any of them changes the specs a seed produces.
- `--only` batches count toward the corpus's scenario totals, so the ±1 share bound holds only across batches drawn without `--only`. The append-only corpus cannot remove the surplus of a scenario that `--only` over-represents; the quota method stops drawing it until the corpus grows into its share.
- The scenario list, labels, risk bands and weights are the owner's to set; the v0 values are a draft (plan ruling P2-R4).

### `export/`

- Exports go under `$SYNTHBENCH_ROOT/exports/`, never into the append-only corpus or the repo (the eval store refuses repo-resident media); `export vss` refuses an `--out` that resolves inside `$SYNTHBENCH_ROOT/corpus` (exit 1).
- An export set is create-once: identical content is skipped, different content is an `ExportConflict` (exit 2). A new set is staged beside the export directory, never under it — the importer reads every `*/*/expected_labels.json` there.
- A test pins `export/vss.py`'s `CATEGORY_LABEL` equal to the importer's `_CATEGORY_LABELS`.

### `run/` and `score/`

- Replay never starts, stops or reconfigures a model server, and refuses while the renderer runs; the renderer check fails closed — only `inactive` or `failed` counts as stopped.
- The client is the shipped `VlmClient`; only its settings and transport differ per model (plan ruling P5a-R2). Its capture root is the export directory — the client refuses any image outside `foscam_base_path` — and the export is resolved before the import.
- A store whose held items differ from their sets in the export is refused (`check_current`): the importer skips an id the store holds, so an export rebuilt in place would replay old snapshots. A set the importer refuses outright (`LabelImportError`) is `ImportRefused` (exit 2).
- `run/models.py` stays backend-free: `cli.py` imports every command at startup, and `replay`'s command imports `models.py` (a test pins this).
- `ModelField` keeps the client's request extensions (its timeouts), merges a vLLM model's `request_extra` into each chat body, and puts its `system_message` ahead of the shipped user message. Only the vLLM models set any: `flagship` thinking off; `cosmos-reason2-8b` `max_tokens` 4096, 120 s, and its model card's reasoning-format system message. Cosmos must be served with vLLM's `--reasoning-parser qwen3`, so its reasoning lands in the reasoning channel and the content holds only the verdict.
- Each replay gets a new eval run id; its `run.json` names the endpoint, build and commit, and the conditions the requests actually carried (enforcement probe, request extra, `max_tokens`, the effective read timeout, the system message) — `score` states them per model in the report (decision A7).
- S2 and S3 come only from `backend/evaluation/s_metrics.py`; `score/metrics.py`'s `outcome` restates their per-row rule for slices, the gallery and the comparison, and a test holds the two equal. Labels and S3 floors come from the eval store, as `vlm_replay` derives them; facts and stills come from the export.
- Every rate is a `cell`: k, n, rate and the 95% Wilson interval, insufficient under n = 10.
- `report.md` is committed: it never names an item (per-item content lives in `results.jsonl` and `report.html`, under `$SYNTHBENCH_ROOT/runs/scores/`) and shows paths relative to `$SYNTHBENCH_ROOT`, never an absolute host path — `metrics.json`'s identity keeps them absolute.

### `audit/` and `clips/`

- The clip audit is what makes a clip number publishable: no clip number is quoted before its blind audit is complete. The clip page is blind — its inputs are the round's `audit-draw.jsonl`, the ready attempt's provenance and the mp4's bytes, never a `spec.json`: a clip's frozen motion names its scenario's props, the strongest leak the audit has.
- The audit page binds `127.0.0.1` only, its `handle` is pure and tested without a socket, and `POST /answer` is same-origin only: the `Host` must be `127.0.0.1:<port>` or `localhost:<port>`, and an `Origin`, when sent, `http://` one of those — anything else is 403 and not logged (loopback binding does not stop another page in the owner's browser). Stills and clips are served by sample index, never by a path from the request; the page's keys ignore Ctrl, Alt and Meta combinations.
- The answer log is append-only; the latest answer per (event, question) wins.
- `audit/clip_sample.py` and `audit/clip_page.py` may import the taxonomy (the scenario and prop lists are the method), but no module under `audit/` may import `backend` — which is why the clip report's Wilson intervals live in `score/clip_audit_report.py`.
- A clip event never modifies its source still (clips design C4); the motion rules — the still rules 1-4 and rule 5, no camera moves or cuts — are `clips/rules.py`.

### `spikes/` — throwaway, not a pattern to copy

- A spike unit-tests only its pure logic, in `backend/tests/unit/synthbench/spikes/`; its GPU work runs only inside a GPU window. A spike may import `synthbench.generate`; `generate/` never imports a spike (or `backend`).
- The P1 bake-off writes under `$SYNTHBENCH_ROOT/p1` (every CLI there takes `--root`); its `measure.py` and `cases.py` run on the renderer image's Python 3.12 — keep them 3.12-parseable.
- A **refusal** there is an image whose OCR text is the model's safety card; `measure.py` writes `refused` (from the text) and `card_like` (a grayscale-std diagnostic), and `report.py` counts a refusal as not good in the threat good rates while leaving it out of OWL hit, identity drift and the judge columns. We never work around a model's safety behaviour.
- `spikes/p1_bakeoff/judge.py` runs on the host only while the flagship is up, never in a GPU window, and is non-leading: the flagship sees only pixels and one fixed instruction, never the prompt, case id or path. Its model is the same family as the pipeline's VLM stage, so `propose_picks` never reads it — the report shows it as evidence plus a judge-vs-owner calibration.
