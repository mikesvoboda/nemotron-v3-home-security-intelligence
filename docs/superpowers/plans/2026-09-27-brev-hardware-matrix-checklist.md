# Brev hardware-matrix checklist (plan 2.3.1) — owner-run [O], repo-side prep only

Dated 2026-09-27. Source: spec §"Phase 2 … 2.3 Hardware matrix on Brev"
(`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md`:444-455) plus F13 (S1 and S4
come **only** from 24 GB-class hardware) and F14 (S2/S3 fixed bars; report n + 95 % Wilson).

**This document claims no execution.** Brev spend is a stop-and-ask and nothing here was run on a
Brev VM; the numbers that would come from one are exactly what this checklist exists to produce.
Every command below was checked against the repo, and the two figures that the GB300 already
settled are marked [V] with their source, so nobody re-measures them on a smaller card to find the
same thing.

## Why the matrix is the only place S1 and S4 can close

S1's bar is **peak VRAM ≤ 20.4 GiB with the detector, the specialists and the VLM resident, no CPU
offload of the VLM** (spec :73), and S4 is **p95 per-batch verdict ≤ 30 s including cold starts**
(:76) — both explicitly "measured on 24 GB-class hardware, not on the GB300". The bake-off
(`docs/plans/2026-09-27-vss-phase2-bakeoff-report.md`) therefore reports its latency as
_indicative_ and claims neither. Salience, by contrast, depends on the build (weights, quant,
engine), not on the GPU (spec :284-286), which is why the S2/S3 numbers are already in and why a
Brev run's job is fit, latency, and architecture confirmation — not a re-run of the bake-off.

**What this box's own numbers already tell each tier** (single-container readings on the GB300,
bake-off report; they predict, they do not decide):

| candidate                      | engine-reported footprint                                   | 24 GB tier (A10G / L4) | T4 16 GB                                                                                                         |
| ------------------------------ | ----------------------------------------------------------- | ---------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Qwen3-VL-4B Q4_K_M             | 7285 MiB projected (KV 4608 @ 16384 cells × 36 layers)      | fits with room         | **does not fit at that ctx** — 4608 MiB of KV alone plus 2.7 GB of weights; drop CTX_SIZE and re-read            |
| Qwen3-VL-8B Q4_K_M             | 9376 MiB projected (same KV geometry, 4455 MiB of tensors)  | fits with room         | same warning, more acute                                                                                         |
| Nemotron-Nano-12B-v2-VL Q4_K_M | 7998 MiB projected, **KV only 768 MiB** (6 KV layers of 63) | fits with room         | tightest of the three on weights (6.8 GiB of tensors), but its KV is the cheapest — the interesting one at 16 GB |

Two honesty notes on the table: those `projected` figures are **one container on a 249 GiB GPU**,
so they are the VLM's own floor — S1 asks a harder question (the whole stack resident), and a tier
that "fits" this number has not yet passed S1. And the T4 column is **arithmetic, not a
measurement**: nothing has been served on a T4 here, and the row below exists to produce that
measurement.

Note also that the table's KV figures are per-`CTX_SIZE`: 4608 MiB is 16384 cells × 36 layers, so
**the footprint grows with `CTX_SIZE × PARALLEL`** before any image
arrives. A 24 GB card serving `CTX_SIZE 32768 / PARALLEL 2` is serving 32768 tokens of KV; S1's
question is whether that is affordable _with the rest of the stack resident_, so record the ctx
settings beside every S1 number, and run the worst-case four-image batch (`~12.2K tokens`
per the 1.7 handout) rather than an idle serve.

**Dated 2026-09-28 — the table's rows are no longer symmetric (owner ruling, ledger item 35).** The
owner picked **Qwen3-VL-8B-Instruct Q4_K_M** as the shipped serving VLM ("lets go with Qwen3-VL-8B for
now. we can revisit later if needed."), so this matrix is now the measurement that **confirms or
reopens** that pick rather than informing it: the 8B row is the one S1 must clear, and the 4B row is
the named fallback (flip condition 1 — if 8B fails S1 here, the pick falls to 4B, which is why its row
stays measured and not retired). The `uncertain`-prior condition is answered by the post-item-19
corpus, not by a Brev box.

Weights for the **8B** pair, pinned by sha256 as fetched and re-verified 2026-09-28 (`Qwen/Qwen3-VL-8B-Instruct-GGUF`):
`Qwen3VL-8B-Instruct-Q4_K_M.gguf` 5,027,784,800 B `67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2`;
`mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf` 752,289,728 B `c6ba85508d82f42590e6eb77d5340369ab6fecf107a7561d809523d8aa5f3bfd`.

Weights for the **4B fallback** pair, added 2026-09-28 (`Qwen/Qwen3-VL-4B-Instruct-GGUF`) — this row did not exist until the A5500 readiness audit (ledger item 36) found that a tier is *required* to serve the fallback and the repo had no way to fetch it authentically:
`Qwen3VL-4B-Instruct-Q4_K_M.gguf` 2,497,281,664 B `66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a`;
`mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf` 453,974,304 B `30ba2c7dd3127a4561b6cba9d13d0f711c91bdb38742e2f56d73c8cb596bd06d`.
Both repo ids and all four byte counts checked against the HuggingFace API 2026-09-28 and matching the GB300 share exactly. **Take the `Q8_0` projector, never the `F16`** — each repo also ships `mmproj-…-F16.gguf` (8B 1,159,029,824 B, 4B 836,180,256 B); an F16 serve starts fine and its hash matches nothing above.
No model-zoo row exists for any serving VLM (`models.yml` is the Triton/enrichment set), so these
sha256s live in this document and the ledger — they cannot ride the zoo's `sha256:` mechanism.
**Bake-off finding F applies to a fresh box:** files fetched into the weights root arrive mode **640**,
and `ai/vlm` runs as uid 1000 `llama` — the _other_ class on a bind-mounted root — so the serve dies
`Permission denied` on a file the host reads fine. `chmod 644` both files after fetching.

## Read this before trusting any tier's number

1. **Confirm the architecture first** (spec :455, and the risk table :587 names the failure: "A
   Brev VM's GPU differs from its label"). Run this before the build, not after the run:

   ```bash
   nvidia-smi --query-gpu=name,compute_cap,memory.total --format=csv
   ```

   If `compute_cap` disagrees with the tier label, **ledger it as that tier's row with the real
   value** and build for the real value; a number produced by a card that is not the tier's card is
   not that tier's number.

2. **Build for that architecture.** `ai/vlm/Dockerfile:64` takes `ARG CUDA_ARCHITECTURES` and
   threads it into `-DCMAKE_CUDA_ARCHITECTURES`; `.env.example:598` ships **89**, so an A10G
   (sm_86) box silently builds the wrong binary if nobody edits it. This is the same
   check-before-build the A5500 handout records for 86.
3. **Two files or it is not a VLM.** A projector-less serve loads text-only and silently degrades
   every `vlm_assess` — always pass `MMPROJ_PATH` with `MODEL_PATH`.
4. **Probe before trusting a verdict.** `scripts/vlm_probes/enforcement.py --expect-build <pin>`
   and `scripts/vlm_probes/tool_calls.py --expect-build <pin>` against the served endpoint before
   any replay row is read on that tier. Both read `/props build_info`, so they also catch the
   wrong-image-served case.
5. **Read the ladder before reading a refusal rate.** Ledger findings A and B both produce
   refusals that are not the model's doing: the enforcement probe's 400-token budget truncates on
   the multimodal shape (`finish_reason: length` filed as `ignored`), and five probe failures trip
   the shared `ai-vlm` breaker so everything after answers `VlmUnavailableError` without I/O. A
   tier whose report shows a wall of refusals has probably measured its own probe. Check
   `raw_response.error` classes before the rate.
6. **Aggregate only (D10).** The report writer emits rates, n and Wilson intervals; no per-item
   rows or imagery in git.

## What a tier's replay can measure today, and what it cannot (owner item 19)

The replay runs against the frozen gen-2 store, so a tier sees exactly what the GB300 saw: **13
media-bearing stock items, whose snapshots carry an empty `detections` list and no
`specialist_outputs`** (ledger findings C and D). That means a Brev run's S2/S3 columns are the
same floor-on-grammar the bake-off reports, **not** the fixed-bar verdicts — and the deferred
question (does the VLM hedge when specialist context is present?) still cannot be asked, because
the media-bearing set and the specialist-context set are disjoint.

**The unblocking action is not on a Brev VM.** It is media for the 408 labeled synthetic items.
`scripts/synthetic_media.py` (its own `main()`, `--scenarios --per --root`, default root
`out/media/stock`) is the existing keyless path for the 13 stock scenarios; the owner's ruling is
that incident media is **synthetically generated**, not scraped (ledger F5 amendment). Once media
exists, `load_stock_items`/`build_gen2` (`backend/evaluation/eval_store.py:546`) refreeze a new
generation and the harness runs it with **no code change** — S2's n and S3's denominator are
corpus properties, and F14's report n + Wilson is precisely the guard against over-reading the 5
and 8 that exist now.

Until then: **record S1 and S4 as the tier's real contribution** (they never depended on the
corpus), and carry S2/S3 forward as the bake-off's numbers plus the standing BLOCKED note.

## Per tier

Fill one row per tier; an unrunnable tier is **BLOCKED with the probe output**, never an
unobserved pass. The replay is candidate-agnostic by construction, so no new code is needed to
run any tier — `--candidate` is the string that names what was measured.

Common shapes (run from the repo root; `PYTHONPATH=.` is required to invoke the harness by path):

```bash
# build FOR the tier (the ARG is real: ai/vlm/Dockerfile:64 -> -DCMAKE_CUDA_ARCHITECTURES)
docker build --build-arg CUDA_ARCHITECTURES=<tier cap> -t ai-vlm:tier-<cap> ai/vlm

# serve (this is the sandbox's agent-gpu form; on a Brev VM use the repo's compose/`docker run`
# equivalent with the same env, and keep the honest-VRAM discipline)
MODEL_PATH=/models/vlm/<weights>.gguf MMPROJ_PATH=/models/vlm/<mmproj>.gguf \
  GPU_LAYERS=auto CTX_SIZE=32768 PARALLEL=2 PORT=8098  # record CTX/PARALLEL with every S1 number

# probe, then replay, pinned to the commit you built from
uv run python scripts/vlm_probes/enforcement.py --url http://<endpoint> --expect-build <pin>
uv run python scripts/vlm_probes/tool_calls.py --url http://<endpoint> --expect-build <pin>

# The replay reads eval.sqlite and speaks HTTP to the endpoint - it opens no database. But it
# imports backend.core.config, whose validator REFUSES to construct Settings without a
# DATABASE_URL, and (measured here) refuses a weak password unless ENVIRONMENT says non-prod.
# So both are settings-validation incantations, not a connection: a placeholder URL is enough.
export DATABASE_URL="postgresql+asyncpg://localhost/placeholder"
ENVIRONMENT=test PYTHONPATH=. FOSCAM_BASE_PATH=<media root> \
  uv run python backend/evaluation/vlm_replay.py \
    --store <eval-store gen-2 dir> \
    --candidate "<weights+quant>@<image tag>" \
    --vlm-url http://<endpoint> --out <tier>-<candidate>.json
git rev-parse --short HEAD   # goes in the row next to the run_id the report prints
```

### - [ ] A10G — 24 GB, sm_86 (expected)

- [ ] `nvidia-smi --query-gpu=name,compute_cap,memory.total --format=csv` → name `____` cap `____` mem `____` (expect sm_86; if not, ledger the real value)
- [ ] built with `CUDA_ARCHITECTURES=86` (`ai/vlm/Dockerfile:64`; `.env.example:598` ships 89 — do not inherit it)
- [ ] serve the three candidates in turn (4B first: it is the smoke model and the cheapest fit case), `GPU_LAYERS=auto` and **no** `--n-gpu-layers` reduction — S1's bar forbids CPU offload of the VLM, so an offloaded serve is not a passing serve
- [ ] **S1 reading:** peak VRAM with detector + specialists + VLM resident, sampled (`nvidia-smi --query-gpu=memory.used --format=csv -l 1` during a replay), plus the engine's own `projected to use N MiB` / `llama_kv_cache: size = …` lines. **Bar: ≤ 20.4 GiB (0.85 × 24 GB).** Record `CTX_SIZE`/`PARALLEL` and the resident set, because the number is meaningless without them
- [ ] **S4 reading:** p95 per-batch verdict ≤ 30 s **including cold starts** — the replay's `latency_ms_indicative_only` block is per-item, so a formal S4 needs the cold-start cases too (first request after `--sleep-idle-seconds`, and after a real restart). The GB300 readings (median 6.2–7.5 s, p95 10.8–20.7 s) are indicative only
- [ ] enforcement + tool-calling probes: verdict and `build_info` recorded
- [ ] ledger row: tier, compute_cap as measured, commit, run_id, S1 peak, S4 p95, S2/S3 unchanged (they do not depend on the GPU) or restated as the same run's numbers

### - [ ] L4 — 24 GB, sm_89 (expected)

Same boxes as A10G with `CUDA_ARCHITECTURES=89` (the shipped default, so it is the tier most likely
to pass by accident — still confirm the cap). L4's FP16 throughput is the interesting variable for
S4; its 24 GB budget is the same question as A10G's.

### - [ ] RTX PRO 4500 — 32 GB, sm_120 [A] (expected; **architecture unconfirmed**)

Same boxes with the arch from step 1, not from the label. The `[A]` marker is the spec's own
hedge — this tier's compute capability is the least certain of the four, so its `compute_cap`
reading is its most important line. At 32 GB the fit question is easy; the reason to run it is the
NVFP4 reading below.

### - [ ] T4 — 16 GB (Turing; the deliberate no-fit case)

- [ ] `compute_cap` reading (Turing is sm_75; check what the build actually supports for that arch, and whether `--flash-attn on` (`ai/vlm/Dockerfile:122` default) is available — if FA must go off, record that as part of the tier's configuration, not as a silent change)
- [ ] expected finding: **the 4608 MiB KV of a 32768/2 serve plus ~2.7 GiB of 4B weights does not leave room for the rest of the stack in 16 GB.** That is a legitimate BLOCKED/does-not-fit row — but _measure_ it: read the engine's `projected to use N MiB of M free` line and report both numbers. A "does not fit" with no numbers is the same kind of claim this ledger refuses elsewhere
- [ ] if a reduced `CTX_SIZE` makes it fit, that is a **different operating point** and must be labelled as one, not filed under the 32768/2 row

## The NVFP4 question — stated as a reading task, 2.3.2

On the RTX PRO 4500, serve `nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD` in vLLM and **read the
resolved quantization method from the startup log** (`docs/vss-integration/04-fp4-and-deployment.md`
§6). That single reading settles whether NVFP4 computes natively on consumer Blackwell
(`03` Q1). **Nothing here asserts an answer**, and the checklist deliberately does not predict the
log line.

Why the log and not a benchmark: the checkpoint is w4a4 NVFP4 with group size 16
(`04:25`), and `04:43` records that such checkpoints leave the vision tower, some attention layers
and the Mamba `conv1d` unquantized — so "NVFP4" as a label is compatible with several different
resolved methods, and only the server's own resolution says which one ran. Two traps named before
the fact, both from `04`:

- **the allow-list** — `RTVI_VLM_MODEL_PATH_ALLOWLIST` must carry the `git:`-form model path
  (`04:74-75`), or the endpoint refuses before loading anything and the reading never happens;
- **the branch points** — `04:54` lists the loader branches (`:638, :1692, :1784, :2486, :3738,
:3831, :3862`); if the resolved method is not what the checkpoint declares, that list is where
  the substitution happened.

Row for it: `compute_cap` + the verbatim startup-log quantization line + the commit + one sentence
saying what it settled. If vLLM will not start for that checkpoint on that card, **that is the
answer's other half** and gets the same verbatim treatment.

## 2.3.3 — BLOCKED honestly

No Brev VM was started, no VM was priced, and **no S1 or S4 number is claimed by anything in this
document or by the bake-off report.** Brev spend is a stop-and-ask (ledger open-issue 11), so the
matrix runs when the owner runs it. The repo-side half — this checklist, the probes, the
candidate-agnostic harness, the four-line report — is what the run needs, and it is shipped.
