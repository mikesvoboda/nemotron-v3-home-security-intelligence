# synthbench command reference

Every command runs from the repository root as `uv run python -m synthbench <command> …`.

| Exit code | Meaning                                       |
| --------- | --------------------------------------------- |
| `0`       | done                                          |
| `1`       | the request or one of your files needs fixing |
| `2`       | stop and ask the owner                        |

An unexpected error (a bug, or a corpus file no command expects) also exits 2, with
`unexpected error: <type>: <message>`.

Paths below are relative to the corpus version directory,
`$SYNTHBENCH_ROOT/corpus/<version>/` (today `/synthbench/corpus/tierb-v0/`). `<b>` is a
batch name and `<id>` an event id.

Each section's options table lists exactly the command's options; a test compares it with
argparse (`backend/tests/unit/synthbench/test_command_reference.py`).

## `sample`

Samples fact-only Tier B specs into a new batch (design §3 step 1). The same request gives the
same specs, and running it again finishes a batch that was only partly written.

| Option         | Default             | Meaning                                                 |
| -------------- | ------------------- | ------------------------------------------------------- |
| `--batch <b>`  | required            | a new batch name: lowercase letters, digits and hyphens |
| `--n <n>`      | required            | number of events, 1-500 (a pilot is 10, a batch 50)     |
| `--seed <s>`   | from the batch name | sampler seed                                            |
| `--only <ids>` | every scenario      | comma-separated scenario ids                            |

- **Reads:** `synthbench/taxonomy/tier_b_v0.yaml`, `corpus.json`, `index.jsonl`.
- **Writes:**
  - `corpus.json` (the version's first batch only);
  - `batches/<b>/batch.json`;
  - `events/B/<id>/spec.json`;
  - `index.jsonl` rows with status `sampled`.
- **Exit 1:** a bad option, an unknown scenario, or a batch name already used with other
  options.
- **Exit 2:** the taxonomy changed since the corpus version was created; a spec differs from
  what the sampler makes; or a corpus file cannot be read or written.

## `check`

Validates `batches/<b>/prompts.jsonl` and freezes the prompts when every one passes (design §3
step 3, rules in §3.1). It also verifies the whole batch: facts against the sampler, frozen
prompts against the rules, every recorded image against its sha256, and the triage limits
(design §4). The owner runs it on the host to confirm a batch.

| Option        | Default  | Meaning    |
| ------------- | -------- | ---------- |
| `--batch <b>` | required | batch name |

- **Reads:** the batch's specs, `prompts.jsonl`, `triage.jsonl`, each `provenance.json`, and
  the images it names.
- **Writes (only when every prompt passes):**
  - `spec.json` with `prompt` and `camera_suffix` frozen;
  - `provenance.json` with attempt 1;
  - `index.jsonl` rows with status `prompted`.
- **Prints:** `Next: render --batch <b>` while some event's current attempt awaits a render.
- **Exit 1:**
  - a prompt breaks a rule (`<id>: rule N: …`);
  - a `prompts.jsonl` row is missing, malformed, unknown or duplicated, or differs from its
    frozen prompt;
  - a `triage.jsonl` row is malformed, unknown or duplicated;
  - specs were never written (it prints the `sample` command that finishes the batch);
  - no batch `<b>` (run `sample` first).
- **Exit 2:**
  - a spec's facts differ from the sampler's;
  - a frozen prompt now breaks a rule, or the camera suffix changed;
  - an attempt's seed or `prompt_sha256` is not the one its event, attempt number and frozen
    prompt give;
  - an image is missing, modified, or not named by provenance;
  - a triage limit is broken: an attempt follows one without a reroll verdict, an event was
    rerolled twice, the batch rerolled more than its 10% allows, or a recorded verdict is not
    its `triage.jsonl` row.

## `render`

Renders each frozen event's pending attempt at 1280x720 through ComfyUI (design §3 step 4).
Before every image it reads `/synthbench/status/flagship.json`, and waits, polling every
5 s, while the flagship is unhealthy or has requests waiting.

| Option                 | Default  | Meaning                                             |
| ---------------------- | -------- | --------------------------------------------------- |
| `--batch <b>`          | required | batch name                                          |
| `--budget-seconds <s>` | 480      | start no new image after this many seconds (30-480) |

- **Reads:** specs, `provenance.json`, `index.jsonl`, the status file.
- **Writes:**
  - `events/B/<id>/renders/a<k>-s<seed>.png`;
  - `provenance.json` (the render's sha256, seconds and model hashes, or a failure: a failed
    `job`, or `unreachable` when the renderer stopped answering);
  - `index.jsonl` rows with status `rendered`, or `failed` for an event whose attempt failed its
    third job.
- **Prints:** `N rendered now, M still to render`. Run it again until M is 0; with nothing
  left it prints `0 still to render`.
- **Exit 1:** an event has no frozen prompt (run `check` first); no batch `<b>` (run `sample`
  first).
- **Exit 2:**
  - the renderer is unreachable, or stops answering mid-run (recorded as `unreachable`, which
    does not count as a failed job);
  - the status file is missing or older than 30 s;
  - an attempt failed its third job. Its event is now `failed`: render marks it in
    `index.jsonl`, renders the rest, and exits 2 once. Later runs skip the event;
  - an unrecorded file is in the way.

## `camera`

Turns each new render into a 1920x1080 Foscam-style JPEG still (design §3 step 5, §7): resize,
lens distortion, IR grey at night, sensor noise, the timestamp, JPEG.

| Option        | Default  | Meaning    |
| ------------- | -------- | ---------- |
| `--batch <b>` | required | batch name |

- **Reads:** each render and its sha256.
- **Writes:** `events/B/<id>/stills/a<k>-s<seed>.jpg`, and `provenance.json` (the still's
  sha256, the parameter set, and the drawn timestamp).
- **Exit 1:** no batch `<b>` (run `sample` first).
- **Exit 2:** a render no longer matches its sha256; an unrecorded still differs; or the stage
  fails.

## `triage`

Records the verdicts in `batches/<b>/triage.jsonl` and schedules the allowed rerolls (design §3
step 7, §4). Each row is `{"event_id": …, "k": <attempt>, "verdict": "ok"}` or
`{…, "verdict": "reroll", "reason": <one of the seven>}`.

| Option        | Default  | Meaning    |
| ------------- | -------- | ---------- |
| `--batch <b>` | required | batch name |

- **Writes:** `provenance.json` (the verdict; attempt `k + 1` for a scheduled reroll), and
  `index.jsonl` rows with status `ready`, `rerolled` or `failed`.
- **Exit 1:**
  - a malformed, unknown or duplicated row;
  - an attempt that does not exist or has no still;
  - a changed verdict (verdicts are final);
  - no batch `<b>` (run `sample` first).
- **Exit 2:** a reroll past the batch's 10% cap. That event is marked failed; its verdict is
  recorded.

## `report`

Writes `batches/<b>/report.md` and `batches/<b>/sheet.html` (design §3 step 8). Every run
replaces them.

| Option        | Default  | Meaning    |
| ------------- | -------- | ---------- |
| `--batch <b>` | required | batch name |

- **report.md:**
  - counts by state;
  - rerolls by reason;
  - failed events, and failures by scenario;
  - render timing (median, p90, total) and failed jobs;
  - snapshot holds from `/synthbench/status/snapshots.json`;
  - one row per event.
- **sheet.html:** a contact sheet of every event's current still.
- **Exit 1:** no batch `<b>` (run `sample` first).
- **Exit 2:** a corpus file cannot be read or written.

## `corpus coverage`

Shows how the corpus is spread across the taxonomy, what the next n events will add, and what a
draft taxonomy would change (owner request, 2026-09-29). Read-only: it writes nothing. The model
behind the numbers, `synthbench/taxonomy/coverage.py`, is the sampler's own distribution, and a
test checks it against real draws.

| Option             | Default        | Meaning                                                                 |
| ------------------ | -------------- | ----------------------------------------------------------------------- |
| `--n <n>`          | 400            | the next n events to plan, 1-100000                                     |
| `--only <ids>`     | every scenario | draw the next n from these scenarios only, as `sample --only`           |
| `--against <file>` | none           | compare a draft taxonomy YAML with the committed one; not with `--only` |

- **Reads:** the committed taxonomy, `corpus.json`, `index.jsonl`, every `events/B/<id>/spec.json`
  and, with `--against`, that one file.
- **Writes:** nothing. A draft is never installed.
- **Prints**, for every declared value of the scenario axis and then property, zone, camera,
  lighting and weather:
  - `p`: each value's long-run chance per event;
  - `to 30`: how many more events 30 of the value would take, by chance, counting every drawn
    event that has not failed (`never` if no scenario can show the value);
  - `expect` (`share` for scenarios), `drawn` and `ready`: what the corpus holds against what
    `p` predicts;
  - `next <n>`: what the next n events would add. The scenarios come from the same allocation
    `sample` makes, so the next n include the catch-up after a `--only` batch.
- **Also prints:**
  - for each design space: how many rows it has (a designed quota's size), how many are drawn
    now and after the next n, and the events a random draw needs to touch 90% and 95% of the
    rows;
  - every value with `p` under 2%: how many scenarios can show it, counted by label (none
    benign means no false-alarm rate for that value), and the three likeliest to.
- **With `--against`:** the count of scenarios, properties, zones, cameras, cells and design-space
  rows on each side, and every value whose `p` moves (`none` if none does). A value only one side
  declares is marked `(new)` or `(dropped)`. A draft that keeps the committed `version` gets a
  warning: installed like that, it would make every command exit 2.
- **Exit 1:** a bad `--n`, an unknown scenario in `--only`, `--only` with `--against`, or a
  draft that does not load.
- **Exit 2:** the committed taxonomy does not load or no longer matches `corpus.json`, or a
  corpus file cannot be read.

## `export vss`

Owner only. Writes every ready Tier B event in the layout the VSS eval store imports
(`import_generated_items` in `backend/evaluation/label_import.py`), for P5a's replay
(`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §2). It reads the corpus
and never writes it.

| Option        | Default                                  | Meaning          |
| ------------- | ---------------------------------------- | ---------------- |
| `--out <dir>` | `$SYNTHBENCH_ROOT/exports/<version>/vss` | export directory |

- **Reads:** `corpus.json`, `index.jsonl`, and each ready event's `spec.json`, `provenance.json`
  and still.
- **Writes:** `<out>/<category>/<id>/` holding `expected_labels.json`, `still.jpg` and
  `still.json` (its attribution). Each set is written once; a re-export skips an identical set.
- **Categories:** benign and hard_negative go to `normal/`, suspicious to `suspicious/`, threat to
  `threats/`. Ambiguous events are not exported: S2 and S3 count neither label.
- **`expected_labels.json`:** `category`, `risk` (the risk band), `timestamp` (the scene time on
  2026-04-15, or 2026-01-15 for snow, in America/New_York) and a `synthbench` block with the
  event's facts.
- **Prints:** how many sets were written and how many were unchanged, and how many events were not
  exported, by reason.
- **Exit 1:** the corpus has no events.
- **Exit 2:** a set on disk differs from the corpus, a still no longer matches its sha256, a ready
  event has no still, an event's label disagrees with its group, or a corpus file cannot be read
  or written.

## `audit`

Owner only. Serves the owner's audit page on `127.0.0.1` for the P5a replay's truth check
(`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §4): 60 exported stills,
20 threat, 10 suspicious, 15 hard negative and 15 benign, each stratum spread across its lighting
values, drawn with a fixed seed. It runs until Ctrl-C.

| Option           | Default                                  | Meaning          |
| ---------------- | ---------------------------------------- | ---------------- |
| `--port <n>`     | 8765                                     | loopback port    |
| `--export <dir>` | `$SYNTHBENCH_ROOT/exports/<version>/vss` | export directory |

- **Reads:** the export's sets (never the corpus) and the answer log.
- **Writes:** appends one line per answer to `$SYNTHBENCH_ROOT/audits/<version>/audit.jsonl`
  (`event_id`, `question`, `answer`, `time`). The latest answer per question wins, so the owner can
  stop and resume, and change an answer.
- **Questions** (`y` yes, `n` no, `u` unclear): scene ("Does this show …?"), prop (threat scenes:
  "Is the … visible?"), people ("Exactly N person(s)?") and conditions (lighting and weather).
- **From another machine:** `ssh -L 8765:127.0.0.1:8765 <this host>`, then open
  `http://127.0.0.1:8765/`.
- **Exit 1:** the export has no sets, or the port cannot be opened.

## `replay`

Owner only. Replays one served VLM over the exported items through the shipped replay
(`backend/evaluation/vlm_replay.py`), for P5a
(`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §3). The model must
already be served: `replay` never starts, stops or reconfigures a model server.

| Option           | Default                                  | Meaning                                                                            |
| ---------------- | ---------------------------------------- | ---------------------------------------------------------------------------------- |
| `--model <name>` | required                                 | `qwen3-vl-8b`, `qwen3-vl-4b`, `nemotron-12b-vl`, `cosmos-reason2-8b` or `flagship` |
| `--url <url>`    | per model (below)                        | the model's endpoint                                                               |
| `--limit <n>`    | every item                               | replay only the first n items                                                      |
| `--export <dir>` | `$SYNTHBENCH_ROOT/exports/<version>/vss` | export directory                                                                   |

- **Endpoints:** the three `ai-vlm` models at `$AI_VLM_URL`, else `http://127.0.0.1:8098`;
  `cosmos-reason2-8b` at `$SYNTHBENCH_COSMOS_URL`, else `http://127.0.0.1:8099`; `flagship` at
  `$SYNTHBENCH_FLAGSHIP_URL`, else `http://127.0.0.1:8000`.
- **Checks, before the first item:** the endpoint answers; the renderer is stopped
  (`synthbench-renderer` is not active and no `synthbench-comfyui` container runs); the endpoint
  serves the named model (for `ai-vlm`, the model file stem `/props` reports; for vLLM, an id in
  `/v1/models`).
- **Client:** the shipped `VlmClient`, reading stills from the export. vLLM models run it with the
  enforcement probe off (vLLM has no `/props`) and the served model's name added to each request.
- **Reads:** the export's sets.
- **Writes:** imports the export into `$SYNTHBENCH_ROOT/eval/<version>/eval.sqlite` (a set
  already imported is skipped), then the replay's results there under a new eval run id, and
  `$SYNTHBENCH_ROOT/runs/replays/<replay_id>/run.json`: the model, endpoint, build, eval run id,
  commit and the replay's report.
- **Prints:** the items replayed, S2 false alarms, S3 incidents at level, refusals, and the path
  of `run.json`.
- **Exit 1:** the export has no sets.
- **Exit 2:** a check failed, or a set did not import for a reason other than "already imported".

## `corpus snapshot`

Host only; the owner's `synthbench-snapshot.timer` runs it every 6 h (design §6). It snapshots
`primary/export/synthbench/corpus` as `@synthbench-<UTC time>` and prunes to the newest 5,
destroying only the oldest, and only when it holds no only copy. It writes
`/synthbench/status/snapshots.json`.

No options.

- **Exit 2:** a hold (the oldest snapshot holds the only copy of a removed or changed file), or
  a zfs failure.

## `doctor`

Checks that this machine has everything a batch needs, and prints a one-sentence fix for each
gap (owner request, 2026-09-28). It runs in the agent's sandbox and on the host, as the
handoff's step 0. Read-only: it touches nothing in the corpus except one temporary probe file,
created and removed at once, to prove the corpus mount is writable.

No options.

- **Checks, in order:** OpenCV imports; `$SYNTHBENCH_ROOT/corpus` exists and is writable; the
  guard's `status/flagship.json` exists, parses and is fresh; the fresh status says the
  flagship is healthy (otherwise a `WAIT` line, which does not change the exit code); the
  renderer answers (`synthbench.generate.render.comfy_url`); any existing corpus version's
  `corpus.json` was sampled from the committed taxonomy.
- **Writes:** nothing, except the temporary probe file (created and removed at once).
- **Prints:** one line per check, `ok   <what>` or `FAIL <what>: <fix>`, then a summary line.
- **Exit 0:** every check passed or only waited on the flagship: `ready for every command`.
- **Exit 2:** one or more checks failed: `N problem(s); tell the owner the FAIL lines and
wait`.
