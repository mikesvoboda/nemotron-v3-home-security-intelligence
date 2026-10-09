# R2 Ruling Sheet — session date TBD by the owner

> Created early by `W2.2` (docs lane), before `F2.2` runs. The template
> (`templates/r2-sheet.md`) says `F2.2` copies it here and fills it; `W2.2`'s Done-when needs its
> three rows committed before the owner's ruling session, so this file starts with only the docs
> rows (§2b) and nothing else. **`F2.2`: fill §1, §2 and §3 around §2b — do not rewrite or
> renumber this section.** The §2b OD numbers (`OD-33`…`OD-35`) are assigned; register rows run to
> `OD-32` today, so continue from `OD-36` if new decisions surface.
>
> Every row is written so it can be ruled from the row alone, without opening code. Facts were first
> measured at `1d847a6a` (2026-10-08, 23:48 -0400 — the header said 2026-10-09, which is the calendar
> day the sheet was written, not the commit's date; corrected in the third round) and **re-measured at
> every revision of this branch since** (the first being `10ab08e8`) by the commands named in each row.
> Every revision that touched this file differs from the last only in this file, with three exceptions:
> the merge `10ab08e8`, which brings in `origin/main` (39 paths) and does not touch this file at all
> (its sheet blob is byte-identical to the draft's, so at the merge the sheet's _text_ still carried
> the draft numbers); the row-flip commit `cdd0ca95`, which touches only README's status table; and
> the merge `2a558bdb`, which is the first revision that both brings in `origin/main` (22 paths) _and_
> moves numbers this file prints — the fifth-round corrections below are what that move forced —
> so a number printed here is checkable at any of them (the merge's tree was checked for the census
> and ERR legs in the fourth round; every moved number was re-measured at the fifth round's head) —
> including the ERR count's two legs,
> which are the one pair measured in two different trees (the `1d847a6a` leg, 216 ERR / 169 OK, re-run
> in a detached worktree at that commit; this branch's leg, 222 / 163, at head — not remembered; the
> third round re-ran every two-commit pair in a detached worktree at each leg's own baseline — ERRs,
> register lines, the 24-citer split — none carried over). Forty-three claims did not survive that
> re-measurement, a fresh-context review of the sheet, the re-measurement at the second merge head, or a
> fresh-context verification pass on the fifth round's own wording — the count now runs through four review
> rounds and a merge-head re-measurement, the third, fourth and sixth from a separate agent, and it grew each time because those rounds'
> findings, re-measured here, confirmed claims earlier rounds had asserted without measuring; the fifth
> round's thirteen came not from a reviewer but from `origin/main` moving under the branch again, found
> by this lane re-measuring at the new head before pushing; the sixth round's two sit in that round's own
> sentences — and
> the bullets say where each came
> from:
> thirteen were wrong in the draft as first committed (one of them this header's own date label), fifteen
> were true at the measured commit and went
> stale when `origin/main` merged (two at the first merge, thirteen at the second — first bullet), and fifteen were introduced _by the corrections_ —
> three found by the second round, six by the third, four by the fourth, two by the sixth (last bullet). Every one is corrected in place
> and the row names the draft's wording at the correction, so an owner reading one row sees what changed
> rather than a silently tidied fact — the corrections sit inside the Facts prose, not at the row end:
>
> - **moved with a merge** (15 — two at `10ab08e8`, thirteen at `2a558bdb`, counted as stale printed
>   facts, one per fact wherever the sheet prints it twice): `docs/plans`' level-1 ERR 216 → **222**
>   (OD-33) — which arrived as evidence, not just a number, because the tree itself had zero changed
>   paths; and the register's line count, which has moved twice, 8,485 → 8,518 → **8,565**, with its
>   staleness delta 373 → **420** (the plan text's 8,145 did not move) (OD-34). The thirteen at the
>   second merge: the four page-count facts of OD-33's nav row and their echo inside this header —
>   600 → **601** pages, 599 → **600** `index.html`, home 148 → **149** nav links, busiest 316 →
>   **317**, and the header's own "148–316 of 600" → **149–317 of 601** is the same four facts at a
>   second location, counted once — all four from one cause: `mkdocs.yml` gained exactly one nav entry
>   (`developer/agents-md-standard.md`) and `awesome-pages` rides every nav entry on every page's
>   sidebar; the invariant the row argues — no page links into the trees — survives it, verified over
>   all 601. Seven line-number cites: the `ci.yml` citation-job cite :229 → **:230** — a re-anchor, not
>   same-line drift (the draft's :229 pointed inside the step's run block even at the draft commit;
>   OD-33's row carries the decomposition); `docs/uplevel/40-docs.md:176` →
>   **:156** (W2.1 rewrote that file); `README.md:243` → **:246** (same rewrite); the validator's `≥2`
>   test `agents_md_validator.py:619` → **:702** (W2.1 grew the validator +186/−6); and inside the
>   register itself, `## Intake log` 7096 → **7143**, OD-24's log line L7150 → **L7197**, "§5 … at
>   708" → **744** — those three moved by prefix-sum arithmetic, not page counts: main's B1.2 hunks
>   added +36 lines at 708 and +11 at 3232, so everything below 708 held (the `Ruled 2026` hits at
>   578–603 did not move) while §5 moved +36 and the log moved +47. Two of these are the lesson of the
>   round: `docs-scan-findings.md:311` was re-checked and _did not_ move (blob `e4597283` identical at
>   both commits) — a line cite is only as stable as the merge above it, and you cannot tell which
>   without opening both. The second merge moved no other number: the census (11/12/1 + 44/36/32,
>   136 mentions / 104 citers), the tree counts (93/37/26), the ERR leg re-run at this head (385
>   checked / 163 OK / **222** ERR — the number the row prints is now verified here, not inherited),
>   the 154 published pages (91+37+26 in the fresh build), the register's 32 rows and 5-markup
>   findings, and OD-35's family (26 files / **8,314** lines re-summed at this head from
>   `git cat-file`, not remembered) all re-measured unchanged — disclosed because a held claim
>   verified is a different thing from a claim never re-checked.
> - **wrong at every commit** (11): this header's own "(2026-10-09)" date label for `1d847a6a`, which
>   commits 2026-10-08 23:48 -0400; OD-33's "~91 citing files" (an arithmetic slip) and its per-tree
>   columns (45/35/31, which match no instrument — the first replacement kept them verbatim and was
>   wrong too, last bullet); its "0 nav entries" (true of the nav, false of
>   publication); OD-34's "7 bolded
>   rulings" and "5 more only in the intake log" (both miscounts of the same 12 decisions — and the
>   miscount mechanism is now the row's argument for the column it asks for); OD-35's quoted provenance
>   header, "~200–250 lines each", "one per architecture doc", "they cross-cite each other" (one-way),
>   and "2 external referrers to re-aim" (both are prose mentions, not citations).
> - **a ruling this sheet had not read** (1, and the most serious): OD-35 recommended moving the family
>   into `docs/archive/`, which **UR-19** has already ruled deleted and **`O1.5`** executes — and README's
>   "Considered and rejected" table rejects that exact move. OD-35's options and recommendation are
>   rewritten around that; nothing in the draft mentioned UR-19.
> - **a command that ran but measured nothing** (1): OD-35's transcribed `git ls-files` passed both stems
>   inside one quoted argument, which matches no path and returns **0** — the printed 26 came from a
>   different invocation than the one the row showed a reviewer. Fixed to two pathspecs.
> - **first corrections that were themselves wrong** (15 — three found by the second review round,
>   six by the third, four by the fourth, two by the sixth, each named where it sits): (a) OD-33's — the first re-measurement
>   replaced "~91 citing files" with "97 distinct across 135 mentions", and re-running its own printed
>   commands shows its columns (45/35/31) reproduce under no instrument (the nearest prints 44/36/31,
>   ±1 twice in opposite directions inside the 111 the sum carried), and its 97 silently mixed two
>   scopes — AGENTS citers counted repo-wide, docs citers counted only inside the grep's search
>   directories. One whole-repo rule now, transcribed as one command per column: 11/12/1 + 44/36/32 =
>   **136** mentions across **104** distinct citers; the re-aim cost the recommendation quotes moves
>   97 → 104. (b) OD-35's — the same pass printed "median 315" for the family's sizes, which is no
>   median under any convention: the probe averaged the two middle files (313, 318 → 315.5) and `int()`
>   truncated it. OD-35's row now prints the straddle. (c) OD-33's nav note — the same pass printed
>   "296 nav links on a page", a single-page string count that is neither rerunnable nor stable across
>   pages (`md-nav__link` rides `<label>`s as well as anchors; real anchor counts run 149–317 of 601
>   built pages at the fifth round's head — the 148–316-of-600 form was the measurement at the revision
>   before it, and the merge moved it). The row now
>   prints the invariant the argument needs: none of the 601 built pages carries a nav link into the
>   three trees. (d)–(i) are the third round's six, each confirmed here
>   by re-measurement before being fixed: OD-33's citation passage said the 24 out-of-scope citers
>   include "the 6 doc files **under the 4 paths** the draft's grep listed" — the inverse of what the
>   enumeration shows (all 6 sit _outside_ those paths; they are now named). OD-34 said "2 of the 11
>   mention the ruling in a second cell" (strict count **5**; the correction named only OD-1's Source
>   and OD-30's Unblocks), and "3 rows carry the Intake-log pointer from their options cell" (only
>   OD-1's is in the options cell; OD-31's and OD-32's are in Source). OD-35 said api-reference
>   "carries both of the last two" date fields (it carries `**Revalidation Date:**` +
>   `**Original Validation Date:**`; `**Re-Validation Date:**` is observability's alone), that "the
>   other 6 … carry `**Hub:**` instead" (5 files name no area; exactly 2 carry `**Hub:**`), and — my
>   own second-round re-measurement, same class — that the families "name the same 10 areas
>   (identical sets)" (they are one apart: revalidation also names `data-model`). The first two of
>   these six came from prose a correction wrote about _counts_ without re-reading the underlying
>   cells/files; the OD-35 area claim came from trusting the earlier residue list after the counts
>   next to it were fixed. (j)–(m) are the fourth round's four, same reviewer, each confirmed by
>   re-measurement: OD-35's _recommendation_ still read "~10 architecture areas covered twice over"
>   after the Facts above moved to ~11/almost — the correction never propagated to the second place
>   the number lived (a phrase the correction round itself introduced). OD-33's census-correction said
>   the first correction's census "printed 44 / 36 / 31" — it printed the draft's 45 / 35 / 31
>   verbatim; 44 / 36 / 31 is what re-running _its instrument_ yields (both verified at its own commit
>   and at head) — the sentence asserted the correction both kept and replaced the columns. The
>   header's file-hygiene claim named one exception but the merge `10ab08e8` is a second (39 paths,
>   sheet untouched — now both exceptions are named). And OD-34's "`Ruled 2026` finds 5 and misses 6"
>   had "those 12" as its object while 6 is the count against the 11 table rows — now "misses 6 of the
>   11 table rows (7 of the full 12)". (n)–(o) are the sixth round's two, same reviewer, found
>   verifying the fifth round's new wording rather than the repo: (n) OD-33's new `ci.yml` sentence
>   claimed the cite had "shifted by one" at the merge — false twice over: the step-name line was :226
>   at `a0b4ca31` (:229 was the step's loop line there), and the merge's two insert hunks (+3 after
>   old 195, +1 after old 217) shift every line from 218 down by four, so the :229 → :230 pair is a
>   re-anchor, not drift (verified at
>   both commits with `sed -n '226p;229p'` and the `-U0` hunk headers — the row now carries the full
>   history, which is worse than the reviewer filed: :229 was never the name line even at the draft);
>   (o) the header's moved-facts bullet opened "the six page-count facts" and then enumerated four
>   pairs — the totals only close on four, so "six" contradicted its own sentence (the kind-cut
>   13 = 11+1+1, the merge-split 15 = 2+13 and the census 43 all require four). The lesson compounds
>   again: a corrected number has to be chased into every sentence that quotes it, including the
>   recommendation, "printed" is a claim about an artifact you can open, not about an instrument you
>   re-ran, and a correction sentence written to explain a drift is itself a drift claim — the fix
>   for a wrong cite has to open the file at both commits before it says which line moved by how much.
>
> Everything else measured identically at the first commit, at every revision of this branch since, and
> — for the claims this header names as held — in a detached worktree at the second merge head.

## 2b. Docs-lane rulings (`W2.2`)

### OD-33 — one home for future plans and specs

**The question** (`40-docs.md` W2.2): VSS material is split across `docs/plans/`,
`docs/superpowers/` and `docs/vss-integration/` today. Where do future plans and specs go?

**Facts.** `git ls-files docs/plans/ docs/superpowers/ docs/vss-integration/` — all extensions; an
`--include='*.md'` variant loses 2 `.json` design files and reports 91 files / 56 dated, which is the
wrong census: `docs/plans/` **93** files (**57** dated-named, span 2025-01-23 → 2026-10-04 — still
live: the AGENTS.md validator's own design doc lives here); `docs/superpowers/` **37** files, ALL
dated, span 2026-09-12 → 2026-10-07 (the VSS specs — the tree the programme is actively writing into);
`docs/vss-integration/` **26** files (5 dated; the register and its companions). None of the three
trees appears in `mkdocs.yml`'s nav — 0 explicit entries each, which is what the draft said and is true
of the nav, and the built site agrees: `uv run mkdocs build --site-dir <tmp>` at this head emits 601
pages (600 `index.html` + Material's `404.html`) — 600/599 at every revision before the `2a558bdb`
merge, which added one nav entry and moved the pair — and **none of the 601
carries a nav link into the three trees** (parsed `<a … md-nav__link …>` tags quote-agnostically —
`minify` strips the quotes, so a `href="…"` regex matches nothing; the home page runs 149 such links
at this head (148 before the merge), the busiest page 317 (was 316 — same system-ops page, and the
delta is the one new nav entry, which every page's sidebar carries); counting the raw string
`md-nav__link` over-counts because Material puts it on
`<label>`s too, and an earlier revision of this sheet quoted one such count, "296", as if it were a
page property — it is neither rerunnable nor stable across pages) — but the draft's "(0 entries
each)" invites the inference that these trees are not on the site, and they are: **154 pages built and
URL-reachable**, `site/plans/` 91 + `site/superpowers/` 37 + `site/vss-integration/` 26, because
`mkdocs.yml` loads `awesome-pages` and there are zero `.pages`
files repo-wide to exclude anything. So "not in the nav" is not "not published" — it is published
unlinked — which is what `W3.3` (rebuild the nav to cover every living doc) actually has to fix, and it
constrains any freeze rule phrased in terms of the nav. A move is citation-cheap in one direction and
expensive in the other. Files _outside_ the cited tree that name it, one rule stated as a command:
`git grep -l -- '<tree>/' -- '**/AGENTS.md' 'AGENTS.md'` for the AGENTS column, and `git grep -l --
'<tree>/' -- '*.md' ':(exclude)<tree>/' ':(exclude)docs/uplevel/r2-sheet.md'
':(exclude,glob)**/AGENTS.md'` for the docs column (this sheet excludes itself — its mentions are this
ruling's subject text, not a path to re-aim; the template's one mention of `docs/vss-integration/` at
line 51 is an instruction that a move would have to re-aim, so it counts). Result at both the first
measured commit and this one: **11 / 12 / 1** `AGENTS.md` and **44 / 36 / 32** other docs. Per-tree
counts overstate: **136** mentions across **104 distinct files** — the double-count is 32 entries from
**29 multi-tree citers** (28 docs + 1 `AGENTS.md` name two or three trees; 26 name two, 3 name all
three). What is being corrected, precisely, and by whom: the draft printed the columns **45 / 35 / 31**
and "~91 citing files", and the first re-measurement of this sheet replaced the 91 with "**135** mentions
across **97** distinct" plus a five-files-in-both-columns mechanism — while keeping the draft's columns
verbatim. Re-running that first correction's own commands at this commit shows they never reproduced
either — including the columns it kept: its census commands print **44 / 36 / 31** (verified at the
correction's own commit and at head), not the 45 / 35 / 31 it printed — the same whole-repo rule as
above, except it excluded this sheet by _basename_, and that basename exclusion silently dropped
`docs/uplevel/templates/r2-sheet.md` with it. The template is a real citer: line 51 instructs the
record PR to write rulings into `docs/vss-integration/17-action-plan.md`, so a move must re-aim it and
it belongs in the column. The printed 45 / 35 / 31 and the re-run's 44 / 36 / 31 agree in sum
(111) and disagree file by file (±1 twice, in opposite directions) — a reader checking the total would
never see the split; excluding by full path instead of basename gives the honest docs column, 44 / 36 /
**32**. And that correction's 97 silently mixed scopes — 23 `AGENTS.md` citers counted repo-wide + 74
docs citers counted only inside `docs scripts .github README.md` (23 + 74 = 97 exactly; 24 citers live
outside those search dirs). Its "five files sit in both columns" mechanism was real _for the draft's
grep_ — `--include='*.md'` matches `AGENTS.md` basenames, so
`docs/architecture`, `docs/benchmarks`, `docs/decisions`, `docs/synthbench` and `docs/vss-integration`
`/AGENTS.md` each land in both columns — an artifact of the instrument, not the repo; the rule above
splits columns by basename, so the overlap is 0 by construction. Counting every tracked `.md`
whole-repo, the citers outside the draft's docs-scope (`docs scripts .github README.md`) are **24** —
18 `AGENTS.md` files (root, `ai/`, `backend/`, `frontend/`, `synthbench/` subtrees) the draft's
repo-wide AGENTS grep already caught anyway, + the 6 doc files that sit **only** outside the 4 listed
paths: `.claude/skills/synthbench-generation/SKILL.md` and `reference.md`,
`ai/gateway/export/README.md`, `archive/wp25-feed/HANDOFF-WP43.md` and its
`memory/sandbox-recreate-vs-reboot.md`, `backend/tests/plugins/README.md`. (This clause said "the 6
doc files under the 4 paths it listed" — the inverse of what the enumeration shows: a path under
those 4 dirs is by definition inside the scope, so 6 files that all sit outside it cannot be "under"
them.) And **no CI gate would catch a mis-move**: the
level-1 citation job (`ci.yml:230` at this head — the step's name line; the draft cited `:229`, which
was never the name line at any measured commit: it was :225 at the draft (the first merge's +1 hunk
made it :226, this merge's +3/+1 hunks made it :230) and :229 sat inside the step's own run block,
4 lines below the name — so this cite is now correct for the first time, by re-anchoring, not drift;
the prose name + the step's `run:` block are the stable way to re-find it), "Docs citation existence")
validates citations _authored inside_
exactly `docs/decisions deployment getting-started operations ui` — 43 citations across all five, every
one ERR-free today — and of the citers **exactly 2 sit inside those five directories**
(`docs/decisions/2026-01-12-docs-reorganization-design.md`, `docs/decisions/AGENTS.md`); the other 102 of
104 are outside its reach. `docs/plans` itself carries **222 level-1 ERR
citations** (`python -m
scripts.validate_docs docs/plans --no-ast --no-code-match --no-cross-ref --no-staleness`; 385 checked,
163 OK), up from 216/169 at `1d847a6a` with **zero changed paths under `docs/plans/`** — the +6 came in
on a neighbour's merge (`O1.2` deleted `docker-compose.ghcr.yml`, cited by 7 files here, and shrank
`setup_lib/image_pull.py` 379 → 103 lines). So the decay is already running, ungated: the tree that
most needs consolidation is the one whose citations no gate watches. `docs/superpowers/` is citation-
gated by nothing but is the only tree with a uniform naming discipline (100% dated names).

**Options as the register states them.** (a) consolidate the three trees into one directory now;
(b) name one home for FUTURE material and freeze the others as history; (c) keep the split and
record each tree's role.

**Recommendation: (b)**, home = `docs/superpowers/<date>-<slug>/` — the discipline is already proven
there (37/37 dated names, current spans), it moves zero files, and it makes the freeze testable by eye:
a dated file outside `docs/superpowers/` after this ruling is the violation. (a) is the worst option on
the evidence: **104 citing files** to re-aim, of which a gate re-checks 2. One caveat so (b) is not
chosen for the wrong reason: moving nothing removes the _re-aim_ risk, not the _decay_ — the 222 rose
from 216 without an edit to `docs/plans`, when `O1.2` retired a file seven of them cite. (b) leaves
that ungated either way; closing it is a separate decision (extend the level-1 job's dir list, or gate
`docs/plans` on a no-new-ERR bar), and it is not what OD-33 is asking. Under (b), `docs/plans/` and
`docs/vss-integration/` stay where their citations point; `docs/vss-integration/` remains the
register's home (it is live, not history).

**Ruling:**

### OD-34 — the register's OD table and its closed issues

**The question** (`40-docs.md` W2.2): the register gains a ruling column — rulings are inline in the
options column today, "which is how three rulings were misread during the audit" — and closed issues
move to a history file.

**Facts.** `docs/vss-integration/17-action-plan.md` is **8,565 lines** (`wc -l` at this head — this
file's count has moved twice since the draft: 8,485 → 8,518 → 8,565, each move a merge of
`origin/main`, never an edit by this branch) — the plan text says
8,145, stale by **420** lines, about one Phase 1's growth (the first merge added 44 lines and removed 11
per `git diff --numstat`; the second brought +47/−0 in two hunks, +36 at 708 and +11 at 3232, from
`B1.2`'s replay-parity material). The plan-text edit belongs in whichever PR touches it first, or the owner's
next plan edit. Its OD table has **32 rows** (`grep -cE '^\| *OD-[0-9]+'`), 5 columns each.

**Where the rulings actually are.** **11 of the 32 rows record their ruling inside the options cell, and
they do it in three different markups** — which is the finding, and the argument for the column: **10
bolded** clauses, of which only 5 begin `**Ruled 2026…` (OD-3/12/15/20/28) while 5 use other wording
(OD-1 `**Follow-up scope ruled…**`, OD-8 `**Acceptance half ruled…**`, and OD-30/31/32 lowercase
`**ruled 2026-10-05 (a):**`), plus **1 unbolded** ruling at OD-29 (`ruled 2026-10-05 (a): the arm B
rubric text …`, plain text in the options cell). Even "which cell names the ruling" is not single-valued:
**5 of the 11 mention it in a second cell** — OD-1's Source is a pointer ("follow-up ruled in the
2026-10-05 Intake log"), OD-29's and OD-30's Source each read "owner ruling 2026-10-05, Intake log",
OD-30's Unblocks argues with it ("the ruling reached (c) only"), OD-31's Decision names "the same-day
smallest-slice ruling", and OD-31's and OD-32's Source each read "17 Intake log entry 2026-10-05".
(The first correction of this sentence said "2 of the 11", naming only OD-1's Source and OD-30's
Unblocks — it missed OD-29's and OD-32's Source pointers and both of OD-31's second cells.)
**1 more ruling, OD-24, exists nowhere in the table** —
only as an intake-log line ("OD-24 ruled by the owner [O]", L7197 at this head — the register's
internal line cites below moved +36 to +47 with the merge's two hunks, re-anchored here); that is the _only_ log-only ruling,
and 3 rows (OD-1/31/32) carry an explicit "(Intake log entry 2026-10-05)" pointer — OD-1's **from the
options cell**, OD-31's and OD-32's **from the Source cell**. An earlier draft of this row said "7 bolded rulings, 5 more only in the intake log"; both halves
were wrong, and wrong in the instructive way. The 7 came from one grep vocabulary
(`**Ruled` + `**Both floors` + `**Follow-up scope ruled`), which **misses 5 real rulings** (OD-8,
OD-29/30/31/32 — casing and wording variance, exactly the misreading hazard the package text cites)
**and includes 1 non-ruling**: OD-2's bold clause is "**Both floors are measured as of 2026-10-05**",
and OD-5's says out loud "**Input landed 2026-10-05, not a ruling:**". The "5 more in the intake log"
were the `Ruled 2026` grep hits at lines 578–603 (unchanged at this head — both incoming hunks land
below 707) — those lines are _inside_ §4's own table (OD-3/12/15/
20/28), a strict subset of the 7 already counted, and the Intake log (`## Intake log`, line 7143 at
this head, 7096 before the merge — it is
unnumbered; §5 is "The register", at 744, was 708) contains **0** occurrences of that string. So the corrected
total is **12 ruled decisions across table and log**, of which 11 are in the table in 3 markups and 1 is
log-only. No grep returns those 12 as a clean set — that is the machine-checkable form of "three rulings
were misread during the audit": `Ruled 2026` finds **5** and misses 6 of the 11 table rows (7 of the
full 12 — OD-24 is log-only); a bold-clause grep returns **12
rows** of which only **10** are rulings (it wrongly takes in OD-2 and OD-5, and still misses the unbolded
OD-29); case-insensitive `[Rr]uled` catches all 11 table rows but adds OD-5's disclaimer and, in the log,
surfaces OD-24 only as one of 22 log lines that use the word at all.

The register's own status vocabulary (§1) already requires a dated closure note and says "A closed issue
is never deleted" — so a history-file move conflicts with the file's stated doctrine unless the moved
line leaves a dated pointer in place. The
OD table is 5 columns × 32 rows: a 6th "ruling" column re-lays in one mechanical commit.

**Options.** (a) as the package text proposes: ruling column + closed issues to a history file;
(b) ruling column only, closed issues stay; (c) status quo, fix the reading discipline instead.

**Recommendation: (a) with one amendment** — the history file keeps the text (so "never deleted"
survives) but every moved issue leaves a one-line dated pointer at its original position, matching
the register's existing closure-note convention; the ruling column is the part the misreading hazard
actually justifies, and it converts **12 ruled decisions in 3 markups** (10 bold + OD-29 unbolded +
OD-24 log-only) into one column that greps. Cost, measured, and it is not the zero-cost edit the draft
implied: the re-lay itself is one mechanical commit (5→6 columns × 32 rows), but **the extraction cannot
be a grep** — the draft's own vocabulary misses 5 of the 11 table rulings and a bold-only read misses
OD-29, so populating the column honestly costs a human read of all 32 rows plus one log-only ruling
(OD-24) recovered from §Intake log. Budget that read; do not let the history-file half block the column
half — they are separable commits.

**Ruling:**

### OD-35 — the 26 image-(re)validation plans: history or gone

**The question** (`40-docs.md` W2.2): whether the near-identical `docs/plans/image-(re)validation-*`
plans stay as history or go.

**Facts.** The plan text says 28; **the tree holds 26** (`git ls-files 'docs/plans/image-validation-*' 'docs/plans/image-revalidation-*'` — two pathspecs; the single quoted argument `'…-* …-*'` the draft transcribed matches nothing and returns **0**): 12 `image-revalidation-*` + 14 `image-validation-*`, both families dated
2026-01-24 — **all 26 carry that date in their first 15 lines**, which is the provenance fact that
matters, and it is uniform. What is _not_ uniform is the field name: **8 header shapes** across the 26
(`**Validation Date:**` 7, `**Revalidation Date:**` 5, `**Generated:**` 5, `**Date:**` 4, a quoted
`> Generated:` 2, `**Date**:` 2, `**Original Validation Date:**` and `**Re-Validation Date:**` 1 each —
27 lines over 26 files — the double is `image-revalidation-api-reference.md`, which carries
`**Revalidation Date:**` alongside `**Original Validation Date:**` (`**Re-Validation Date:**` is unique
to `image-revalidation-observability.md`; the first correction of this row said api-reference "carries
both of the last two", misidentifying the pair while keeping the 27/26 total it explained),
and validator attribution is a minority header — only **9/26** name Claude Opus 4.5 at all, split four
ways: `**Validator:**` 3, a quoted `> Validator:` 2, `**Reviewer:**` 2, `**Reviewer**:` 2 (note the
field role varies — 4 files call the model the _reviewer_, not the validator). An earlier draft of this
row said each file _begins_
"Generated: 2026-01-24 / Validator: Claude Opus 4.5"; that adjacent pair exists in exactly **2 of 26**
(both named `data-model`, at lines 3–4) — a generalisation from the two files the draft opened, not a
family property. Sizes vary far more than the draft's "~200–250 lines each": **median 315.5 (the 13th
and 14th files run 313 and 318), range 156–546** (`image-revalidation-observability.md` 156 →
`image-validation-security.md` 546), and only **7 of 26** fall in that band. (The first re-measurement
printed "median 315" here, which is no median at all — the probe took the mean of the two middle files,
315.5, and `int()` truncated it. Same lesson as the census: a printed statistic inherits its
instrument's arithmetic, and `int()` is an arithmetic.) Coverage is roughly one per architecture area, not exactly one: 10 validation files and 11
revalidation files each name a distinct `docs/architecture/<area>/`, and the two families' sets are
**one apart, not identical** — the revalidation half also names `data-model`, because
`image-revalidation-data-model.md` points at `docs/architecture/data-model/` while its validation twin
points at the _image_ tree it audited (`docs/images/architecture/data-model/`); all 11 directories are
still on disk. The other 5 name no `docs/architecture/<area>/` at all: validation `data-model` and
`dataflows` (whose headers point at the `docs/images/architecture/` image tree they audited —
`dataflows` and validation `security` are the two files carrying `**Hub:**`), validation `security`
(whose `**Hub:**` is the bare word "Security"), and `detection-pipeline` on **both** sides (neither
names any path). (The first corrections of this passage said "the two
families name the same 10 areas (identical sets)" and "the other 6 … carry `**Hub:**` instead" — the
residue is 5 files, not 6, only 2 carry `**Hub:**`, and the count was off because
`image-revalidation-data-model.md` was sitting in the residue list while naming an area directory.)
So 26 files cover ~11 architecture areas almost twice over — the positive form of "the same audit run
twice", not 26 distinct audits.
The cross-cites run **one way**: 8 of the 12 revalidation files name an `image-validation-*` sibling by
exact stem (0 the other way — the validation half never mentions the revalidation half), 9 such
occurrences in total across the family. **Zero `AGENTS.md` files cite them** (`git grep -lE
'image-(re)?validation-' -- '**/AGENTS.md' 'AGENTS.md'` → no hits) and they sit outside every CI
citation gate (OD-33 facts). Outside the family, **2 files mention it and neither is a re-aimable path**
(a third, this sheet, names the family as its own subject and is not a referrer to re-aim):
`docs/uplevel/40-docs.md:156` says "image-validation plans." in prose (cited as `:176` before the
merge — W2.1's rewrite of that file moved the line, not the mention),
and `docs/plans/2026-09-22-docs-scan-findings.md:311` records them as an audit finding — "other
image-validation-* and image-revalidation-_ (14 files)" — which is a _record of what that audit saw_,
so re-aiming it would falsify it. The draft's "2 external referrers to re-aim" was a file count of
those two prose mentions, not a citation count; the real re-aim surface is the 9 intra-family
occurrences.

**The archive destination is already ruled out.** An earlier draft of this row recommended moving the
family to `docs/archive/`, citing it as "the in-repo precedent for retired docs material", already in
the validator's `no_agents_md_required` list. Both halves were true at the measured commit and are
foreclosed by a standing ruling the draft had not read: **UR-19** (`docs/uplevel/README.md`) is
"`archive/` and `docs/archive/` are deleted … git history is not rewritten", **`O1.5`** (
`30-ops.md:125-137`) executes it — "`git rm -r archive docs/archive`. Remove the archive excludes from
… `.agents-md-validator.yml`" — and its status row is still `not started` (`README.md:246` at this
head, :243 before the merge — the table shifted, the row did not). README's
"Considered and rejected" table then rejects this row's exact move: "Moving dead code into `archive/` |
relocates sediment; git history already keeps every deleted file | UR-19". Recommending it again would
be reopening a settled ruling inside a ruling request. UR-19's stated reason is also the direct answer
to this row's own argument against deletion — "git history already keeps every deleted file" is why
deleting the family does not throw away the record. (The `no_agents_md_required` fact the draft leaned
on does no work either way: `check_missing_agents_md` fires on directories holding ≥`min_code_files: 2`
files matching `code_extensions` — `.md` is not among them — so 26 markdown files could not trip
`missing_agents_md` wherever they sat. Its `≥2` test lives at `agents_md_validator.py:702` at this
head (the draft's :619, moved by W2.1's +186/−6 growth of the validator), not in
`find_directories_with_code`.)

**Options.** (a) keep in place as history; (b) delete. (The archive move is not on the list because
UR-19 removed its destination.)

**Recommendation: (b) delete.** They are one-run audit outputs, not plans, and they sit in the tree the
programme reads as live plans: 26 files / 8,314 lines, ~11 architecture areas almost twice over (the
Facts above said ~10/twice until the fourth round fixed the area-set measurement — the recommendation
had kept the stale figure). Under
OD-33's (b) `docs/plans/` freezes as history either way, so (a) is coherent rather than wrong — choose
(a) if the January findings are still being consulted. Delete is recommended because the cost of (b) is
near zero and the cost of (a) is permanent: 9 intra-family occurrences to clear, no path citations
outside the family to re-aim, no gate to satisfy and no AGENTS.md consequence either way (above). The
gate claim is measured, not inferred: the only files mentioning the family are two prose mentions plus
this sheet, and **none of the five gate-validated directories mentions it at all** — so deleting the 26
files breaks zero citations in a gated tree. `git rm -r` of the two pathspecs keeps the record
recoverable, which is UR-19's own doctrine — and unlike the draft's version, this recommendation needs
no `validate_docs` before/after ERR-delta ritual, for that measured reason. If the owner rules (a), the
row's answer to "then what marks them as dead?" is OD-33's freeze rule, not a new file.

**Ruling:**

---

_Fill order for the owner: these three are Phase 2 `W2.2` rows; `R2` rules them in the same session
as the feature rows. The frontend lane's record PR copies each ruling into_
`docs/vss-integration/17-action-plan.md` _per the template's §4 — `OD-33/34/35` are new numbers and
the register has no rows for them yet, so the record step ADDS those three rows, it does not edit
existing ones._
