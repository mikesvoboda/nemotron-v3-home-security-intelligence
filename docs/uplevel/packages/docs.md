# Docs packages

Open packages of the docs lane: every package whose row in the
[README status table](../README.md#status) is not `done`. How to claim, build, review and merge
one is in [`../rules.md`](../rules.md) and [`../roles/lane.md`](../roles/lane.md). Finished
packages are in [`../history/packages-done.md`](../history/packages-done.md).

## Lane scope

- The lane owns `docs/` (except `docs/reference/feature-inventory.md`, which the frontend lane owns,
  and `docs/uplevel/`, which is shared), every `AGENTS.md`, `llms.txt`, `mkdocs.yml`, the root
  `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md` and `SECURITY.md`, and the AGENTS.md validator
  (`scripts/agents_md_validator.py`, `.agents-md-validator.yml`), except the `AGENTS.md` lines
  UR-81 gives to the lane whose change updates them.
- The AGENTS.md files are the map agents trust most, and at the audit it was the least accurate
  one: 77 of 244 files cited 213 files that exist nowhere in the repo, and 57 described retired
  components. `W1.1` gave the validator ratchet baselines and real exit codes. This lane makes the
  map true and keeps it true.
- When its Phase 3 work starts: UR-68.
- **The AGENTS.md standard** is
  [`docs/developer/agents-md-standard.md`](../../developer/agents-md-standard.md) (UR-88, moved
  there by `W2.1`); `W3.2` rewrites the boundary files to it.

## Phase 3 — Make the map true

Each package here starts on a lane's directories as UR-68 allows.

### W3.1 Boundaries only

**Flags:** none. **Depends on:** `R2`; the target lane's Phase 3 `done`.

- [ ] Delete every `AGENTS.md` outside the boundary list (`UR-21`), moving any non-discoverable
      knowledge it holds into the nearest boundary file.
- [ ] Switch the validator from "required in every directory with two code files" to "required at
      each boundary, forbidden elsewhere".

**Done when:** the validator passes in boundary mode, and the PR reports the files and lines
removed.

### W3.2 Rewrite the boundary files to the standard

**Flags:** none. **Depends on:** `R2`; the target lane's Phase 3 `done`.

One PR per lane's boundary files.

- [ ] Rewrite each boundary `AGENTS.md` to the standard: purpose, entry points, invariants with
      their guarding tests, traps, how to test, pointers. No inventories, no history narratives.
- [ ] Have the lane's own agent review the PR for accuracy before merge.
- [ ] Switch the line caps from reporting to failing. "Failing" is a per-file baseline for the
      boundary files that may only fall (the `retired_name_baseline` / `ratchet-check.py`
      doctrine: about 42 committed numbers, maintained with the census pattern); the plain tier
      threshold stays the rewrite target. The caps stay reporting-only, with no growth ratchet,
      until this package (ruling 33).
- [ ] The 20-code-file membership rule stands, with `synthbench/commands` as its one pinned
      exception (ruling 33).

**Done when:** every boundary file passes the validator with its cap failing, and each lane's
agent has approved its own files.

### W3.3 Living docs truth

**Flags:** none. **Depends on:** `R2`; the target lane's Phase 3 `done`.

- [ ] Delete the 30 redirect stubs in `docs/development/` (**DECIDE** whether mkdocs needs
      redirects for external links), the `docs/goal-prompt-*.txt` files and the goal prompts in
      `docs/plans/`, and the pages in no nav and linked from nowhere (54 at `d6ba78d5`; review the
      list in the PR).
- [ ] Bring living docs in line with the code: retired components appear in 20 living pages, and
      in `CHANGELOG.md` and `llms.txt`.
- [ ] Rebuild the mkdocs nav to cover every living doc.
- [ ] Fix the dead citations outside the scoped `validate_docs` gate (`ci.yml:298-304` runs level 1
      over `docs/decisions`, `docs/deployment`, `docs/getting-started`, `docs/operations` and
      `docs/ui` only), widening `ci.yml`'s scoped list as UR-124 says. Ops reviews the `ci.yml` list
      entries (ruling 140).

**Done when:** a grep for `florence`, `nemotron` and `enrichment` in living docs finds only explicit
history notes (the PR reports before/after counts from `O1.7`'s script), every living doc is in
the nav, and the link checker passes. A hit on the repository's own GitHub slug,
`mikesvoboda/nemotron-v3-home-security-intelligence`, in a URL or bare, counts as a history note,
as `.agents-md-validator.yml` already treats the repository's own name (owner ruling 70).
`scripts.validate_docs` at level 1 passes over every living-docs directory, and `ci.yml`'s scoped
list covers them, each directory added in the PR that fixes its citations (owner ruling 140).

### W3.4 Carry out the docs rulings

**Flags:** none. **Depends on:** `R2`.

- [ ] Apply the `R2` rulings from `W2.2`: the single plan home, the register's shape, the
      image-validation plans. `R2a` ruled them (ruling 89):
  - **OD-33:** future plans go in `docs/superpowers/<date>-<slug>/`; `docs/plans/` freezes as
    history; `docs/vss-integration/` stays the register's live home; nothing moves.
  - **OD-34:** the register gains a ruling column, and closed issues move to a history file. Each
    moved issue leaves a one-line dated pointer; the two halves are separate commits; filling the
    column is a read of all 32 rows, not a grep.
  - **OD-35:** the 26 image-(re)validation plans are deleted with `git rm`, so history keeps them.

**Done when:** each ruling is applied and the link checker passes.

## Phase 4 — Keep it true

### Keep it true (on trigger)

**Flags:** none. **Depends on:** a trigger: a validator failure, or a report of a stale claim.

The ratchets hold the map true; who updates a boundary file's lines, and when this lane reviews
them, is UR-81. This lane opens a package only on a trigger (UR-68).
