# VSS Integration

Research and design for bringing NVIDIA's **Video Search and Summarization (VSS)** blueprint's
approach to this project on **consumer gaming GPUs**, a market VSS does not serve.

> **Currency — 2026-09-29 [V].** The status line below ("design approved, nothing implemented yet")
> was true when written and is now **false.** The
> VLM path is implemented and is the shipped default: `4bfd6fa4` ("Phase 1 - the VLM path runs end
> to end and ships as the default", #6681, 2026-09-27) flipped `docker-compose.prod.yml:578` to
> `PIPELINE_MODE=${PIPELINE_MODE:-vlm}`, and the A5500 qualification run is ledger items 38-41.
> What has _not_ happened is M1-M4 closure. M1 stays open — the run's own close pointer says so
> ("the notification link is unwired", ledger `:415`) — and M2 stays open because the VLM pick is
> still the owner's, listed as deferred at [`12`](12-postponed-roadmap.md) R10. S3 fails its bar in
> every arm measured (`10/20` at `:401` against `S3_MIN = 90%`, the ruling at `:221`). Read "shipped
> as the default" as "shipping", not as "accepted". The status line is kept as the record of what was
> decided on 2026-09-23. Current state: the ledger,
> [`2026-09-23-vss-gaming-gpu-ledger.md`](../plans/2026-09-23-vss-gaming-gpu-ledger.md).

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
| [`14-specialist-model-research.md`](14-specialist-model-research.md)          | Which small models the specialists should use, and the rev 7 shortlist    |
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
