---
title: The AGENTS.md Standard
source_refs:
  - .agents-md-validator.yml:1
  - scripts/agents_md_validator.py:1
  - docs/uplevel/40-docs.md:20
---

# The AGENTS.md Standard

The reference every `AGENTS.md` is written to and reviewed against. `W2.1` moved it here from
`docs/uplevel/40-docs.md`, whose standard section now points at this file instead of holding a
second copy — a rule written in two documents is two rules the next time one of them is edited
(`UR-21`).

## Where they live

At **boundaries** only: the root, each lane root (`backend/`, `frontend/`, `ai/`, `scripts/`,
`.github/`, `synthbench/`, `monitoring/`), and packages that hold real invariants or traps (for
example `backend/services/`, `backend/ai_contract/`, `frontend/src/`).

The committed boundary list lives in `.agents-md-validator.yml` as `boundary_list`, one line of
`reason` per entry — that file is the source of truth for whether a directory is a boundary, and
this page does not copy the list. Its membership rule, also recorded in the config comment:

- the root and the seven lane roots;
- every directory with **20 or more code files** that is not a test, `docs/`, or `archive/`
  directory and that has an `AGENTS.md` today;
- the directories the standard names above, plus the ones guarding a cross-lane or CI contract
  (`backend/api/`, `ai/gateway/`, `ai/gateway/export/`, `synthbench/contract/`,
  `.github/codeql/custom-queries/`).

Test directories and `docs/` subfolders have none: tests and docs index themselves. A directory the
size rule would otherwise keep is listed **only if it has an `AGENTS.md`**, because the boundary
list is also the delete-don't-add list `W3.1` works from — a boundary with no file would be a
permanent hole in that map. `synthbench/commands/` is that case, and the validator's
`missing_agents_md` arm still reports it.

## What an AGENTS.md holds

What an agent cannot find by looking:

- the directory's purpose, in one to three sentences;
- its entry points: where to start reading, and which files are generated;
- its invariants and contracts: what must stay true, and the test that guards each;
- its traps: the non-obvious failure modes, each with the file or test that shows it;
- how to test it: the command;
- pointers to the design docs and decisions behind it.

## What it leaves to the environment

File-by-file inventories, restated code, counts, and history narratives. The directory listing, the
imports and `git log` are the source of truth; a copy of them is a cache that goes stale as soon as
the code moves. That is where the lane's headline finding came from — 77 of 244 `AGENTS.md` files
citing 213 files that existed nowhere, stated at the head of `docs/uplevel/40-docs.md` against the
`d6ba78d5` baseline. `W1.3` drained every dead reference the validator's grammar can see and
removed the allowlist that excused them, so a new one fails the run; the wider-grammar sweep that
would cover the remainder is a follow-up recorded in #6915's honest-scope section, not finished
work.

## How it is written

State the target behaviour rather than the prohibition. One meaning in one place: link to the doc
that owns a rule instead of restating it.

## Line caps

The root file is the longest, then the lane roots, then packages. The caps are per tier — root,
lane root, package — and their **values live in `.agents-md-validator.yml` under `line_caps`**, not
here; raising a cap to fit a file that outgrew it is the same mistake as raising a baseline to fit a
file that gained a retired-name mention, so the config keys are pinned in
`scripts/test_agents_md_validator.py` and a change has to move the pin in the same PR.

**Reporting only until `W3.2`.** A boundary file over its cap appears in the validator report's
`ratchet.line_caps.over` block and in the run's console summary, and the run stays green. That is
deliberate: most boundary files are over cap today, and a cap that failed on adoption would redden
every PR touching a file that is itself scheduled to be rewritten. The over-cap set is `W3.2`'s work
list, one PR per lane; `W3.2` switches the arm to failing as it rewrites.

## Enforcing it

`scripts/agents_md_validator.py` runs the checks that the standard can be checked by at all: dead
file references (zero tolerance since `W1.3`), retired-name ratchet baselines, unbalanced code
fences, the `missing_agents_md` arm, and the line caps above. Exit codes: **0** green, **1** a
content violation, **2** the gate could not run (bad config, missing key) — so a broken gate never
blames a docs PR.

`W3.1` switches the required rule from "an `AGENTS.md` in every directory with two code files" to
"required at each boundary, forbidden elsewhere", which is when this page's _where they live_
section becomes enforced rather than advisory.
