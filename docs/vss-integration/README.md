# VSS Integration

Research and design for bringing NVIDIA's **Video Search and Summarization (VSS)** blueprint's
approach to this project on **consumer gaming GPUs**, a market VSS does not serve.

> **Status (2026-09-23): design approved, nothing implemented yet.**
> The plan is the design spec:
> [`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).
> Agents: start with [`AGENTS.md`](AGENTS.md).

## Where things stand

- **The decision.** A detector gates each FTP still. **One vision-language model** then describes,
  verifies and scores each candidate in a single constrained call. That's VSS's alert-verification
  pattern, aimed at this product's real problem: false positives.
- **Engines.** llama.cpp serves the model first. VSS's own RT-VLM joins behind the same contract in
  a later, gated phase.
- **Proof.** Development and replay run on the GB300. A Brev hardware matrix measures fit and latency per
  GPU tier, and the go-live happens on one RTX A5500 (24 GB).

**What the research found:**

- VSS's _services_ mostly don't fit a single-box product. They are video-first and tied to
  Kafka/Elasticsearch.
- Its _verification pattern_ fits exactly.
- The smallest configuration VSS validates is two 32 GB GPUs, so the consumer gap is real ([`11`](11-errata-2026-09-23.md) E2).

## Read in this order

| Document                                                                      | What it answers                                                           |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| **The design spec** (link above)                                              | What we are building, the success criteria, the phases                    |
| [`13-implementation-brief.md`](13-implementation-brief.md)                    | How the implementing agent works, including a kickoff prompt              |
| [`12-postponed-roadmap.md`](12-postponed-roadmap.md)                          | What we deliberately left for later, and what reopens each item           |
| [`10-audit-feature-inventory.md`](10-audit-feature-inventory.md)              | Which VSS features are worth importing, and what we have that VSS lacks   |
| [`09-audit-integration-surfaces.md`](09-audit-integration-surfaces.md)        | Which VSS components fit, with their exact contracts                      |
| [`08-audit-profile-anatomy.md`](08-audit-profile-anatomy.md)                  | How VSS hardware profiles work; what an upstream consumer tier would take |
| [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md)                          | Corrections to the earlier research (00-07)                               |
| [`00-context.md`](00-context.md) … [`07-lean-backend.md`](07-lean-backend.md) | The original 2026-09-18/19 research. Each doc carries an errata banner.   |

## Evidence convention

Every claim carries a marker. **Preserve these when editing.**

- **[V]** Verified against the source, cited with `path:line`
- **[C]** Computed from a verified formula
- **[E]** External source, needs primary confirmation
- **[?]** Open question
- **[O]** Stated by a human stakeholder; outranks repo inference
- **[A]** Agent-reported, not independently verified; check before acting

## Contributing to this directory

- Promote **[?]** or **[E]** to **[V]** only with a file and line you actually read.
- Record corrections as dated errata with a banner on the corrected doc. The original text stays as
  the record.
- When a roadmap item in [`12`](12-postponed-roadmap.md) is picked up, give it its own spec and mark
  it there with the date and a link.
- VSS is actively developed. A citation that no longer resolves means VSS moved; re-verify it.
