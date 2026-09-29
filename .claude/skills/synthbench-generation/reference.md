# synthbench-generation reference

## Corpus layout

`$SYNTHBENCH_ROOT` is `/synthbench` (a ZFS dataset; `/export/synthbench` is a host symlink to it).
`<v>` is the corpus version, which is the taxonomy's `version` (`tierb-v0` today).

| Path under `/synthbench/corpus/<v>/`           | What it holds                                                                                                                                   |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `corpus.json`                                  | the version's manifest: `taxonomy_sha256`, `render_size`                                                                                        |
| `index.jsonl`                                  | one row per event state change: `event_id`, `batch`, `scenario`, `label`, `status`, `time`. The latest row per event wins.                      |
| `batches/<b>/batch.json`                       | `n`, `seed`, `prior_counts`, `only`, `event_ids`: everything `check` re-derives the specs from                                                  |
| `batches/<b>/prompts.jsonl`                    | your prompts, one `{"event_id", "prompt"}` per line                                                                                             |
| `batches/<b>/triage.jsonl`                     | your verdicts, one `{"event_id", "k", "verdict", "reason"?}` per line                                                                           |
| `batches/<b>/report.md`, `sheet.html`          | the batch views that `report` rewrites                                                                                                          |
| `events/B/<event_id>/spec.json`                | the facts, plus `prompt` and `camera_suffix` once frozen                                                                                        |
| `events/B/<event_id>/provenance.json`          | `attempts[]`: `k`, `seed`, `prompt_sha256`, `render`, `still`, `render_seconds`, `render_failures[]`, `camera_params`, `overlay_time`, `triage` |
| `events/B/<event_id>/renders/a<k>-s<seed>.png` | the 1280x720 FLUX.2 render of attempt `k`                                                                                                       |
| `events/B/<event_id>/stills/a<k>-s<seed>.jpg`  | the 1920x1080 camera-stage still that you triage                                                                                                |

Event ids are `B-<batch>-NNN`. The index statuses run `sampled` → `prompted` → `rendered`, then
`ready`, `rerolled` or `failed`. Also under `/synthbench/status/` (read-only in the sandbox):

- `flagship.json`, the guard's status, which `render` waits on;
- `snapshots.json`, the snapshot timer's result: any hold is the owner's to resolve.

## Spec fields

`cell` holds `scenario`, `group`, `property_type`, `zone`, `camera`, `lighting`, `weather` and
`artifacts[]`. The spec also has:

- `scene_time` (HH:MM: write it as light, never as a clock time);
- `label` (`incident`/`benign`/`ambiguous`) and `risk_band` `[lo, hi]`;
- `subjects[]` (`id`, `class`, `role`, `attributes.clothing`);
- `props[]` (`id`, `class`, `held_by`).

## Taxonomy model (`synthbench.taxonomy.model`)

`load_taxonomy()` returns a `Taxonomy` with these fields:

| Field                           | Items                                                                                                                             |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `version`                       | the corpus version string                                                                                                         |
| `zones`                         | zone ids                                                                                                                          |
| `lighting`                      | `id`, `hours`, `weight`, `outdoor_only`                                                                                           |
| `weather`                       | `id`, `weight`                                                                                                                    |
| `artifacts`                     | `id`, `probability`, `lighting`, `weather`, `outdoor_only`                                                                        |
| `cameras`                       | `id`, `zones`, `indoor`                                                                                                           |
| `properties`                    | `id`, `zones`                                                                                                                     |
| `colors`, `garments`, `clothed` | the clothing vocabulary, and the subject classes that get clothing                                                                |
| `terms`                         | `{class: accepted words}`. Rule 1 of `check` needs one of these per subject and prop.                                             |
| `scenarios`                     | `id`, `group`, `label`, `risk_band`, `weight`, `zones`, `lighting`, `weather`, `subjects[one_of, role]`, `props[one_of, held_by]` |

Helpers: `compatible_cells(tax, scenario)`, `lighting_options`, `weather_options`,
`artifact_options`, and `taxonomy_sha256()`. The hash is canonical JSON, so comment and layout
edits don't change it and value edits do. The sampler is
`synthbench.taxonomy.sampler.sample_specs(tax, *, version, batch, n, seed, prior, only)`; it is
pure, so it is safe to call for simulations.

## Where the rules live

- Prompt rules: `synthbench/prompt/rules.py`; the blocked phrases are in
  `synthbench/prompt/blocklist.yaml`.
- Triage reasons and limits: `docs/synthbench/agent-handoff.md`.
- Every command's options and exit codes: `docs/synthbench/command-reference.md`.
- The design: `docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md`.
