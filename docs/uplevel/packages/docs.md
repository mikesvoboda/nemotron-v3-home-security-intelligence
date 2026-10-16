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

### [r196b] F-234's channel test

**Flags:** none. **Assigned:** docs, first on its queue. **Depends on:** none. **PR:** #7181 (merged 2026-10-16T05:28:12Z as `257572118`, head `6e28d9e2c`).
(rulings 192, 194, 196)

- [x] `test.use({ channel: 'chromium' })` at the top of
      `frontend/tests/golden/notify-access/permission.spec.ts` only; `frontend/playwright.config.ts`
      is unchanged (ruling 194). The PR's title carries `[r196b]`; frontend reviews.
      Re-measured at the merge this turn: `git diff --name-only 5365165f8 6e28d9e2c` is TWO files —
      `permission.spec.ts` and `docs/reference/feature-inventory.md` — with exactly 1 added
      `+test.use({ channel: 'chromium' });` line and a 0-line diff on `playwright.config.ts`. (Base
      `5365165f8` is the PR's base, not the merge's first parent: diffing the MERGE commit
      `257572118` instead lists a third file, `known-person-embedding.seeded.spec.ts`, which is
      #7199's work coming in through the merge — attribute a merged PR against its own head.)
- [x] One CI run decides. If the granted leg executes and passes, F-234 flips to **awaiting real
      tier** on that run. If it still reads `denied`, or the browser cannot launch in the golden
      container, revert the line, post the run on #6996, and the row returns to the owner.
      The deciding run is the row's cited `38781211294` / job `116583068172`
      (`Feature check (fake AI)`, `success`), whose artifact attests the execution half: the spec's
      own runtime self-skip at `permission.spec.ts:181-187` did NOT fire, so the granted leg ran
      rather than skipped. That non-fire is F-234's evidence cell's attestation, which I did NOT
      re-download this turn; what I re-measured at the merge is the outcome half by column — parsing
      all 294 `F-` rows at `257572118`, F-234's status cell is `unverified` at base `5365165f8` and
      `awaiting real tier` at the merge, so the flip rode this PR.
      `awaiting real tier`, not `works`: the real tier has not run (rulings 103, 148).

**Done when:** F-234 is **awaiting real tier**, or the run that returns it to the owner is posted.
**MET** — F-234 is `awaiting real tier` on `main` as of `257572118`; no revert leg was needed, so
nothing was posted to #6996 for that purpose. (That draft PR is itself now closed under ruling 209 —
see its release comment 6208840202 — which is also why this box's "post the run on #6996" branch is
moot rather than pending.)

### [r215d] F-278's leg on the seeded face vector

**Flags:** none. **Assigned:** docs, now, alongside `[r196b]`, with UR-52 waived (ruling 226).
**Depends on:** `[r215a]` merged (#7188). **PR:** #7204 (merged 2026-10-16T06:47:23Z as `f1c300662`, head `0981aa40b`). (rulings 215, 226; records
6200719567, 6206280092)

- [x] F-278's leg runs in `Feature check (seeded)`: it opens the seeded person, sees the enrolled
      face, and deletes it (`DELETE /api/known-persons/{person_id}/embeddings/{embedding_id}`).
      The leg is `frontend/tests/golden/identity/known-person-embedding.seeded.spec.ts:226` (#7199,
      merged `25dda07c8`), and it EXECUTED rather than skipped: the fleet's own witness, CI's
      `Inventory witness (ruling 218)` step in `Feature check (seeded)` at `a8a20e8b2`, prints
      `READY to flip: F-278 (unverified -> awaiting real tier): 1 leg(s), each passed in this job`
      with `0 failing`. On the artifact (run `38846528640`, job `116799424527`, artifact
      `12024277094`): list stdout `✓ 1 … (F-278) … (3.9s)` and footer `4 passed (18.3s)`; junit
      `<testcase time="3.919">` with NO child (a skip or a retry-absorbed failure would leave one);
      `retries: 0` in the spec makes attempt 1 final, because the leg destroys its one-embedding
      fixture. `summary.json` is not the no-retry witness — it stores only the final attempt.

**Done when:** the leg passes and F-278 flips to **awaiting real tier** on that run (rulings 103,
114). **MET** — the leg passed as above, and this PR sets F-278 to **awaiting real tier** (not
**works**: the real tier has not run, ruling 148), with §2's §3.12 and `all` rows re-derived so
`scripts/check-inventory-summary-arith.py` passes on this tree.

### [r207] Rows the real tier cannot confirm

**Flags:** none. **Assigned:** docs, after `[r196b]`. **Depends on:** none.
**PR:** #7209 (open). (ruling 207, record 6199844401)

The real tier serves the real VLM with the fake detector (UR-136), and no agent run exercises
`yolo26`, `reid` or `threat` (`r2-sheet.md`, "The real-tier gap"). Yet **works** reads "confirmed
on the real tier" (`docs/reference/feature-inventory.md:33`).

- [x] The inventory legend says the real tier is the real VLM with the detector, re-ID and threat
      models fake (UR-136), as `README.md`'s vocabulary now does.
- [x] List the rows whose behaviour comes from detector, re-ID or threat output, each with the code
      path that reads it. Each carries the note `needs real Triton models` and stays at
      **awaiting real tier** until a host run with the real Triton models covers it; a listed row
      now at **works** goes back, and the PR names it.

**Done when:** the legend agrees with UR-136, and every listed row carries the note and is not
**works**. **MET** — the legend row says the detector, re-ID and threat models stay fake at
`--real` (box-1 commit `5ffdb080b`); the listing lives at `feature-inventory.md`, "Ruling 207: rows
the real tier cannot confirm" (§1), 35 rows, each carrying `needs real Triton models` in its
evidence cell and each named by the code path that reads the fake-leg value. Membership was measured
from the writers outward (`detector_client.py`, the re-ID embedding and clustering writers, the threat
consumers) rather than from the earlier row list, and the two boundaries that reading forced — a row
about the fake value vs a surface that merely renders one, and a figure the row promises vs the pipeline
counting its own running — are published in the §1 intro so a reader can re-check them; the same
paragraph names every non-member and its reason. The one listed row at **works** was F-097 and this PR
names it back to **awaiting real tier** (§2's 3.6 and `all` rows re-derived); the sweep found no
second one, and the closest call is named: F-031 renders the detector-drawn crop in its feed cards but
promises the VLM-written verdict/notify/risk badges, which its own golden spec asserts and F-054's does
not, so it stays out with the reason rather than in by silence.

### [r231] Every model family the real tier fakes

**Flags:** none. **Assigned:** docs, after `[r207]`. **Depends on:** `[r207]` merged (#7209).
**PR:** none yet. (ruling 231, record 6215981513)

Ruling 207 named the detector, re-ID and threat families. The real tier serves only the real VLM
(UR-136), and `models.yml` serves more families through the AI gateway: face detection and
recognition (`face-detector-scrfd`, `face-recognizer`, `yolo11-face`), license plates
(`yolo11-license-plate`, `fast-alpr`, `paddleocr`) and general detection (`yolo26-general`).
Ruling 231 extends ruling 207 to every family except the VLM.

- [ ] **MEASURE** which `models.yml` families the real tier fakes, from its compose and UR-136, and
      list them in the PR.
- [ ] List the rows whose behaviour comes from those families' output, each with the code path
      that reads it. Each carries the note `needs real Triton models`, and a listed row at **works**
      goes back to **awaiting real tier**, named in the PR. The inventory legend names the set.
- [ ] F-270, F-271 and F-275's evidence cells cite the 2026-10-13 real-tier run that set them to
      **works** (commit `5db3c56f7`, project `hsi-check-20261013234949-a14ce4`) in place of the
      stale "promoted to `awaiting real tier` by ruling 103" sentence (DO-3 rows, ruling 87),
      unless the list above puts the row back to **awaiting real tier**.

**Done when:** every listed row carries the note and is not **works**, the legend agrees with
UR-136, and each of the three evidence cells cites its real-tier run unless the list put its row
back.

### [r165b] F-235: cure the quarantined notify channels spec

**Flags:** none. **Assigned:** docs, first on its queue. **Depends on:** none. **PR:** #7122 (merged 2026-10-14T18:36:41Z as `8977e9457`, head `f1d923174`).
(rulings 125, 165)

- [x] First commit: the ruling-125 mark's expiry in
      `frontend/tests/golden/notify-access/notify.spec.ts` reads 2026-10-16T00:00Z.
      Done at `e21e139e1`, which moved the expiry there. The cure then deleted the mark outright
      (`8a374c2e1`), so the box is satisfied by the commit that wrote it and superseded by the one
      that removed it — at HEAD `grep -c test.fixme` on that spec is 0.
- [x] The F-235 channels test passes without a retry; the `test.fixme` mark is removed.
      Run `38584761421`, job `Feature check (fake AI)` (115923989614), `success` at 15:29:34Z on
      tree `6f1e1d9` (merge of main `2f7effd72` + head `c675919bc`). `golden-playwright.log`:
      `✓ 63 … notify.spec.ts:212:3 › F-235 channels … (3.7s)`, first attempt, tally
      `165 passed / 1 flaky / 12 skipped`. The no-retry witness is that log, not `summary.json`
      (which stores only the final attempt): the run's ONE `(retry #…)` line is
      `timeline/event-feedback.spec.ts:213`, a different leg, published under ruling 166.

**Done when:** the spec passes in CI's `Feature check (fake AI)` with no mark, before
2026-10-16T00:00Z. **MET** — run `38584761421` above, 2026-10-14T15:29:34Z, ~38 h inside the mark's
expiry and the ruling-165 clock (12:08:57Z + 48 h on the 16th). The F-235 inventory row moves
`unverified` → `awaiting real tier` in the same commit, and §2's §3.10/all totals roll with it.
