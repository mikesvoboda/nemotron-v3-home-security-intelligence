# Synthbench P5a: the live probe (plan Task 1)

- **Date:** 2026-09-29, about 22:15–00:50 UTC, on the GB300 (sm_103, 256.7 GB). The flagship
  was resident throughout (`VLLM::EngineCore`, 191.5 GB, `/health` 200); the renderer was stopped.
- **Code:** branch `docs/synthbench-p5a-vlm-replay`: the built `export vss` and `replay` (plan
  Tasks 2–5), then the fixes the probe led to (`ad175fe1`, `2d581e6c`, `c7a6e992`, `e2f92866`).
- **Plan:** `docs/superpowers/plans/2026-09-29-synthbench-p5a-vlm-replay.md`. **Spec:**
  `docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` (amended: A6, A7).

The probe brought up what already existed and ran the built commands against real servers. It
changed the design twice: the owner chose an ideal detector (A6) and a reasoning prompt for
Cosmos only (A7).

## Serving

**Weights.** Six GGUF files were copied from `/agents/agent-vss1/gpu/models/vlm/` to
`/export/models/ai_models/vlm/`: the product pair, the Qwen3-VL-4B pair and the Nemotron-12B-VL
pair. The copy took 0.9 s (ZFS cloned the blocks) and needed no sudo. Modes are 0755 for
directories and 0644 for files. `SHA256SUMS` was checked against the source folder: 6 of 6 OK.
The product model is `67d1659b…` (`Qwen3VL-8B-Instruct-Q4_K_M.gguf`), its mmproj `c6ba8550…`.

**Images.** `podman save | podman load` copied the images from the agent-gpu store (uid 1001) into
the default rootless store in 31 s. The IDs match the source: `sm103-v12` is `d723137f4ed4`
(3.59 GB) and `sm103-b11090` is `a0fcc4267d5a` (3.63 GB).

**`.env.bench` and compose.**

- `config` also needs `POSTGRES_PASSWORD`, which the backend requires and `ai-vlm` never reads. It
  is passed on the command line, never written to the committed file.
- **Refuted:** `podman compose` cannot start `ai-vlm` with its GPU. The docker-compose plugin goes
  through podman's Docker API, which drops the CDI device `nvidia.com/gpu=0`. The container logs
  "NVIDIA Driver was not detected" and `llama-server` exits 127 on `libcuda.so.1`.
- `podman-compose` 1.0.6 passes `--device nvidia.com/gpu=0` and works. It has no `--profile`;
  naming the service is enough. It expects the image
  `localhost/nemotron-v3-home-security-intelligence_ai-vlm:latest`, so `sm103-v12` is tagged with
  that name.
- For P5b: this host's GPU compose services need `podman-compose`.

**`ai-vlm` (Qwen3-VL-8B).**

- Ready within about 6 s of the start (the weights were in page cache); `/health` answered 200 at
  the first poll.
- `/props` reports `b7972-e06088da0` and `/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf`, with 2 slots
  of 16,384 tokens each (the shipped 32k).
- It holds 11,216 MiB; the plan estimated about 10 GB.

**Cosmos-Reason2-8B (vLLM).**

- The flagship's image, `vllm/vllm-openai@sha256:c2b7c425…` (id `79a6507d5859`, 22.4 GB, vLLM
  `0.28.1rc1.dev681+ge7edf17ce`), was pulled into synthbench's store in 3 minutes.
- It serves offline from the HF snapshot `a9fae2cf89dc64db96b12860417f0eb403013bb9` (16.33 GiB)
  at `--gpu-memory-utilization 0.10`.
- A cold start is 170–190 s (weights 6.6 s, model load 18.6 s, `torch.compile` 34.8 s). It holds
  24,938 MiB.
- `/v1/models` reports `nvidia/Cosmos-Reason2-8B` with `max_model_len` 16384.

## The built commands

**Export.** 450 sets are written in 1.3 s: `normal` 209, `suspicious` 45 and `threats` 196, so
241 incidents. Not exported: 9 ambiguous and 1 failed. That is 130 MB of stills and labels.

**Replay plumbing.**

- Two `replay --model qwen3-vl-8b --limit 5` runs took 50 s and 42 s. Each scored 5 items with 0
  refused, under distinct eval run ids with 5 results each.
- The first run imported 450 items; the second found all 450 already imported. The verdicts were
  identical across the two runs.
- Median latency is 5.5–6.2 s per item, max 12.5–16.3 s. These are indicative only (spec A1).
- The store's items are dated 2026-01-15 (snow) or 2026-04-15, with offsets −05:00 and −04:00.
- Harmless noise: "Service 'ai-vlm' not registered" prints once per item. It comes from the
  product's degradation manager, which is not initialized in a CLI process.

## What changed the design

**1. With no detections, the VLM declines to judge (→ spec A6).** The shipped prompt asks the VLM
to verify detected candidates. With stills only it reads `Detections: []`, and it answered:

- Qwen3-VL-8B: `uncertain`, risk 0 on 5 of 6 incident stills ("No detections provided; cannot
  verify or assess risk") and on 4 of 5 benign stills;
- the flagship with thinking off: the same.

Only a still with a knife plainly in hand scored (85). The owner chose the **ideal detector**:
each exported set now carries the event's declared subjects and props as detections (Task 3a,
`e2f92866`). Rows carry an object type and confidence 1.0, with no box.

**2. The flagship thinks past the budget (fixed in `ad175fe1`).**

- It spent the product client's whole 1024-token budget reasoning: `reasoning_tokens` 1024, empty
  content, `VlmTruncatedError` on 2 of 3 items.
- With `chat_template_kwargs.enable_thinking=false` it answers schema-valid in 187 tokens.
- `replay` now sends that flag for the flagship only, at the shipped budget.

**3. Cosmos loops under the schema (→ spec A7).**

- Cosmos-Reason2-8B writes schema-valid JSON, but its first `evidence` string runs away. One item
  was 142 sentences, only 14 of them distinct: a three-sentence cycle repeated 44 times, running
  past both 1024 and 4096 tokens.
- Its recommended sampling (temperature 0.7, top-p 0.8, top-k 20) still looped on 2 of 3 items.
- Its chat template has no thinking switch; it reasons only when asked.
- The owner chose **Cosmos only**: `replay` adds the model card's `<think>` format instruction as
  a system message, with a budget of 4096 tokens and 120 s (`2d581e6c`, `c7a6e992`). The server
  runs with `--reasoning-parser qwen3`.
- The three items that had looped then finished in 467–519 tokens, with the reasoning kept apart
  from the JSON.

**Also fixed from the task review, before the probe could hit them (`ad175fe1`):**

- vLLM requests had lost the client's timeouts.
- A relative `--export` stored unusable media paths.

## A spread probe of each model (indicative)

Twenty items per model, five from each group, the same items for every model, with declared
detections. The product prompt went to Qwen and the flagship; Cosmos had its A7 prompt.
**hit** means the score reached the incident's level (S3's rule); **clear** means a benign
scene was scored below medium (S2's rule).

| Model                   | Threat (5) | Suspicious (5) | Hard negative (5) | Benign (5) | Refused            |
| ----------------------- | ---------- | -------------- | ----------------- | ---------- | ------------------ |
| Qwen3-VL-8B (`ai-vlm`)  | 1 hit      | 0 hit          | 5 clear           | 4 clear    | 0                  |
| Flagship (thinking off) | 3 hit      | 1 hit          | 5 clear           | 5 clear    | 0                  |
| Cosmos-Reason2-8B (A7)  | 0 hit      | 0 hit          | 4 clear           | 4 clear    | 3 (length at 4096) |

- **Qwen3-VL-8B:** it called every detection `confirmed`, but kept risk low. A handgun scored 75
  (band 85–100), a knife 70, fire 10, and the suspicious scenes 0–10.
- **The flagship:** a masked intruder at night scored 95, a knife 85, fire 85, and peering into
  windows 65. A handgun scored 45.
- **Cosmos:** mostly `uncertain` 0, with a handgun at 30 and a knife at 50.

The shipped prompt is a verification prompt ("is the detection real?"), and the risk score
follows from it. These twenty items do not measure anything; Task 7's full run does. They show
that the harness now separates the models.

## Left for the full run (Task 7)

- The artifacts made before A6 were moved, not deleted, to `/synthbench/p5a-probe-pre-detections/`.
  The current export and eval store carry declared detections.
- `qwen3-vl-4b` and `nemotron-12b-vl` were not served; they run only if the owner asks.
- Cosmos's refusal rate on the full set is still open (3 of 20 in the spread).
