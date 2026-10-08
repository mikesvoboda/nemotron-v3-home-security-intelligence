# 40 — Docs Lane

> Owns `docs/` (except `docs/reference/feature-inventory.md`, which the frontend lane owns, and
> `docs/uplevel/`, which is shared), every `AGENTS.md`, `llms.txt`, `mkdocs.yml`, the root
> `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md` and `SECURITY.md`, and the AGENTS.md validator
> (`scripts/agents_md_validator.py`, `.agents-md-validator.yml`). Read [`README.md`](README.md)
> first: its vocabulary, contract and rulings (`UR-n`) bind every package here.

The AGENTS.md files are the map agents trust most, and today it is the least accurate one: 77 of
244 files cite 213 files that exist nowhere in the repo, 57 describe retired components, and the
validator that detected dead references always exited 0 — `W1.1` gave it ratchet baselines and
real exit codes.
This lane makes the map true and keeps it true.

Its heavy work waits for the other lanes' Phase 3: rewriting docs before the code they describe is
deleted would be wasted. Phase 1 stops active misdirection; Phase 3 rewrites to the standard below.

---

## The AGENTS.md standard

The reference every package in this lane applies (UR-21).

**Where they live.** At **boundaries** only: the root, each lane root (`backend/`, `frontend/`,
`ai/`, `scripts/`, `.github/`, `synthbench/`, `monitoring/`), and packages that hold real
invariants or traps (for example `backend/services/`, `backend/ai_contract/`, `frontend/src/`). The
committed boundary list lives in `.agents-md-validator.yml`, one reason per entry. Test directories
and `docs/` subfolders have none: tests and docs index themselves.

**What an AGENTS.md holds** — what an agent cannot find by looking:

- the directory's purpose, in one to three sentences;
- its entry points: where to start reading, and which files are generated;
- its invariants and contracts: what must stay true, and the test that guards each;
- its traps: the non-obvious failure modes, each with the file or test that shows it;
- how to test it: the command;
- pointers to the design docs and decisions behind it.

**What it leaves to the environment** — file-by-file inventories, restated code, counts, and
history narratives. The directory listing, the imports and `git log` are the source of truth; a
copy of them is a cache that goes stale as soon as the code moves. That is where the 213 dead
references live.

**How it is written.** State the target behaviour rather than the prohibition. One meaning in one
place: link to the doc that owns a rule instead of restating it. The root file is the longest;
**DECIDE** a line cap per tier in `W2.1` and enforce it in the validator.

---

## Phase 1 — Stop the misleading

### W1.1 The validator with teeth

**Files:** `scripts/agents_md_validator.py`, `.agents-md-validator.yml`,
`.github/workflows/agents-md.yml`, the validator's tests.

Today's tree already holds dead references, so a gate that failed on any of them would turn every
PR red until `W1.3` lands. This package installs ratchets instead: nothing new gets in, and what
exists drains.

- [ ] Write the failing test: an `AGENTS.md` that adds a reference to a file existing nowhere makes
      the validator exit non-zero, while the dead references already in the committed baseline
      do not.
- [ ] Commit two baselines in `.agents-md-validator.yml`: the dead file references that exist today
      (as an allowlist of `file → reference` pairs), and the count of retired-name mentions
      (`florence`, `nemotron`, `enrichment`, `xclip`, `pose`, `demographics`). The run fails on a
      dead reference outside the allowlist, on a broken link, or on a retired-name count above the
      baseline. Today `main()` always returns 0.
- [ ] **MEASURE** both baselines at HEAD and put them in the PR.

**Done when:** CI passes on the current tree, and fails on a fixture `AGENTS.md` that adds a new
dead reference or a retired-name mention above the baseline.

### W1.2 Root truth

**Files:** the root `AGENTS.md`, `llms.txt`, the root `README.md`.

- [ ] Check every claim in the root `AGENTS.md` sections "Directory Structure", "Key Design
      Decisions", "Data Flow" and "Service Ports" against the code; correct each one that is false.
      Known: `data/` is called gitignored but holds 1,409 tracked fixture files; `archive/` leaves
      with `O1.5`. The auth-model and network-binding lines belong to `B1.5` and `O1.6`, which
      rewrite them when they land.
- [ ] Same for `llms.txt` and the root `README.md`.

**Done when:** the PR lists every claim checked, with the file or command that confirms or
corrects it.

### W1.3 Remove dead references now

- [ ] Delete every line in an `AGENTS.md` that cites a file existing nowhere in the repo (213 at
      `d6ba78d5`), keeping any non-discoverable knowledge the line carried.
- [ ] At the top of the six largest inventory files (`backend/services`, `backend/core`,
      `frontend/src/hooks`, `backend/api/schemas`, `backend/api/routes`, `backend/models`), add a
      banner: their inventories are unmaintained until `W3.2`; the code is the source of truth.

- [ ] Empty the dead-reference allowlist and remove it, so any dead reference fails from then on.

**Done when:** the validator reports zero dead file references with the allowlist removed, and CI
passes.

---

## Phase 2 — Prepare the standard

### W2.1 The boundary list and the line caps

- [ ] Write the boundary list into `.agents-md-validator.yml`: every directory that keeps an
      `AGENTS.md`, each with a one-line reason. Expect 30 to 50 entries.
- [ ] **DECIDE** a line cap per tier (root, lane root, package) and add it to the validator,
      reporting only until `W3.2` switches it to failing.
- [ ] Put the standard above into `docs/developer/` as its single home, and point here to it.

**Done when:** the validator config carries the boundary list and the caps, and the standard has
one home.

### W2.2 Docs rulings for `R2`

Collect this lane's owner decisions so they are ruled in the same session (contract rule 4):

- **RULING:** one home for future plans and specs. VSS material is split across `docs/plans/`,
  `docs/superpowers/` and `docs/vss-integration/` today.
- **RULING:** the register `docs/vss-integration/17-action-plan.md` (8,145 lines). Proposal: its
  OD table gains a ruling column — rulings are written inline in the options column today, which
  is how three rulings were misread during the audit — and closed issues move to a history file.
- **RULING:** whether the 28 near-identical `docs/plans/image-(re)validation-*` plans stay as
  history or go.

**Done when:** the three items are on the `R2` sheet with the facts and a recommendation each.

---

## Phase 3 — Make the map true

Each package here starts for a lane's directories only after that lane's Phase 3 packages are
`done`, so the docs describe the code that remains.

### W3.1 Boundaries only

- [ ] Delete every `AGENTS.md` outside the boundary list (`UR-21`), moving any non-discoverable
      knowledge it holds into the nearest boundary file.
- [ ] Switch the validator from "required in every directory with two code files" to "required at
      each boundary, forbidden elsewhere".

**Done when:** the validator passes in boundary mode, and the PR reports the files and lines
removed.

### W3.2 Rewrite the boundary files to the standard

One PR per lane's boundary files.

- [ ] Rewrite each boundary `AGENTS.md` to the standard: purpose, entry points, invariants with
      their guarding tests, traps, how to test, pointers. No inventories, no history narratives.
- [ ] Have the lane's own agent review the PR for accuracy before merge.
- [ ] Switch the line caps from reporting to failing.

**Done when:** every boundary file passes the validator with its cap failing, and each lane's
agent has approved its own files.

### W3.3 Living docs truth

- [ ] Delete the 30 redirect stubs in `docs/development/` (**DECIDE** whether mkdocs needs
      redirects for external links), the `docs/goal-prompt-*.txt` files and the goal prompts in
      `docs/plans/`, and the pages in no nav and linked from nowhere (54 at `d6ba78d5`; review the
      list in the PR).
- [ ] Bring living docs in line with the code: retired components appear in 20 living pages, and
      in `CHANGELOG.md` and `llms.txt`.
- [ ] Rebuild the mkdocs nav to cover every living doc.

**Done when:** a grep for `florence`, `nemotron` and `enrichment` in living docs finds only explicit
history notes (the PR reports before/after counts from `O1.7`'s script), every living doc is in
the nav, and the link checker passes.

### W3.4 Carry out the docs rulings

- [ ] Apply the `R2` rulings from `W2.2`: the single plan home, the register's shape, the
      image-validation plans.

**Done when:** each ruling is applied and the link checker passes.

---

## Phase 4 — Keep it true

The ratchets hold the map true; the cross-lane rule makes every code PR update the boundary file
whose invariants it changes. This lane reviews those edits against the standard and opens a
package only on a trigger: a validator failure, or a report of a stale claim.

---

## Kickoff prompt

Paste this to the agent taking the docs lane.

```text
You are the docs lane of the uplevel programme. Read docs/uplevel/README.md
(vocabulary, contract, rulings), then docs/uplevel/40-docs.md, including its
AGENTS.md standard, then the docs/uplevel/00-audit.md sections each package
cites.

Take the package the coordinator assigns you. Otherwise claim one yourself: the
lowest-numbered package in your current phase that is "not started", not
flagged heavy, unclaimed (no open draft PR titled [<package>]) and whose
dependencies are merged. Claim it by opening that draft PR with
gh pr create --draft --template uplevel.md (docs/uplevel/50-coordination.md).
If every remaining package in your phase waits on another lane, take the next
phase's first ready package; never start Phase 3 work on a lane's
directories before that lane's Phase 3 is done.

One package per PR. Write the failing test first. Before marking the PR ready,
dispatch a fresh-context subagent to self-review it against the package's Done
when, and record what it found. Keep commit subjects at 72 characters or fewer.
The PR sets the package's README status row to done, with its number, when it
merges.

Reviews come first (UR-32). Before you start or resume a package, run
gh pr list --state open --label review:docs; review each PR independently against
its package's Done when, the contract and the hot-file rules, post the review
comment in the form 50-coordination.md gives, and remove the label.

Read your own open PRs before resuming a package (UR-35): gh pr view <n>
--comments for each. An owner ruling or a requested change there comes before
new work; nobody tells you about a comment except by writing it.

State only what you have just read (UR-31): every commit, PR, file, test result
and question you cite comes from output you ran in the same turn.

You own docs/, every AGENTS.md, llms.txt, mkdocs.yml, the root markdown files
and the AGENTS.md validator. Write what an agent cannot find by looking; leave
inventories to the code. When the plan does not answer a question, stop and
report the question.
```
