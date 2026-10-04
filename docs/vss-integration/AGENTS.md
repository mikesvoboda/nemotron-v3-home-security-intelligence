# VSS Integration - Agent Guide

This folder is the maintained source of truth for the AI/VLM stack: what is **decided**, **measured**,
**open** and **next**, plus the guardrails. What the stack **runs today** is described by
[`docs/architecture/ai-pipeline-current-state.md`](../architecture/ai-pipeline-current-state.md); the two
pages link to each other and neither restates the other (owner decision 2026-10-03 [O]). The
2026-09-23 text of this guide and of the README is kept verbatim in
[`21-entry-pages-record-2026-09-23.md`](21-entry-pages-record-2026-09-23.md) and is never the answer to
"what is true now".

The cold-start order, the recording table and the edit rules below are agent-authored proposals
(2026-10-03, [A]) until the owner ratifies them; the evidence convention, the VSS-repository note and
the patterns are carried over unchanged from the 2026-09-23 guide.

## Cold start (read in this order, stop when you have your answer)

1. [`README.md`](README.md) sections 1 to 6: which source wins on a conflict, what is shipped and
   measured, the decisions in force, what is open and next, the guardrails. It carries an as-of date and
   the commit it was verified against; if that commit is far behind, say so before relying on it.
2. [`17-action-plan.md`](17-action-plan.md): the living register (`ISS-nnn`, owner decisions `OD-n`).
3. The newest rows of the execution ledger,
   [`docs/plans/2026-09-23-vss-gaming-gpu-ledger.md`](../plans/2026-09-23-vss-gaming-gpu-ledger.md): what
   actually ran, one row per step. Cite a row by its heading text and commit, never by number: rows
   renumber when branches merge.
4. The design spec,
   [`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md):
   the locked decisions (D1-D12), success criteria (S1-S6) and milestones (M0-M4). Its own status line
   and its S2/S3 rows are stale (README section 7).
5. The code, compose files and tests at HEAD. They answer what is deployed.

Do not start from `13-implementation-brief.md`'s kickoff prompt (it predates the shipped VLM path) or
from the entry-pages record. README section 8 says what each doc is for and what it must never be used for.

## Recording work

Pick the row that matches what you found. Every path ends in a commit; ledger rows and spec revisions are
merged by the owner.

| You found                         | Do this                                                                                                                                                                                                                                                                                                                     |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A defect or missing piece         | Allocate the id with `python scripts/vss-next-id.py iss` (it scans every branch and worktree). Put the `#### ISS-nnn` block in its area section of `17`, add a dated line to its Intake log, and update the header count, the Dashboard, the area heading counts and (for P0 and P1) the P0 and P1 list in the same commit. |
| A measurement                     | Commit a report under `docs/benchmarks/synthbench/`, append a ledger row (owner merges), then add the README Measured row with its conditions. A number with no committed source is listed as unrecorded.                                                                                                                   |
| An owner ruling                   | The ledger row (or spec revision) is the record. Then update README section 4 with the ruling marked `[O]`, citing that source. A ruling known only from a commit message or a handoff stays unconfirmed.                                                                                                                   |
| A wrong statement in an older doc | Append an errata entry at the very end of `16`, under its `Later entries` heading (`python scripts/vss-next-id.py e` gives the number; docs 15 and 18 to 21 are corrected there too), starting with a `Corrects:` line, and add a known-false row to README section 7. Do not rewrite the frozen text.                      |
| An id collision after a merge     | Never renumber. The later issue takes a lettered suffix (`python scripts/vss-next-id.py iss --suffix-of ISS-088` prints the first letter not yet cited anywhere, for example `ISS-088c` once `ISS-088b` is taken).                                                                                                          |

`scripts/check-vss-docs-currency.py` is the gate. It recomputes the register's counts from its blocks,
checks that README's pins still match the code, that every doc is in the map, and that every id README
cites exists. Run it before you commit; its message says which side moved.

## Edit rules by file class

| Class                                     | Files                          | Rule                                                                                                                                               |
| ----------------------------------------- | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frozen record                             | `00` to `15`, `18` to `21`     | Not rewritten. A correction is an errata entry plus a README known-false row, or a dated banner above the stale claim where the gate requires one. |
| Append-only tail                          | `16-errata-2026-10-03.md`      | Add entries at the end; every earlier line stays where it is.                                                                                      |
| Live, edited in place (git is the record) | `README.md`, `AGENTS.md`, `17` | Fix a status, a count or a typo in place; correct a published issue with a dated note under its block.                                             |
| Owner-held                                | the ledger, the spec, the bars | Ledger rows and spec revisions are the owner's to merge. Never move a bar.                                                                         |

Cite code by file and symbol, and other docs by file and heading or id, not by line number: line numbers
rot when anyone inserts a line above them. Commit to the current branch; push, PR and merge need the owner's
go-ahead (README section 6). A wrong statement in `docs/architecture/ai-pipeline-current-state.md` is the
owner's page to correct: only one-line pointer edits were approved there.

## Evidence convention

**Every claim in this directory carries a status marker.** Preserve this when editing: the point is
that a future agent can tell a verified fact from an inference.

| Marker  | Meaning                                                                                                                               |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **[V]** | Verified by reading the source in-session. Cited by file and symbol, heading or id (a `path:line` only where no symbol can be named). |
| **[C]** | Computed from a verified formula. The formula and inputs are shown.                                                                   |
| **[E]** | External knowledge or web source. Needs confirmation against a primary source.                                                        |
| **[?]** | Open question. Not established.                                                                                                       |
| **[O]** | Stated by a human stakeholder. Outranks repo inference.                                                                               |
| **[A]** | Agent-reported, not independently verified. Check before acting.                                                                      |

Promote a **[?]** or **[E]** to **[V]** only with the file and line you read. A claim is **[O]** only
when a durable source records the owner saying it (a ledger heading plus commit, or a spec revision);
a commit message, a handoff or a memory note is **[A]**.

## The VSS repository

Upstream: `NVIDIA-AI-Blueprints/video-search-and-summarization` (public). Docs 00-07 cite commit
`cdad5cc0e`; docs 08-12 and the spec cite `1e94133b4`. VSS moved 78 commits and 701 files in the
four days between those commits. **Re-verify any `path:line` before relying on it**; a citation
that fails to resolve means VSS moved, not that the finding was wrong.

## Patterns

- **Name the layer.** VSS bundles three independently adoptable layers:

  1. models: RT-CV, RT-Embed, RT-VLM, LLM;
  2. storage: Milvus, Elasticsearch, Neo4j, ArangoDB;
  3. bus: Kafka.

  Say which one a question is about. The design adopts a _pattern_ from layer 1 and none of layers
  2-3.

- **Separate three model claims:**

  1. a variant _exists_;
  2. VSS _wires_ it;
  3. it _runs on a consumer GPU_.

  Only the third decides anything.

- **Size from blob sizes, never the VSS formula.** The formula understates NVFP4 by ~40% (see 02's
  boxed warning and 04). For llama.cpp, sum the weights, mmproj, KV and buffers.
- **Measure on one build.** A number measured on one llama.cpp build or quantization is not the number on
  another (ISS-087); a cross-model comparison shares one build, and a build bump is a re-qualification
  with a control replay.
- **When a roadmap item is picked up,** give it its own spec and mark it in 12 with the date and a
  link.

## Related documentation

- [`ai/AGENTS.md`](../../ai/AGENTS.md): the AI tier. Note that E4 corrects its on-demand Triton
  loading claim for production.
- [`backend/ai_contract/AGENTS.md`](../../backend/ai_contract/AGENTS.md): the contract seam the
  design extends with `vlm_assess`.
- [`docs/ROADMAP.md`](../ROADMAP.md): the project-wide post-MVP roadmap.
