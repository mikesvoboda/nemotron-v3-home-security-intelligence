# P3: The one-worker loop

> **Task level. Expand before execution:** when P2 has merged, run superpowers:writing-plans on this file against the then-current tree. Tasks 8 and 9 change the `dgx-station-inference-stack` repository and are planned and merged there. Index: [`README.md`](README.md).

**Goal:** A Claude manager on the host writes one brief, launches one flagship-Qwen worker in an sbx sandbox, and the worker runs trials through the executor until it returns the brief, with every step on the ledger. The equivalent of autocuda's `optimize-hill`.

**Spec:** design [`01`](../../auto-vlm-research/01-architecture.md) §3.8–3.10, §4–6; [`03`](../../auto-vlm-research/03-idea-catalogue.md) §9; [`05`](../../auto-vlm-research/05-stack-integration.md) §2.

**Prerequisites:** P2 merged; P0's S2 (herdr status) and S3 (unattended start) recorded, with the fallbacks they chose.

---

### Task 1: A prompt-template seam in the backend

The search needs to vary the prompt, and a winner must ship through the product's own client, so the seam belongs in the backend (a backend-lane change, reviewed by its owner).

**Files:** modify `backend/services/vlm_client.py` (prompt construction behind a `PromptBuilder` protocol); create `autovlm/templates/` and `autovlm/templates.py`; modify `autovlm/recipe.py` (`vlm.prompt` accepts `"shipped"` or a registered template id); tests in `backend/tests/unit/services/` and `backend/tests/unit/autovlm/test_templates.py`.

**Interfaces:** `PromptBuilder.build(context: VlmAssessContext, request: VlmAssessRequest) -> str`; `ShippedPromptBuilder` (today's behaviour); `TemplatePromptBuilder(template_text)` rendering with a sandboxed Jinja environment over the context fields only.

**Tests:** for a fixed set of contexts, `ShippedPromptBuilder` renders byte for byte what the client renders before the change (the regression gate for production); a template cannot reach attributes outside the context; a template containing taxonomy vocabulary fails P1's vocabulary check at submission.

---

### Task 2: The findings register

**Files:** create `autovlm/findings.py`, `autovlm/findings/seed.yaml`, `autovlm/commands/findings.py` (`autovlm findings add|retract|list`, for the manager and the auditor); test `backend/tests/unit/autovlm/test_findings.py`.

**Interfaces:** `Finding(id, claim, effect: {metric, point, ci}, conditions: {corpus_version, build, model, quant, input_mode, decision_head}, evidence: list[str], status)`; `Register(path)` with `add`, `retract(id, reason)`, `relevant(conditions) -> list[Finding]` (exact-condition matches are `supported`/`refuted`; others are returned as `stale`).

**Seed:** the seven results of design `03` §9, each with its source document and conditions (one still, oracle detections, the shipped 8B, build b11376 or b7972 as recorded).

**Tests:** a claim naming a taxonomy scenario is refused; retracting keeps the row with its reason; a finding measured on one build reads as `stale` under another; the seed file loads and every row cites a document that exists.

---

### Task 3: Briefs

**Files:** create `autovlm/commands/brief.py`; modify `autovlm/cli.py`; test `backend/tests/unit/autovlm/test_brief.py`.

**Interfaces:** `autovlm brief new --tag --kind macro|micro --parent <commit> --description <text>` (manager; prints `brief_id=<K>`); `autovlm brief continue --tag --brief-id --description` (manager); `autovlm brief show --tag --brief-id` (worker; prints the objective, the parent recipe, and the findings rows relevant to the parent's conditions).

**Tests:** `new` writes a `brief` row with the next id; `continue` requires a prior `brief_stop`; `show` quotes relevant findings and never prints item ids or labels.

---

### Task 4: Worker trial verbs

**Files:** create `autovlm/commands/trial.py`, `autovlm/commands/log.py`; test `backend/tests/unit/autovlm/test_trial_cli.py`.

**Interfaces:** `autovlm trial submit --tag --brief-id --commit HEAD` (resolves the commit, posts with `idempotency_key = sha256(tag, brief, commit)`, prints `trial_id=<id>`); `autovlm trial wait <id>` (polls with backoff, returns when done; exits 1 on failure with the reason); `autovlm trial show <id>` (train per-item outcomes and select aggregates); `autovlm log start|stop --tag --brief-id [--description]`. The executor URL and token come from the files `agent-dgx --autovlm` mounts (Task 8).

**Tests (against a fake API):** a resubmitted commit returns the same trial; `wait` survives the API restarting mid-poll; `show` output for select contains no item ids; every verb is safe to repeat after a crash.

---

### Task 5: herdr control

**Files:** create `autovlm/control/__init__.py`, `autovlm/control/herdr.py`; test `backend/tests/unit/autovlm/test_herdr.py`.

**Interfaces:** `Herdr(runner=subprocess.run)` with `agents() -> list[AgentInfo]`, `status(agent_id) -> "idle"|"working"|"blocked"|"done"|"unknown"`, `prompt(agent_id, text)`; all argv lists, never a shell.

**Behaviour:** if S2 showed herdr cannot track Qwen-backed panes, `status` derives idle from the session transcript's age instead, and says so in its result.

**Tests (with a fake runner):** argv shapes for each verb; parsing of `herdr agent get` output; the transcript-age fallback.

---

### Task 6: Manager and worker skills

**Files:** create `.claude/skills/autovlm-manager/SKILL.md`, `.claude/skills/autovlm-worker/SKILL.md`.

**Content, adapted from autocuda's `optimize-tree` and `explore-brief`:**

- **Manager:** read `autovlm status` and the ledger; write a brief (one idea, a parent, a kind, 10–100 words, no acceptance bars or stop conditions); launch the worker with `agent-dgx run … --autovlm <run> -- <brief prompt>`; wait for ledger events; continue, replace or restart; keep the findings register current; never call `confirm`, never read labels, never edit outside the manifest.
- **Worker:** `autovlm brief show`; branch from the parent; edit only recipes and templates; `autovlm trial submit` and `wait`; commit what was measured, regressions included; read train-split detail to decide the next edit; return with measurements, not verdicts; never look for labels, never read other runs.

**Acceptance:** a dry run of each skill against a fake executor completes a brief end to end.

---

### Task 7: Worker workspace hygiene

**Files:** create `autovlm/control/workspace.py`; test `backend/tests/unit/autovlm/test_workspace.py`.

**Behaviour:** after `agent-dgx` seeds a worker's workspace, apply a git sparse-checkout that removes `synthbench/taxonomy/`, `synthbench/export/`, `docs/benchmarks/` (the sweep's `items.csv` holds per-item labels), `docs/vss-integration/` and `autovlm/scorer/` data paths. The worker still has everything it needs to edit recipes and templates and run the CLI.

**Tests:** in a temporary clone, the excluded paths are absent and the allowed paths present; re-applying is idempotent.

---

### Task 8 (stack repo): `agent-dgx run --autovlm <run>`

**Behaviour:** like `--gpu`, the flag mounts the `autovlm` CLI entry point, a per-session executor token (mode 600) and the run's train-split inputs read-only, never select or holdout frames; it applies the per-sandbox sbx denies S4 proved (the `agent-gpu` pool range and every autovlm port but the executor's), and the launcher re-applies them, because sbx rules live in sbx's local state.

**Tests (in the stack repo's suite):** the composed `sbx create` arguments carry exactly those mounts; the deny rules are issued for the sandbox name; a run directory under `/export` is refused, because sbx cannot mount there.

---

### Task 9 (stack repo): a stall trigger for autovlm workers

**Behaviour:** the stall watch, which today acts only when `/goal` is active and unmet, also acts when the run's ledger shows the worker's brief open, herdr (or the Task 5 fallback) shows the session idle, and the transcript has been quiet for a set time; it pokes with `herdr agent prompt <id> "Continue brief <K>: run autovlm brief show and your next trial."`, at most twice in three hours, then notifies.

**Tests (in the stack repo's suite):** the trigger fires on an open brief with an idle, quiet session; it does not fire after `brief_stop`; it respects the poke limit.

---

### Task 10: The first agentic run (operational)

**Steps:** create a run on the P1 baseline; the manager writes one macro brief (for example, "show the VLM the last four frames of the burst instead of one still"); launch one worker; let it run at least three trials; the owner reviews the ledger, the worker's commits and the trials' checks.

**Acceptance:** every trial row has a commit and a recipe hash; no manifest or vocabulary violation; the worker never reached the scorer socket or a pool port (sbx policy log); the findings register gained at most mechanism-level rows; a stall, if one happened, was resolved by a poke without human input.
