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
**Assigned:** heavy-a, one PR per lane; it moved from docs' queue (ruling 300, record 6322983128).
**PR:** #7331 (PR 1), #7351 (backend), #7353 (frontend). (rulings 241, 300)

heavy-a opens each draft PR itself, labelled `heavy` with no lane label (UR-59). Each PR names in
its body the part of the boxes it completes and reports the files and lines it removed; the last PR
ticks both boxes. A PR leaves alone any file an open PR edits, names it in the body, and takes it in
a later `W3.1` PR. Between PRs heavy-a is waiting, not stalled, and its beat names the lane it waits
on (UR-38).

- [ ] Delete every `AGENTS.md` outside the boundary list (`UR-21`), moving any non-discoverable
      knowledge it holds into the nearest boundary file.
- [ ] Switch the validator from "required in every directory with two code files" to "required at
      each boundary, forbidden elsewhere".

The PRs (ruling 300 items 2-4):

1. **PR 1, #7331 (merged).** The validator requires an `AGENTS.md` at each `boundary_list`
   directory and reports, without failing, every one outside the list. The `AGENTS.md` files under
   `docs/` are deleted, except one an open PR edits, which its body names. `docs/` is the docs
   lane's own tree, so UR-68 does not gate it.
2. **One PR per lane,** each opened once that lane's Phase 3 rows read `done` in the README status
   table: backend (`backend/`); frontend (`frontend/`); ops (`ai/`, `scripts/`, `.github/`,
   `tests/`, `monitoring/`, `docker/`, `data/`, `setup_lib/`).
3. **The last lane's PR** switches "forbidden elsewhere" from reporting to failing.

`synthbench/`'s eight `AGENTS.md` files outside the list belong to the synthbench workstream
(UR-82). #7331's body answers ruling 300 item 5: `W3.1` does not touch `synthbench/`, and the last
PR exempts those eight files in the validator, unless the owner rules otherwise.

**Done when:** the last lane's PR merges and the validator passes in boundary mode, and each PR has
reported the files and lines it removed.

### W3.2 Rewrite the boundary files to the standard

**Flags:** none. **Assigned:** docs, first once `[r262]` merges: backend's, then frontend's, one PR
per lane (ruling 316). **Depends on:** `R2`; the target lane's Phase 3 `done`.
**PR:** none yet — backend's in progress. (ruling 241)

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

**Flags:** none. **Assigned:** docs, after `W3.2`: backend's, then frontend's, one PR per lane
(ruling 316).
**Depends on:** `R2`; the target lane's Phase 3 `done`.
**PR:** #7411. (ruling 241)

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
**PR:** #7250. (ruling 241)

- [x] Apply the `R2` rulings from `W2.2`: the single plan home, the register's shape, the
      image-validation plans. `R2a` ruled them (ruling 89):
  - **OD-33:** future plans go in `docs/superpowers/<date>-<slug>/`; `docs/plans/` freezes as
    history; `docs/vss-integration/` stays the register's live home; nothing moves.
    **Done** — UR-87 (`rules.md`) states the rule, and a re-measure at `9806a5298` finds **0**
    date-named plan files under `docs/` outside `docs/superpowers/` whose name date is after
    2026-10-10; nothing moved, as the wording requires.
  - **OD-34:** the register gains a ruling column, and closed issues move to a history file. Each
    moved issue leaves a one-line dated pointer; the two halves are separate commits; filling the
    column is a read of all 32 rows, not a grep.
    **Done** — #7127 (merged 2026-10-14 as `ff7e8f5da`) added the `Ruling` column and moved the
    closed blocks. Measured **at `ff7e8f5da`**, where it landed: **13** archived `#### ISS-` blocks
    in `history/17-closed-issues.md` against **13** dated "Moved to history" pointers in the
    register — the pair the ruling requires to match, and they do. Measured **at the base
    `9806a5298`**: the same pair reads **14** and **14**, the fourteenth arriving later in
    `12fd37341` (ISS-073, 2026-10-16), and the register's `OD-` table carries **39** rows, **39**
    with a populated `Ruling` cell (grown past the 32 the ruling's own "read all 32 rows"
    instruction names). `check-vss-docs-currency.py` recomputes and enforces the pairing and exits
    0 at the base.
  - **OD-35:** the 26 image-(re)validation plans are deleted with `git rm`, so history keeps them.
    **Done** — `a911285a1` deletes exactly **26** files / **8,314** lines (`git diff --numstat
origin/main...a911285a1` — the deleted tree itself yields 0 by `ls`, so the diff is the
    instrument that carries the count), matching the ruling's own count, and lists them in
    `scripts/retired_paths.txt` so
    the gate keeps them gone and flags a living citation. Citation census over `docs/plans` falls
    385 checked / 164 OK / **221** ERR at `9806a5298` to 370 / 160 / **210** after the deletion,
    and the whole delta is attributable to the family: **3** of the 26 files carry citation blocks,
    holding 15 checked cites — 4 OK, 11 ERR — which is the delta line for line. The other 23 cite
    nothing. `audit_mkdocs.py` prints the same two pre-existing warnings before and after.

**Done when:** each ruling is applied and the link checker passes. **MET** — OD-33 and OD-34 are
applied in merged work (above); OD-35 is applied in this PR, where its own instrument,
`scripts/test_retired_paths.py`, goes **red with 26 "retired path exists again" findings** when the
entries are listed and **green (`OK: 37 retired path(s) stay gone`) once the files are removed** —
red-then-green on one tree, not a claim. `scripts/test_retired_paths.py` exits 0, `audit_mkdocs.py`
reports 0 errors and its 2 pre-existing warnings, and `check-vss-docs-currency.py` exits 0. "The link
checker" here is `audit_mkdocs.py`, which this lane runs by hand: CI's own link leg is `docs.yml`'s
lychee at `continue-on-error: true`, so it cannot pass or fail for anyone. The clause is met by the
instrument that can, and that instrument's two warnings are unchanged from the base tree.

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
**PR:** #7209. (ruling 207, record 6199844401)

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
paragraph names the adjudicated non-members whose own §3 evidence cites a coordinate §1 publishes as
an exclusion ground, and states that bound plus what the claim does NOT cover rather than asserting
it is total. The one listed row at **works** was F-097 and this PR
names it back to **awaiting real tier**; the sweep found no
second one, and the closest call is named: F-031 renders the detector-drawn crop in its feed cards but
promises the VLM-written verdict/notify/risk badges, which its own golden spec asserts and F-054's does
not, so it stays out with the reason rather than in by silence.

### [r231] Every model family the real tier fakes

**Flags:** none. **Assigned:** docs, after `[r207]`. **Depends on:** `[r207]` merged (#7209).
**PR:** #7235. (ruling 231, record 6215981513)

Ruling 207 named the detector, re-ID and threat families. The real tier serves only the real VLM
(UR-136), and `models.yml` serves more families through the AI gateway: face detection and
recognition (`face-detector-scrfd`, `face-recognizer`, `yolo11-face`), license plates
(`yolo11-license-plate`, `fast-alpr`, `paddleocr`) and general detection (`yolo26-general`).
Ruling 231 extends ruling 207 to every family except the VLM. (The clause "through the AI gateway"
is the ruling's WHY and #7235's box-1 measurement corrects it: the gateway's Triton set is
`{yolo26, reid, threat}`, and these seven are backend model-zoo loaders no agent tier feeds
weights. The ruling's verdict — the extended set is never exercised for real — holds unchanged.)

- [x] **MEASURE** which `models.yml` families the real tier fakes, from its compose and UR-136, and
      list them in the PR. Done at `d0809bd71` and the PR's box-1 Evidence: the set is all ten
      `models.yml` rows (the real VLM is not a `models.yml` row — `--real` serves it from the library
      GGUF pin, `scripts/feature_check.py:136-140`), in two measured modes: **A**, the three the fake
      `ai-gateway` answers (the Triton repository baked into its image holds exactly `yolo26`, `reid`,
      `threat`), and **B**, the seven no agent tier loads at all (the CI+fake-ai compose pair carries
      0 `AI_MODELS_PATH` lines against `docker-compose.prod.yml`'s 7, and each of the seven raises).
- [x] List the rows whose behaviour comes from those families' output, each with the code path
      that reads it. Each carries the note `needs real Triton models`, and a listed row at **works**
      goes back to **awaiting real tier**, named in the PR. The inventory legend names the set.
      Done at `8f6a955ab`. The writers-outward census over the extended set found **no new member
      row**: a mode-B family's value is never _produced_, so it cannot reach a surface, and every row
      adjacent to the seven lands in an exclusion class — catalogue state (F-104/F-125/F-127/F-129),
      an uncalled latency feed (F-105/F-130), a dead control (F-128/F-269), a seeded table
      (F-268), user-entered stores the family reads _instead of_ feeding (F-241/F-242), a read-time
      liveness probe (the `get_health` consumers F-005/F-007/F-020/F-028/F-037/F-126/F-139 and the
      readiness/liveness probes F-016/F-134/F-146/F-147 — §1's fourth boundary, added after the UR-89
      review: writers-outward is blind to a probe with no write site, so the class is named by the
      row's own promise, ground a route and a symbol, no new line-coordinate ground); each is named
      with the reason. What shipped instead of new rows: the seven `[r207]` legs mislabeled
      `re-ID (face)` are re-leged `face (zoo)` (measured producer: SCRFD + w600k_r50 at
      `backend/services/model_zoo.py:345`/`:346` and the `yolo11-face` loader `:335`, not the Triton
      `reid` op), the
      marker's family list is glossed (§8's rule keys on the note string, which names ten families,
      not Triton literally), a third boundary — faked _and_ never-produced output both list it — and
      the legend `works` cell plus `README.md`'s vocabulary name the set. §1 lists 35 rows, all 35
      carry the note, and `[r231]`'s sweep found **no listed row at works** to name back.
- [x] F-270, F-271 and F-275's evidence cells cite the 2026-10-13 real-tier run that set them to
      **works** (commit `5db3c56f7`, project `hsi-check-20261013234949-a14ce4`) in place of the
      stale "promoted to `awaiting real tier` by ruling 103" sentence (DO-3 rows, ruling 87),
      unless the list above puts the row back to **awaiting real tier**. Done at `8f6a955ab`, on the
      proceed branch: box 2 put none of the three back — §1 names them **User-entered** (the family
      reads _their_ store, `backend/services/household_matcher.py:452` /
      `backend/services/vlm_specialists.py:742`, not the row
      displaying the family's output), and `5db3c56f7` was a default-shape real run, which box 1's
      bound makes a valid promotion for a row whose value no leg fakes. `5db3c56f7`'s own commit
      message names `hsi-check-20261013234949-a14ce4`.

**Done when:** every listed row carries the note and is not **works**, the legend agrees with
UR-136, and each of the three evidence cells cites its real-tier run unless the list put its row
back. **MET** — at `8f6a955ab`: 35 §1 rows, 35 note-carrying §3 cells, 0 at **works** (measured from
the tree, `split(' | ')` status cell); the legend `works` cell and the README vocabulary both name
the extended set and cite the box-1 measurement; the three cells carry the `5db3c56f7` /
`hsi-check-20261013234949-a14ce4` citation in place of the stale ruling-103 sentence. `docs/reference/feature-inventory.md:33`, §1, §3.12.

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

### [r231b] Keep it true: the bare cites and probe-class residuals `r231`'s close left

**Flags:** none. **Assigned:** docs, opened on trigger (this lane opens Phase 4 packages only on a
trigger — the trigger fired: r231-reviewer's note 1, a validator failure reported against a merged
claim, review comment `6236622758` on #7235, dispositioned there as this package's lead item).
**Depends on:** `[r231]` merged (#7235, `5d5c4bcc5`). **PR:** #7237. (ruling 231, record 6215981513)

- [x] The three bare-filename cites `[r231]`'s repair commit `683d49566` published in its own
      packages prose — `model_zoo.py`:345 at :235, `household_matcher.py`:452 and
      `vlm_specialists.py`:742 at :245 (the third published at `:741`; `537cc20d8`'s ground swap
      moved it) — carry their full repo-relative paths
      (`backend/services/…`), the form the validator resolves and the inventory prose already
      uses. Done when `validate_docs` level 1 over `packages/docs.md` reads **3 ERRs, not 6**: the
      base `f85f27a5f` set (`ci.yml`:298-304, `permission.spec.ts`:181-187,
      `timeline/event-feedback.spec.ts`:213) and nothing else. The three base ERRs are NOT this
      package's to fix — they were published under earlier rulings and sit in other batches' prose.
      This block names every cite in the split form (closing backtick BEFORE the colon, as above):
      `INLINE_CITATION_PATTERN` matches only a `file.ext:NNN` wholly inside one code span, so the
      block cannot re-grow the class it fixes — and if a later re-wrap merges those spans, the
      ERR set this Done when reads is what makes that loud. The instrument is HAND-RUN: this file
      sits outside the citation gate's five scanned dirs (`ci.yml`:392), so the ERR set speaks when
      the next review re-runs it — which UR-91 obliges on every new head.
      Done at `a49f24bc7`; #7237's Evidence carries the three instrument outputs.
- [x] §1's fourth boundary names the two residuals its own bullet left open (reviewer note 3):
      **F-022** (its evidence names tiered `GET /api/system/health/websocket` through the
      always-open `WebSocketHealthPanel`) and **F-140** (its API cell cites
      `GET /api/system/health` outright). Both are `half-built`, zero works exposure; naming is
      prose-only — the ground stays route+symbol, so the reverse sweep's obligation is unchanged:
      grounds re-run reads **31 grounds, 0 unnamed** with controls green, and the bullet's class
      count moves from eleven named to thirteen.
      Done at `a49f24bc7`; the sweep re-printed 31/0 there. Round 2 blocked this clause while its
      only carrier sat in `/tmp` — contract rule 3 — and the instrument now lives at
      `scripts/uplevel/grounds_sweep.py`, re-printing 31/10/0 + the five controls identical to the
      copy it replaced (modulo its path header line). The F-022 row's route-tier claim
      re-verified at the `@router.get` decorator of `GET /health/websocket` in
      `backend/api/routes/system.py` (`RateLimitTier.DEFAULT`) — symbol-anchored, deliberately no
      line number: this cluster is the repo's known ~11-line cite-drift family (the F-022 row's own
      `:1626` is already stale), so a fresh coordinate here would age the same way.

**Done when:** the validator reads 3 ERRs on `packages/docs.md` (not 6), the grounds sweep
(`scripts/uplevel/grounds_sweep.py`, committed) still foots at 31/0 with F-022 and F-140 named in
the fourth boundary, and prettier is clean on both files.

### [r262] Audit the code the Qwen-era merges left on main

**Flags:** owner (ruling 262: the owner rules on every item). **Assigned:** docs, first on its
queue. **Depends on:** none.
**PR:** #7265. (ruling 262, record 6257468143)

The fast lanes ran Qwen3.8-Flash-Next from #6850 (2026-10-07) until the vLLM crash at about
2026-10-18T07:36Z, and GLM 5.3 Flash after the restart. The owner session compared the two blind on
2026-10-19 (four matched pairs) and found no quality gap. It did find defects that each model's own
UR-89 review let through. This package reads the code the Qwen-era merges left on main and writes a
to-do sheet the owner rules on. Ruling 262 is this lane's trigger (UR-68).

It changes no code, not even a one-liner: each fix is the owner's call, made later by the lane that
owns the path. The PR adds one file, `docs/uplevel/r262-audit.md`, and that file's line in the
README's file map; its claim also writes this block's `**PR:**` field (UR-183). Label the claim PR
`lane:docs` and `owner`.

- [ ] **MEASURE** the census at a SHA of main pinned at the claim. Write the SHA, the census command
      below and its counts at the sheet's head. The census is every PR merged to main from
      2026-10-07T00:00Z to 2026-10-18T07:36Z that carries a `lane:` label, plus the `[red-main]`
      PRs with no label at all. Ruling 262 excludes two kinds: a PR with any label containing
      `heavy` (`heavy`, `cell:heavy`, `cell:heavy-b`: another model), and the owner session's PRs:
      a head branch that starts `uplevel/owner-`, or a commit with a `Co-Authored-By: Claude Opus`
      trailer (the owner session's; the lanes' commits carry `Claude Code`). A PR's files are its
      merge commit's diff
      against its first parent, kept if the same path exists at the pinned SHA (a file a later PR
      renamed drops out). Each kept file has one class, the first that matches: Markdown is not
      code and is skipped; **test** is a path with a `tests/`, `test/` or `__tests__/` directory,
      or a `test_*.py`, `conftest.py`, `*.test.*` or `*.spec.*` file; **production** is under
      `backend/`, `frontend/src/`, `setup_lib/`, `ai/` or `monitoring/`, or a root
      `docker-compose*.yml`; **tooling** is under `scripts/` or `.github/`; anything else is
      skipped. A PR's class is the first it has, in the order production, test, tooling.

```bash
python3 - "$PIN" <<'PY'
import json, re, subprocess, sys
pin = sys.argv[1]
run = lambda *a: subprocess.run(a, capture_output=True, text=True, check=True).stdout
prs = json.loads(run("gh", "pr", "list", "--state", "merged", "--limit", "600",
    "--search", "merged:2026-10-07..2026-10-18T07:36:00Z",
    "--json", "number,title,labels,headRefName,mergeCommit"))
live = set(run("git", "ls-tree", "-r", "--name-only", pin).split())
TEST = re.compile(r"(^|/)(tests?|__tests__)/|(^|/)(test_[^/]*\.py|conftest\.py)$"
                  r"|\.(test|spec)\.")
def kind(p):
    if p.endswith(".md"): return None
    if TEST.search(p): return "test"
    if p.startswith(("backend/", "frontend/src/", "setup_lib/", "ai/", "monitoring/")) \
            or re.match(r"docker-compose[^/]*\.ya?ml$", p): return "production"
    if p.startswith(("scripts/", ".github/")): return "tooling"
    return None
out = []
for p in sorted(prs, key=lambda p: p["number"]):
    names = {l["name"] for l in p["labels"]}
    if any("heavy" in n for n in names) or p["headRefName"].startswith("uplevel/owner-"):
        continue
    if not any(n.startswith("lane:") for n in names) and not (
            not names and p["title"].startswith("[red-main]")): continue
    m = p["mergeCommit"]["oid"]
    if "Co-Authored-By: Claude Opus" in run("git", "log", "--format=%B", f"{m}^1..{m}"):
        continue
    k = {}
    for f in run("git", "diff", "--no-renames", "--name-only", f"{m}^1", m).split():
        if f in live and kind(f): k.setdefault(kind(f), []).append(f)
    first = next((c for c in ("production", "test", "tooling") if c in k), "none")
    out.append({"pr": p["number"], "class": first, "files": k})
print(json.dumps(out, indent=1))
PY
```

Control: at `a3b1bd336` the owner session's run gave 228 PRs, by class 52 production, 110 test, 6
tooling and 60 none. A different count at the pinned SHA is recorded at the sheet's head with its
reason; it is not a stop.

- [ ] **Audit** each census PR once, in its class, with all its kept files: production first, then
      test, then tooling, and within a class in PR-number order. The PR's diff and body say what it
      meant to do; the verdict is on the code as it stands at the pinned SHA. Something a later PR
      already fixed is not an item. A PR of class none is listed with "no code on main". An item
      is one of six classes:
  - **bug:** wrong behaviour or an unhandled case on a reachable path;
  - **guard:** a refusal, validation or check removed or weakened without saying so;
  - **test:** a test that cannot fail, mirrors its implementation, or misses a behaviour the code or
    the PR claims;
  - **claim:** a comment, docstring, message or doc that says what the code does not do;
  - **drift:** docs or config naming a setting, path or symbol that no longer exists;
  - **fit:** a duplicate or an abstraction that costs something, such as two copies that diverged.

  Each item has a severity. **high:** wrong behaviour on a production path, on data or on auth, or
  a gate that passes when it should fail. **medium:** a test gap or a dropped guard that hides a
  plausible bug, or tooling that misreports. **low:** a claim or drift that changes no behaviour.
  Taste, cite density, line length and anything a lint or format gate enforces are not items.

- [ ] **Verify** each item before it enters the sheet. It cites a path and line at the pinned SHA,
      quotes the lines, and shows the proof: the other lines read, or a command and its output. An
      item the auditor could not verify is not listed. A fresh, unnamed subagent (ruling 232) then
      gets only the item and the repo at the pinned SHA and tries to refute it; a refuted item is
      dropped, and each batch records how many were. At most two audit subagents run at once. The
      cites stay at the pinned SHA as main moves; the package that later fixes an item re-reads it
      on its own base.
- [ ] **Pilot.** Batch 1 is the first ten production PRs. The lane pushes it and posts a PR comment
      with counts by class and severity and the refuted count. It then holds: the PR stays draft,
      each tick reads the PR's comments, the lane pushes nothing, and its heartbeat says it is
      holding for the owner. An owner comment (one that starts `**Owner`) saying `continue` ends
      the hold. If the owner's comment changes the bar instead, the lane re-checks batch 1 against
      the new bar before batch 2. Later batches are about fifteen PRs, one comment each.
- [ ] **Owner decisions.** The owner answers each item in an owner comment (one that starts
      `**Owner`) with `fix`, `skip` or `later`, and the lane writes the answer into the sheet. The
      PR stays draft until every item has an answer; the lane then marks it ready and runs its
      UR-89 review.

**The bar from batch 7 on** (ruling 296, record 6307432184). The audit still reads every remaining
census PR: the 79 test PRs, then the 6 tooling PRs. A row goes only to a bug of any severity, or to
any finding the auditor rates medium or higher, and each row still goes through the refutation pass.
A low stale `path:line` cite or a low claim gets no row and no refutation pass; each batch comment
gives instead one count of them per PR, with the PR numbers. Batches 1–6 stay as written, and the 68
rows of batches 4–6 still await the owner's `fix`, `skip` or `later` (ruling 262). The stale-cite
class goes to a checker package whose scope the owner rules on; until then, no lane fixes low stale
cites one by one. This package's PR does not touch `history/ruling-map.md`.

Each item in the sheet takes this form:

```text
### Q-001 · <class> · <severity> · <path>:<line> · #<PR>
- Wrong: one sentence.
- Evidence: the quoted lines, and the read or command that proves it.
- Fix: one sentence; size S, M or L; the lane that owns the path.
- Owner: fix | skip | later
```

**Done when:** every census PR is in the sheet with its items, "no items" or "no code on main";
every item survived the refutation pass; every item carries an owner decision; and the UR-89 review
approves. The owner's next ruling turns the `fix` items into packages for the owning lanes.

### [r271c] The dead-code register and the API_KEYS note say what the code does

**Flags:** none. **Assigned:** docs, beside `[r262]` (ruling 271).
**Depends on:** none. **PR:** #7292. (ruling 271, record 6277412644; audit items Q-024, Q-025,
Q-026 and Q-032 of `[r262]`)

Cites are at the audit's pin `41bc0fce7`; re-read them on the PR's base. A one-off exception to
UR-52: docs holds #7265 and this package's PR at once and works it between
audit batches; the exception ends when this package merges. Until it merges, no deletion package
acts on the register's `WebSocketEmitterService` entry: that path is live.

- [ ] `docs/reference/backend-entry-points.md` `:1530` and `:1349` state that `main.py` imports
      `WebSocketEmitterService` and wires it with the system broadcaster only; its
      `event_broadcaster` and `redis_client` slots stay None in production, so only the
      system-channel branch delivers.
- [ ] Q-025 and Q-026's `main.py` cites (`backend-entry-points.md`; `feature-inventory.md` F-008,
      F-016 and `:1207`) are re-aimed on the PR's base.
- [ ] `docs/reference/config/env-reference.md:372`: plain `API_KEYS` entries are accepted by
      `verify_api_key` and the gate; scoped entries are honoured only by the middleware gate, and
      the legacy `verify_api_key` routes (`dlq.py`, `system.py`) refuse them with 401.

**Done when:** merged at a ready head, each rewritten sentence citing the line it rests on at the
PR's base.

### [r277b] F-022's stale citations

**Flags:** none. **Assigned:** docs, beside `[r262]`, a one-off UR-52 exception counted toward
ruling 269's two, like `[r271c]` (ruling 277). **Depends on:** none. **PR:** #7265, beside
`[r262]`. (ruling 277, record 6291992942; audit items Q-093 and Q-075 of `[r262]`)

- [x] F-022's row in `docs/reference/feature-inventory.md` carries its five citations re-derived
      against `main`'s base, not the audit's pin: `extractRateLimitInfo`, its `update()` call, the
      three-header guard, `fetchWebSocketHealth`'s fetch, and the websocket-health route with its
      `DEFAULT` tier in `backend/api/routes/system.py`. The PR quotes each cited line from its base.
      Frontend's Q-076 holds two of the same citations in
      `frontend/tests/golden/shell/rate-limit.spec.ts`; it goes to frontend's later cleanup, not this PR.

**Done when:** merged at a ready head, each citation quoting its line at the PR's base.

### [r305] The three weak tests and the 15 prose rows of `[r262]` batches 4–6

**Flags:** none. **Assigned:** heavy-a, between `W3.1`'s PRs; `W3.1`'s next PR goes first whenever
its lane is `done` (ruling 305). **Depends on:** none. **PR:** #7332. (ruling 305, record
6323706301; amends ruling 299 item 3)

heavy-a opens its draft PR itself, labelled `heavy` with no lane label (UR-59), and follows each
owning lane's file ownership. Ruling 269's two open packages are `W3.1` and this one. The 45 stale
citations of the same batches go to the cite-checker package ruling 296 item 3 scopes, not here.

- [x] **Q-127** (`ai/gateway/tests/test_dockerfile_agent_gpu_buildable.py:270-282` matches long
      flag names only), **Q-142** (`backend/tests/unit/api/routes/test_admin_cache_invalidation.py`
      `:303` counts only the census invalidators) and **Q-190**
      (`backend/tests/unit/scripts/test_duration_budget_gate.py:2530-2531` names u5 the longest
      breach; u6, at 5.0 s, is). Each test is made to fail first on what it claims, then pass
      (UR-69).
- [x] **The 15 prose rows** ruling 299 names, as `r262-audit.md`'s owner column lists them at #7265
      (docs' `9970a8073`). A row in an `AGENTS.md` that `W3.1` deletes closes with that deletion; a
      row in a file an open PR edits waits for that PR.

**Done when:** the three tests fail on a mutant of what they claim and pass at the head, each prose
row is corrected or named as closed, and the UR-89 review approves.

### [r307d] The deployment page says where the backend's models run

**Flags:** none. **Assigned:** docs, after `W3.2` and `W3.3` (rulings 307, 316). **Depends on:**
none.
**PR:** #7265, as a rider on `[r262]`. (ruling 307, record 6323846997)

`docs/operator/deployment/README.md:164-166` says the backend's OSNet, face and ALPR weights "load
on the GPU the backend container holds". The backend's torch is CPU-only (`pyproject.toml:984-994`),
the face leg forces `CPUExecutionProvider` (`backend/services/face_recognizer_loader.py:152`), and
the backend image installs only the `face` extra (`backend/Dockerfile:150`), so fast-alpr is not
installed.

- [x] The page states today's truth: OSNet and the face leg run on the CPU inside the backend
      (CPU-only torch wheels, `CPUExecutionProvider`), loaded at boot only when
      `BACKEND_MODEL_PRELOAD=true`; fast-alpr is not installed; and rulings 306 and 307 move them to
      Triton. Later PRs that move a model update the page (UR-81).

**Done when:** merged at a ready head, each sentence citing the line it rests on at the PR's base.

### [r308b] User guides for the P1 features

**Flags:** none. **Assigned:** docs, after `[r277b]` (ruling 308). **Depends on:** each page on its
feature's last build PR. **PR:** none yet. (ruling 308, record 6326364266)

- [ ] One page per feature in `docs/guides/`: alerts and notifications (`B4.1`–`B4.5`, `F4.1`,
      `F4.2`), Trash (`B4.4`, `F4.3`), timeline filters (`F4.4`), and backup and restore (`B4.6`).
      Each is written after that feature's last build PR merges and cites the code at that merge
      (UR-81).

**Done when:** all four pages are merged, each sentence citing the line it rests on.

### [r311b] The arming user guide

**Flags:** none. **Assigned:** docs, after `[r308b]` (ruling 311). **Depends on:** `B4.7` and
`F4.5` merged; its MQTT part on the MQTT section of Settings. **PR:** none yet. (ruling 311,
record 6328311780)

- [ ] One page in `docs/guides/` on arming: modes and their cameras, the schedule, critical alerts
      while unarmed, the webhooks and `/alert`, and MQTT with what it needs from the broker. It is
      written after `B4.7` and `F4.5` merge, its MQTT part after the MQTT section lands, and it
      cites the code at those merges (UR-81).

**Done when:** the page is merged, each sentence citing the line it rests on.
