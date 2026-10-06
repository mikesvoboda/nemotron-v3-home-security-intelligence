# Dogfood 2026-10-06: the shipped replay path on the pinned build

**What this run is.** One replay of the full 450-still `tierb-v0` corpus through the shipped
replay machinery, on the pinned llama.cpp build `b7972-e06088da0`, to prove the ISS-087
recording chain end-to-end: identity asserted at `/props` before the first request, the build
recorded, the server settings **declared** into `run.json` by hand (acceptance #1's
declared-not-observed semantics), and the score report rendering the conditions table with the
`Build` and `Server settings` columns. It is the owner-directed OD-23 shape: the out-of-repo
`driver/replay_dogfood.py` is shipped `execute()` minus exactly one check (`renderer_stopped` —
the VLM here is a fenced `agent-gpu` container with its own VRAM budget, so the check's premise
does not hold); every other guard — health, served identity, stills, import incl.
`check_current`, the ISS-016 split import, the shipped client, the grammar probe — runs from the
library. `run.json` carries the label.

**What it is not.** A measurement of the product on 24 GB hardware, a selection reading, or a
reproduction of the 2026-10-03 sweep — that ran on `b11376` with prompt cache off; this runs on
the GB300, on `b7972`, with the compose defaults (`--cache-reuse 256`). Same weights (sha256 in
the conditions row, verified before serve), same greedy decoding.

## Readings (from `report.md`, the scorer's own output)

| Split     | S2                      | S3                      | Refusals | Uncertain |
| --------- | ----------------------- | ----------------------- | -------- | --------- |
| all 450   | 16.3% [11.9-21.9] (209) | 43.6% [37.5-49.9] (241) | 0        | 3.3%      |
| dev (386) | 16.3% [11.9-21.9] (209) | 47.5% [40.2-54.8] (177) | 0        | 3.4%      |
| holdout   | — (n=0, by design)      | 32.8% [22.6-45.0] (64)  | 0        | 3.1%      |

The `2026-10-03` control on the shipped Q4_K_M read S2 10.0%, S3 39.0%, 2 refusals on `b11376`.
The +6.3 pt S2 / +4.6 pt S3 movement under identical weights, prompt, and greedy decoding is
exactly the unrecorded-variable drift ISS-087 exists to expose — one build (`b11376` → `b7972`)
plus two cache flags, with no paired control here, does **not** let any of that movement be
attributed; attributing it needs the paired comparison the `identical` column measures, which a
single-model score correctly refuses to render ("One model scored: nothing to compare"). The
holdout reading is a leak check only — suspicious-heavy by the hash's draw, expected to sit
below dev (ISS-016 B4; the report's own words).

Latency (indicative only, GB300): median 5.76 s, p95 8.99 s, max 15.2 s per still —
`max_tokens` 2048, read timeout 180 s client-side, probe on, temp 0.0, unseeded.

## What the chain proved

- 450/450 scored, **0 refusals, 0 verification failures** — the shipped client at 180 s patient
  reads over a sleeping server (`--sleep-idle-seconds 300`) needs one pre-wake request and no
  other care; the smoke run's 3/3 `ConstrainedDecodingNotEnforced` failures were a 25 s-timeout
  wake artifact, not a transport fault.
- `run.json` recorded build, declared `server_settings`, split sha; `report.md` rendered the
  conditions row with both new columns appended last; scoring version 4; the single-model
  comparison path degraded as designed.
- `report.html` stays in the off-repo score dir (`$SYNTHBENCH_ROOT/runs/scores/20261006T231717Z/`)
  with the gallery; only these files are committed, because `metrics.json`, `results.jsonl` and
  `run.json` embed this sandbox's absolute paths (`/agents/…`), which the repo's own
  committed-report rule keeps out of git.

**Re-derive:** the driver in `driver/` runs against any endpoint serving the shipped identity:
`PYTHONPATH=<repo> SYNTHBENCH_ROOT=<root> uv run --no-sync python driver/replay_dogfood.py
<url> <export> <root> [limit]`, then `synthbench score --replay <replay_id>` with the same root.
Provenance: replay `20261006T223737Z-qwen3-vl-8b`, eval run `663da001ab5840ab85e672dba777d801`,
score `20261006T231717Z`, replay commit `8107ee63`, container `vss8-dogfood`
(image `localhost/agent-vss8/ai-vlm:sm103`, torn down after the run).
