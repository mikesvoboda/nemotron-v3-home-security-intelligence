# R2 Ruling Sheet — session date TBD by the owner

> Created early by `W2.2` (docs lane), before `F2.2` runs. The template
> (`templates/r2-sheet.md`) says `F2.2` copies it here and fills it; `W2.2`'s Done-when needs its
> three rows committed before the owner's ruling session, so this file starts with only the docs
> rows (§2b) and nothing else. **`F2.2`: fill §1, §2 and §3 around §2b — do not rewrite or
> renumber this section.** The §2b OD numbers (`OD-33`…`OD-35`) are assigned; register rows run to
> `OD-32` today, so continue from `OD-36` if new decisions surface.
>
> Every row is written so it can be ruled from the row alone, without opening code. Facts are
> measured at `1d847a6a` (2026-10-09) by the commands named in each row.

## 2b. Docs-lane rulings (`W2.2`)

### OD-33 — one home for future plans and specs

**The question** (`40-docs.md` W2.2): VSS material is split across `docs/plans/`,
`docs/superpowers/` and `docs/vss-integration/` today. Where do future plans and specs go?

**Facts.** `git ls-files` at this commit: `docs/plans/` 93 files (57 dated-named, span 2025-01-23 →
2026-10-04 — still live: the AGENTS.md validator's own design doc lives here);
`docs/superpowers/` 37 files, ALL dated, span 2026-09-12 → 2026-10-07 (the VSS specs — the tree the
programme is actively writing into); `docs/vss-integration/` 26 files (5 dated; the register and its
companions). None of the three trees appears in `mkdocs.yml`'s nav (0 entries each). A move is
citation-cheap in one direction and expensive in the other: the trees are cited FROM 11 / 12 / 1
`AGENTS.md` files and 45 / 35 / 31 other docs, and **no CI gate would catch a mis-move** — the
level-1 citation job (`ci.yml` "Docs citation existence") covers exactly
`docs/decisions deployment getting-started operations ui`; `docs/plans` itself carries **216
level-1 ERR citations today** (`python -m scripts.validate_docs docs/plans --no-ast
--no-code-match --no-cross-ref --no-staleness`), i.e. the tree that most needs consolidation is the
one whose citations no gate watches. `docs/superpowers/` is already citation-gated by nothing but is
the only tree with a uniform naming discipline (100% dated names).

**Options as the register states them.** (a) consolidate the three trees into one directory now;
(b) name one home for FUTURE material and freeze the others as history; (c) keep the split and
record each tree's role.

**Recommendation: (b)**, home = `docs/superpowers/<date>-<slug>/` — the discipline is already
proven there (37/37 dated names, current spans), it moves zero files (so the 216 ungated citations
cannot silently worsen), and it makes the freeze testable by eye: a dated file outside
`docs/superpowers/` after this ruling is the violation. (a) is the worst option on the evidence:
~91 citing files to re-aim with no gate verifying the re-aim. Under (b), `docs/plans/` and
`docs/vss-integration/` stay where their citations point; `docs/vss-integration/` remains the
register's home (it is live, not history).

**Ruling:**

### OD-34 — the register's OD table and its closed issues

**The question** (`40-docs.md` W2.2): the register gains a ruling column — rulings are inline in the
options column today, "which is how three rulings were misread during the audit" — and closed issues
move to a history file.

**Facts.** `docs/vss-integration/17-action-plan.md` is **8,485 lines** — the plan text says 8,145,
which is stale by roughly a Phase 1's growth (~340 lines; the plan-text edit belongs in whichever PR
touches it first, or the owner's next plan edit). Its OD table has **32 rows**
(`grep -cE '^\| *OD-[0-9]+'`). Rulings ride inline: **7 OD rows carry bolded "**Ruled/Both
floors/Follow-up scope ruled …**" clauses inside the options cell** (e.g. OD-1's option list ends
with a bolded follow-up ruling pointing at "(Intake log entry 2026-10-05)"), and 5 more rulings live
only in Intake log entries ("Ruled 2026…"). The register's own status vocabulary (§1) already
requires a dated closure note and says "A closed issue is never deleted" — so a history-file move
conflicts with the file's stated doctrine unless the moved line leaves a dated pointer in place. The
OD table is 5 columns × 32 rows: a 6th "ruling" column re-lays in one mechanical commit.

**Options.** (a) as the package text proposes: ruling column + closed issues to a history file;
(b) ruling column only, closed issues stay; (c) status quo, fix the reading discipline instead.

**Recommendation: (a) with one amendment** — the history file keeps the text (so "never deleted"
survives) but every moved issue leaves a one-line dated pointer at its original position, matching
the register's existing closure-note convention; the ruling column is the part the misreading hazard
actually justifies, and it converts 7 inline bold rulings + 5 intake-log rulings into a column that
greps. Do not let the history-file half block the column half: they are separable commits.

**Ruling:**

### OD-35 — the 26 image-(re)validation plans: history or gone

**The question** (`40-docs.md` W2.2): whether the near-identical `docs/plans/image-(re)validation-*`
plans stay as history or go.

**Facts.** The plan text says 28; **the tree holds 26** (`git ls-files 'docs/plans/image-validation-*
image-revalidation-*'`): 12 `image-revalidation-*` + 14 `image-validation-*`, both families generated
2026-01-24 (each begins "Generated: 2026-01-24 / Validator: Claude Opus 4.5"), one per architecture
doc, ~200–250 lines each — the same audit run twice under two name stems, not 28 distinct audits.
They cross-cite each other and `docs/plans/2026-09-22-docs-scan-findings.md` cites the family; **zero
`AGENTS.md` files cite them**, and they are outside every CI citation gate (OD-33 facts).
`docs/archive/` exists as the in-repo precedent for retired docs material and is already in the
validator's `no_agents_md_required` list (`docs/archive/`), so moving the family there creates no
AGENTS.md obligation and is invisible to the boundaries work (`W3.1`).

**Options.** (a) keep in place as history; (b) move to `docs/archive/image-validation/`; (c) delete.

**Recommendation: (b).** They are one-run audit outputs, not plans — "keep in place" leaves 26 files
(8,314 lines by `wc -l`) in the tree the programme reads as live plans, and deletion (c) throws away the only
record of what the January docs audit found, which the W2.2 register history in OD-34's spirit says
to keep. A move needs its 2 external referrers re-aimed (`docs/uplevel/40-docs.md`,
`docs/plans/2026-09-22-docs-scan-findings.md`) plus the intra-family cites; no CI gate verifies the
re-aim (OD-33 facts), so the mover runs `scripts.validate_docs` over `docs/plans` before and after
and counts ERR deltas by hand. If the owner expects these to be deleted rather than archived,
say so and the lane will re-run the recommendation as (c) with the same re-aim list.

**Ruling:**

---

_Fill order for the owner: these three are Phase 2 `W2.2` rows; `R2` rules them in the same session
as the feature rows. The frontend lane's record PR copies each ruling into_
`docs/vss-integration/17-action-plan.md` _per the template's §4 — `OD-33/34/35` are new numbers and
the register has no rows for them yet, so the record step ADDS those three rows, it does not edit
existing ones._
