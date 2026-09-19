# Open Questions Register

Everything not yet established. **Update this file as questions are answered** — move resolved
items into the relevant topic document with a **[V]** marker and a citation, and strike them here
with the answer and the date.

## Blocking questions

These gate the decision. None is answered.

### Q1. Does the consumer thesis survive contact with NVFP4 reality? **[?]**

Consumer Blackwell (RTX 50-series) is compute capability `sm_120`; datacenter Blackwell is
`sm_100`. NVFP4 kernel availability in vLLM / TensorRT-LLM / ModelOpt is **not uniform across
them**. Three separable claims, only the third of which decides anything:

1. A 4-bit checkpoint **exists** — and is it an official NVIDIA release or a community upload?
2. **VSS wires it** — a tested in-tree configuration, versus a capability someone must assemble.
3. **It runs on a GeForce card** — kernels exist for `sm_120` and it fits VRAM.

If FP4 does not work on consumer Blackwell, every FP4 figure in
[`02-model-inventory.md`](02-model-inventory.md) is inert and the consumer shape must be built at
FP8.

### Q2. Are NVIDIA credentials needed at runtime or only at pull time? **[?]**

`NGC_API_KEY` / `NGC_CLI_API_KEY` plus `docker login nvcr.io` are required for private NIM images
**[V]**; `NVIDIA_API_KEY` is required for agent-side NVIDIA API calls in some profiles **[V]**.

- **Pull-time only** → acceptable. The developer pulls once and ships images.
- **Per-user at runtime** → **fatal for a consumer product.** No consumer will hold an NGC
  entitlement.

This is the cheapest question to answer and one of the most decisive. Answer it early.

### Q3. What are the RT-CV and RT-Embed VRAM footprints? **[?]**

Until these are known, **no configuration can be declared to fit**. Every sizing claim that counts
only the VLM is misleading. See `skills/vss-build-vision-ai/references/services/rt-cv.md` and
`rt-embed.md`.

### Q4. Is the storage abstraction clean or leaky? **[?]**

Four backends coexist behind a `type:` discriminator **[V]**, and `LVS_DATABASE_BACKEND` is
env-selectable **[V]**. That is evidence an interface exists; it is **not** evidence the interface
is clean.

The failure mode: divergent contracts, where Milvus implements vector-only, Elasticsearch
implements full-text plus time-range, Neo4j implements traversal, and individual VSS functions
silently depend on a specific backend. If that is the shape, "implement the interface" understates
the work by an order of magnitude.

Decompose by **capability**, not by product: vector ANN search; full-text relevance ranking; graph
traversal; event time-range query; pub/sub fan-out; durable replay; metadata persistence. For each,
ask whether it is needed _at single-home scale_ — a capability essential for a city deployment may
be irrelevant for one house with four cameras.

### Q5. Is Kafka mandatory? **[?]**

Contradictory defaults observed **[V]**: `kafka_enabled: !ENV ${KAFKA_ENABLED:false}` in
`config.yaml` (off), versus `RTVI_VLM_MESSAGE_BUS=kafka` as "the current Compose default" (on).

The real question is whether the bus provides **durability and replay** or merely **decoupling**.
Redis Streams has consumer groups and persistence and would substitute for the latter. It would
not substitute if anything depends on partition ordering, log compaction, offset rewind,
exactly-once delivery, or retention-based reprocessing.

## Strategic options under evaluation

Not yet decided. Listed so a future agent does not assume option 2 was chosen.

| Option                       | Shape                                                                                                                                | Notes                                                                                                                                                      |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Models only**           | Serve Cosmos Reason / Nemotron VL with vLLM behind our existing FastAPI; keep Postgres, Redis, React UI; adopt no VSS infrastructure | Requires zero VSS integration. Our `ai/` tier is already HTTP model servers behind clients, so this is the shortest path to a demo.                        |
| **2. Lean backend upstream** | Contribute a Redis/Postgres-backed lightweight storage and bus backend to VSS, enabling a single-box profile                         | Builds relationship with the VSS team and makes the work visible. Also: contributing infrastructure _before_ proving the consumer thesis may be premature. |
| **3. Fork and embed**        | Fork VSS, strip to a lean profile, ship downstream                                                                                   | Faster than upstreaming, but invisible to NVIDIA and eventually divergent from a repo under active development.                                            |
| **4. Full adoption**         | Adopt VSS wholesale including Milvus, Elasticsearch, Neo4j, Kafka                                                                    | Heaviest. Hard to justify at single-home scale.                                                                                                            |

**Sequencing note.** Options 2 and 3 are infrastructure work. Option 1 is product work. Doing
infrastructure before the consumer thesis is proven is building a road to a place not yet
confirmed worth going.

## Questions nobody has asked yet

Flagged deliberately so they are not lost:

- **Frontend.** The stated goal includes frontend stability, but nearly all analysis so far is
  backend. VSS ships its own `services/ui/`. Does our React dashboard survive, or does a swap
  drag the frontend along?
- **Model weight distribution.** How do multi-GB weights reach a consumer user? First-run download?
  Bundled? This is a product-packaging problem with no current answer.
- **Licensing split.** Blueprint code is Apache-2.0 **[V]**, but NVIDIA model licenses frequently
  differ from surrounding code licenses. The models' commercial-redistribution terms are **[?]**
  and are a question for NVIDIA legal, not for inference from the repo.
- **Support and update burden.** VSS moves fast — commits landed during this research. A consumer
  product pinned to it inherits that cadence.
- **Domain fit.** Is home security actually what VSS is good at? Its Foundations are `alerts`,
  `search`, `warehouse`, `public safety`, `smart city` **[V]**. None is residential.
- **Dual-architecture interaction.** There is separate GB300/arm64 work in flight on this repo.
  Whether it helps or conflicts with a VSS swap is unexamined.

## In-flight investigations

Three multi-agent investigations were dispatched on 2026-09-18 and had not reported when this
document was written:

1. **Pivot assessment** — whether the test-platform work serves the VSS goal, and whether 2-3
   more days of WP4.4 mutation census is the right spend.
2. **Model deployment recon** — Q1 above, plus local deployment paths and the Cosmos Reason family.
3. **Lean backend feasibility** — Q4 and Q5 above, plus VSS contribution governance.

**If you are a future agent and these results are not reflected in this directory, they were never
folded in.** Do not assume they were. Re-run the investigation or treat the questions as open.

## What to verify first

If picking this up cold, in this order:

1. **Q2** (credentials) — cheapest, and can kill the consumer thesis outright.
2. **Q1** (FP4 on `sm_120`) — decides whether the shape is built at FP4 or FP8.
3. **Q3** (RT-CV / RT-Embed footprints) — required before any fit claim is meaningful.
4. Only then: the storage and bus questions, which are infrastructure and can wait.

## Related

- [`00-context.md`](00-context.md) — why this research exists
- [`01-vss-architecture.md`](01-vss-architecture.md) — what VSS is
- [`02-model-inventory.md`](02-model-inventory.md) — models and sizing
