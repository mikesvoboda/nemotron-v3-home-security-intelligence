# synthbench command reference

Every command runs from the repository root as `uv run python -m synthbench <command> …`.

| Exit code | Meaning                                       |
| --------- | --------------------------------------------- |
| `0`       | done                                          |
| `1`       | the request or one of your files needs fixing |
| `2`       | stop and ask the owner                        |

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
prompts against the rules, and every recorded image against its sha256. The owner runs it on
the host to confirm a batch.

| Option        | Default  | Meaning    |
| ------------- | -------- | ---------- |
| `--batch <b>` | required | batch name |

- **Reads:** the batch's specs, `prompts.jsonl`, each `provenance.json`, and the images it
  names.
- **Writes (only when every prompt passes):**
  - `spec.json` with `prompt` and `camera_suffix` frozen;
  - `provenance.json` with attempt 1;
  - `index.jsonl` rows with status `prompted`.
- **Exit 1:** a prompt breaks a rule (`<id>: rule N: …`); a row is missing, malformed, unknown
  or duplicated; a row differs from its frozen prompt; or specs were never written (it prints
  the `sample` command that finishes the batch).
- **Exit 2:** a spec's facts differ from the sampler's; a frozen prompt now breaks a rule; the
  camera suffix changed; or an image is missing, modified, or not named by provenance.

## `render`

Renders each frozen event's pending attempt at 1280x720 through ComfyUI (design §3 step 4).
Before every image it reads `/synthbench/status/flagship.json`, and waits, polling every
5 s, while the flagship is unhealthy or has requests waiting.

| Option                 | Default  | Meaning                                             |
| ---------------------- | -------- | --------------------------------------------------- |
| `--batch <b>`          | required | batch name                                          |
| `--budget-seconds <s>` | 480      | start no new image after this many seconds (30-500) |

- **Reads:** specs, `provenance.json`, the status file.
- **Writes:**
  - `events/B/<id>/renders/a<k>-s<seed>.png`;
  - `provenance.json` (the render's sha256, seconds and model hashes, or a failed job);
  - `index.jsonl` rows with status `rendered`.
- **Prints:** `N rendered now, M still to render`. Run it again until M is 0.
- **Exit 1:** an event has no frozen prompt (run `check` first).
- **Exit 2:**
  - the renderer is unreachable, or stops answering mid-run;
  - the status file is missing or older than 30 s;
  - one attempt failed to render 3 times;
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
  - a changed verdict (verdicts are final).
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
- **Exit 2:** a corpus file cannot be read or written.

## `corpus snapshot`

Host only; the owner's `synthbench-snapshot.timer` runs it every 6 h (design §6). It snapshots
`primary/export/synthbench/corpus` as `@synthbench-<UTC time>` and prunes to the newest 5,
destroying only the oldest, and only when it holds no only copy. It writes
`/synthbench/status/snapshots.json`.

No options.

- **Exit 2:** a hold (the oldest snapshot holds the only copy of a removed or changed file), or
  a zfs failure.
