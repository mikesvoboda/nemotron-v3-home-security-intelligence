# VSS Integration Research

Research into replacing this project's self-built AI pipeline with NVIDIA's **Video Search and
Summarization (VSS)** blueprint, targeting a market VSS does not currently serve: **consumer
gaming GPUs**.

> **Status: research in progress. Nothing here has been implemented or decided.**

## Read in this order

| Document                                               | What it answers                                         |
| ------------------------------------------------------ | ------------------------------------------------------- |
| [`00-context.md`](00-context.md)                       | Why this exists; the three-step plan; the market thesis |
| [`01-vss-architecture.md`](01-vss-architecture.md)     | What VSS actually is, and how it maps onto `ai/`        |
| [`02-model-inventory.md`](02-model-inventory.md)       | Every model, its slot, and whether it fits 24-32 GB     |
| [`03-open-questions.md`](03-open-questions.md)         | What is unresolved, and what to verify first            |
| [`04-fp4-and-deployment.md`](04-fp4-and-deployment.md) | FP4 reality and the verified consumer fit               |
| [`05-hardware-profiles.md`](05-hardware-profiles.md)   | Hardware tiering: halo / volume / entry                 |
| [`06-repo-a-readiness.md`](06-repo-a-readiness.md)     | What must be fixed in THIS repo first                   |
| [`07-lean-backend.md`](07-lean-backend.md)             | Avoiding Milvus/ES/Neo4j/Kafka; the overlay play        |

Agents should also read [`AGENTS.md`](AGENTS.md) for the evidence convention.

## The one-paragraph summary

VSS and this project independently converged on the same architecture: a perception tier of
specialized models feeding a reasoning tier. VSS's `services/rtvi/` (RT-CV, RT-Embed, RT-VLM)
maps almost one-to-one onto our YOLO26, CLIP, and Florence-2, and both systems use Nemotron for
reasoning. The opportunity is that VSS's sizing documentation stops at a 32 GB workstation card
and its edge profiles target unified-memory devices — **nothing addresses a discrete consumer
GPU.** The obstacles are VSS's heavy stateful infrastructure (Milvus, Elasticsearch, Neo4j,
ArangoDB, Kafka), an unresolved question about whether NVIDIA credentials are needed at runtime,
and an unresolved question about whether FP4 quantization actually works on consumer Blackwell.

## Evidence convention

Every claim carries a marker. **Preserve these when editing.**

- **[V]** Verified against the VSS repo, cited with `path:line`
- **[C]** Computed from a verified formula
- **[E]** External source, needs primary confirmation
- **[?]** Open question
- **[A]** Agent-reported, not independently verified — check before acting

## Contributing to this directory

- Do not promote **[?]** or **[E]** to **[V]** without citing a file and line you actually read.
- When a question in [`03-open-questions.md`](03-open-questions.md) is answered, move the answer
  into the relevant topic document and strike it in the register with the date.
- VSS is actively developed. A citation that no longer resolves means VSS moved — re-verify rather
  than assuming the finding was wrong.
