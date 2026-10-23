# P4: The tree fleet

> **Task level. Expand before execution:** when P3 has merged and its first agentic run has been reviewed, run superpowers:writing-plans on this file against the then-current tree. Index: [`README.md`](README.md).

**Goal:** The manager keeps N workers busy on diverse briefs, combines winners, rotates data between epochs with the fleet drained, and an auditor removes gamed trials from the fronts. The equivalent of autocuda's `optimize-tree`.

**Spec:** design [`01`](../../auto-vlm-research/01-architecture.md) §3.9, §3.12, §5; [`02`](../../auto-vlm-research/02-evaluation.md) §2, §6–8; [`05`](../../auto-vlm-research/05-stack-integration.md) §4.

**Prerequisites:** P3 merged; the first agentic run reviewed by the owner.

---

### Task 1: Brief kinds and combine

**Files:** create `autovlm/combine.py`; modify `autovlm/commands/brief.py`; test `backend/tests/unit/autovlm/test_combine.py`.

**Interfaces:** brief kinds `macro`, `micro`, `combine`; `--parent` repeats for `combine` (at least two). `merge_recipes(base: Recipe, others: list[Recipe]) -> MergeResult(recipe, conflicts: list[str])`: keys changed by only one parent merge automatically; a key changed by two parents in different ways is a conflict the worker resolves as part of the brief. Minimum shares per kind (`--min-macro` and the rest) follow autocuda's semantics: each in [0, 1], summing to at most 1, checked when a brief is recorded.

**Tests:** disjoint changes merge; a conflicting key is reported, not silently chosen; a `combine` brief with one parent is refused; a brief that would break the minimum shares is refused.

---

### Task 2: `autovlm wait` and the manager loop

**Files:** create `autovlm/commands/wait.py`; modify `.claude/skills/autovlm-manager/SKILL.md`; test `backend/tests/unit/autovlm/test_wait.py`.

**Interfaces:** `autovlm wait --tag [--timeout]` blocks until the ledger gains a row after the caller's last-seen offset (kept in a per-manager state file) and prints that row as JSON; the waiting happens inside the command, so the manager never writes a polling shell loop.

**Tests:** returns immediately when rows are pending; blocks, then returns, when another process appends; honours the timeout with exit code 3; two managers keep separate offsets.

---

### Task 3: Fleet launch and slots

**Files:** create `autovlm/control/fleet.py`; test `backend/tests/unit/autovlm/test_fleet.py`.

**Interfaces:** `Fleet(width, herdr, launcher)` with `fill(open_briefs)`, `on_return(brief_id)`, `restart(brief_id)`; a launch opens a herdr pane per worker (`agent-dgx run autovlm-<tag>-w<n> --agent claude --endpoint dgx --autovlm <run> --split -- <brief prompt>`), or uses the batch mode if the stack repo has gained one.

**Tests (with fakes):** slots fill to width; a returned brief frees its slot; a crashed session restarts the same brief without a second `brief_start`; width changes on resume take effect at the next fill.

---

### Task 4: Epochs with a drained fleet

**Files:** create `autovlm/epochs.py`, `autovlm/commands/epoch.py`; test `backend/tests/unit/autovlm/test_epochs.py`.

**Behaviour:** `progress.stalled` turns true when no tier's front has changed for N trials or H hours (configurable, recorded in the run config). Starting an epoch: stop launching, wait for every worker to return, request a fresh synthbench batch through synthbench's own GPU window (the owner's approval for generation runs applies; the workers run on the flagship the window stops), blind the new batch with P1's `blind`, rotate the split (the old select scenarios join train; the new batch supplies select and holdout through P1's `draw_three_tier` with a new seed), re-measure each tier's envelope (P2 Task 9), and append an `epoch` row.

**Tests:** the stall rule on synthetic ledgers; rotation keeps every scenario in exactly one tier, keeps every earlier holdout scenario in the holdout, and never moves a train scenario to select; an epoch cannot start while a worker is running.

---

### Task 5: The select-query budget

**Files:** modify `autovlm/executor/runner.py`, `autovlm/status.py`; test `backend/tests/unit/autovlm/test_budget.py`.

**Behaviour:** each epoch has a select-query budget per cost class (C1, C2, C3; design `03` §1), set in the run config. Past a class's budget, the executor answers that class's trials on train only, using scenario-grouped cross-validation, and marks them `select-budget-spent`; they cannot change a front until the next epoch. `autovlm status` shows the remaining budget per class.

**Tests:** the budget decrements per answered select query; an over-budget C1 trial gets a train-only answer and no front change; a new epoch resets the budgets.

---

### Task 6: The auditor

**Files:** create `.claude/skills/autovlm-auditor/SKILL.md`, `autovlm/audit.py`, `autovlm/commands/audit.py`; test `backend/tests/unit/autovlm/test_audit.py`.

**Behaviour:** at each epoch's end, `autovlm audit --tag` lists every trial that changed a front, with its diff against its parent and its checks. The auditor skill reads them and records findings with `autovlm log retroactive --brief-id --trial --status reward_hacking|invalid --reason <evidence>`. A reclassified trial leaves every front, and so does every descendant whose brief chain runs through it; each front falls back to its last clean member.

**Tests:** the taint follows parent chains, including `combine` parents; a front falls back correctly; an identical retroactive retry is a no-op, a conflicting one is refused.

**Acceptance (the planted-gaming drill, design `01` §8):** three planted trials are each caught: a template that names a scenario (the vocabulary check), a template that tells the model to answer "uncertain" whenever unsure (the uncertain cap), and a template that forces one fixed score (the degenerate check). A fourth, a template that keys on a generator artefact without naming anything, must be caught by the auditor's review; if it is not, the drill's report says so.

---

### Task 7: Brev hand-off for tier confirmation

**Files:** create `autovlm/commands/bundle.py`, `docs/auto-vlm-research/runbooks/brev-tier-confirmation.md`; test `backend/tests/unit/autovlm/test_bundle.py`.

**Behaviour:** `autovlm bundle --trial <id>` writes a self-contained directory: the recipe, the weight and projector sha256s, the pinned build, the llama-server arguments, and a measurement script that records peak VRAM of the whole stack and p50/p95 latency (S1, S4) on the card it runs on. The runbook covers starting a Brev VM of the tier, copying the bundle over SSH, running it, and wiping the VM (the owner's data ruling for Brev). `autovlm front confirm --trial --bucket --measured-gib --latency-p95` records the result (P2 Task 3's `confirm`).

**Tests:** the bundle contains no labels or item ids; the measurement script's arguments match the recipe; `front confirm` demotes a stack that does not fit.
