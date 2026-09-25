# 13 — Implementation Brief

For the agent implementing
[`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).
The spec says **what** to build. This brief says **how to work**. The step-by-step plans are yours
to write, one phase at a time.

## Read, in this order

1. **The spec**: decisions D1-D12, success criteria S1-S6, phases G0-4 and their checklists. It is
   the single source of truth.
2. [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md) before relying on any claim in docs 00-07.
   [`12-postponed-roadmap.md`](12-postponed-roadmap.md) for what is out of scope.
3. The audits ([`08`](08-audit-profile-anatomy.md), [`09`](09-audit-integration-surfaces.md),
   [`10`](10-audit-feature-inventory.md)) only by section, when a step needs their evidence. They
   total ~30K words.
4. The `AGENTS.md` of any directory before you change it.

## How to work

- **Plan one phase at a time.** Use the `superpowers:writing-plans` skill for the phase in front of
  you (G0 first), then execute it (`superpowers:subagent-driven-development` or
  `superpowers:executing-plans`). Each phase's results reshape the next, so a plan written for M4
  today would be stale by M1.
- **Spike before building.** These five checks each take minutes to hours, and each can change the
  plan. Run them early and record every result in the ledger:
  1. Does llama.cpp `b7972` silently ignore `nvext.guided_json` (E5)? One request settles it.
  2. Does llama.cpp **enforce** `json_schema` on chat requests that carry images, at the pin you
     choose? Use the enforcement probe from spec §3.
  3. A salience smoke test: ~10 synthetic items, including benign look-alikes, through Qwen3-VL-4B
     with the constrained verdict. Does it reject the obvious benign ones?
  4. Does llama.cpp build for aarch64 + sm_103 in a CUDA container on this GB300?
  5. Does the Nemotron-12B-VL GGUF load with its mmproj on a bumped llama.cpp pin?
- **Test first.** The repo is TDD (`superpowers:test-driven-development`).
- **A milestone closes on evidence, not on written code.** Use
  `superpowers:verification-before-completion`.
- **Work in parallel where dependencies allow.** G0 and the 0.25 null-safety audit are independent.
  After the contract work (1.1), backend (1.3), residency (1.4) and frontend (1.6) can proceed in
  parallel.
- **Review at milestone boundaries.** `/codex:adversarial-review --wait --base origin/main` works on
  this host. One run found two real design defects in this spec (rev 2).

## Keep a ledger

Create `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md` before the first change. The repo precedent
is `docs/plans/2026-09-12-context-map-doc-updates.md`.

- **One row per step** (G0.1 … 4.3): status, date, evidence (the command and a summary of its
  result, plus the commit), and open issues.
- **A spike row per spike.**
- **A milestone row closes only with its S# numbers.**

Link the ledger from this directory's `AGENTS.md` "Start here" block when you create it. The
ledger is how the owner, and the next agent, know where things stand.

## Stop and ask the owner

Bring these to the owner, with the evidence prepared. Don't resolve them yourself:

- **The VLM pick at M2.** You deliver the bake-off table; the owner chooses.
- **Go-live sign-off** (step 3.1; "cutover" before rev 5).
- **The S2 and S3 bars** (`S2_MAX`, `S3_MIN`), before the bake-off report (step 2.2). Rev 5 made
  them fixed bars, and the owner sets the numbers.
- **Any change to a decision (D#) or success criterion (S#).** When reality contradicts the spec,
  the fix is a spec revision the owner approves, as with rev 2-5. Smaller factual corrections go in
  the ledger. Corrections to the VSS research go in a dated errata file in this directory.
- **The co-resident `dgx-inference` stack:** restarting the flagship vLLM, making the Cosmos stop
  permanent, or changing LiteLLM routes.
- **Brev spend:** which GPU types, and for how long, before you launch a VM.
- **The reasoning-LLM choice (R10).** The owner makes it.
- **Anything in [`12`](12-postponed-roadmap.md).** Propose it; don't build it.
- **Pushing, opening PRs and merging.** Follow the owner's go-ahead.

## Guardrails

These hold on every run:

- **The flagship vLLM stays resident.** Check `nvidia-smi` before loading any model, and keep our
  total a few GiB under the free memory. Manage our containers with `podman`; leave the
  `dgx-inference` containers (rootful docker) to the owner.
- **Real-camera data lives only in the eval store**, off-repo (D10). Wipe it from a Brev VM at
  teardown.
- **The legacy path is unsupported (spec rev 5).** Don't deploy it, measure against it, or extend
  it. Its code, including the approved 0.25 and 0.3 changes, stays in the repo with its tests
  passing until R8 deletes it.
- **Retired code stays until R8.** Build empty states, not deletions.
- **Commits pass the repo's hooks.** This host has none installed, so run
  `uvx pre-commit run --files <changed files>` and the `commit-msg` stage explicitly before each
  commit.
- **Evidence written into this directory carries its markers:** [V] [C] [E] [?] [O] [A] (see
  [`AGENTS.md`](AGENTS.md)).

## Environment pointers

- **Where each step runs:** the spec §8 table (GB300 now; the A5500 for the `vlm`-mode bring-up
  and go-live; Brev for the hardware matrix).
- **The GB300 checklist:** spec §8, Phase G0.
- **A local VSS clone** is at `~/github/video-search-and-summarization`, with `develop` at
  `1e94133b4` (fast-forwarded 2026-09-23). Re-verify citations against current upstream.
- **If a Codex review comes back suspiciously empty,** run `codex sandbox -- true` first. This host
  loads a `bwrap` AppArmor profile so Codex's sandbox can start.

## Report at each milestone

Keep reports short:

- what is proven, with the S# numbers;
- what failed, and why;
- what comes next;
- which decisions the owner needs to make.

Use aggregate metrics only; no real-camera content.

## Kickoff prompt (for the owner to paste)

```text
You are implementing the VSS gaming-GPU design in this repository, on branch
feat/vss-gaming-gpu-profile. Start at docs/vss-integration/AGENTS.md ("Start here"), then read
docs/vss-integration/13-implementation-brief.md and follow it. Begin with Phase G0 on this GB300.
Plan one phase at a time with the writing-plans skill, run the brief's five spikes first, and
record every result in the ledger. Stop and ask me at the decision points the brief lists.
```
