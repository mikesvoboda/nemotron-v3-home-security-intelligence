# Synthbench P3: Agent-Driven Tier B Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a flagship agent in a Docker Sandbox the commands and documents to drive Tier B
generation beside the flagship. The commands are `check`, `render`, `camera`, `triage` and
`report`. The host side keeps the flagship safe: a guard, a renderer unit, and snapshots with a
prune rule.

**Architecture:** The agent runs `uv run python -m synthbench <command>` in its clone. Commands
read and write the append-only corpus through `CorpusStore`, and `render` calls ComfyUI's HTTP
API at `:8188`. Each command lives in `synthbench/commands/`, and `cli.py` only parses and
dispatches. Host-only code lives in `synthbench/host/` and runs under systemd user units from a
dedicated worktree:

- the guard writes `status/flagship.json` every 5 s, and `render` yields on it;
- the renderer runs ComfyUI in the foreground;
- a timer snapshots the corpus dataset and prunes.

**Tech Stack:** Python 3.14, pydantic 2, httpx, Pillow 12, numpy and OpenCV 5 (`cv2`); both come
with main dependencies (`accelerate`, `ultralytics`), so CI's `uv sync --extra dev` has them. PyYAML, argparse; systemd user units; ZFS; podman (renderer) and rootful
docker (flagship, read-only here). pytest with xdist, `-p randomly` and a 5 s timeout. No new
dependencies.

**Spec:** `docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md`
(the whole document; this plan is its §9 item 2) and its parent
`docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md` (rev 3: §2, §3.4,
§3.6, §3.8, §4.2, §7). Read both before starting. The P2 plan
(`docs/superpowers/plans/2026-09-28-synthbench-p2-contract-sampler.md`) built the code this plan
extends.

**Branch:** `feat/synthbench-p3`, from `main` at 8df51918 (P2, PR #6703, merged on 2026-09-28).
Its PR targets `main`. To change a PR's base, use `gh api -X PATCH` (`gh pr edit` fails silently
in this repo).

**Paths (2026-09-28, Task 1):** sbx sandboxes cannot mount paths under `/export`, so the
`primary/export/synthbench` dataset now mounts at `/synthbench` (the corpus at `/synthbench/corpus`),
and `/export/synthbench` is a host symlink to it. Dataset names are unchanged. See
`docs/benchmarks/synthbench/p3-probes.md`.

## Rulings made while planning (the executor does not revisit these)

- **P3-R1: the CLI is `python -m synthbench <command>`** (P2-R2 stands). The design's
  `synthbench <command>` is shorthand. The agent runs `uv run python -m synthbench …`.
- **P3-R2: `taxonomy_sha256` hashes the validated taxonomy as canonical JSON** (owner ruling,
  2026-09-28). Comments and layout in the YAML no longer change a corpus version's identity; any
  value does. No corpus version exists yet, so nothing migrates.
- **P3-R3: `synthbench camera calibrate` moves to its own follow-up plan** (owner ruling,
  2026-09-28). P3 ships the camera stage with committed default parameters (`default-v1`), and
  each attempt records the parameter set id (design §7). Calibration needs the owner to map the
  five real cameras to camera types.
- **P3-R4: prompts are at most 1,200 characters** (design §3.1 rule 3):
  - FLUX.2 [dev]'s reference text length is 512 tokens: `MAX_LENGTH = 512` in BFL's
    `flux2/text_encoder.py`, and `max_sequence_length=512` in diffusers' `Flux2Pipeline`
    (read 2026-09-28).
  - ComfyUI v0.37.0 applies no limit (its Mistral3 tokenizer has `max_length=99999999`,
    `min_length=1`), so the pin cannot come from the workflow itself.
  - Measured in the renderer image with the checkpoint's own tekken tokenizer (2026-09-28): the
    chat template is 33 tokens, and English scene text runs 4.6-4.9 characters per token.
  - At a pessimistic 3.5 characters per token, 1,200 characters plus the fixed suffix stays
    under 512 tokens.
- **P3-R5: JSON files change by atomic replace** (temporary file, fsync, `os.replace`), never by
  an in-place overwrite, which a crash would leave torn. This was measured on the corpus dataset
  on 2026-09-28 (the probe snapshots were destroyed afterwards):

  | Write                          | `zfs diff -FH` shows         |
  | ------------------------------ | ---------------------------- |
  | a replace                      | `-` and `+` on the same path |
  | an in-place write or an append | `M`                          |
  | `write_new`'s hard link        | a single `+`                 |
  | directories                    | `M` with type `/`            |

- **P3-R6: the prune rule, made exact** (design §6):
  - Ignore directories (type `/`) and the store's temporary files (`.<name>.<random>.tmp`).
  - A path with both `-` and `+` is **modified**. `R old new` removes `old` and creates `new`.
  - **Hold** when a file was removed, or when a modified file is anything but
    `.json`/`.jsonl`/`.md`/`.html`. `report.md` and `sheet.html` are rewritten views, and an
    unknown file type is treated conservatively.
  - A modified `.json`, `.jsonl`, `.md` or `.html` file is **churn**.
- **P3-R7: attempt seeds** are `int(sha256(f"{event_id}:{k}")[:8 hex], 16)`
  (`attempt_seed`). Output names are `renders/a<k>-s<seed>.png` and `stills/a<k>-s<seed>.jpg`.
- **P3-R8: host units run from a dedicated worktree**, `/synthbench/host-checkout`
  (detached HEAD, its own `.venv`), not from the owner's working clone. The guard is a safety
  component, and the working clone switches branches. The root filesystem is 96% full, so the
  worktree goes on `/export`. `python -m synthbench.host.units install` renders the unit files
  from the checkout that runs it.
- **P3-R9: ComfyUI's address** is `$SYNTHBENCH_COMFYUI_URL` if set. Otherwise it is the first of
  `http://127.0.0.1:8188` and `http://host.docker.internal:8188` whose `/system_stats` answers
  within 3 s. The same code then works on the host and in the sandbox; Task 1 measures which
  address answers inside the sandbox.
- **P3-R10: `render` takes a time budget** (`--budget-seconds`, default 480). Claude Code's Bash
  tool allows at most 10 minutes per call. `render` stops starting images when the budget runs
  out, prints how many remain, and exits 0; the agent runs it again until none remain.
- **P3-R11: the triage cap** (design §4):
  - A batch of `n` events may schedule `floor(n / 10)` triage rerolls over its lifetime.
    Verdicts are processed in event-id order.
  - A reroll verdict beyond the cap marks its event `failed`, with no attempt scheduled. That run
    of `triage` then exits 2.
  - Nothing is deleted. The owner decides whether to sample replacements.
- **P3-R12: quota prior counts include failed events** (P2 behaviour kept). Counting only usable
  events would redraw a scenario FLUX.2 keeps failing and tilt the corpus toward generator
  failures. The report lists failures by scenario so the owner sees any shortfall.
- **P3-R13: index statuses.** `sampled` → `prompted` (`check` froze the prompt) → `rendered`
  (`render` stored the attempt's PNG) → `ready` (triage ok), `rerolled` (a new attempt is
  scheduled, and `render` writes `rendered` again) or `failed`.
- **P3-R14: `provenance.json` goes to schema_version 2.** Each attempt gains `render_failures`
  and `overlay_time` (the timestamp the camera stage drew; P5 names the FTP upload with it). No
  version-1 file exists, because the corpus was empty on 2026-09-28. The parent spec gets a
  migration note.
- **P3-R15: no lock on `index.jsonl`.** A batch has one writer at a time, the agent; the owner's
  host `check` writes nothing once a batch is frozen. Each append is a single `O_APPEND` write.
- **P3-R16: the overlay date.** The spec fixes the scene time (HH:MM). The camera stage draws
  `2026-MM-DD HH:MM:SS`, with month, day and seconds seeded by the attempt, and a winter month
  when the weather is snow. The Foscam overlay's exact layout is **[A]**; the owner compares a
  pilot still with a real one (Task 14).

## Global Constraints

- **Exit codes** (design §3), for every command:

  - `0`: done.
  - `1`: error. The request is wrong; fix it and run again.
  - `2`: stop and ask the owner. This covers an unreachable renderer, a stale status file, the
    batch reroll cap, and any corpus or taxonomy state the command does not expect.

  argparse usage errors exit **1**.

- **Append-only corpus** (design §2):
  - No command deletes, moves or overwrites an image or a clip. A reroll writes a new attempt
    file.
  - Only `.json` files and the batch views (`report.md`, `sheet.html`) change in place, and only
    by atomic replace. `index.jsonl` only grows.
  - All writes go through `CorpusStore`.
- **The sampler owns the facts, the agent owns the wording** (G4). A frozen prompt never
  changes; a different prompt is a new event.
- **Render at 1280×720** (G7). The camera stage makes the 1920×1080 JPEG still (§7).
- **Yield** (§5.2):
  - Before each image, `render` reads `status/flagship.json`.
  - It waits, polling every 5 s, while `waiting > 0` or `healthy` is false.
  - A file older than 30 s exits 2.
- **Triage** (§4):
  - The agent may reroll only for the seven reasons in `TriageReason`.
  - One triage reroll per event; a second triage failure marks the event `failed`.
  - At most 3 attempts per event (`MAX_ATTEMPTS`).
  - Rerolls are capped at 10% of a batch (P3-R11).
- **Flagship safety** (G2, §5):
  - The agent never touches docker, podman, the GPU or the weights.
  - Only the guard stops the renderer automatically. Nothing in this plan stops or starts the
    flagship.
  - The flagship's util gate becomes **0.76** (Task 12, owner-applied). The renderer refuses to
    start above it.
- **GPU windows stay owner-only** (G11). The agent's documents do not describe them.
- **Ports:** ComfyUI listens on `127.0.0.1:8188` only. The flagship is `127.0.0.1:8000`.
- **Imports:** only `synthbench/score/` and `synthbench/run/` may import `backend` (parent §7.1).
  Durable code never imports `synthbench/spikes/`.
- **Tests:**
  - They live in `backend/tests/unit/synthbench/`.
  - No GPU, docker, podman, zfs, systemd or network: every subprocess and HTTP call goes through
    an injected fake (`run=`, `get=`, `transport=`).
  - No real sleeps; fake `sleep` and `clock`. No writes outside `tmp_path`.
  - Each test finishes well under 5 s _including setup_. Load the taxonomy at module level.
- **Content rules** (parent §3.8): realistic, non-graphic threat content; anonymous people.
- **Lint and types:**
  - ruff (S, T20: no `print`, use `sys.stdout`/`sys.stderr`; PTH; PL; ARG; RUF) and mypy
    (`disallow_untyped_defs`, pydantic plugin) pass on `synthbench/` and the tests.
  - Vulture scans `backend/`, tests included. Name deliberately unused parameters with a leading
    `_`. Before any push, run
    `uv run vulture backend/ vulture_whitelist.py --config pyproject.toml`.
- **Commits:**
  - Run `SKIP=semgrep uvx pre-commit run --files <files> && git add <files> && git commit …`,
    and gate the commit on the hook's exit code. Pre-commit is not installed as a git hook on
    this host.
  - Never `--no-verify`, and never chain with `;`.
  - Messages are conventional commits ending with
    `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Live steps** (Tasks 1, 12, 13, 14) touch the host. Each says which steps need the owner.
  Never run `agent-dgx help` or `agent-dgx ls`: an unknown word starts a real session.

---

### Task 1: Probe the design's two assumptions and the sandbox mount (live, gate)

The design's §9 makes this the first P3 task. **If the route or the image read fails, stop the
plan and ask the owner** before writing any code.

**Files:**

- Create: `docs/benchmarks/synthbench/p3-probes.md`
- Modify: `docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md`
  (the two **[A]** rows of "Measurements this design rests on" become **[V]**)

**Interfaces:**

- Consumes: nothing from the code. The host has `agent-dgx`, `sbx`, the empty corpus dataset
  and `uv`.
- Produces:

  - **Which address answers in the sandbox.** Ruling P3-R9's default list must include it. If
    only an unlisted address works, stop and ask.
  - **Whether hard links work on the corpus mount.** If not, `write_new` uses Task 2's `O_EXCL`
    fallback.
  - **Whether `os.replace` and `O_APPEND` work there.** Both are required.
  - **The uid and mode that the host sees on files the sandbox created.**

- [ ] **Step 1: Prepare the host side**

```bash
mkdir -p /synthbench/status /synthbench/tmp/p3-probe/stub
echo '{"stub": true}' > /synthbench/tmp/p3-probe/stub/system_stats
WORD="$(uv run python -c 'import secrets, string; print("".join(secrets.choice(string.ascii_uppercase) for _ in range(4)) + "-" + str(1000 + secrets.randbelow(9000)))')"
echo "$WORD" > /synthbench/tmp/p3-probe/word.txt
uv run python - "$WORD" <<'EOF'
import sys
from PIL import Image, ImageDraw, ImageFont
image = Image.new("RGB", (900, 300), "white")
ImageDraw.Draw(image).text((40, 90), sys.argv[1], fill="black", font=ImageFont.load_default(size=110))
image.save("/synthbench/status/probe-word.png")
EOF
```

Write `/synthbench/status/p3-probe.py`. The sandbox mounts `status/` read-only, so it can
run this file but not change it:

```python
"""P3 Task 1 probe, run inside the sandbox. Prints one JSON object."""

import errno
import fcntl
import json
import os
import tempfile
from pathlib import Path

import httpx


def _error(error: OSError) -> str:
    return f"FAILED {errno.errorcode.get(error.errno or 0, error.errno)}"


result: dict[str, object] = {"uid": os.getuid(), "gid": os.getgid()}
for url in ("http://127.0.0.1:8188", "http://host.docker.internal:8188"):
    try:
        result[url] = httpx.get(f"{url}/system_stats", timeout=5).text.strip()
    except httpx.HTTPError as error:
        result[url] = f"FAILED {type(error).__name__}: {error}"

probe = Path("/synthbench/corpus/.p3probe-sbx")
probe.mkdir(exist_ok=True)
fd, tmp = tempfile.mkstemp(dir=probe, prefix=".linked.json.", suffix=".tmp")
os.write(fd, b"{}\n")
os.fchmod(fd, 0o644)
os.close(fd)
try:
    os.link(tmp, probe / "linked.json")
    result["hardlink"] = "ok"
except OSError as error:
    result["hardlink"] = _error(error)
Path(tmp).unlink()

(probe / "replaced.json").write_text("{}\n")
fd, tmp = tempfile.mkstemp(dir=probe, prefix=".replaced.json.", suffix=".tmp")
os.write(fd, b'{"v": 2}\n')
os.close(fd)
try:
    os.replace(tmp, probe / "replaced.json")
    result["replace"] = "ok" if (probe / "replaced.json").read_text() == '{"v": 2}\n' else "WRONG"
except OSError as error:
    result["replace"] = _error(error)

fd = os.open(probe / "log.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
os.write(fd, b'{"r": 1}\n')
os.close(fd)
result["append"] = "ok"
with (probe / "log.jsonl").open("a") as handle:
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result["flock"] = "ok"
    except OSError as error:
        result["flock"] = _error(error)
print(json.dumps(result, indent=1))
```

Start the stub renderer. Use `run_in_background`, because it serves until you stop it:

```bash
python3 -m http.server 8188 --bind 127.0.0.1 --directory /synthbench/tmp/p3-probe/stub
```

Check it: `curl -sS 127.0.0.1:8188/system_stats` prints `{"stub": true}`.

- [ ] **Step 2 (owner): create a fresh probe sandbox and ask it to read the image**

The owner runs this in a terminal, from the repo root on this branch. The sandbox workspace is a
clone of the current checkout.

```bash
cd ~/github/nemotron-v3-home-security-intelligence
agent-dgx run p3probe --agent claude --endpoint dgx \
  --mount /synthbench/corpus:rw --mount /synthbench/status:ro
```

If the launch asks for `--profile`, add the host's governance profile. In the Claude session,
the owner types:

> Read /synthbench/status/probe-word.png and reply with only the text it shows.

The owner records the reply, then leaves the session with `/exit`.

**Pass:** the reply equals `/synthbench/tmp/p3-probe/word.txt`.

**Fail** (a refusal, a description, or a wrong word): the image did not reach Qwen's vision
input through LiteLLM (design R1). **Stop the plan and ask the owner.**

- [ ] **Step 3: Run the route and mount probe inside the sandbox**

```bash
sbx exec agent-p3probe bash -lc 'cd /agents/agent-p3probe/workspace && uv sync --frozen -q && uv run python /synthbench/status/p3-probe.py'
stat -c '%U:%G %a %n' /synthbench/corpus/.p3probe-sbx/*
```

Decide:

| Result                                                             | Then                                                              |
| ------------------------------------------------------------------ | ----------------------------------------------------------------- |
| an address in P3-R9's list prints `{"stub": true}`                 | pass (record which one)                                           |
| neither prints it                                                  | **stop and ask the owner** (design R2)                            |
| `hardlink` failed                                                  | continue: Task 2's `O_EXCL` fallback covers it (record the errno) |
| `replace` or `append` failed                                       | **stop and ask the owner**: the store needs both                  |
| `flock` failed                                                     | continue: P3-R15 takes no lock (record it)                        |
| the host cannot read a file the sandbox wrote (`stat` shows `600`) | continue: Task 2 sets mode `0644` (record the uid mapping)        |

- [ ] **Step 4: Clean up**

```bash
rm -rf /synthbench/corpus/.p3probe-sbx /synthbench/tmp/p3-probe
rm -f /synthbench/status/probe-word.png /synthbench/status/p3-probe.py
```

Stop the background `http.server`. The owner removes the sandbox:
`agent-dgx stop p3probe && agent-dgx session rm p3probe --force`. Then confirm the corpus is
empty and has no snapshots:

```bash
ls -A /synthbench/corpus
zfs list -t snapshot -r primary/export/synthbench
```

The first prints nothing, and the second prints `no datasets available`.

- [ ] **Step 5: Record the evidence**

`docs/benchmarks/synthbench/p3-probes.md`:

```markdown
# Synthbench P3 probes (2026-09-28)

Evidence for the agent-driven design's two **[A]** assumptions and for the corpus mount, from a
fresh `agent-dgx` sandbox (`p3probe`) with `/synthbench/corpus:rw` and
`/synthbench/status:ro`. Plan: `docs/superpowers/plans/2026-09-28-synthbench-p3-agent-driven-generation.md`, Task 1.

| Question                                            | Result                                           |
| --------------------------------------------------- | ------------------------------------------------ |
| Sandbox reaches the host's `:8188` (design R2)      | <which URL answered, and the other one's result> |
| Image read reaches Qwen vision through LiteLLM (R1) | <the word shown, and the agent's reply>          |
| `os.link` on the corpus mount                       | <ok / errno>                                     |
| `os.replace` on the corpus mount                    | <ok / errno>                                     |
| `O_APPEND` write on the corpus mount                | <ok / errno>                                     |
| `flock` on the corpus mount                         | <ok / errno>                                     |
| uid:gid and mode the host sees for sandbox files    | <`stat` output>                                  |

## ZFS (host, same day)

A replace shows as `-` and `+` on the same path in `zfs diff -FH`. An in-place write or an
append shows as `M`, `write_new`'s hard link as a single `+`, and directories as `M` with type
`/` (plan rulings P3-R5 and P3-R6).
```

Fill in every `<…>` cell from Steps 2-3. In the design's measurement table, change the two
**[A]** rows to **[V]**, add "(P3 probe, 2026-09-28, `docs/benchmarks/synthbench/p3-probes.md`)"
to each value, and name the address that answered.

- [ ] **Step 6: Commit**

```bash
F="docs/benchmarks/synthbench/p3-probes.md docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "docs(synthbench): P3 probes - sandbox route to :8188, image reads, corpus mount semantics

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Contract, store and taxonomy follow-ups from P2

These are the P2 handoff items that P3's commands rely on: validated updates, the replace path,
readable modes, the hard-link fallback, single-write index appends, the canonical taxonomy id,
the golden-hash sampler test, and a `sample` rerun that compares facts only.

**Files:**

- Modify: `synthbench/contract/common.py`, `synthbench/contract/spec.py`,
  `synthbench/contract/provenance.py`, `synthbench/contract/corpus.py`,
  `synthbench/contract/store.py`, `synthbench/taxonomy/model.py`, `synthbench/cli.py:234`
- Modify: `synthbench/contract/AGENTS.md`, parent spec §2.1 (migration note)
- Create: `backend/tests/unit/synthbench/fixtures/tiny_taxonomy.yaml`
- Test: `backend/tests/unit/synthbench/test_contract.py`,
  `backend/tests/unit/synthbench/test_contract_store.py`,
  `backend/tests/unit/synthbench/test_taxonomy.py`,
  `backend/tests/unit/synthbench/test_sampler.py`,
  `backend/tests/unit/synthbench/test_cli_sample.py`

**Interfaces:**

- Produces (`common.py`): `ContractModel.updated(**changes) -> Self`, a validated copy.
  `model_copy(update=…)` skips validators. Changes use field names, never an aliased field such
  as `cls`.
- Produces (`spec.py`):
  - `Spec.frozen -> bool` (property).
  - `Spec.facts() -> dict[str, Any]`: the JSON dump without `prompt` and `camera_suffix`.
  - `Spec.with_prompt(prompt, camera_suffix) -> Spec`: raises `ValueError` if the spec is
    already frozen.
- Produces (`provenance.py`):
  - `attempt_seed(event_id, k) -> int`; `render_name(k, seed) -> str`;
    `still_name(k, seed) -> str`.
  - `RenderFailure(time, error)`.
  - `Attempt` gains `render_failures`, `overlay_time`, and consistency rules: a still needs its
    render, `camera_params` and `overlay_time`; a triage needs a still.
  - `Provenance.schema_version == 2`.
  - `OutputFile` accepts normalized relative paths only.
- Produces (`corpus.py`):
  - `EventStatus` adds `"ready"` and `"rerolled"`.
  - `PromptRow(event_id, prompt)`.
  - `TriageRow(event_id, k, verdict, reason)`, with `.triage() -> Triage`.
- Produces (`store.py`):
  - `write_new_bytes(path, data)`: never replaces, falls back to `O_EXCL` when hard links are
    refused.
  - `replace_text(path, text)` and `replace_json(path, model)`: atomic, for `.json`, `.md` and
    `.html` only.
  - `sha256_file(path) -> str` (module function).
  - Every write stays inside `version_dir` (else `ValueError`), with files at mode `0644`.
  - `append_index` makes one `os.write` per call.
- Produces (`model.py`): `taxonomy_sha256(path)` hashes canonical JSON (P3-R2).

- [ ] **Step 1: Write the failing tests**

In `backend/tests/unit/synthbench/test_contract.py`:

1. Extend the imports:
   - `from synthbench.contract.provenance import RenderFailure, attempt_seed, render_name, still_name`
     (alongside the existing provenance names);
   - `from synthbench.contract.corpus import PromptRow, TriageRow`.
2. Replace `test_output_paths_stay_inside_the_event_directory` with the first test below.
3. Append the other tests below.

```python
@pytest.mark.parametrize(
    "path", ["/abs/a1.png", "../a1.png", "", ".", "./a1.png", "renders//a1.png", "renders/"]
)
def test_output_paths_stay_inside_the_event_directory(path: str) -> None:
    assert OutputFile(path="renders/a1-s7.png", sha256=SHA).path == "renders/a1-s7.png"
    with pytest.raises(ValidationError, match="relative to the event directory"):
        OutputFile(path=path, sha256=SHA)


def test_updated_revalidates() -> None:
    spec = _spec()
    assert spec.updated(scene_time="23:59").scene_time == "23:59"
    with pytest.raises(ValidationError, match="HH:MM"):
        spec.updated(scene_time="24:00")


def test_facts_leave_out_the_frozen_prompt() -> None:
    spec = _spec()
    frozen = spec.with_prompt("a person at the door", "the suffix")
    assert frozen.frozen
    assert not spec.frozen
    assert frozen.facts() == spec.facts()
    assert "prompt" not in spec.facts()
    assert "camera_suffix" not in spec.facts()
    with pytest.raises(ValueError, match="already has a frozen prompt"):
        frozen.with_prompt("another prompt", "the suffix")


def test_provenance_is_schema_version_2() -> None:
    failure = RenderFailure(time="2026-09-28T00:00:00+00:00", error="TimeoutError: slow")
    attempt = Attempt(k=1, seed=5, prompt_sha256=SHA, render_failures=(failure,))
    prov = Provenance(event_id="B-pilot-1-000", attempts=(attempt,))
    assert prov.schema_version == 2
    assert Provenance.model_validate_json(prov.model_dump_json()) == prov
    data = prov.model_dump(mode="json")
    data["schema_version"] = 1
    with pytest.raises(ValidationError):
        Provenance.model_validate(data)


def test_a_still_needs_its_render_params_and_overlay_time() -> None:
    render = OutputFile(path="renders/a1-s5.png", sha256=SHA)
    still = OutputFile(path="stills/a1-s5.jpg", sha256=SHA)
    done = Attempt(
        k=1,
        seed=5,
        prompt_sha256=SHA,
        render=render,
        still=still,
        camera_params="default-v1",
        overlay_time="2026-03-04 20:15:09",
    )
    assert done.still == still
    with pytest.raises(ValidationError, match="a still needs"):
        Attempt(k=1, seed=5, prompt_sha256=SHA, render=render, still=still)
    with pytest.raises(ValidationError, match="overlay_time"):
        done.updated(overlay_time="2026-03-04T20:15:09")
    with pytest.raises(ValidationError, match="triage needs a still"):
        Attempt(k=1, seed=5, prompt_sha256=SHA, triage=Triage(verdict="ok"))


def test_attempt_seeds_and_file_names_are_stable() -> None:
    first = attempt_seed("B-pilot-1-000", 1)
    assert first == attempt_seed("B-pilot-1-000", 1)
    assert first != attempt_seed("B-pilot-1-000", 2)
    assert 0 <= first < 2**32
    assert render_name(2, 77) == "renders/a2-s77.png"
    assert still_name(2, 77) == "stills/a2-s77.jpg"


def test_agent_rows_validate() -> None:
    row = PromptRow.model_validate_json('{"event_id": "B-pilot-1-000", "prompt": "a man"}')
    assert row.prompt == "a man"
    verdict = TriageRow(event_id="B-pilot-1-000", k=1, verdict="reroll", reason="blank")
    assert verdict.triage() == Triage(verdict="reroll", reason="blank")
    with pytest.raises(ValidationError, match="needs a reason"):
        TriageRow(event_id="B-pilot-1-000", k=1, verdict="reroll")
    with pytest.raises(ValidationError):
        TriageRow.model_validate(
            {"event_id": "B-pilot-1-000", "k": 1, "verdict": "ok", "note": "looks fine"}
        )
```

Append to `backend/tests/unit/synthbench/test_contract_store.py`. Also add `import errno`,
`import hashlib`, `import os` and `import stat` at the top, and extend the store import to
`from synthbench.contract.store import CorpusStore, sha256_file, to_json`:

```python
def test_written_files_are_world_readable(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path, "tierb-v0")
    store.write_new(store.manifest_file, _manifest())
    store.append_index([_row("B-pilot-1-000")])
    store.replace_text(store.spec_file("B-pilot-1-000"), "{}\n")
    for path in (store.manifest_file, store.index_file, store.spec_file("B-pilot-1-000")):
        assert stat.S_IMODE(path.stat().st_mode) == 0o644, path


def test_write_new_bytes_stores_exact_bytes_and_never_replaces(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path, "tierb-v0")
    path = store.event_dir("B-pilot-1-000") / "renders" / "a1-s5.png"
    store.write_new_bytes(path, b"\x89PNG first")
    with pytest.raises(FileExistsError):
        store.write_new_bytes(path, b"\x89PNG second")
    assert path.read_bytes() == b"\x89PNG first"
    assert sha256_file(path) == hashlib.sha256(b"\x89PNG first").hexdigest()
    assert [p.name for p in path.parent.iterdir()] == ["a1-s5.png"]


def test_write_new_falls_back_where_hard_links_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(self: Path, _target: Path) -> None:
        raise PermissionError(errno.EPERM, "Operation not permitted", str(self))

    monkeypatch.setattr(Path, "hardlink_to", refuse)
    store = CorpusStore(tmp_path, "tierb-v0")
    store.write_new(store.manifest_file, _manifest())
    assert store.read(store.manifest_file, CorpusManifest) == _manifest()
    with pytest.raises(FileExistsError):
        store.write_new(store.manifest_file, _manifest(created="2026-09-29T00:00:00+00:00"))
    assert [p.name for p in store.version_dir.iterdir()] == ["corpus.json"]


def test_other_link_failures_propagate_and_leave_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(self: Path, _target: Path) -> None:
        raise OSError(errno.EIO, "Input/output error", str(self))

    monkeypatch.setattr(Path, "hardlink_to", broken)
    store = CorpusStore(tmp_path, "tierb-v0")
    with pytest.raises(OSError, match="Input/output error"):
        store.write_new(store.manifest_file, _manifest())
    assert list(store.version_dir.iterdir()) == []


def test_nothing_is_written_outside_the_version(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "corpus", "tierb-v0")
    with pytest.raises(ValueError, match="outside corpus version"):
        store.write_new_bytes(tmp_path / "elsewhere.png", b"x")
    with pytest.raises(ValueError, match="outside corpus version"):
        store.replace_text(store.version_dir / ".." / "other-v0" / "x.json", "{}\n")


def test_replace_text_swaps_json_and_views_atomically(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path, "tierb-v0")
    path = store.spec_file("B-pilot-1-000")
    store.replace_text(path, '{"a": 1}\n')
    store.replace_text(path, '{"a": 2}\n')
    assert path.read_text(encoding="utf-8") == '{"a": 2}\n'
    assert [p.name for p in path.parent.iterdir()] == ["spec.json"]
    view = store.batch_dir("pilot-1") / "report.md"
    store.replace_text(view, "# report\n")
    assert view.read_text(encoding="utf-8") == "# report\n"
    with pytest.raises(ValueError, match="change in place"):
        store.replace_text(path.with_name("a1.png"), "x")


def test_an_index_append_is_one_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sizes: list[int] = []
    real_write = os.write

    def counting(fd: int, data: bytes) -> int:
        sizes.append(len(data))
        return real_write(fd, data)

    monkeypatch.setattr(os, "write", counting)
    store = CorpusStore(tmp_path, "tierb-v0")
    store.append_index([_row("B-pilot-1-000"), _row("B-pilot-1-001"), _row("B-pilot-1-002")])
    assert len(sizes) == 1
    assert len(store.latest_index()) == 3
```

In `backend/tests/unit/synthbench/test_taxonomy.py`:

- **Delete `test_the_digest_is_the_file_sha256`.** It pins the raw-bytes hash that ruling
  P3-R2 replaces, and the two tests below take its place. Drop the file's `import hashlib`
  too: only that test used it.
- Add `import re` and `from pathlib import Path` at the top if they are absent. The file
  already imports `DEFAULT_TAXONOMY` and `taxonomy_sha256`; keep those imports.
- Append:

```python
_VERSION_LINE = re.compile(r"^version: (\S+)$", re.MULTILINE)


def test_the_taxonomy_id_ignores_comments_and_layout(tmp_path: Path) -> None:
    text = DEFAULT_TAXONOMY.read_text(encoding="utf-8")
    edited = _VERSION_LINE.sub(r"version:   '\1'   # quoted, with a note", text, count=1)
    assert edited != text
    copy = tmp_path / "tier_b.yaml"
    copy.write_text("# an owner's review note\n" + edited, encoding="utf-8")
    assert taxonomy_sha256(copy) == taxonomy_sha256()


def test_the_taxonomy_id_changes_with_any_value(tmp_path: Path) -> None:
    text = DEFAULT_TAXONOMY.read_text(encoding="utf-8")
    copy = tmp_path / "tier_b.yaml"
    copy.write_text(_VERSION_LINE.sub("version: another-v0", text, count=1), encoding="utf-8")
    assert taxonomy_sha256(copy) != taxonomy_sha256()
```

Create `backend/tests/unit/synthbench/fixtures/tiny_taxonomy.yaml`:

```yaml
# A tiny taxonomy for the sampler's golden-hash test. Do not edit: the digest pinned in
# test_sampler.py depends on every value here.
version: tiny-v0

zones: [porch, yard, kitchen]

lighting:
  - { id: day, hours: [['08:00', '16:59']], weight: 3 }
  - { id: ir_night, hours: [['21:00', '04:59']], weight: 1 }
  - { id: porch_lit_night, hours: [['21:00', '04:59']], weight: 1, outdoor_only: true }

weather:
  - { id: clear, weight: 3 }
  - { id: rain, weight: 1 }

artifacts:
  - { id: lens_droplets, probability: 0.5, weather: [rain], outdoor_only: true }
  - { id: motion_blur, probability: 0.2 }

cameras:
  - { id: doorbell, zones: [porch] }
  - { id: eave, zones: [porch, yard] }
  - { id: corner, zones: [kitchen], indoor: true }

properties:
  - { id: house, zones: [porch, yard, kitchen] }
  - { id: cabin, zones: [porch, yard] }

colors: [black, red]
garments: [hoodie, coat]
clothed: [person]

terms:
  person: [person, man, woman]
  dog: [dog]
  package: [package, parcel]
  knife: [knife]

scenarios:
  - id: delivery
    group: benign
    label: benign
    risk_band: [0, 20]
    weight: 2
    zones: [porch]
    lighting: [day]
    subjects: [{ one_of: [person], role: courier }]
    props: [{ one_of: [package], held_by: 0 }]
  - id: dog_in_yard
    group: benign
    label: benign
    risk_band: [0, 10]
    zones: [yard]
    subjects: [{ one_of: [dog], role: pet }]
  - id: knife_in_kitchen
    group: threat
    label: incident
    risk_band: [70, 95]
    zones: [kitchen, porch]
    subjects: [{ one_of: [person], role: intruder }]
    props: [{ one_of: [knife], held_by: 0 }]
```

Append to `backend/tests/unit/synthbench/test_sampler.py`, adding `import json` and
`from pathlib import Path` at the top:

```python
TINY = load_taxonomy(Path(__file__).with_name("fixtures") / "tiny_taxonomy.yaml")
# Pinned 2026-09-28 (P3 plan, Task 2) from the P2 sampler. A different digest means the draw
# order, a draw or the quota method changed, so every seed now makes different specs: that
# needs an owner ruling and a new corpus version, never a new digest pasted in here.
# pragma: allowlist nextline secret
GOLDEN_FACTS_SHA256 = "146178f00404ab49db3ab9f47e43a94817e5b5cf854f9a76118aab439e23adb7"


def test_the_sampler_draws_are_pinned() -> None:
    specs = sample_specs(TINY, version="tiny-v0", batch="golden", n=40, seed=12345)
    blob = json.dumps([spec.facts() for spec in specs], sort_keys=True)
    assert hashlib.sha256(blob.encode()).hexdigest() == GOLDEN_FACTS_SHA256
```

Append to `backend/tests/unit/synthbench/test_cli_sample.py`:

```python
def test_a_rerun_accepts_specs_whose_prompt_is_frozen(tmp_path: Path) -> None:
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "3") == cli.EXIT_OK
    store = _store(tmp_path)
    path = store.spec_file("B-pilot-1-001")
    frozen = store.read(path, Spec).with_prompt("a person waits at the door", "the suffix")
    store.replace_json(path, frozen)
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "3") == cli.EXIT_OK
    assert store.read(path, Spec) == frozen
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_contract.py backend/tests/unit/synthbench/test_contract_store.py backend/tests/unit/synthbench/test_taxonomy.py backend/tests/unit/synthbench/test_sampler.py backend/tests/unit/synthbench/test_cli_sample.py -q -n0 -p no:randomly`

Expected: FAIL.

- `ImportError` for `RenderFailure`, `PromptRow` and `sha256_file` stops collection of two
  files.
- The taxonomy "ignores comments" test fails, because the raw-byte hash changes.
- `test_the_sampler_draws_are_pinned` fails with `AttributeError: 'Spec' object has no
attribute 'facts'`.

When this plan was written, applying every task and running the suite left exactly one
unplanned failure: P2's `test_the_digest_is_the_file_sha256`, which this step deletes.

- [ ] **Step 3: Implement**

`synthbench/contract/common.py`: add `Any` and `Self` to the `typing` import, and give
`ContractModel` this method:

```python
    def updated(self, **changes: Any) -> Self:
        """A validated copy with changes applied; model_copy(update=...) skips validators.

        Changes use field names, never an aliased field such as `cls`.
        """
        return self.model_validate({**self.model_dump(), **changes})
```

`synthbench/contract/spec.py`: add `Any` to the `typing` import, `PROMPT_FIELDS` below the
imports, and these members at the end of `Spec`:

```python
PROMPT_FIELDS = frozenset({"prompt", "camera_suffix"})
```

```python
    @property
    def frozen(self) -> bool:
        return self.prompt is not None

    def facts(self) -> dict[str, Any]:
        """Everything the sampler fixed: the spec without its frozen prompt (design G4)."""
        return self.model_dump(mode="json", exclude=set(PROMPT_FIELDS))

    def with_prompt(self, prompt: str, camera_suffix: str) -> Spec:
        """Freeze the agent's prompt and the fixed suffix in (design §3.1), validated."""
        if self.frozen:
            raise ValueError(
                f"{self.event_id} already has a frozen prompt; a new prompt is a new event"
            )
        return self.updated(prompt=prompt, camera_suffix=camera_suffix)
```

`synthbench/contract/provenance.py`: replace the file with:

```python
"""provenance.json: every attempt at an event (spec §2.1; agent-driven design §2 and §4).

Schema version 2 (P3): each attempt records its failed render jobs and the timestamp the camera
stage drew. No version-1 file was ever written.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import Field, model_validator

from synthbench.contract.common import ContractModel, Sha256

# Parent spec §4.2: at most 3 seeds per event, shared by the agent's triage and the verifier.
MAX_ATTEMPTS = 3

# Agent-driven design §4: the only reasons the agent may reroll an event.
TriageReason = Literal[
    "blank",
    "refusal_card",
    "wrong_scene",
    "no_person",
    "broken_anatomy",
    "not_security_camera",
    "text_overlay",
]

_OVERLAY_TIME = re.compile(
    r"\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]) ([01]\d|2[0-3]):[0-5]\d:[0-5]\d"
)


def attempt_seed(event_id: str, k: int) -> int:
    """Attempt k's seed, from the event id and k, so a rerun renders the same image (§3)."""
    return int(hashlib.sha256(f"{event_id}:{k}".encode()).hexdigest()[:8], 16)


def render_name(k: int, seed: int) -> str:
    """The raw 1280x720 render of attempt k, relative to the event directory (design §2)."""
    return f"renders/a{k}-s{seed}.png"


def still_name(k: int, seed: int) -> str:
    """The 1920x1080 camera still of attempt k, relative to the event directory (design §2)."""
    return f"stills/a{k}-s{seed}.jpg"


class OutputFile(ContractModel):
    """A file an attempt produced, relative to the event directory, with its sha256."""

    path: str
    sha256: Sha256

    @model_validator(mode="after")
    def _relative(self) -> Self:
        pure = PurePosixPath(self.path)
        if not pure.parts or pure.is_absolute() or str(pure) != self.path or ".." in pure.parts:
            raise ValueError(
                f"path must be a normalized path relative to the event directory: {self.path!r}"
            )
        return self


class Triage(ContractModel):
    verdict: Literal["ok", "reroll"]
    reason: TriageReason | None = None

    @model_validator(mode="after")
    def _reason_matches_verdict(self) -> Self:
        if (self.verdict == "reroll") != (self.reason is not None):
            raise ValueError("a reroll needs a reason from the list; an ok verdict has none")
        return self


class RenderFailure(ContractModel):
    """A render job that failed; `render` retries the same seed on its next run."""

    time: str
    error: str = Field(min_length=1, max_length=500)


class Attempt(ContractModel):
    k: int = Field(ge=1)
    seed: int = Field(ge=0)
    prompt_sha256: Sha256
    models: dict[str, Sha256] = Field(default_factory=dict)
    render: OutputFile | None = None
    render_seconds: float | None = Field(default=None, ge=0.0)
    render_failures: tuple[RenderFailure, ...] = ()
    still: OutputFile | None = None
    camera_params: str | None = None
    overlay_time: str | None = None
    triage: Triage | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.overlay_time is not None and not _OVERLAY_TIME.fullmatch(self.overlay_time):
            raise ValueError(f"overlay_time must be YYYY-MM-DD HH:MM:SS, got {self.overlay_time!r}")
        if self.still is not None and (
            self.render is None or self.camera_params is None or self.overlay_time is None
        ):
            raise ValueError("a still needs its render, camera_params and overlay_time")
        if self.triage is not None and self.still is None:
            raise ValueError("triage needs a still: the agent triages what it looked at")
        return self


class Provenance(ContractModel):
    schema_version: Literal[2] = 2
    event_id: str
    attempts: tuple[Attempt, ...] = ()

    @model_validator(mode="after")
    def _attempts(self) -> Self:
        ks = [attempt.k for attempt in self.attempts]
        if ks != list(range(1, len(ks) + 1)):
            raise ValueError(f"attempts must be numbered 1..n in order, got {ks}")
        if len(ks) > MAX_ATTEMPTS:
            raise ValueError(
                f"at most {MAX_ATTEMPTS} attempts per event (spec §4.2), got {len(ks)}"
            )
        return self
```

`synthbench/contract/corpus.py`: import `TriageReason` and `Triage` from
`synthbench.contract.provenance`, widen `EventStatus`, and append the two agent-row models:

```python
EventStatus = Literal["sampled", "prompted", "rendered", "ready", "rerolled", "failed"]
```

```python
class PromptRow(ContractModel):
    """One prompts.jsonl row, written by the agent (design §3 step 2)."""

    event_id: str
    prompt: str


class TriageRow(ContractModel):
    """One triage.jsonl row: the agent's verdict on attempt k's still (design §3 step 6)."""

    event_id: str
    k: int = Field(ge=1)
    verdict: Literal["ok", "reroll"]
    reason: TriageReason | None = None

    @model_validator(mode="after")
    def _reason_matches_verdict(self) -> Self:
        if (self.verdict == "reroll") != (self.reason is not None):
            raise ValueError("a reroll needs a reason from the list; an ok verdict has none")
        return self

    def triage(self) -> Triage:
        return Triage(verdict=self.verdict, reason=self.reason)
```

`synthbench/contract/store.py`: replace the file with:

```python
"""Where a corpus version's files live, and how they are written (agent-driven design §2).

The corpus is append-only. Images and clips are created once and never replaced. JSON files
and the batch views (report.md, sheet.html) change only by atomic replace. index.jsonl only
grows. Every file is mode 0644 so the owner can read what the sandbox agent wrote.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TypeVar

from synthbench.contract.common import SLUG, ContractModel
from synthbench.contract.corpus import IndexRow

M = TypeVar("M", bound=ContractModel)

DEFAULT_SYNTHBENCH_ROOT = Path("/synthbench")
# A tier letter, then no path separators or dot segments: the id never leaves version_dir.
_EVENT_ID = re.compile(r"[AB]-[A-Za-z0-9][A-Za-z0-9_-]*")
_FILE_MODE = 0o644
_REPLACEABLE = frozenset({".json", ".md", ".html"})
# A filesystem that refuses hard links (the sandbox's virtiofs mount may: P3 Task 1) gets an
# O_EXCL create instead. It still never replaces a file.
_NO_HARDLINK = frozenset({errno.EPERM, errno.EOPNOTSUPP, errno.ENOTSUP, errno.EMLINK})


def to_json(model: ContractModel) -> str:
    """Stable JSON: alias keys, no nulls, sorted keys, one-space indent, trailing newline."""
    payload = model.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, indent=1, sort_keys=True) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_tmp(directory: Path, name: str, data: bytes) -> Path:
    """A fsynced 0644 temporary file beside `name`; store temps are named `.<name>.*.tmp`."""
    fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=f".{name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), _FILE_MODE)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return tmp


def _create_exclusive(path: Path, data: bytes) -> None:
    """The fallback where hard links are refused: O_EXCL never replaces; a failed write is
    removed rather than left half-written."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _FILE_MODE)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), _FILE_MODE)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


class CorpusStore:
    """Paths and writes for one corpus version, under <root>/<version>/."""

    def __init__(self, root: Path, version: str) -> None:
        if not SLUG.fullmatch(version):
            raise ValueError(f"corpus version {version!r} must match {SLUG.pattern}")
        self.root = root
        self.version = version

    @classmethod
    def from_env(cls, version: str, env: Mapping[str, str] | None = None) -> CorpusStore:
        """The corpus lives at $SYNTHBENCH_ROOT/corpus (a ZFS dataset on maui, design §6)."""
        environment = os.environ if env is None else env
        root = Path(environment.get("SYNTHBENCH_ROOT", str(DEFAULT_SYNTHBENCH_ROOT)))
        return cls(root / "corpus", version)

    @property
    def version_dir(self) -> Path:
        return self.root / self.version

    @property
    def manifest_file(self) -> Path:
        return self.version_dir / "corpus.json"

    @property
    def index_file(self) -> Path:
        return self.version_dir / "index.jsonl"

    def event_dir(self, event_id: str) -> Path:
        if not _EVENT_ID.fullmatch(event_id):
            raise ValueError(
                f"event_id must be A- or B- followed by letters, digits, '_' or '-': {event_id!r}"
            )
        return self.version_dir / "events" / event_id[0] / event_id

    def spec_file(self, event_id: str) -> Path:
        return self.event_dir(event_id) / "spec.json"

    def provenance_file(self, event_id: str) -> Path:
        return self.event_dir(event_id) / "provenance.json"

    def batch_dir(self, name: str) -> Path:
        if not SLUG.fullmatch(name):
            raise ValueError(f"batch name {name!r} must match {SLUG.pattern}")
        return self.version_dir / "batches" / name

    def batch_file(self, name: str) -> Path:
        return self.batch_dir(name) / "batch.json"

    def _check_inside(self, path: Path) -> None:
        if not path.resolve().is_relative_to(self.version_dir.resolve()):
            raise ValueError(f"{path} is outside corpus version {self.version_dir}")

    def write_new(self, path: Path, model: ContractModel) -> None:
        """Create path holding model's JSON. Raises FileExistsError if it exists."""
        self.write_new_bytes(path, to_json(model).encode())

    def write_new_bytes(self, path: Path, data: bytes) -> None:
        """Create path holding data, atomically where hard links work; never replaces a file.

        Raises FileExistsError if path exists.
        """
        self._check_inside(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = _write_tmp(path.parent, path.name, data)
        try:
            path.hardlink_to(tmp)  # a new link never replaces: FileExistsError if path exists
        except OSError as error:
            if error.errno not in _NO_HARDLINK:
                raise
            _create_exclusive(path, data)
        finally:
            tmp.unlink(missing_ok=True)

    def replace_text(self, path: Path, text: str) -> None:
        """Write a JSON file or a batch view atomically, replacing any earlier version.

        zfs diff shows the replace as `-` and `+` on the same path; the snapshot prune rule
        counts that pair as a modification (plan rulings P3-R5, P3-R6).
        """
        self._check_inside(path)
        if path.suffix not in _REPLACEABLE:
            raise ValueError(
                f"only {', '.join(sorted(_REPLACEABLE))} files change in place, not {path.name}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = _write_tmp(path.parent, path.name, text.encode())
        try:
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)

    def replace_json(self, path: Path, model: ContractModel) -> None:
        self.replace_text(path, to_json(model))

    @staticmethod
    def read(path: Path, model: type[M]) -> M:
        return model.model_validate_json(path.read_text(encoding="utf-8"))

    def append_index(self, rows: Iterable[IndexRow]) -> None:
        """Append rows in one O_APPEND write, so no other append splits a row (ruling P3-R15)."""
        data = "".join(
            json.dumps(row.model_dump(mode="json", exclude_none=True), sort_keys=True) + "\n"
            for row in rows
        ).encode()
        if not data:
            return
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        created = not self.index_file.exists()
        fd = os.open(self.index_file, os.O_WRONLY | os.O_APPEND | os.O_CREAT, _FILE_MODE)
        try:
            if created:
                os.fchmod(fd, _FILE_MODE)
            written = os.write(fd, data)
            if written != len(data):
                raise OSError(
                    errno.EIO, f"short append to {self.index_file}: {written} of {len(data)} bytes"
                )
            os.fsync(fd)
        finally:
            os.close(fd)

    def latest_index(self) -> dict[str, IndexRow]:
        """The latest row per event. The index is append-only, so later rows win."""
        if not self.index_file.exists():
            return {}
        latest: dict[str, IndexRow] = {}
        for line in self.index_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = IndexRow.model_validate_json(line)
                latest[row.event_id] = row
        return latest
```

`synthbench/taxonomy/model.py`: add `import json`, and replace `taxonomy_sha256`:

```python
def taxonomy_sha256(path: Path = DEFAULT_TAXONOMY) -> str:
    """sha256 of the validated taxonomy as canonical JSON (owner ruling P3-R2, 2026-09-28).

    Comments, key order, quoting and layout in the YAML do not change it; any value does,
    including a default the model fills in.
    """
    canonical = json.dumps(
        load_taxonomy(path).model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
```

`synthbench/cli.py:234`: compare facts, not whole specs:

```python
        elif _read(store, path, Spec).facts() != spec.facts():
```

`synthbench/contract/AGENTS.md`:

- In the Files table, change the `provenance.py` row to: "`Provenance` (schema 2), `Attempt`
  (render failures, overlay time), `Triage`, `attempt_seed`, `render_name`/`still_name`,
  `MAX_ATTEMPTS = 3`".
- Change the `corpus.py` row to add "`PromptRow`, `TriageRow` (the agent's rows)".
- Replace the first Rules bullet with:

```markdown
- The corpus is append-only (agent-driven design §2): no command deletes, moves or overwrites
  an image or a clip. Files are created only through `CorpusStore.write_new` /
  `write_new_bytes`, which raise `FileExistsError` rather than replace; JSON files and the
  batch views change only through `replace_text` / `replace_json` (atomic); `index.jsonl`
  grows only through `append_index`. Every write stays inside the version directory.
- `ContractModel.updated(...)` is the only way to change a model: `model_copy(update=...)`
  skips the validators.
```

Parent spec: at the end of §2.1 (after "All three are pydantic models … `schema_version`."),
add:

```markdown
**Rev 3 (P3):** `provenance.json` is schema version 2. Each attempt adds `render_failures` and
`overlay_time`. No version-1 file was ever written (the corpus was empty on 2026-09-28), so
nothing migrates.
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/ -q -n0 -p no:randomly`

Expected: PASS, the P2 suite included. Then run:

```bash
uv run mypy synthbench/
uv run ruff check synthbench/ backend/tests/unit/synthbench/
uv run ruff format --check synthbench/ backend/tests/unit/synthbench/
```

All three are clean.

- [ ] **Step 5: Commit**

```bash
F="synthbench/contract/common.py synthbench/contract/spec.py synthbench/contract/provenance.py synthbench/contract/corpus.py synthbench/contract/store.py synthbench/taxonomy/model.py synthbench/cli.py synthbench/contract/AGENTS.md docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md backend/tests/unit/synthbench/fixtures/tiny_taxonomy.yaml backend/tests/unit/synthbench/test_contract.py backend/tests/unit/synthbench/test_contract_store.py backend/tests/unit/synthbench/test_taxonomy.py backend/tests/unit/synthbench/test_sampler.py backend/tests/unit/synthbench/test_cli_sample.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "feat(synthbench): replace path, provenance v2, canonical taxonomy id, pinned sampler draws

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Command modules and one dispatch point

`cli.py` has grown one command, and P3 adds six. Each command moves into its own module under
`synthbench/commands/`. `cli.py` only builds the parser and maps the two stop kinds to exit
codes, as the P2 handoff asked (dispatch via `set_defaults`, with `_CorpusError` and taxonomy
failures handled in `main()`).

**Files:**

- Create: `synthbench/commands/__init__.py`, `synthbench/commands/common.py`,
  `synthbench/commands/sample.py`
- Modify: `synthbench/cli.py` (rewritten)
- Test: `backend/tests/unit/synthbench/test_cli_main.py`; the existing
  `test_cli_sample.py` must pass unchanged

**Interfaces:**

- Consumes: Task 2's store and models.
- Produces (`commands/common.py`):
  - Exit codes and messages: `EXIT_OK`, `EXIT_ERROR`, `EXIT_ASK`, `ASK_OWNER`,
    `TAXONOMY_CHANGED`.
  - `Parser` (usage errors exit 1).
  - `RequestError` (exit 1), `AskOwner` (exit 2), `CorpusError(verb, path, error)` (an
    `AskOwner`).
  - `now_iso() -> str`, `fail(code, message) -> int`, `batch_name(text) -> str` (an argparse
    type), `taxonomy() -> Taxonomy`.
  - `open_batch(tax, env, batch) -> tuple[CorpusStore, BatchRecord]`,
    `check_manifest(store) -> None`.
  - Corpus I/O wrappers, each turning `OSError` or validation failures into `CorpusError`:
    `read`, `read_index`, `write_new`, `write_new_bytes`, `replace_json`, `replace_text`,
    `append_index`, `read_bytes`.
- Produces (each command module): `add_parser(commands)` and
  `run(args, env) -> int`. `add_parser` registers the subcommand and
  `set_defaults(run=run)`.
- Produces (`cli.py`): `EXIT_OK`, `EXIT_ERROR`, `EXIT_ASK` (re-exported), `build_parser()`,
  `main(argv=None, env=None) -> int`, and `COMMANDS` (the registered modules, in help order).
  Later tasks add their module to `COMMANDS`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_cli_main.py`:

```python
"""cli.main: dispatch, and the mapping of the two stop kinds to exit codes (design §3)."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest
import yaml
from synthbench import cli
from synthbench.commands import common, sample
from synthbench.taxonomy.model import Taxonomy

ARGV = ["sample", "--batch", "pilot-1", "--n", "1"]


def _raising(error: Exception) -> Callable[[argparse.Namespace, Mapping[str, str]], int]:
    def run(_args: argparse.Namespace, _env: Mapping[str, str]) -> int:
        raise error

    return run


@pytest.mark.parametrize(
    ("error", "code", "text"),
    [
        (common.RequestError("fix the request"), cli.EXIT_ERROR, "synthbench: fix the request"),
        (
            common.AskOwner("the corpus is odd."),
            cli.EXIT_ASK,
            "the corpus is odd. Stop and ask the owner.",
        ),
    ],
)
def test_stop_kinds_map_to_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    code: int,
    text: str,
) -> None:
    monkeypatch.setattr(sample, "run", _raising(error))
    assert cli.main(ARGV, env={"SYNTHBENCH_ROOT": str(tmp_path)}) == code
    assert text in capsys.readouterr().err


def test_a_taxonomy_that_does_not_load_stops_every_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken() -> Taxonomy:
        raise yaml.YAMLError("mapping values are not allowed here")

    monkeypatch.setattr(common, "load_taxonomy", broken)
    assert cli.main(ARGV, env={"SYNTHBENCH_ROOT": str(tmp_path)}) == cli.EXIT_ASK
    err = capsys.readouterr().err
    assert "the committed taxonomy does not load (YAMLError" in err
    assert "Stop and ask the owner." in err


def test_a_bad_batch_name_is_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as stop:
        cli.main(
            ["sample", "--batch", "Pilot 1", "--n", "1"], env={"SYNTHBENCH_ROOT": str(tmp_path)}
        )
    assert stop.value.code == cli.EXIT_ERROR


def test_every_registered_command_dispatches_to_its_module() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(ARGV)
    assert args.run is sample.run
    assert cli.COMMANDS[0] is sample
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_cli_main.py -q -n0 -p no:randomly`

Expected: FAIL with `ModuleNotFoundError: No module named 'synthbench.commands'`.

- [ ] **Step 3: Implement**

`synthbench/commands/__init__.py`:

```python
"""One module per `python -m synthbench` command (agent-driven design §3)."""
```

`synthbench/commands/common.py`:

```python
"""What every command shares: exit codes, the two stop kinds, and corpus I/O (design §3).

A command returns EXIT_OK, raises RequestError (exit 1: the request is wrong, fix it and run
again) or raises AskOwner (exit 2: the corpus, taxonomy or host is not in the state the command
expects, so the agent stops and asks the owner). cli.main maps the exceptions to exit codes.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, TypeVar

import yaml
from pydantic import ValidationError

from synthbench.contract.common import SLUG, ContractModel
from synthbench.contract.corpus import BatchRecord, CorpusManifest, IndexRow
from synthbench.contract.store import CorpusStore
from synthbench.taxonomy.model import Taxonomy, load_taxonomy, taxonomy_sha256

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ASK = 2
ASK_OWNER = "Stop and ask the owner."
TAXONOMY_CHANGED = (
    "the taxonomy changed since corpus version {version} was created, so new batches would not "
    "be comparable. A changed taxonomy needs a new corpus version, which the owner sets by "
    "editing `version:` in synthbench/taxonomy/tier_b_v0.yaml."
)

M = TypeVar("M", bound=ContractModel)


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on a usage error, but 2 means "ask the owner" here, so exit 1."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"{self.prog}: error: {message}\n")


class RequestError(Exception):
    """The request is wrong: fix it and run the command again (exit 1)."""


class AskOwner(Exception):
    """The corpus, taxonomy or host is not in the state the command expects (exit 2).

    The message is one or more sentences; cli.main appends "Stop and ask the owner."
    """


class CorpusError(AskOwner):
    """A corpus file could not be read, parsed or written."""

    def __init__(self, verb: str, path: Path, error: Exception) -> None:
        lines = str(error).splitlines()
        detail = f"{type(error).__name__}: {lines[0]}" if lines else type(error).__name__
        super().__init__(f"cannot {verb} {path} ({detail}).")


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def fail(code: int, message: str) -> int:
    sys.stderr.write(f"synthbench: {message}\n")
    return code


def batch_name(text: str) -> str:
    """argparse type for --batch: a slug, so no batch path can leave the corpus."""
    if not SLUG.fullmatch(text):
        raise argparse.ArgumentTypeError(f"batch name must match {SLUG.pattern}: {text!r}")
    return text


def taxonomy() -> Taxonomy:
    """The committed taxonomy; one that does not load is the owner's to fix (exit 2)."""
    try:
        return load_taxonomy()
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValidationError) as error:
        first = (str(error).splitlines() or [""])[0]
        raise AskOwner(
            f"the committed taxonomy does not load ({type(error).__name__}: {first})."
        ) from error


def read(store: CorpusStore, path: Path, model: type[M]) -> M:
    try:
        return store.read(path, model)
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise CorpusError("read", path, error) from error


def read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise CorpusError("read", path, error) from error


def read_index(store: CorpusStore) -> dict[str, IndexRow]:
    try:
        return store.latest_index()
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise CorpusError("read", store.index_file, error) from error


def write_new(store: CorpusStore, path: Path, model: ContractModel) -> None:
    try:
        store.write_new(path, model)
    except OSError as error:  # includes FileExistsError when two first runs race
        raise CorpusError("write", path, error) from error


def write_new_bytes(store: CorpusStore, path: Path, data: bytes) -> None:
    try:
        store.write_new_bytes(path, data)
    except OSError as error:
        raise CorpusError("write", path, error) from error


def replace_json(store: CorpusStore, path: Path, model: ContractModel) -> None:
    try:
        store.replace_json(path, model)
    except OSError as error:
        raise CorpusError("write", path, error) from error


def replace_text(store: CorpusStore, path: Path, text: str) -> None:
    try:
        store.replace_text(path, text)
    except OSError as error:
        raise CorpusError("write", path, error) from error


def append_index(store: CorpusStore, rows: Iterable[IndexRow]) -> None:
    try:
        store.append_index(rows)
    except OSError as error:
        raise CorpusError("write", store.index_file, error) from error


def check_manifest(store: CorpusStore) -> None:
    """Exit 2 if corpus.json records a different taxonomy than the committed one."""
    if read(store, store.manifest_file, CorpusManifest).taxonomy_sha256 != taxonomy_sha256():
        raise AskOwner(TAXONOMY_CHANGED.format(version=store.version))


def open_batch(
    tax: Taxonomy, env: Mapping[str, str], batch: str
) -> tuple[CorpusStore, BatchRecord]:
    """The store and record of a batch that `sample` created (exit 1 if there is none)."""
    store = CorpusStore.from_env(tax.version, env)
    if not store.batch_file(batch).exists():
        raise RequestError(f"no batch {batch} in corpus version {tax.version}; run sample first")
    check_manifest(store)
    return store, read(store, store.batch_file(batch), BatchRecord)
```

`synthbench/commands/sample.py`:

```python
"""`sample --batch <b> --n <n>`: fact-only Tier B specs into a new batch (design §3 step 1)."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Mapping

from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    Parser,
    RequestError,
    append_index,
    batch_name,
    check_manifest,
    now_iso,
    read,
    read_index,
    taxonomy,
    write_new,
)
from synthbench.contract.corpus import TIER_B_RENDER_SIZE, BatchRecord, CorpusManifest, IndexRow
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.taxonomy.model import Taxonomy, taxonomy_sha256
from synthbench.taxonomy.sampler import MAX_BATCH, default_seed, sample_specs


def _batch_size(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"n must be an integer 1..{MAX_BATCH}: {text!r}") from None
    if not 1 <= value <= MAX_BATCH:
        raise argparse.ArgumentTypeError(f"n must be 1..{MAX_BATCH}, got {value}")
    return value


def _seed(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"seed must be an integer >= 0: {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"seed must be an integer >= 0, got {value}")
    return value


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "sample",
        help="sample Tier B specs (facts only, no prompt) into a new batch",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--batch",
        type=batch_name,
        required=True,
        help="new batch name: lowercase letters, digits and hyphens",
    )
    parser.add_argument(
        "--n", type=_batch_size, required=True, help=f"number of events, 1..{MAX_BATCH}"
    )
    parser.add_argument(
        "--seed",
        type=_seed,
        default=None,
        help="sampler seed (default: derived from the batch name)",
    )
    parser.add_argument(
        "--only", default="", help="comma-separated scenario ids to sample from (default: all)"
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    only = tuple(sorted({s for s in args.only.split(",") if s}))
    if unknown := sorted(set(only) - {s.id for s in tax.scenarios}):
        valid = ", ".join(s.id for s in tax.scenarios)
        raise RequestError(f"unknown scenario(s): {', '.join(unknown)}; valid: {valid}")
    seed: int = args.seed if args.seed is not None else default_seed(args.batch)
    store = CorpusStore.from_env(tax.version, env)
    return _sample(tax, store, batch=args.batch, n=args.n, seed=seed, only=only)


def _sample(
    tax: Taxonomy, store: CorpusStore, *, batch: str, n: int, seed: int, only: tuple[str, ...]
) -> int:
    version = store.version
    if store.manifest_file.exists():
        check_manifest(store)
    else:
        write_new(
            store,
            store.manifest_file,
            CorpusManifest(
                version=version,
                taxonomy_sha256=taxonomy_sha256(),
                render_size=TIER_B_RENDER_SIZE,
                created=now_iso(),
            ),
        )

    batch_file = store.batch_file(batch)
    record = read(store, batch_file, BatchRecord) if batch_file.exists() else None
    if record is not None and (record.seed, record.n, record.only) != (seed, n, only):
        raise RequestError(
            f"batch {batch} already exists with seed={record.seed}, n={record.n}, "
            f"only={','.join(record.only) or 'all'}; choose a new batch name"
        )
    index = read_index(store)
    if record is not None:
        prior = record.prior_counts
    else:
        prior = dict(Counter(row.scenario for row in index.values()))
    specs = sample_specs(
        tax, version=version, batch=batch, n=n, seed=seed, prior=prior, only=only or None
    )
    if record is None:
        write_new(
            store,
            batch_file,
            BatchRecord(
                name=batch,
                version=version,
                seed=seed,
                n=n,
                only=only,
                prior_counts=prior,
                event_ids=tuple(s.event_id for s in specs),
                created=now_iso(),
            ),
        )

    written = 0
    for spec in specs:
        path = store.spec_file(spec.event_id)
        if not path.exists():
            write_new(store, path, spec)
            written += 1
        elif read(store, path, Spec).facts() != spec.facts():
            raise AskOwner(
                f"{path} is not what the sampler produces for batch {batch}: the corpus was "
                "changed by hand."
            )
    append_index(
        store,
        [
            IndexRow(
                event_id=s.event_id,
                batch=batch,
                scenario=s.cell.scenario,
                label=s.label,
                status="sampled",
                time=now_iso(),
            )
            for s in specs
            if s.event_id not in index
        ],
    )
    counts = ", ".join(
        f"{k} {v}" for k, v in sorted(Counter(s.cell.scenario for s in specs).items())
    )
    sys.stdout.write(
        f"batch {batch} in corpus version {version}: {len(specs)} events ({written} written now)\n"
        f"  scenarios: {counts}\n"
        f"  specs: {store.event_dir(specs[0].event_id).parent}/"
        f"{specs[0].event_id} .. {specs[-1].event_id}\n"
    )
    return EXIT_OK
```

`synthbench/cli.py`: replace the file with:

```python
"""`python -m synthbench <command>`: the synthbench command line (agent-driven design §3).

Every command exits 0 when done, 1 on an error (fix the request and retry), and 2 when the
agent must stop and ask the owner. Each command lives in synthbench/commands/.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from types import ModuleType

from synthbench.commands import sample
from synthbench.commands.common import (
    ASK_OWNER,
    EXIT_ASK,
    EXIT_ERROR,
    EXIT_OK,
    AskOwner,
    Parser,
    RequestError,
    fail,
)

__all__ = ["COMMANDS", "EXIT_ASK", "EXIT_ERROR", "EXIT_OK", "build_parser", "main"]

# In help order. Each module has add_parser(commands) and run(args, env).
COMMANDS: tuple[ModuleType, ...] = (sample,)


def build_parser() -> Parser:
    parser = Parser(
        prog="python -m synthbench",
        description=(
            "Synthetic benchmark generation. Exit codes: 0 done, 1 error (fix the request), "
            "2 stop and ask the owner."
        ),
        allow_abbrev=False,
    )
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    for module in COMMANDS:
        module.add_parser(commands)
    return parser


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    environment: Mapping[str, str] = os.environ if env is None else env
    try:
        code: int = args.run(args, environment)
    except RequestError as error:
        return fail(EXIT_ERROR, str(error))
    except AskOwner as error:
        return fail(EXIT_ASK, f"{error} {ASK_OWNER}")
    return code
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/ -q -n0 -p no:randomly`

Expected: PASS, including every `test_cli_sample.py` test, unchanged. Then run
`uv run mypy synthbench/` and `uv run ruff check synthbench/ backend/tests/unit/synthbench/`;
both are clean.

- [ ] **Step 5: Commit**

```bash
F="synthbench/commands/__init__.py synthbench/commands/common.py synthbench/commands/sample.py synthbench/cli.py backend/tests/unit/synthbench/test_cli_main.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "refactor(synthbench): one module per command; main maps RequestError to 1 and AskOwner to 2

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The prompt rules and `check`

**Files:**

- Create: `synthbench/prompt/__init__.py`, `synthbench/prompt/rules.py`,
  `synthbench/prompt/blocklist.yaml`, `synthbench/commands/check.py`
- Modify: `synthbench/cli.py` (add `check` to `COMMANDS`)
- Create: `backend/tests/unit/synthbench/helpers.py`
- Test: `backend/tests/unit/synthbench/test_prompt_rules.py`,
  `backend/tests/unit/synthbench/test_cli_check.py`

**Interfaces:**

- Consumes: Task 2 (`Spec.facts`, `Spec.with_prompt`, `PromptRow`, `attempt_seed`,
  `render_name`, `still_name`, `sha256_file`); Task 3 (`commands.common`).
- Produces (`prompt/rules.py`):
  - Constants: `CAMERA_SUFFIX: str`, `MAX_PROMPT_CHARS = 1200`, `RULE_OF_CATEGORY`.
  - Matching: `words(text) -> list[str]`, `mentions(text, terms) -> bool` (rule 1),
    `contains_phrase(text, phrase) -> bool` (rules 2 and 4), `blocklist() -> dict[str,
tuple[str, ...]]`.
  - What FLUX.2 receives: `render_text(spec) -> str` (`f"{prompt} {camera_suffix}"`; raises
    `ValueError` if the spec is unfrozen) and `prompt_sha256(spec) -> str`.
  - `problems(spec, prompt, tax) -> list[str]`: each problem starts with `rule N:`.
- Produces (`commands/check.py`): `add_parser`, `run`. Behaviour:
  1. Re-sample the batch from `batch.json` and compare each `spec.json`'s facts. A spec that
     was never written exits 1, with the exact `sample` command that finishes the batch. A
     spec whose facts differ exits 2.
  2. Read `prompts.jsonl`. A bad line, an unknown event or a duplicate exits 1.
  3. Check each frozen spec: its prompt still passes the rules, its `camera_suffix` is
     `CAMERA_SUFFIX`, and its row (if any) equals the frozen prompt.
  4. Check each unfrozen spec: its row exists and passes the rules.
  5. Verify every recorded output against its sha256, and allow no unexpected file under
     `renders/` or `stills/`. The store's `.*.tmp` files are ignored. A failure here exits 2.
  6. If any problem is the agent's, exit 1 and freeze nothing.
  7. Otherwise freeze every pending prompt, write `spec.json` first, then create any missing
     `provenance.json` (attempt 1: `attempt_seed`, `prompt_sha256`), and index `prompted`.
- Produces (`helpers.py`, tests only): `TAX`, `VERSION`, `env(root)`, `store(root)`,
  `run(root, *argv)`, `sample(root, batch, n)`, `good_prompt(spec)`,
  `write_prompts(root, batch, prompts)`, `frozen_batch(root, batch, n)`,
  `record_output(root, spec, *, render=None, still=None)`, `rendered_batch(root, batch, n)`,
  `stilled_batch(root, batch, n)`, `png(width, height, color)`.

- [ ] **Step 1: Write the test helpers**

`backend/tests/unit/synthbench/helpers.py`:

```python
"""Builders shared by the synthbench command tests: batches, prompts, outputs and images."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

from PIL import Image
from synthbench import cli
from synthbench.contract.corpus import BatchRecord
from synthbench.contract.provenance import OutputFile, Provenance, render_name, still_name
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.taxonomy.model import load_taxonomy

TAX = load_taxonomy()  # at import: collection pays for the load, not a timed test
VERSION = TAX.version


def env(root: Path) -> dict[str, str]:
    return {"SYNTHBENCH_ROOT": str(root)}


def store(root: Path) -> CorpusStore:
    return CorpusStore(root / "corpus", VERSION)


def run(root: Path, *argv: str) -> int:
    return cli.main(list(argv), env=env(root))


def sample(root: Path, batch: str = "pilot-1", n: int = 4) -> list[Spec]:
    assert run(root, "sample", "--batch", batch, "--n", str(n)) == cli.EXIT_OK
    s = store(root)
    record = s.read(s.batch_file(batch), BatchRecord)
    return [s.read(s.spec_file(event), Spec) for event in record.event_ids]


def good_prompt(spec: Spec) -> str:
    """A prompt that passes every rule: the first term of each subject's and prop's class."""
    nouns = [TAX.terms[item.cls][0] for item in (*spec.subjects, *spec.props)]
    place = spec.cell.zone.replace("_", " ")
    return f"At the {place}: {', '.join(nouns) if nouns else 'an empty scene'}."


def write_prompts(root: Path, batch: str, prompts: dict[str, str]) -> None:
    path = store(root).batch_dir(batch) / "prompts.jsonl"
    rows = [json.dumps({"event_id": event, "prompt": text}) for event, text in prompts.items()]
    path.write_text("".join(f"{row}\n" for row in rows), encoding="utf-8")


def frozen_batch(root: Path, batch: str = "pilot-1", n: int = 4) -> list[Spec]:
    """A sampled batch whose prompts `check` has frozen; returns the frozen specs."""
    specs = sample(root, batch, n)
    write_prompts(root, batch, {spec.event_id: good_prompt(spec) for spec in specs})
    assert run(root, "check", "--batch", batch) == cli.EXIT_OK
    s = store(root)
    return [s.read(s.spec_file(spec.event_id), Spec) for spec in specs]


def record_output(
    root: Path, spec: Spec, *, render: bytes | None = None, still: bytes | None = None
) -> None:
    """Store and record the current attempt's render and still, as render and camera do."""
    s = store(root)
    path = s.provenance_file(spec.event_id)
    prov = s.read(path, Provenance)
    attempt = prov.attempts[-1]
    event_dir = s.event_dir(spec.event_id)
    changes: dict[str, Any] = {}
    if render is not None:
        name = render_name(attempt.k, attempt.seed)
        s.write_new_bytes(event_dir / name, render)
        changes["render"] = OutputFile(path=name, sha256=hashlib.sha256(render).hexdigest())
        changes["render_seconds"] = 8.0
    if still is not None:
        name = still_name(attempt.k, attempt.seed)
        s.write_new_bytes(event_dir / name, still)
        changes["still"] = OutputFile(path=name, sha256=hashlib.sha256(still).hexdigest())
        changes["camera_params"] = "default-v1"
        changes["overlay_time"] = "2026-03-04 10:15:09"
    s.replace_json(path, prov.updated(attempts=(*prov.attempts[:-1], attempt.updated(**changes))))


def png(
    width: int = 1280, height: int = 720, color: tuple[int, int, int] = (90, 110, 130)
) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), color).save(out, "PNG")
    return out.getvalue()


def rendered_batch(root: Path, batch: str = "pilot-1", n: int = 4) -> list[Spec]:
    """A frozen batch whose attempt 1 has a real 1280x720 PNG render recorded."""
    specs = frozen_batch(root, batch, n)
    for spec in specs:
        record_output(root, spec, render=png())
    return specs


def stilled_batch(root: Path, batch: str = "pilot-1", n: int = 4) -> list[Spec]:
    """A frozen batch whose attempt 1 has a render and a still recorded (stand-in bytes: fast)."""
    specs = frozen_batch(root, batch, n)
    for spec in specs:
        tag = spec.event_id.encode()
        record_output(root, spec, render=b"png " + tag, still=b"jpeg " + tag)
    return specs
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/unit/synthbench/test_prompt_rules.py`:

```python
"""The prompt rules `check` enforces (agent-driven design §3.1)."""

from __future__ import annotations

import pytest
from synthbench.contract.spec import Cell, Prop, Spec, Subject
from synthbench.prompt import rules
from synthbench.taxonomy.model import load_taxonomy

TAX = load_taxonomy()
GOOD = "A delivery man in a navy rain jacket carries a cardboard parcel up the porch steps."


def _spec() -> Spec:
    return Spec(
        event_id="B-pilot-1-000",
        tier="B",
        corpus_version="tierb-v0",
        batch="pilot-1",
        cell=Cell(
            scenario="delivery_driver",
            group="benign",
            property_type="suburban_house",
            zone="front_porch",
            camera="doorbell_fisheye",
            lighting="day",
            weather="clear",
        ),
        scene_time="10:00",
        label="benign",
        risk_band=(0, 20),
        subjects=(Subject(id="S1", cls="person", role="delivery_driver"),),
        props=(Prop(id="X1", cls="package", held_by="S1"),),
    )


def test_a_prompt_naming_every_subject_and_prop_passes() -> None:
    assert rules.problems(_spec(), GOOD, TAX) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("A man walks to the door.", "rule 1: mention prop X1 (package)"),
        ("A parcel sits by the door.", "rule 1: mention subject S1 (person)"),
        ("   ", "rule 1: the prompt is empty"),
    ],
)
def test_rule_1_needs_every_subject_and_prop(text: str, expected: str) -> None:
    found = rules.problems(_spec(), text, TAX)
    assert any(problem.startswith(expected) for problem in found), found


def test_terms_match_whole_words_in_any_order_with_plurals() -> None:
    assert rules.mentions("two guns on the table", ["gun"])
    assert not rules.mentions("a gunmetal gray car", ["gun"])
    assert rules.mentions("the frame of the window is bent", ["bent frame"])
    assert rules.mentions("boxes stacked by the door", ["box"])


@pytest.mark.parametrize(
    ("phrase", "rule"),
    [
        ("blood", "rule 2"),
        ("dead body", "rule 2"),
        ("celebrity", "rule 2"),
        ("security camera", "rule 4"),
        ("timestamp", "rule 4"),
        ("CCTV", "rule 4"),
    ],
)
def test_blocklisted_phrases_break_rules_2_and_4(phrase: str, rule: str) -> None:
    found = rules.problems(_spec(), f"{GOOD} {phrase}.", TAX)
    assert any(p.startswith(rule) and f"'{phrase.lower()}'" in p for p in found), found


def test_phrases_match_in_order_only() -> None:
    assert rules.contains_phrase("a dead body on the lawn", "dead body")
    assert not rules.contains_phrase("a dead leaf on the body of the car", "dead body")
    assert rules.contains_phrase("two wounds", "wound")


def test_rule_3_caps_the_length() -> None:
    long = GOOD + " The sky is gray." * 80
    assert len(long) > rules.MAX_PROMPT_CHARS
    assert any(p.startswith("rule 3:") for p in rules.problems(_spec(), long, TAX))


def test_the_prompt_and_suffix_fit_flux2s_512_tokens() -> None:
    # Plan ruling P3-R4: 512 tokens, 33 of them the chat template, 3.5 characters per token
    # at worst (English scene text measured 4.6-4.9).
    assert len(rules.CAMERA_SUFFIX) + 1 + rules.MAX_PROMPT_CHARS <= (512 - 33) * 3.5


def test_the_suffix_ends_by_forbidding_overlay_text() -> None:
    assert rules.CAMERA_SUFFIX.endswith("no on-screen text, no timestamp, no watermark.")


def test_no_fact_term_is_blocklisted() -> None:
    clashes = [
        (term, phrase)
        for terms in TAX.terms.values()
        for term in terms
        for phrases in rules.blocklist().values()
        for phrase in phrases
        if rules.contains_phrase(term, phrase)
    ]
    assert clashes == []


def test_the_blocklist_has_exactly_the_rule_categories() -> None:
    assert set(rules.blocklist()) == set(rules.RULE_OF_CATEGORY)


def test_render_text_is_the_prompt_then_the_suffix() -> None:
    spec = _spec().with_prompt(GOOD, rules.CAMERA_SUFFIX)
    assert rules.render_text(spec) == f"{GOOD} {rules.CAMERA_SUFFIX}"
    assert len(rules.prompt_sha256(spec)) == 64
    with pytest.raises(ValueError, match="no frozen prompt"):
        rules.render_text(_spec())
```

`backend/tests/unit/synthbench/test_cli_check.py`:

```python
"""`check --batch <b>` (agent-driven design §3 step 3, §3.1): validate, freeze, verify."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from synthbench import cli
from synthbench.contract.provenance import Provenance, attempt_seed, render_name
from synthbench.contract.spec import Spec
from synthbench.prompt import rules

from backend.tests.unit.synthbench import helpers as h


def _check(root: Path) -> int:
    return h.run(root, "check", "--batch", "pilot-1")


def test_check_freezes_passing_prompts_and_opens_provenance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.frozen_batch(tmp_path, n=4)
    store = h.store(tmp_path)
    for spec in specs:
        assert spec.prompt == h.good_prompt(spec)
        assert spec.camera_suffix == rules.CAMERA_SUFFIX
        (attempt,) = store.read(store.provenance_file(spec.event_id), Provenance).attempts
        assert (attempt.k, attempt.seed) == (1, attempt_seed(spec.event_id, 1))
        assert attempt.prompt_sha256 == rules.prompt_sha256(spec)
    assert {row.status for row in store.latest_index().values()} == {"prompted"}
    assert "4 frozen now" in capsys.readouterr().out


def test_one_failing_prompt_freezes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.sample(tmp_path, n=3)
    prompts = {spec.event_id: h.good_prompt(spec) for spec in specs}
    prompts[specs[1].event_id] += " There is blood on the step."
    h.write_prompts(tmp_path, "pilot-1", prompts)
    assert _check(tmp_path) == cli.EXIT_ERROR
    assert f"{specs[1].event_id}: rule 2: remove 'blood'" in capsys.readouterr().err
    store = h.store(tmp_path)
    assert not any(store.read(store.spec_file(s.event_id), Spec).frozen for s in specs)
    assert not any(store.provenance_file(s.event_id).exists() for s in specs)


def test_bad_lines_and_missing_rows_are_the_agents_to_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.sample(tmp_path, n=3)
    path = h.store(tmp_path).batch_dir("pilot-1") / "prompts.jsonl"
    first = json.dumps({"event_id": specs[0].event_id, "prompt": h.good_prompt(specs[0])})
    other = json.dumps({"event_id": "B-other-000", "prompt": "a man"})
    path.write_text(f"{first}\nnot json\n{other}\n{first}\n", encoding="utf-8")
    assert _check(tmp_path) == cli.EXIT_ERROR
    err = capsys.readouterr().err
    assert "line 2: not a prompt row" in err
    assert "line 3: B-other-000 is not in batch pilot-1" in err
    assert f"line 4: a second row for {specs[0].event_id}" in err
    h.write_prompts(tmp_path, "pilot-1", {specs[0].event_id: h.good_prompt(specs[0])})
    assert _check(tmp_path) == cli.EXIT_ERROR
    assert f"{specs[1].event_id}: no row in prompts.jsonl" in capsys.readouterr().err


def test_a_rerun_freezes_nothing_new_and_a_frozen_prompt_never_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.frozen_batch(tmp_path, n=2)
    capsys.readouterr()
    assert _check(tmp_path) == cli.EXIT_OK
    assert "0 frozen now" in capsys.readouterr().out
    lines = h.store(tmp_path).index_file.read_text(encoding="utf-8").splitlines()
    assert sum('"prompted"' in line for line in lines) == 2
    h.write_prompts(tmp_path, "pilot-1", {s.event_id: f"{h.good_prompt(s)} Later." for s in specs})
    assert _check(tmp_path) == cli.EXIT_ERROR
    assert "the frozen prompt never changes" in capsys.readouterr().err


def test_a_hand_edited_fact_stops_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    specs = h.frozen_batch(tmp_path, n=2)
    path = h.store(tmp_path).spec_file(specs[0].event_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["scene_time"] = "03:33" if data["scene_time"] != "03:33" else "04:44"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert _check(tmp_path) == cli.EXIT_ASK
    assert "facts differ from the sampler's" in capsys.readouterr().err


def test_a_changed_suffix_stops_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)
    path = h.store(tmp_path).spec_file(spec.event_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["camera_suffix"] = "A different camera look."
    path.write_text(json.dumps(data), encoding="utf-8")
    assert _check(tmp_path) == cli.EXIT_ASK
    assert "camera_suffix differs" in capsys.readouterr().err


@pytest.mark.parametrize("damage", ["modified", "missing"])
def test_a_changed_or_missing_image_stops_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], damage: str
) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)
    h.record_output(tmp_path, spec, render=b"\x89PNG original")
    store = h.store(tmp_path)
    seed = attempt_seed(spec.event_id, 1)
    image = store.event_dir(spec.event_id) / render_name(1, seed)
    if damage == "modified":
        image.write_bytes(b"\x89PNG edited")
    else:
        image.unlink()
    assert _check(tmp_path) == cli.EXIT_ASK
    expected = "was modified" if damage == "modified" else "is missing"
    assert f"{render_name(1, seed)} {expected}" in capsys.readouterr().err


def test_an_unexpected_file_stops_check_but_store_temps_do_not(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)
    renders = h.store(tmp_path).event_dir(spec.event_id) / "renders"
    renders.mkdir()
    (renders / ".a1-s1.png.x1y2.tmp").write_bytes(b"left by a crash")
    assert _check(tmp_path) == cli.EXIT_OK
    (renders / "extra.png").write_bytes(b"?")
    assert _check(tmp_path) == cli.EXIT_ASK
    assert "unexpected file renders/extra.png" in capsys.readouterr().err


def test_check_finishes_a_freeze_that_stopped_before_provenance(tmp_path: Path) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)
    store = h.store(tmp_path)
    store.provenance_file(spec.event_id).unlink()
    assert _check(tmp_path) == cli.EXIT_OK
    (attempt,) = store.read(store.provenance_file(spec.event_id), Provenance).attempts
    assert attempt.seed == attempt_seed(spec.event_id, 1)


def test_check_needs_a_sampled_batch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert h.run(tmp_path, "check", "--batch", "nope") == cli.EXIT_ERROR
    assert "run sample first" in capsys.readouterr().err
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_prompt_rules.py backend/tests/unit/synthbench/test_cli_check.py -q -n0 -p no:randomly`

Expected: FAIL with `ModuleNotFoundError: No module named 'synthbench.prompt'`.

- [ ] **Step 4: Implement the rules**

`synthbench/prompt/__init__.py`:

```python
"""The rules a prompt must pass before `check` freezes it (agent-driven design §3.1)."""
```

`synthbench/prompt/blocklist.yaml`:

```yaml
# Prompt content blocklist for `python -m synthbench check` (agent-driven design §3.1 rules 2
# and 4; parent spec §3.8). A phrase matches as whole words, in order; its last word may be
# plural (s/es). No fact term of the taxonomy may appear here (test_prompt_rules.py).
#
# OWNER REVIEW: a v0 draft. A blocklist cannot catch every real person's name; the owner's
# audit is the backstop (design §3.1).

# rule 2: realistic, never graphic
injury:
  - blood
  - bloody
  - bleeding
  - gore
  - gory
  - wound
  - wounded
  - corpse
  - dead body
  - severed
  - dismembered
  - decapitated
  - mutilated
  - entrails
  - gunshot
  - stabbed
  - open fracture

# rule 2: every Tier B person is anonymous (parent spec §1.1)
real_people:
  - celebrity
  - celebrities
  - famous
  - lookalike
  - look alike
  - president
  - senator
  - politician
  - prince
  - princess
  - actor
  - actress
  - singer
  - rapper
  - athlete
  - influencer
  - portrait of

# rule 4: the agent writes the scene; check adds the camera look, the camera stage the overlay
styling:
  - security camera
  - cctv
  - surveillance
  - footage
  - camera view
  - timestamp
  - time stamp
  - date stamp
  - watermark
  - caption
  - on screen text
  - text overlay
  - subtitle
  - logo
  - wide angle lens
  - fisheye
```

`synthbench/prompt/rules.py`:

```python
"""The prompt rules `python -m synthbench check` enforces (agent-driven design §3.1).

1. Every subject and prop is named with a term from its class's list (taxonomy `terms:`),
   matched as the P1 judge matched prop terms: whole words, any order, plural s/es allowed.
2. No blocklisted injury or real-person phrase (parent spec §3.8).
3. At most MAX_PROMPT_CHARS characters (plan ruling P3-R4).
4. No camera styling or overlay words: check appends CAMERA_SUFFIX, and the camera stage draws
   the real timestamp.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from functools import cache
from pathlib import Path

import yaml

from synthbench.contract.spec import Spec
from synthbench.taxonomy.model import Taxonomy

BLOCKLIST_FILE = Path(__file__).resolve().parent / "blocklist.yaml"
RULE_OF_CATEGORY = {"injury": 2, "real_people": 2, "styling": 4}

# Rule 4. It ends with the negatives because FLUX.2 draws a fake timestamp bar when asked for
# security-camera footage (design, measured 2026-09-28).
CAMERA_SUFFIX = (
    "Photorealistic still from a fixed, high-mounted security camera looking down at the scene "
    "through a wide-angle lens, ordinary everyday detail, no on-screen text, no timestamp, "
    "no watermark."
)
# Rule 3 (plan ruling P3-R4): FLUX.2 [dev] reads at most 512 tokens; the chat template takes
# 33, and English scene text measured 4.6-4.9 characters per token.
MAX_PROMPT_CHARS = 1200


def words(text: str) -> list[str]:
    """Lowercase alphanumeric words: "ground-floor" -> ["ground", "floor"]."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _forms(word: str) -> set[str]:
    return {word, f"{word}s", f"{word}es"}


def mentions(text: str, terms: Sequence[str]) -> bool:
    """Rule 1: some term has all its words in the text, in any order, each a whole word."""
    field = set(words(text))
    return any(
        all(_forms(word) & field for word in term_words)
        for term_words in (words(term) for term in terms)
        if term_words
    )


def contains_phrase(text: str, phrase: str) -> bool:
    """Rules 2 and 4: the phrase's words appear together and in order (the last may be plural)."""
    target = words(phrase)
    if not target:
        return False
    tokens = words(text)
    size = len(target)
    return any(
        tokens[i : i + size - 1] == target[:-1] and tokens[i + size - 1] in _forms(target[-1])
        for i in range(len(tokens) - size + 1)
    )


@cache
def blocklist(path: Path = BLOCKLIST_FILE) -> dict[str, tuple[str, ...]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if set(data) != set(RULE_OF_CATEGORY):
        raise ValueError(
            f"{path}: categories must be {sorted(RULE_OF_CATEGORY)}, got {sorted(data)}"
        )
    return {category: tuple(str(p).lower() for p in phrases) for category, phrases in data.items()}


def render_text(spec: Spec) -> str:
    """Exactly what FLUX.2 receives: the frozen prompt, then the camera suffix."""
    if spec.prompt is None or spec.camera_suffix is None:
        raise ValueError(f"{spec.event_id} has no frozen prompt")
    return f"{spec.prompt} {spec.camera_suffix}"


def prompt_sha256(spec: Spec) -> str:
    return hashlib.sha256(render_text(spec).encode()).hexdigest()


def problems(spec: Spec, prompt: str, tax: Taxonomy) -> list[str]:
    """Every rule the prompt breaks for this spec, one line each; empty when it passes."""
    if not prompt.strip():
        return ["rule 1: the prompt is empty"]
    found: list[str] = []
    for kind, items in (("subject", spec.subjects), ("prop", spec.props)):
        for item in items:
            terms = tax.terms[item.cls]
            if not mentions(prompt, terms):
                found.append(
                    f"rule 1: mention {kind} {item.id} ({item.cls}) with one of: {', '.join(terms)}"
                )
    for category, phrases in blocklist().items():
        for phrase in phrases:
            if contains_phrase(prompt, phrase):
                found.append(f"rule {RULE_OF_CATEGORY[category]}: remove '{phrase}' ({category})")
    if len(prompt) > MAX_PROMPT_CHARS:
        found.append(f"rule 3: {len(prompt)} characters; at most {MAX_PROMPT_CHARS}")
    return found
```

- [ ] **Step 5: Implement `check`**

`synthbench/commands/check.py`:

```python
"""`check --batch <b>`: validate prompts, freeze them, verify the batch (design §3 step 3).

The agent runs it after writing prompts.jsonl. When every prompt passes, it freezes each one
into spec.json with the fixed camera suffix and opens provenance.json with attempt 1. It also
verifies what the batch already holds: the facts against the sampler, every frozen prompt
against the rules, and every recorded image against its sha256. The owner runs the same command
on the host to confirm a batch before relying on it.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence

from pydantic import ValidationError

from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    CorpusError,
    Parser,
    RequestError,
    append_index,
    batch_name,
    now_iso,
    open_batch,
    read,
    read_index,
    replace_json,
    taxonomy,
    write_new,
)
from synthbench.contract.corpus import BatchRecord, IndexRow, PromptRow
from synthbench.contract.provenance import (
    Attempt,
    Provenance,
    attempt_seed,
    render_name,
    still_name,
)
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore, sha256_file
from synthbench.prompt import rules
from synthbench.taxonomy.model import Taxonomy
from synthbench.taxonomy.sampler import sample_specs

_OUTPUT_DIRS = ("renders", "stills")


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "check",
        help="validate prompts.jsonl, freeze passing prompts, and verify the batch's files",
        allow_abbrev=False,
    )
    parser.add_argument("--batch", type=batch_name, required=True, help="batch name")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_batch(tax, env, args.batch)
    specs = _sampled_specs(tax, store, record)
    rows = _prompt_rows(store, record)
    ask: list[str] = []
    fix: list[str] = []
    pending: dict[str, str] = {}
    for spec in specs:
        row = rows.get(spec.event_id)
        if spec.frozen:
            ask.extend(_frozen_problems(spec, tax))
            if row is not None and row != spec.prompt:
                fix.append(
                    f"{spec.event_id}: the frozen prompt never changes; restore it in "
                    "prompts.jsonl (a different prompt is a new event)"
                )
        elif row is None:
            fix.append(f"{spec.event_id}: no row in prompts.jsonl")
        else:
            fix.extend(f"{spec.event_id}: {problem}" for problem in rules.problems(spec, row, tax))
            pending[spec.event_id] = row
    output_problems, verified = _output_problems(store, specs)
    ask.extend(output_problems)
    if ask:
        raise AskOwner(
            f"batch {record.name} is not in the state check expects:\n  " + "\n  ".join(ask) + "\n"
        )
    if fix:
        raise RequestError(
            f"{len(fix)} problem(s) in batch {record.name}; fix prompts.jsonl and run check "
            "again:\n  " + "\n  ".join(fix)
        )
    frozen_now = _freeze(store, record, specs, pending)
    sys.stdout.write(
        f"check {record.name}: {len(specs)} events, {frozen_now} frozen now, every prompt "
        f"frozen; {verified} recorded output file(s) verified\n"
        f"Next: render --batch {record.name}\n"
    )
    return EXIT_OK


def _sampled_specs(tax: Taxonomy, store: CorpusStore, record: BatchRecord) -> list[Spec]:
    """The batch's specs, each compared with what the sampler makes from batch.json."""
    expected = sample_specs(
        tax,
        version=store.version,
        batch=record.name,
        n=record.n,
        seed=record.seed,
        prior=record.prior_counts,
        only=record.only or None,
    )
    if tuple(spec.event_id for spec in expected) != record.event_ids:
        raise AskOwner(f"batch.json of {record.name} lists events the sampler does not make.")
    if missing := [s.event_id for s in expected if not store.spec_file(s.event_id).exists()]:
        only = f" --only {','.join(record.only)}" if record.only else ""
        raise RequestError(
            f"{len(missing)} spec(s) of batch {record.name} were never written; run "
            f"`python -m synthbench sample --batch {record.name} --n {record.n} "
            f"--seed {record.seed}{only}` to finish the batch"
        )
    specs: list[Spec] = []
    drift: list[str] = []
    for want in expected:
        have = read(store, store.spec_file(want.event_id), Spec)
        if have.facts() != want.facts():
            drift.append(f"{want.event_id}: spec.json facts differ from the sampler's")
        specs.append(have)
    if drift:
        raise AskOwner(f"batch {record.name} was changed by hand:\n  " + "\n  ".join(drift) + "\n")
    return specs


def _prompt_rows(store: CorpusStore, record: BatchRecord) -> dict[str, str]:
    path = store.batch_dir(record.name) / "prompts.jsonl"
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RequestError(f"cannot read {path} ({type(error).__name__}); rewrite it") from error
    rows: dict[str, str] = {}
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = PromptRow.model_validate_json(line)
        except ValidationError as error:
            problems.append(f"line {number}: not a prompt row ({error.errors()[0]['msg']})")
            continue
        if row.event_id not in record.event_ids:
            problems.append(f"line {number}: {row.event_id} is not in batch {record.name}")
        elif row.event_id in rows:
            problems.append(f"line {number}: a second row for {row.event_id}")
        else:
            rows[row.event_id] = row.prompt.strip()
    if problems:
        raise RequestError(f"{path}:\n  " + "\n  ".join(problems))
    return rows


def _frozen_problems(spec: Spec, tax: Taxonomy) -> list[str]:
    assert spec.prompt is not None
    found = [
        f"{spec.event_id}: the frozen prompt now breaks {problem}"
        for problem in rules.problems(spec, spec.prompt, tax)
    ]
    if spec.camera_suffix != rules.CAMERA_SUFFIX:
        found.append(f"{spec.event_id}: camera_suffix differs from the committed suffix")
    return found


def _output_problems(store: CorpusStore, specs: Sequence[Spec]) -> tuple[list[str], int]:
    """Every recorded image against its sha256, and no image provenance does not name (§2)."""
    problems: list[str] = []
    verified = 0
    for spec in specs:
        path = store.provenance_file(spec.event_id)
        if not spec.frozen or not path.exists():
            continue
        prov = read(store, path, Provenance)
        event_dir = store.event_dir(spec.event_id)
        want = rules.prompt_sha256(spec)
        expected: set[str] = set()
        for attempt in prov.attempts:
            where = f"{spec.event_id} attempt {attempt.k}"
            if attempt.prompt_sha256 != want:
                problems.append(f"{where}: prompt_sha256 is not the frozen prompt's")
            if attempt.seed != attempt_seed(spec.event_id, attempt.k):
                problems.append(f"{where}: seed {attempt.seed} is not the attempt's seed")
            expected |= {render_name(attempt.k, attempt.seed), still_name(attempt.k, attempt.seed)}
            for output in (attempt.render, attempt.still):
                if output is None:
                    continue
                file = event_dir / output.path
                if not file.is_file():
                    problems.append(f"{spec.event_id}: {output.path} is missing")
                    continue
                try:
                    digest = sha256_file(file)
                except OSError as error:
                    raise CorpusError("read", file, error) from error
                if digest != output.sha256:
                    problems.append(f"{spec.event_id}: {output.path} was modified")
                else:
                    verified += 1
        for sub in _OUTPUT_DIRS:
            folder = event_dir / sub
            if not folder.is_dir():
                continue
            for file in sorted(folder.iterdir()):
                name = f"{sub}/{file.name}"
                if name not in expected and not _store_temp(file.name):
                    problems.append(f"{spec.event_id}: unexpected file {name}")
    return problems, verified


def _store_temp(name: str) -> bool:
    """CorpusStore's temporary files (`.<name>.<random>.tmp`), left only by a crash."""
    return name.startswith(".") and name.endswith(".tmp")


def _freeze(
    store: CorpusStore, record: BatchRecord, specs: Sequence[Spec], pending: Mapping[str, str]
) -> int:
    """Freeze each pending prompt, then open provenance for every frozen spec that lacks it."""
    index = read_index(store)
    rows: list[IndexRow] = []
    frozen_now = 0
    for spec in specs:
        current = spec
        if spec.event_id in pending:
            current = spec.with_prompt(pending[spec.event_id], rules.CAMERA_SUFFIX)
            replace_json(store, store.spec_file(spec.event_id), current)
            frozen_now += 1
        if not current.frozen:
            continue
        provenance = store.provenance_file(spec.event_id)
        if not provenance.exists():  # spec.json is written first, so a crash leaves only this
            first = Attempt(
                k=1,
                seed=attempt_seed(spec.event_id, 1),
                prompt_sha256=rules.prompt_sha256(current),
            )
            write_new(store, provenance, Provenance(event_id=spec.event_id, attempts=(first,)))
        latest = index.get(spec.event_id)
        if latest is None or latest.status == "sampled":
            rows.append(
                IndexRow(
                    event_id=spec.event_id,
                    batch=record.name,
                    scenario=spec.cell.scenario,
                    label=spec.label,
                    status="prompted",
                    time=now_iso(),
                )
            )
    append_index(store, rows)
    return frozen_now
```

In `synthbench/cli.py`, import `check` beside `sample` and set `COMMANDS = (sample, check)`.

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/ -q -n0 -p no:randomly`

Expected: PASS. Then run `uv run mypy synthbench/` and
`uv run ruff check synthbench/ backend/tests/unit/synthbench/`; both are clean.

- [ ] **Step 7: Commit**

```bash
F="synthbench/prompt/__init__.py synthbench/prompt/rules.py synthbench/prompt/blocklist.yaml synthbench/commands/check.py synthbench/cli.py backend/tests/unit/synthbench/helpers.py backend/tests/unit/synthbench/test_prompt_rules.py backend/tests/unit/synthbench/test_cli_check.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "feat(synthbench): prompt rules and check - validate, freeze with the camera suffix, verify sha256s

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `render`: yield to the flagship, render through ComfyUI

**Files:**

- Create: `synthbench/status.py`, `synthbench/generate/render.py`,
  `synthbench/commands/render.py`
- Modify: `synthbench/cli.py` (add `render` to `COMMANDS`),
  `backend/tests/unit/synthbench/helpers.py` (status and clock helpers)
- Test: `backend/tests/unit/synthbench/test_render.py`

**Interfaces:**

- Consumes: Task 2 (`OutputFile`, `RenderFailure`, `render_name`, `Provenance`); Task 3
  (`commands.common`); Task 4 (`rules.render_text`); P1 (`ComfyClient`, `ComfyError`,
  `flux2_dev_t2i`, `load_manifest`).
- Produces (`status.py`):
  - `STALE_AFTER_S = 30.0`.
  - `FlagshipStatus(schema_version=1, time, healthy, running=None, waiting=None, failures=0)`;
    `SnapshotHold(snapshot, count, paths)`;
    `SnapshotStatus(schema_version=1, time, snapshots, hold=None)`.
  - `status_dir(env)`, `flagship_file(env)`, `snapshots_file(env)`.
  - `write_status(path, model)` (atomic, 0644); `read_status(path, model)`.
  - `FlagshipUnknown`; `fresh_flagship(path, now) -> FlagshipStatus`, which raises
    `FlagshipUnknown` when the file is missing, unreadable or older than 30 s.
- Produces (`generate/render.py`):
  - `RENDER_MODEL = "flux2-dev"`, `DEFAULT_URLS`, `YIELD_POLL_S = 5.0`.
  - `RendererUnreachable`.
  - `model_hashes() -> dict[str, str]`; `comfy_url(env, get) -> str`.
  - `wait_for_flagship(status_file, *, deadline, clock, sleep, now) -> bool`.
  - `attempt_graph(spec, attempt) -> Graph`; `check_png(data) -> None`, which raises
    `ValueError`.
- Produces (`commands/render.py`):

  - `DEFAULT_BUDGET_S = 480`, `MAX_RENDER_FAILURES = 3`.
  - `Deps(transport, get, sleep, clock, now)`.
  - `add_parser`, `run`, and `execute(batch, budget_s, env, deps) -> int` (raises
    `RequestError` or `AskOwner`).

- [ ] **Step 1: Extend the test helpers**

Append to `backend/tests/unit/synthbench/helpers.py`, and add
`from datetime import UTC, datetime` and
`from synthbench.status import FlagshipStatus, flagship_file, write_status` to its imports:

```python
NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def flagship(root: Path, *, healthy: bool = True, waiting: int = 0, time: datetime = NOW) -> None:
    """Write status/flagship.json as the guard does."""
    status = FlagshipStatus(time=time, healthy=healthy, running=1, waiting=waiting)
    write_status(flagship_file(env(root)), status)


class FakeClock:
    """A monotonic clock that only fake sleeps and fake work move."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/unit/synthbench/test_render.py`:

```python
"""`render` (agent-driven design §3 step 4, §5.2) against a fake ComfyUI (httpx.MockTransport)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from synthbench import cli
from synthbench.commands import render
from synthbench.commands.common import AskOwner, RequestError
from synthbench.contract.provenance import (
    Attempt,
    OutputFile,
    Provenance,
    Triage,
    attempt_seed,
    render_name,
)
from synthbench.contract.spec import Spec
from synthbench.generate.render import (
    RendererUnreachable,
    check_png,
    comfy_url,
    model_hashes,
)
from synthbench.prompt import rules
from synthbench.status import flagship_file

from backend.tests.unit.synthbench import helpers as h

Handler = Callable[[httpx.Request], httpx.Response]
OOM = [
    "execution_error",
    {
        "node_id": "11",
        "node_type": "SamplerCustomAdvanced",
        "exception_type": "torch.OutOfMemoryError",
        "exception_message": "out of memory",
    },
]


class FakeComfy:
    """ComfyUI's /system_stats, /prompt, /history and /view; one image per queued prompt.

    Each queued prompt moves the fake clock by `seconds`, like a render. Prompt numbers in
    `fail` end in an out-of-memory error.
    """

    def __init__(
        self, clock: h.FakeClock, *, seconds: float = 8.0, fail: frozenset[int] = frozenset()
    ) -> None:
        self.clock = clock
        self.seconds = seconds
        self.fail = fail
        self.image = h.png()
        self.graphs: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/system_stats":
            return httpx.Response(200, json={"system": {}})
        if path == "/prompt":
            self.graphs.append(json.loads(request.content)["prompt"])
            self.clock.now += self.seconds
            return httpx.Response(
                200, json={"prompt_id": f"p{len(self.graphs)}", "node_errors": {}}
            )
        if path.startswith("/history/p"):
            number = int(path.rsplit("p", 1)[1])
            if number in self.fail:
                entry = {"status": {"status_str": "error", "messages": [OOM]}, "outputs": {}}
            else:
                image = {"filename": "x.png", "subfolder": "", "type": "output"}
                entry = {
                    "status": {"status_str": "success"},
                    "outputs": {"13": {"images": [image]}},
                }
            return httpx.Response(200, json={f"p{number}": entry})
        if path == "/view":
            return httpx.Response(200, content=self.image)
        return httpx.Response(404)


def _deps(
    clock: h.FakeClock, handler: Handler, *, on_sleep: Callable[[], None] | None = None
) -> render.Deps:
    transport = httpx.MockTransport(handler)

    def get(url: str, timeout: float) -> httpx.Response:
        with httpx.Client(transport=transport) as client:
            return client.get(url, timeout=timeout)

    def sleep(seconds: float) -> None:
        clock.sleep(seconds)
        if on_sleep is not None:
            on_sleep()

    return render.Deps(transport=transport, get=get, sleep=sleep, clock=clock, now=lambda: h.NOW)


def _render(root: Path, deps: render.Deps, budget: float = 480) -> int:
    return render.execute("pilot-1", budget, h.env(root), deps)


def _attempt(root: Path, spec: Spec) -> Any:
    store = h.store(root)
    return store.read(store.provenance_file(spec.event_id), Provenance).attempts[-1]


def _ready(root: Path, n: int) -> tuple[list[Spec], h.FakeClock]:
    specs = h.frozen_batch(root, n=n)
    h.flagship(root)
    return specs, h.FakeClock()


def test_render_stores_each_pending_attempt(tmp_path: Path) -> None:
    specs, clock = _ready(tmp_path, 3)
    comfy = FakeComfy(clock)
    assert _render(tmp_path, _deps(clock, comfy)) == cli.EXIT_OK
    store = h.store(tmp_path)
    for spec, graph in zip(specs, comfy.graphs, strict=True):
        attempt = _attempt(tmp_path, spec)
        name = render_name(1, attempt_seed(spec.event_id, 1))
        assert attempt.render == OutputFile(
            path=name, sha256=hashlib.sha256(comfy.image).hexdigest()
        )
        assert attempt.render_seconds == 8.0
        assert attempt.models == model_hashes()
        assert (store.event_dir(spec.event_id) / name).read_bytes() == comfy.image
        assert graph["4"]["inputs"]["text"] == rules.render_text(spec)
        assert graph["10"]["inputs"]["noise_seed"] == attempt.seed
        assert (graph["7"]["inputs"]["width"], graph["7"]["inputs"]["height"]) == (1280, 720)
        prefix = f"synthbench/{h.VERSION}/{spec.event_id}/a1-s{attempt.seed}"
        assert graph["13"]["inputs"]["filename_prefix"] == prefix
    assert {row.status for row in store.latest_index().values()} == {"rendered"}


def test_a_second_run_renders_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _specs, clock = _ready(tmp_path, 2)
    assert _render(tmp_path, _deps(clock, FakeComfy(clock))) == cli.EXIT_OK
    again = FakeComfy(clock)
    assert _render(tmp_path, _deps(clock, again)) == cli.EXIT_OK
    assert again.graphs == []
    assert "nothing to render" in capsys.readouterr().out


def test_render_waits_while_the_flagship_has_requests_waiting(tmp_path: Path) -> None:
    _specs, clock = _ready(tmp_path, 1)
    h.flagship(tmp_path, waiting=2)
    comfy = FakeComfy(clock)
    deps = _deps(clock, comfy, on_sleep=lambda: h.flagship(tmp_path, waiting=0))
    assert _render(tmp_path, deps) == cli.EXIT_OK
    assert clock.sleeps == [5.0]
    assert len(comfy.graphs) == 1


def test_an_unhealthy_flagship_holds_every_image_until_the_budget_ends(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _specs, clock = _ready(tmp_path, 1)
    h.flagship(tmp_path, healthy=False)
    comfy = FakeComfy(clock)
    assert _render(tmp_path, _deps(clock, comfy), budget=30) == cli.EXIT_OK
    assert comfy.graphs == []
    assert clock.sleeps == [5.0] * 6
    assert "1 still to render" in capsys.readouterr().out


@pytest.mark.parametrize("state", ["stale", "missing"])
def test_an_unknown_flagship_stops_render(tmp_path: Path, state: str) -> None:
    _specs, clock = _ready(tmp_path, 1)
    if state == "stale":
        h.flagship(tmp_path, time=h.NOW - timedelta(seconds=31))
    else:
        flagship_file(h.env(tmp_path)).unlink()
    comfy = FakeComfy(clock)
    with pytest.raises(AskOwner, match="guard"):
        _render(tmp_path, _deps(clock, comfy))
    assert comfy.graphs == []


def test_render_starts_no_image_after_its_budget(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _specs, clock = _ready(tmp_path, 3)
    comfy = FakeComfy(clock, seconds=200.0)
    assert _render(tmp_path, _deps(clock, comfy), budget=300) == cli.EXIT_OK
    assert len(comfy.graphs) == 2
    assert "1 still to render" in capsys.readouterr().out
    rest = FakeComfy(clock)
    assert _render(tmp_path, _deps(clock, rest), budget=300) == cli.EXIT_OK
    assert len(rest.graphs) == 1


def test_a_failed_job_is_recorded_and_retried_next_run(tmp_path: Path) -> None:
    specs, clock = _ready(tmp_path, 2)
    assert _render(tmp_path, _deps(clock, FakeComfy(clock, fail=frozenset({1})))) == cli.EXIT_OK
    first = _attempt(tmp_path, specs[0])
    assert first.render is None
    assert "OutOfMemoryError" in first.render_failures[0].error
    assert _attempt(tmp_path, specs[1]).render is not None
    assert _render(tmp_path, _deps(clock, FakeComfy(clock))) == cli.EXIT_OK
    assert _attempt(tmp_path, specs[0]).render is not None


def test_three_failed_jobs_stop_and_ask(tmp_path: Path) -> None:
    _specs, clock = _ready(tmp_path, 1)
    for _ in range(2):
        assert _render(tmp_path, _deps(clock, FakeComfy(clock, fail=frozenset({1})))) == 0
    with pytest.raises(AskOwner, match="failed to render 3 times"):
        _render(tmp_path, _deps(clock, FakeComfy(clock, fail=frozenset({1}))))


def test_a_renderer_that_stops_answering_stops_render(tmp_path: Path) -> None:
    specs, clock = _ready(tmp_path, 2)
    comfy = FakeComfy(clock)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            raise httpx.ConnectError("connection refused", request=request)
        return comfy(request)

    with pytest.raises(AskOwner, match="stopped answering"):
        _render(tmp_path, _deps(clock, handler))
    attempt = _attempt(tmp_path, specs[0])
    assert attempt.render is None
    assert len(attempt.render_failures) == 1


def test_no_renderer_is_a_stop(tmp_path: Path) -> None:
    _specs, clock = _ready(tmp_path, 1)

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(AskOwner, match="renderer is down"):
        _render(tmp_path, _deps(clock, down))


def test_render_needs_frozen_prompts(tmp_path: Path) -> None:
    h.sample(tmp_path, n=2)
    h.flagship(tmp_path)
    clock = h.FakeClock()
    with pytest.raises(RequestError, match="run check"):
        _render(tmp_path, _deps(clock, FakeComfy(clock)))


def test_an_unrecorded_render_is_adopted(tmp_path: Path) -> None:
    (spec,), clock = _ready(tmp_path, 1)
    image = h.png(color=(1, 2, 3))
    name = render_name(1, attempt_seed(spec.event_id, 1))
    h.store(tmp_path).write_new_bytes(h.store(tmp_path).event_dir(spec.event_id) / name, image)
    comfy = FakeComfy(clock)
    assert _render(tmp_path, _deps(clock, comfy)) == cli.EXIT_OK
    assert comfy.graphs == []
    attempt = _attempt(tmp_path, spec)
    assert attempt.render.sha256 == hashlib.sha256(image).hexdigest()
    assert attempt.render_seconds is None


def test_a_reroll_renders_a_new_file_and_leaves_the_old_one(tmp_path: Path) -> None:
    (spec,), clock = _ready(tmp_path, 1)
    assert _render(tmp_path, _deps(clock, FakeComfy(clock))) == cli.EXIT_OK
    store = h.store(tmp_path)
    old = store.event_dir(spec.event_id) / render_name(1, attempt_seed(spec.event_id, 1))
    before = old.read_bytes()
    h.record_output(tmp_path, spec, still=b"jpeg")
    path = store.provenance_file(spec.event_id)
    prov = store.read(path, Provenance)
    first = prov.attempts[0].updated(triage=Triage(verdict="reroll", reason="blank"))
    second = Attempt(k=2, seed=attempt_seed(spec.event_id, 2), prompt_sha256=first.prompt_sha256)
    store.replace_json(path, prov.updated(attempts=(first, second)))
    comfy = FakeComfy(clock)
    comfy.image = h.png(color=(9, 9, 9))
    assert _render(tmp_path, _deps(clock, comfy)) == cli.EXIT_OK
    assert old.read_bytes() == before
    new = store.event_dir(spec.event_id) / render_name(2, attempt_seed(spec.event_id, 2))
    assert new.read_bytes() == comfy.image
    assert comfy.graphs[0]["10"]["inputs"]["noise_seed"] == attempt_seed(spec.event_id, 2)


def test_comfy_url_prefers_the_environment_then_the_first_default_that_answers() -> None:
    seen: list[str] = []

    def get(url: str, timeout: float) -> httpx.Response:
        seen.append(url)
        if url.startswith("http://127.0.0.1"):
            raise httpx.ConnectError("connection refused")
        return httpx.Response(200)

    assert comfy_url({}, get) == "http://host.docker.internal:8188"
    assert seen == [
        "http://127.0.0.1:8188/system_stats",
        "http://host.docker.internal:8188/system_stats",
    ]
    configured = {"SYNTHBENCH_COMFYUI_URL": "http://renderer:9000"}
    assert comfy_url(configured, lambda _url, **_kw: httpx.Response(200)) == "http://renderer:9000"
    with pytest.raises(RendererUnreachable):
        comfy_url({}, lambda _url, **_kw: httpx.Response(503))


def test_check_png_wants_a_1280x720_png() -> None:
    check_png(h.png())
    with pytest.raises(ValueError, match="1280x720 PNG"):
        check_png(h.png(640, 360))
    with pytest.raises(ValueError, match="not an image"):
        check_png(b"<html>error</html>")
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_render.py -q -n0 -p no:randomly`

Expected: FAIL with `ModuleNotFoundError: No module named 'synthbench.status'` (the
helpers import it).

- [ ] **Step 4: Implement**

`synthbench/status.py`:

```python
"""Host status files the sandbox reads (agent-driven design §1, §5.2, §6).

The guard writes status/flagship.json every 5 s; `corpus snapshot` writes
status/snapshots.json. The sandbox mounts status/ read-only at the same path.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import AwareDatetime, Field, ValidationError

from synthbench.contract.common import ContractModel

STALE_AFTER_S = 30.0  # design §5.2: an older flagship.json means the guard is down

M = TypeVar("M", bound=ContractModel)


class FlagshipStatus(ContractModel):
    schema_version: Literal[1] = 1
    time: AwareDatetime
    healthy: bool
    running: int | None = Field(default=None, ge=0)
    waiting: int | None = Field(default=None, ge=0)
    failures: int = Field(default=0, ge=0)  # consecutive failed health checks


class SnapshotHold(ContractModel):
    snapshot: str
    count: int = Field(ge=1)
    paths: tuple[str, ...]


class SnapshotStatus(ContractModel):
    schema_version: Literal[1] = 1
    time: AwareDatetime
    snapshots: int = Field(ge=0)
    hold: SnapshotHold | None = None


class FlagshipUnknown(RuntimeError):
    """No fresh flagship status: the guard is down, so nothing may render (design §5.2)."""


def status_dir(env: Mapping[str, str] | None = None) -> Path:
    e = os.environ if env is None else env
    return Path(e.get("SYNTHBENCH_ROOT", "/synthbench")) / "status"


def flagship_file(env: Mapping[str, str] | None = None) -> Path:
    return status_dir(env) / "flagship.json"


def snapshots_file(env: Mapping[str, str] | None = None) -> Path:
    return status_dir(env) / "snapshots.json"


def write_status(path: Path, model: ContractModel) -> None:
    """Replace a status file atomically, world-readable: the sandbox reads it through a mount."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o644)
            handle.write(model.model_dump_json() + "\n")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def read_status(path: Path, model: type[M]) -> M:
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def fresh_flagship(path: Path, now: datetime) -> FlagshipStatus:
    try:
        status = read_status(path, FlagshipStatus)
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise FlagshipUnknown(
            f"cannot read {path} ({type(error).__name__}); is synthbench-guard running?"
        ) from error
    age = (now - status.time).total_seconds()
    if age > STALE_AFTER_S:
        raise FlagshipUnknown(f"{path} is {age:.0f} s old, so the guard is down")
    return status
```

`synthbench/generate/render.py`:

```python
"""Rendering beside the flagship (agent-driven design §3 step 4, §5.2): find ComfyUI, yield to
the flagship, and build the FLUX.2 [dev] graph for one attempt."""

from __future__ import annotations

import io
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path

import httpx
from PIL import Image

from synthbench.contract.corpus import TIER_B_RENDER_SIZE
from synthbench.contract.provenance import Attempt
from synthbench.contract.spec import Spec
from synthbench.generate.comfy.client import Graph
from synthbench.generate.comfy.graphs import flux2_dev_t2i
from synthbench.generate.weights import load_manifest
from synthbench.prompt.rules import render_text
from synthbench.status import fresh_flagship

RENDER_MODEL = "flux2-dev"
MANIFEST = Path(__file__).resolve().parent / "manifests" / "p1-slate.json"
# Plan ruling P3-R9: the host reaches ComfyUI on its loopback; a sandbox reaches the host's
# loopback at host.docker.internal (docs/benchmarks/synthbench/p3-probes.md).
DEFAULT_URLS = ("http://127.0.0.1:8188", "http://host.docker.internal:8188")
YIELD_POLL_S = 5.0


class RendererUnreachable(RuntimeError):
    """No ComfyUI answered."""


def model_hashes(manifest: Path = MANIFEST) -> dict[str, str]:
    """The weights FLUX.2 [dev] renders with, by category: an attempt's `models`."""
    return {f.category: f.sha256 for f in load_manifest(manifest) if f.model == RENDER_MODEL}


def comfy_url(env: Mapping[str, str], get: Callable[..., httpx.Response] = httpx.get) -> str:
    """$SYNTHBENCH_COMFYUI_URL, else the first default whose /system_stats answers."""
    configured = env.get("SYNTHBENCH_COMFYUI_URL")
    candidates = (configured,) if configured else DEFAULT_URLS
    for url in candidates:
        try:
            if get(f"{url}/system_stats", timeout=3.0).status_code == 200:
                return url
        except httpx.HTTPError:
            continue
    raise RendererUnreachable(f"ComfyUI did not answer at {', '.join(candidates)}")


def wait_for_flagship(
    status_file: Path,
    *,
    deadline: float,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
    now: Callable[[], datetime],
) -> bool:
    """Wait, polling every 5 s, while the flagship is unhealthy or has requests waiting (§5.2).

    Returns False when the next poll would pass the deadline. Raises FlagshipUnknown when the
    status file is missing, unreadable or older than 30 s.
    """
    while True:
        status = fresh_flagship(status_file, now())
        if status.healthy and not status.waiting:
            return True
        if clock() + YIELD_POLL_S > deadline:
            return False
        sleep(YIELD_POLL_S)


def attempt_graph(spec: Spec, attempt: Attempt) -> Graph:
    """The attempt's FLUX.2 [dev] graph: the frozen text, the attempt's seed, 1280x720.

    ComfyUI also keeps its own copy under comfy-out/synthbench/<version>/<event>/, the fallback
    for a render lost before a snapshot (design §6).
    """
    width, height = TIER_B_RENDER_SIZE
    graph = flux2_dev_t2i(render_text(spec), seed=attempt.seed, width=width, height=height)
    prefix = f"synthbench/{spec.corpus_version}/{spec.event_id}/a{attempt.k}-s{attempt.seed}"
    for node in graph.values():
        if node["class_type"] == "SaveImage":
            node["inputs"]["filename_prefix"] = prefix
    return graph


def check_png(data: bytes) -> None:
    """Raise ValueError unless data is a 1280x720 PNG."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            kind, size = image.format, image.size
    except OSError as error:  # PIL.UnidentifiedImageError is an OSError
        raise ValueError(f"not an image ({type(error).__name__})") from error
    if kind != "PNG" or size != TIER_B_RENDER_SIZE:
        width, height = TIER_B_RENDER_SIZE
        raise ValueError(f"expected a {width}x{height} PNG, got {kind} {size}")
```

`synthbench/commands/render.py`:

```python
"""`render --batch <b>`: render each frozen event's pending attempt through ComfyUI.

Agent-driven design §3 step 4. It yields to the flagship before every image (§5.2) and starts
no new image once its time budget is spent (plan ruling P3-R10); each run resumes where the last
one stopped. A failed job is recorded and retried on the next run; three failures on one
attempt, a renderer that stops answering, or an unknown flagship state stop the run (exit 2).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    Parser,
    RequestError,
    append_index,
    batch_name,
    now_iso,
    open_batch,
    read,
    read_bytes,
    replace_json,
    taxonomy,
    write_new_bytes,
)
from synthbench.contract.corpus import BatchRecord, IndexRow
from synthbench.contract.provenance import OutputFile, Provenance, RenderFailure, render_name
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.generate.comfy.client import ComfyClient, ComfyError
from synthbench.generate.render import (
    RendererUnreachable,
    attempt_graph,
    check_png,
    comfy_url,
    model_hashes,
    wait_for_flagship,
)
from synthbench.status import FlagshipUnknown, flagship_file

DEFAULT_BUDGET_S = 480
MAX_RENDER_FAILURES = 3
RENDER_TIMEOUT_S = 600.0


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Deps:
    """What render reaches outside the corpus; tests pass fakes."""

    transport: httpx.BaseTransport | None = None
    get: Callable[..., httpx.Response] = httpx.get
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    now: Callable[[], datetime] = _utc_now


def _budget(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"budget must be whole seconds: {text!r}") from None
    if not 30 <= value <= 3600:
        raise argparse.ArgumentTypeError(f"budget must be 30..3600 seconds, got {value}")
    return value


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "render",
        help="render the batch's pending attempts at 1280x720 through ComfyUI, yielding to the flagship",
        allow_abbrev=False,
    )
    parser.add_argument("--batch", type=batch_name, required=True, help="batch name")
    parser.add_argument(
        "--budget-seconds",
        type=_budget,
        default=DEFAULT_BUDGET_S,
        help=f"start no new image after this many seconds (default {DEFAULT_BUDGET_S}); "
        "run render again to continue",
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    return execute(args.batch, args.budget_seconds, env, Deps())


def execute(batch: str, budget_s: float, env: Mapping[str, str], deps: Deps) -> int:
    tax = taxonomy()
    store, record = open_batch(tax, env, batch)
    pending = [(s, p) for s, p in _frozen_events(store, record) if p.attempts[-1].render is None]
    stuck = [
        s.event_id for s, p in pending if len(p.attempts[-1].render_failures) >= MAX_RENDER_FAILURES
    ]
    todo = [(s, p) for s, p in pending if s.event_id not in stuck]
    if not todo:
        if stuck:
            raise AskOwner(_stuck_message(stuck))
        sys.stdout.write(f"render {batch}: nothing to render. Next: camera --batch {batch}\n")
        return EXIT_OK
    try:
        url = comfy_url(env, deps.get)
    except RendererUnreachable as error:
        raise AskOwner(f"{error}: the renderer is down.") from error
    status_file = flagship_file(env)
    deadline = deps.clock() + budget_s
    rendered = failed_jobs = 0
    client = ComfyClient(url, transport=deps.transport)
    try:
        for spec, prov in todo:
            if deps.clock() >= deadline:
                break
            try:
                ready = wait_for_flagship(
                    status_file, deadline=deadline, clock=deps.clock, sleep=deps.sleep, now=deps.now
                )
            except FlagshipUnknown as error:
                raise AskOwner(f"{error}.") from error
            if not ready:
                break
            done, failures = _render_one(store, spec, prov, client, deps)
            if done:
                rendered += 1
            else:
                failed_jobs += 1
                if failures >= MAX_RENDER_FAILURES:
                    stuck.append(spec.event_id)
    finally:
        client.close()
    left = len(pending) - rendered
    sys.stdout.write(
        f"render {batch}: {rendered} rendered now, {left} still to render, {failed_jobs} failed "
        f"job(s) this run (ComfyUI at {url})\n"
    )
    sys.stdout.write("Next: run render again.\n" if left else f"Next: camera --batch {batch}\n")
    if stuck:
        raise AskOwner(_stuck_message(stuck))
    return EXIT_OK


def _stuck_message(stuck: list[str]) -> str:
    return (
        f"{len(stuck)} attempt(s) failed to render {MAX_RENDER_FAILURES} times: "
        f"{', '.join(stuck)}. Their errors are in provenance.json."
    )


def _frozen_events(store: CorpusStore, record: BatchRecord) -> list[tuple[Spec, Provenance]]:
    events: list[tuple[Spec, Provenance]] = []
    unfrozen: list[str] = []
    for event_id in record.event_ids:
        spec = read(store, store.spec_file(event_id), Spec)
        path = store.provenance_file(event_id)
        if not spec.frozen or not path.exists():
            unfrozen.append(event_id)
            continue
        events.append((spec, read(store, path, Provenance)))
    if unfrozen:
        shown = ", ".join(unfrozen[:5]) + (" ..." if len(unfrozen) > 5 else "")
        raise RequestError(
            f"{len(unfrozen)} event(s) of batch {record.name} have no frozen prompt yet "
            f"({shown}); run check --batch {record.name} first"
        )
    return events


def _render_one(
    store: CorpusStore, spec: Spec, prov: Provenance, client: ComfyClient, deps: Deps
) -> tuple[bool, int]:
    """Render the event's current attempt. Returns (rendered, failures recorded for it)."""
    attempt = prov.attempts[-1]
    name = render_name(attempt.k, attempt.seed)
    path = store.event_dir(spec.event_id) / name
    seconds: float | None = None
    if path.exists():  # stored by a run that stopped before recording it: adopt it
        data = read_bytes(path)
        try:
            check_png(data)
        except ValueError as error:
            raise AskOwner(
                f"{path} exists, is not recorded, and is not a render ({error})."
            ) from error
    else:
        started = deps.clock()
        try:
            images = client.run(
                attempt_graph(spec, attempt), timeout_s=RENDER_TIMEOUT_S, sleep=deps.sleep
            )
            if len(images) != 1:
                raise ValueError(f"expected one image, got {len(images)}")
            data = images[0]
            check_png(data)
        except httpx.TransportError as error:
            _record_failure(store, prov, error)
            raise AskOwner(
                f"the renderer stopped answering ({type(error).__name__}: {error}); the guard may "
                "have stopped it."
            ) from error
        except (ComfyError, TimeoutError, httpx.HTTPStatusError, KeyError, ValueError) as error:
            return False, _record_failure(store, prov, error)
        seconds = round(deps.clock() - started, 1)
        write_new_bytes(store, path, data)
    done = attempt.updated(
        render=OutputFile(path=name, sha256=hashlib.sha256(data).hexdigest()),
        render_seconds=seconds,
        models=model_hashes(),
    )
    replace_json(
        store,
        store.provenance_file(spec.event_id),
        prov.updated(attempts=(*prov.attempts[:-1], done)),
    )
    append_index(
        store,
        [
            IndexRow(
                event_id=spec.event_id,
                batch=spec.batch,
                scenario=spec.cell.scenario,
                label=spec.label,
                status="rendered",
                time=now_iso(),
            )
        ],
    )
    return True, len(attempt.render_failures)


def _record_failure(store: CorpusStore, prov: Provenance, error: Exception) -> int:
    """Record a failed job on the current attempt; returns how many it has now."""
    attempt = prov.attempts[-1]
    failure = RenderFailure(time=now_iso(), error=f"{type(error).__name__}: {error}"[:500])
    failures = (*attempt.render_failures, failure)
    replace_json(
        store,
        store.provenance_file(prov.event_id),
        prov.updated(attempts=(*prov.attempts[:-1], attempt.updated(render_failures=failures))),
    )
    return len(failures)
```

In `synthbench/cli.py`, import `render` and set `COMMANDS = (sample, check, render)`.

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/ -q -n0 -p no:randomly`

Expected: PASS. Then run `uv run mypy synthbench/` and
`uv run ruff check synthbench/ backend/tests/unit/synthbench/`; both are clean.

- [ ] **Step 6: Commit**

```bash
F="synthbench/status.py synthbench/generate/render.py synthbench/commands/render.py synthbench/cli.py backend/tests/unit/synthbench/helpers.py backend/tests/unit/synthbench/test_render.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "feat(synthbench): render - yield to the flagship, FLUX.2 at 1280x720, resumable with a time budget

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `camera`: the Foscam camera stage

**Files:**

- Create: `synthbench/generate/camera/__init__.py`, `synthbench/generate/camera/model.py`,
  `synthbench/generate/camera/default-v1.json`, `synthbench/commands/camera.py`
- Modify: `synthbench/cli.py` (add `camera` to `COMMANDS`)
- Test: `backend/tests/unit/synthbench/test_camera.py`,
  `backend/tests/unit/synthbench/test_cli_camera.py`

**Interfaces:**

- Consumes: Task 2 (`still_name`, `OutputFile`, `Attempt.updated`); Task 3; Task 4's helpers
  (`rendered_batch`, `png`).
- Produces (`generate/camera/model.py`):
  - Parameter models: `CameraParams(id, size, jpeg_quality, distortion, noise_sigma,
ir_lighting, bloom, overlay)`, `Bloom`, `Overlay`.
  - `load_params(path=DEFAULT_PARAMS) -> CameraParams`.
  - `overlay_time(scene_time, weather, seed) -> str` (P3-R16).
  - `distort(pixels, k) -> Pixels`; `infrared(pixels, bloom) -> Pixels`.
  - `render_still(png, *, camera, lighting, overlay_text, seed, params) -> bytes` (a JPEG).
- Produces (`commands/camera.py`): `add_parser`, `run`. For each event whose current attempt
  has a render and no still, it:

  1. checks the render's sha256 (a mismatch exits 2);
  2. makes the still with the attempt's seed and writes `stills/a<k>-s<seed>.jpg`, adopting an
     identical unrecorded file and exiting 2 on a different one;
  3. records `still`, `camera_params` and `overlay_time`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_camera.py`:

```python
"""The camera stage (agent-driven design §7; parent §3.4): size, format, determinism, IR,
lens distortion and the timestamp overlay."""

from __future__ import annotations

import io
import re

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image
from synthbench.generate.camera.model import (
    distort,
    load_params,
    overlay_time,
    render_still,
)

from backend.tests.unit.synthbench import helpers as h

PARAMS = load_params()
SMALL = PARAMS.updated(size=(192, 108))  # the same stage on a small image: fast tests
STAMP = "2026-03-04 10:15:09"


def _decode(jpeg: bytes) -> NDArray[np.int16]:
    with Image.open(io.BytesIO(jpeg)) as image:
        return np.asarray(image.convert("RGB"), dtype=np.int16)


def test_the_default_still_is_a_1920x1080_jpeg() -> None:
    still = render_still(
        h.png(), camera="eave_wide", lighting="day", overlay_text=STAMP, seed=7, params=PARAMS
    )
    with Image.open(io.BytesIO(still)) as image:
        assert (image.format, image.size) == ("JPEG", (1920, 1080))


def test_the_same_inputs_give_the_same_bytes_and_other_seeds_differ() -> None:
    first = render_still(
        h.png(),
        camera="doorbell_fisheye",
        lighting="dusk",
        overlay_text=STAMP,
        seed=1,
        params=SMALL,
    )
    again = render_still(
        h.png(),
        camera="doorbell_fisheye",
        lighting="dusk",
        overlay_text=STAMP,
        seed=1,
        params=SMALL,
    )
    other = render_still(
        h.png(),
        camera="doorbell_fisheye",
        lighting="dusk",
        overlay_text=STAMP,
        seed=2,
        params=SMALL,
    )
    assert first == again
    assert first != other


def test_ir_night_is_grey() -> None:
    red = h.png(color=(200, 40, 40))
    night = _decode(
        render_still(
            red, camera="eave_wide", lighting="ir_night", overlay_text="", seed=3, params=SMALL
        )
    )
    day = _decode(
        render_still(red, camera="eave_wide", lighting="day", overlay_text="", seed=3, params=SMALL)
    )
    assert np.abs(night[..., 0] - night[..., 1]).max() <= 3
    assert np.abs(day[..., 0] - day[..., 1]).mean() > 50


def test_distortion_magnifies_the_centre_and_keeps_k_0_as_is() -> None:
    pixels = np.zeros((101, 201, 3), dtype=np.float32)
    pixels[50, 150] = 255.0  # halfway between the centre (x=100) and the right edge
    out = distort(pixels, 0.3)
    _ys, xs = np.nonzero(out[..., 0] > 20)
    assert xs.min() > 150  # pushed outward: barrel distortion magnifies the centre
    assert distort(pixels, 0.0) is pixels


def test_the_overlay_draws_only_in_the_top_left() -> None:
    plain = _decode(
        render_still(
            h.png(), camera="pole_lot", lighting="day", overlay_text="", seed=5, params=PARAMS
        )
    )
    stamped = _decode(
        render_still(
            h.png(), camera="pole_lot", lighting="day", overlay_text=STAMP, seed=5, params=PARAMS
        )
    )
    ys, xs = np.nonzero(np.abs(stamped - plain).sum(axis=2) > 60)
    assert len(ys) > 0
    assert ys.max() < 120
    assert xs.max() < 700


def test_the_default_parameters_cover_the_taxonomy() -> None:
    assert {camera.id for camera in h.TAX.cameras} <= set(PARAMS.distortion)
    assert {light.id for light in h.TAX.lighting} <= set(PARAMS.noise_sigma)
    assert set(PARAMS.ir_lighting) <= {light.id for light in h.TAX.lighting}
    assert PARAMS.id == "default-v1"


def test_an_unknown_camera_is_refused() -> None:
    with pytest.raises(ValueError, match="cover no camera"):
        render_still(h.png(), camera="drone", lighting="day", overlay_text="", seed=1, params=SMALL)


def test_overlay_times_keep_the_scene_time_and_put_snow_in_winter() -> None:
    stamp = overlay_time("20:15", "clear", 9)
    assert re.fullmatch(r"2026-\d\d-\d\d 20:15:\d\d", stamp)
    assert stamp == overlay_time("20:15", "clear", 9)
    assert {overlay_time("07:00", "snow", seed)[5:7] for seed in range(50)} <= {"12", "01", "02"}
```

`backend/tests/unit/synthbench/test_cli_camera.py`:

```python
"""`camera --batch <b>` (agent-driven design §3 step 5)."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest
from PIL import Image
from synthbench import cli
from synthbench.contract.provenance import Provenance, still_name
from synthbench.generate.camera.model import overlay_time

from backend.tests.unit.synthbench import helpers as h


def _camera(root: Path) -> int:
    return h.run(root, "camera", "--batch", "pilot-1")


def test_camera_makes_a_still_for_each_new_render(tmp_path: Path) -> None:
    specs = h.rendered_batch(tmp_path, n=2)
    assert _camera(tmp_path) == cli.EXIT_OK
    store = h.store(tmp_path)
    for spec in specs:
        attempt = store.read(store.provenance_file(spec.event_id), Provenance).attempts[-1]
        assert attempt.still is not None
        assert attempt.still.path == still_name(1, attempt.seed)
        assert attempt.camera_params == "default-v1"
        assert attempt.overlay_time == overlay_time(
            spec.scene_time, spec.cell.weather, attempt.seed
        )
        data = (store.event_dir(spec.event_id) / attempt.still.path).read_bytes()
        assert hashlib.sha256(data).hexdigest() == attempt.still.sha256
        with Image.open(io.BytesIO(data)) as image:
            assert image.size == (1920, 1080)
    assert h.run(tmp_path, "check", "--batch", "pilot-1") == cli.EXIT_OK  # sha256s verified


def test_a_rerun_makes_nothing_new(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    h.rendered_batch(tmp_path, n=1)
    assert _camera(tmp_path) == cli.EXIT_OK
    capsys.readouterr()
    assert _camera(tmp_path) == cli.EXIT_OK
    assert "0 still(s) made now" in capsys.readouterr().out


def test_a_render_that_no_longer_matches_its_sha256_stops_camera(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (spec,) = h.rendered_batch(tmp_path, n=1)
    store = h.store(tmp_path)
    attempt = store.read(store.provenance_file(spec.event_id), Provenance).attempts[-1]
    assert attempt.render is not None
    (store.event_dir(spec.event_id) / attempt.render.path).write_bytes(h.png(color=(0, 0, 0)))
    assert _camera(tmp_path) == cli.EXIT_ASK
    assert "does not match its recorded sha256" in capsys.readouterr().err


def test_camera_waits_for_renders(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    h.frozen_batch(tmp_path, n=2)
    assert _camera(tmp_path) == cli.EXIT_OK
    assert "0 still(s) made now; 2 attempt(s) still await a render" in capsys.readouterr().out
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_camera.py backend/tests/unit/synthbench/test_cli_camera.py -q -n0 -p no:randomly`

Expected: FAIL with `ModuleNotFoundError: No module named 'synthbench.generate.camera'`.

- [ ] **Step 3: Implement the stage**

`synthbench/generate/camera/__init__.py`:

```python
"""The camera stage: a render becomes what a Foscam camera uploads (agent-driven design §7)."""
```

`synthbench/generate/camera/default-v1.json`:

```json
{
  "id": "default-v1",
  "size": [1920, 1080],
  "jpeg_quality": 80,
  "distortion": {
    "doorbell_fisheye": 0.35,
    "eave_wide": 0.12,
    "garage_mounted": 0.08,
    "pole_lot": 0.05,
    "indoor_corner": 0.12
  },
  "noise_sigma": {
    "day": 2.0,
    "golden_hour": 2.5,
    "dusk": 4.0,
    "ir_night": 6.0,
    "porch_lit_night": 5.0
  },
  "ir_lighting": ["ir_night"],
  "bloom": { "threshold": 215, "radius": 9, "strength": 0.35 },
  "overlay": { "font_px": 34, "x": 24, "y": 20, "stroke_px": 2 }
}
```

`synthbench/generate/camera/model.py`:

```python
"""The camera stage (agent-driven design §7; parent spec §3.4).

A 1280x720 render becomes a 1920x1080 JPEG like a Foscam still: a Lanczos resize, per-camera
barrel distortion, IR-night grey and bloom, sensor noise, the timestamp overlay, and JPEG. The
same render, camera, lighting, overlay text, seed and parameters give the same bytes.

The parameters are committed defaults (default-v1.json) until `camera calibrate` fits them to
the owner's footage (parent D13; plan ruling P3-R3). Each still records the set's id.
"""

from __future__ import annotations

import io
import math
import random
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw, ImageFont
from pydantic import Field

from synthbench.contract.common import ContractModel

DEFAULT_PARAMS = Path(__file__).resolve().parent / "default-v1.json"
_LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)

Pixels = NDArray[np.float32]


class Bloom(ContractModel):
    threshold: float = Field(ge=0, le=255)
    radius: float = Field(gt=0)
    strength: float = Field(ge=0)


class Overlay(ContractModel):
    font_px: int = Field(ge=8)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    stroke_px: int = Field(ge=0)


class CameraParams(ContractModel):
    id: str
    size: tuple[int, int]
    jpeg_quality: int = Field(ge=1, le=95)
    distortion: dict[str, float]  # barrel k per camera type (taxonomy camera ids)
    noise_sigma: dict[str, float]  # sensor noise per lighting id, on the 0-255 scale
    ir_lighting: tuple[str, ...]  # lighting ids the camera sees in infrared
    bloom: Bloom
    overlay: Overlay


def load_params(path: Path = DEFAULT_PARAMS) -> CameraParams:
    return CameraParams.model_validate_json(path.read_text(encoding="utf-8"))


def overlay_time(scene_time: str, weather: str, seed: int) -> str:
    """The timestamp the stage draws (plan ruling P3-R16): the spec's HH:MM on a seeded 2026
    date, with seeded seconds; snow falls in December to February."""
    rng = random.Random(seed)  # noqa: S311  # reproducible, not security
    month = rng.choice((12, 1, 2)) if weather == "snow" else rng.randint(1, 12)
    day = rng.randint(1, 28)
    return f"2026-{month:02d}-{day:02d} {scene_time}:{rng.randrange(60):02d}"


def distort(pixels: Pixels, k: float) -> Pixels:
    """Barrel distortion: the corners stay put and the centre is magnified by 1 + k."""
    if k == 0:
        return pixels
    height, width = pixels.shape[:2]
    ys, xs = np.indices((height, width), dtype=np.float32)
    cx, cy = (width - 1) / 2, (height - 1) / 2
    norm = math.hypot(cx, cy)
    dx, dy = (xs - cx) / norm, (ys - cy) / norm
    scale = (1 + k * (dx * dx + dy * dy)) / (1 + k)
    map_x = (cx + dx * scale * norm).astype(np.float32)
    map_y = (cy + dy * scale * norm).astype(np.float32)
    warped = cv2.remap(
        pixels, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
    )
    return np.asarray(warped, dtype=np.float32)


def infrared(pixels: Pixels, bloom: Bloom) -> Pixels:
    """IR night: grey from luma, with a glow around the brightest areas."""
    luma = pixels @ _LUMA
    bright = np.clip(luma - bloom.threshold, 0, None)
    glow = np.asarray(cv2.GaussianBlur(bright, (0, 0), bloom.radius), dtype=np.float32)
    luma = np.clip(luma + bloom.strength * glow, 0, 255)
    return np.repeat(luma[..., None], 3, axis=2).astype(np.float32)


def render_still(
    png: bytes, *, camera: str, lighting: str, overlay_text: str, seed: int, params: CameraParams
) -> bytes:
    """The Foscam-style JPEG still for one render."""
    if camera not in params.distortion or lighting not in params.noise_sigma:
        raise ValueError(
            f"camera parameters {params.id} cover no camera {camera!r} or lighting {lighting!r}"
        )
    with Image.open(io.BytesIO(png)) as source:
        image = source.convert("RGB").resize(params.size, Image.Resampling.LANCZOS)
    pixels = distort(np.asarray(image, dtype=np.float32), params.distortion[camera])
    infrared_night = lighting in params.ir_lighting
    if infrared_night:
        pixels = infrared(pixels, params.bloom)
    height, width = pixels.shape[:2]
    channels = 1 if infrared_night else 3  # one noise plane keeps IR grey
    noise = np.random.default_rng(seed).normal(
        0.0, params.noise_sigma[lighting], (height, width, channels)
    )
    still = Image.fromarray(np.clip(pixels + noise, 0, 255).astype(np.uint8))
    if overlay_text:
        _draw_overlay(still, overlay_text, params.overlay)
    out = io.BytesIO()
    still.save(out, "JPEG", quality=params.jpeg_quality, subsampling="4:2:0")
    return out.getvalue()


def _draw_overlay(image: Image.Image, text: str, overlay: Overlay) -> None:
    """White text with a dark outline in the top-left corner, as Foscam draws it [A]."""
    font = ImageFont.load_default(size=overlay.font_px)
    ImageDraw.Draw(image).text(
        (overlay.x, overlay.y),
        text,
        font=font,
        fill=(255, 255, 255),
        stroke_width=overlay.stroke_px,
        stroke_fill=(0, 0, 0),
    )
```

- [ ] **Step 4: Implement the command**

`synthbench/commands/camera.py`:

```python
"""`camera --batch <b>`: a Foscam-style still for each new render (design §3 step 5, §7)."""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Mapping

from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    Parser,
    batch_name,
    open_batch,
    read,
    read_bytes,
    replace_json,
    taxonomy,
    write_new_bytes,
)
from synthbench.contract.provenance import OutputFile, Provenance, still_name
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.generate.camera.model import CameraParams, load_params, overlay_time, render_still


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "camera",
        help="turn each new 1280x720 render into a 1920x1080 Foscam-style JPEG still",
        allow_abbrev=False,
    )
    parser.add_argument("--batch", type=batch_name, required=True, help="batch name")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_batch(tax, env, args.batch)
    params = load_params()
    made = waiting = 0
    for event_id in record.event_ids:
        spec = read(store, store.spec_file(event_id), Spec)
        path = store.provenance_file(event_id)
        if not spec.frozen or not path.exists():
            continue
        prov = read(store, path, Provenance)
        attempt = prov.attempts[-1]
        if attempt.render is None:
            waiting += 1
        elif attempt.still is None:
            _make_still(store, spec, prov, params)
            made += 1
    sys.stdout.write(
        f"camera {record.name}: {made} still(s) made now; {waiting} attempt(s) still await a "
        "render\n"
    )
    if made:
        sys.stdout.write(
            "Next: open every new still, add its verdict to triage.jsonl, then triage.\n"
        )
    return EXIT_OK


def _make_still(store: CorpusStore, spec: Spec, prov: Provenance, params: CameraParams) -> None:
    attempt = prov.attempts[-1]
    assert attempt.render is not None
    event_dir = store.event_dir(spec.event_id)
    render_file = event_dir / attempt.render.path
    data = read_bytes(render_file)
    if hashlib.sha256(data).hexdigest() != attempt.render.sha256:
        raise AskOwner(f"{render_file} does not match its recorded sha256.")
    stamp = overlay_time(spec.scene_time, spec.cell.weather, attempt.seed)
    try:
        still = render_still(
            data,
            camera=spec.cell.camera,
            lighting=spec.cell.lighting,
            overlay_text=stamp,
            seed=attempt.seed,
            params=params,
        )
    except Exception as error:  # any stage failure on a verified render is the owner's to see
        raise AskOwner(
            f"the camera stage failed on {render_file} ({type(error).__name__}: {error})."
        ) from error
    name = still_name(attempt.k, attempt.seed)
    target = event_dir / name
    if target.exists():  # stored by a run that stopped before recording it
        if read_bytes(target) != still:
            raise AskOwner(
                f"{target} exists, is not recorded, and differs from what the camera stage makes now."
            )
    else:
        write_new_bytes(store, target, still)
    done = attempt.updated(
        still=OutputFile(path=name, sha256=hashlib.sha256(still).hexdigest()),
        camera_params=params.id,
        overlay_time=stamp,
    )
    replace_json(
        store,
        store.provenance_file(spec.event_id),
        prov.updated(attempts=(*prov.attempts[:-1], done)),
    )
```

In `synthbench/cli.py`, import `camera` and set `COMMANDS = (sample, check, render, camera)`.

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/ -q -n0 -p no:randomly --durations=5`

Expected: PASS, with no test over 2 s in `--durations`. A slower camera test needs `SMALL`
parameters, not a longer timeout. Then run `uv run mypy synthbench/` and
`uv run ruff check synthbench/ backend/tests/unit/synthbench/`; both are clean.

- [ ] **Step 6: Commit**

```bash
F="synthbench/generate/camera/__init__.py synthbench/generate/camera/model.py synthbench/generate/camera/default-v1.json synthbench/commands/camera.py synthbench/cli.py backend/tests/unit/synthbench/test_camera.py backend/tests/unit/synthbench/test_cli_camera.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "feat(synthbench): camera stage - 1920x1080 Foscam-style stills from the 1280x720 renders

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `triage`: verdicts, limits and rerolls

**Files:**

- Create: `synthbench/commands/triage.py`
- Modify: `synthbench/cli.py` (add `triage` to `COMMANDS`)
- Test: `backend/tests/unit/synthbench/test_cli_triage.py`

**Interfaces:**

- Consumes: Task 2 (`TriageRow`, `Attempt`, `attempt_seed`, `MAX_ATTEMPTS`); Task 3; Task 4's
  helpers (`stilled_batch`, `rendered_batch`, `record_output`).
- Produces: `REROLL_SHARE = 0.10`, `reroll_allowance(n) -> int`, `add_parser`, `run`.
  Behaviour, for each event in batch order whose current attempt has a still, no verdict, and a
  row for its `k`:

  - `ok`: the event becomes `ready`.
  - `reroll` after an earlier triage reroll, or at `MAX_ATTEMPTS`: `failed`.
  - `reroll` once the batch has used its `floor(n / 10)` triage rerolls: `failed` (over the
    cap), and the run exits 2.
  - Any other `reroll`: attempt `k + 1` gets `attempt_seed(event, k + 1)` and the same
    `prompt_sha256`, and the event becomes `rerolled`.

  Rows that break the file's rules exit 1 and record nothing: a bad row, an unknown event, a
  duplicate `(event, k)`, an attempt that does not exist, a verdict on an attempt with no still,
  or a changed verdict (a verdict is final).

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_cli_triage.py`:

```python
"""`triage --batch <b>` (agent-driven design §3 step 7, §4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from synthbench import cli
from synthbench.commands.triage import reroll_allowance
from synthbench.contract.provenance import Provenance, attempt_seed
from synthbench.contract.spec import Spec

from backend.tests.unit.synthbench import helpers as h


def _verdicts(root: Path, rows: list[dict[str, Any]]) -> None:
    path = h.store(root).batch_dir("pilot-1") / "triage.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _ok(spec: Spec, k: int = 1) -> dict[str, Any]:
    return {"event_id": spec.event_id, "k": k, "verdict": "ok"}


def _reroll(spec: Spec, reason: str, k: int = 1) -> dict[str, Any]:
    return {"event_id": spec.event_id, "k": k, "verdict": "reroll", "reason": reason}


def _triage(root: Path) -> int:
    return h.run(root, "triage", "--batch", "pilot-1")


def _prov(root: Path, spec: Spec) -> Provenance:
    store = h.store(root)
    return store.read(store.provenance_file(spec.event_id), Provenance)


def _status(root: Path, spec: Spec) -> str:
    return h.store(root).latest_index()[spec.event_id].status


def test_the_allowance_is_a_tenth_of_the_batch_rounded_down() -> None:
    assert [reroll_allowance(n) for n in (5, 9, 10, 19, 50, 500)] == [0, 0, 1, 1, 5, 50]


def test_ok_verdicts_make_events_ready(tmp_path: Path) -> None:
    specs = h.stilled_batch(tmp_path, n=2)
    _verdicts(tmp_path, [_ok(spec) for spec in specs])
    assert _triage(tmp_path) == cli.EXIT_OK
    for spec in specs:
        (attempt,) = _prov(tmp_path, spec).attempts
        assert attempt.triage is not None
        assert attempt.triage.verdict == "ok"
        assert _status(tmp_path, spec) == "ready"


def test_a_reroll_schedules_attempt_2_with_its_own_seed(tmp_path: Path) -> None:
    specs = h.stilled_batch(tmp_path, n=10)
    _verdicts(tmp_path, [_reroll(specs[0], "blank"), *(_ok(s) for s in specs[1:])])
    assert _triage(tmp_path) == cli.EXIT_OK
    first, second = _prov(tmp_path, specs[0]).attempts
    assert first.triage is not None
    assert first.triage.reason == "blank"
    assert (second.k, second.seed) == (2, attempt_seed(specs[0].event_id, 2))
    assert second.prompt_sha256 == first.prompt_sha256
    assert second.render is None
    assert _status(tmp_path, specs[0]) == "rerolled"


def test_a_second_triage_failure_fails_the_event(tmp_path: Path) -> None:
    specs = h.stilled_batch(tmp_path, n=10)
    rows = [_reroll(specs[0], "blank")]
    _verdicts(tmp_path, rows)
    assert _triage(tmp_path) == cli.EXIT_OK
    h.record_output(tmp_path, specs[0], render=b"png 2", still=b"jpeg 2")
    _verdicts(tmp_path, [*rows, _reroll(specs[0], "broken_anatomy", k=2)])
    assert _triage(tmp_path) == cli.EXIT_OK
    assert len(_prov(tmp_path, specs[0]).attempts) == 2
    assert _status(tmp_path, specs[0]) == "failed"


def test_rerolls_past_the_cap_fail_their_events_and_stop(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.stilled_batch(tmp_path, n=10)  # one triage reroll allowed
    _verdicts(tmp_path, [_reroll(spec, "no_person") for spec in specs[:3]])
    assert _triage(tmp_path) == cli.EXIT_ASK
    err = capsys.readouterr().err
    assert "exceed 10%" in err
    assert specs[1].event_id in err
    assert specs[2].event_id in err
    assert len(_prov(tmp_path, specs[0]).attempts) == 2
    for spec in specs[1:3]:
        assert len(_prov(tmp_path, spec).attempts) == 1
        assert _status(tmp_path, spec) == "failed"


def test_verdicts_are_final(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    specs = h.stilled_batch(tmp_path, n=2)
    _verdicts(tmp_path, [_ok(specs[0])])
    assert _triage(tmp_path) == cli.EXIT_OK
    _verdicts(tmp_path, [_reroll(specs[0], "blank")])
    assert _triage(tmp_path) == cli.EXIT_ERROR
    assert "a verdict is final" in capsys.readouterr().err


def test_a_verdict_needs_a_still(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (spec,) = h.rendered_batch(tmp_path, n=1)
    _verdicts(tmp_path, [_ok(spec)])
    assert _triage(tmp_path) == cli.EXIT_ERROR
    assert "has no still yet" in capsys.readouterr().err


def test_bad_lines_are_the_agents_to_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.stilled_batch(tmp_path, n=2)
    path = h.store(tmp_path).batch_dir("pilot-1") / "triage.jsonl"
    lines = [
        json.dumps(_reroll(specs[0], "cannot_see_the_knife")),
        json.dumps({"event_id": "B-other-000", "k": 1, "verdict": "ok"}),
        json.dumps(_ok(specs[1])),
        json.dumps(_reroll(specs[1], "blank")),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert _triage(tmp_path) == cli.EXIT_ERROR
    err = capsys.readouterr().err
    assert "line 1: not a triage row" in err
    assert "line 2: B-other-000 is not in batch pilot-1" in err
    assert f"line 4: a second row for {specs[1].event_id} attempt 1" in err
    assert _prov(tmp_path, specs[1]).attempts[0].triage is None  # nothing recorded


def test_a_verdict_on_a_missing_attempt_records_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.stilled_batch(tmp_path, n=2)
    _verdicts(tmp_path, [_ok(specs[0]), _ok(specs[1], k=3)])
    assert _triage(tmp_path) == cli.EXIT_ERROR
    assert f"{specs[1].event_id}: attempt 3 does not exist" in capsys.readouterr().err
    assert _prov(tmp_path, specs[0]).attempts[0].triage is None  # all or nothing


def test_the_summary_counts_stills_awaiting_verdicts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.stilled_batch(tmp_path, n=3)
    _verdicts(tmp_path, [_ok(specs[0])])
    assert _triage(tmp_path) == cli.EXIT_OK
    assert "2 still(s) await a verdict" in capsys.readouterr().out
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_cli_triage.py -q -n0 -p no:randomly`

Expected: FAIL with `ModuleNotFoundError: No module named 'synthbench.commands.triage'`.

- [ ] **Step 3: Implement**

`synthbench/commands/triage.py`:

```python
"""`triage --batch <b>`: record the agent's verdicts and schedule rerolls (design §3 step 7, §4).

The agent may reroll only for a listed mechanical reason, once per event. A second triage
failure fails the event. A batch may schedule at most floor(n / 10) triage rerolls; a reroll
verdict past that fails its event and stops the run (plan ruling P3-R11). Nothing is deleted.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from collections.abc import Mapping

from pydantic import ValidationError

from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    Parser,
    RequestError,
    append_index,
    batch_name,
    now_iso,
    open_batch,
    read,
    replace_json,
    taxonomy,
)
from synthbench.contract.corpus import BatchRecord, EventStatus, IndexRow, TriageRow
from synthbench.contract.provenance import MAX_ATTEMPTS, Attempt, Provenance, attempt_seed
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore

REROLL_SHARE = 0.10  # design §4: triage rerolls may not exceed 10% of a batch's events

Rows = dict[tuple[str, int], TriageRow]


def reroll_allowance(n: int) -> int:
    """Triage rerolls a batch of n events may schedule over its lifetime."""
    return math.floor(n * REROLL_SHARE + 1e-9)


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "triage",
        help="record triage.jsonl verdicts; schedule the allowed rerolls",
        allow_abbrev=False,
    )
    parser.add_argument("--batch", type=batch_name, required=True, help="batch name")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_batch(tax, env, args.batch)
    specs = {e: read(store, store.spec_file(e), Spec) for e in record.event_ids}
    provs = {
        e: read(store, store.provenance_file(e), Provenance)
        for e in record.event_ids
        if store.provenance_file(e).exists()
    }
    rows = _rows(store, record)
    _validate(rows, provs)
    allowance = reroll_allowance(record.n)
    scheduled = sum(1 for prov in provs.values() if _rerolled_before(prov))
    counts: Counter[str] = Counter()
    over_cap: list[str] = []
    index_rows: list[IndexRow] = []
    for event_id in record.event_ids:
        prov = provs.get(event_id)
        if prov is None:
            continue
        attempt = prov.attempts[-1]
        row = rows.get((event_id, attempt.k))
        if row is None or attempt.triage is not None:
            continue
        verdict = row.triage()
        attempts = [*prov.attempts[:-1], attempt.updated(triage=verdict)]
        status: EventStatus
        if verdict.verdict == "ok":
            status = "ready"
        elif _rerolled_before(prov) or len(prov.attempts) >= MAX_ATTEMPTS:
            status = "failed"
        elif scheduled >= allowance:
            status = "failed"
            over_cap.append(event_id)
        else:
            k = attempt.k + 1
            attempts.append(
                Attempt(k=k, seed=attempt_seed(event_id, k), prompt_sha256=attempt.prompt_sha256)
            )
            scheduled += 1
            status = "rerolled"
        counts[status] += 1
        provs[event_id] = prov.updated(attempts=tuple(attempts))
        replace_json(store, store.provenance_file(event_id), provs[event_id])
        spec = specs[event_id]
        index_rows.append(
            IndexRow(
                event_id=event_id,
                batch=record.name,
                scenario=spec.cell.scenario,
                label=spec.label,
                status=status,
                time=now_iso(),
            )
        )
    append_index(store, index_rows)
    awaiting = sum(
        1
        for p in provs.values()
        if p.attempts[-1].still is not None and p.attempts[-1].triage is None
    )
    sys.stdout.write(
        f"triage {record.name}: {counts['ready']} ready, {counts['rerolled']} reroll(s) scheduled, "
        f"{counts['failed']} failed now; {awaiting} still(s) await a verdict; triage rerolls used "
        f"{scheduled} of {allowance}\n"
    )
    if counts["rerolled"]:
        sys.stdout.write("Next: render, camera and triage again for the rerolls (attempt 2).\n")
    if over_cap:
        raise AskOwner(
            f"triage rerolls in batch {record.name} would exceed 10% of its {record.n} events "
            f"({allowance} allowed, all used). These events are now failed, their verdicts "
            f"recorded: {', '.join(over_cap)}."
        )
    return EXIT_OK


def _rerolled_before(prov: Provenance) -> bool:
    """Triage already rerolled this event: an earlier attempt has a reroll verdict."""
    return any(a.triage is not None and a.triage.verdict == "reroll" for a in prov.attempts[:-1])


def _rows(store: CorpusStore, record: BatchRecord) -> Rows:
    path = store.batch_dir(record.name) / "triage.jsonl"
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RequestError(f"cannot read {path} ({type(error).__name__}); rewrite it") from error
    rows: Rows = {}
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = TriageRow.model_validate_json(line)
        except ValidationError as error:
            problems.append(f"line {number}: not a triage row ({error.errors()[0]['msg']})")
            continue
        key = (row.event_id, row.k)
        if row.event_id not in record.event_ids:
            problems.append(f"line {number}: {row.event_id} is not in batch {record.name}")
        elif key in rows:
            problems.append(f"line {number}: a second row for {row.event_id} attempt {row.k}")
        else:
            rows[key] = row
    if problems:
        raise RequestError(f"{path}:\n  " + "\n  ".join(problems))
    return rows


def _validate(rows: Rows, provs: Mapping[str, Provenance]) -> None:
    problems: list[str] = []
    for (event_id, k), row in sorted(rows.items()):
        prov = provs.get(event_id)
        if prov is None or k > len(prov.attempts):
            problems.append(f"{event_id}: attempt {k} does not exist")
            continue
        attempt = prov.attempts[k - 1]
        if attempt.triage is not None:
            if attempt.triage != row.triage():
                problems.append(
                    f"{event_id}: attempt {k} was recorded as {attempt.triage.verdict}; a verdict "
                    "is final"
                )
        elif attempt.still is None:
            problems.append(
                f"{event_id}: attempt {k} has no still yet; run render and camera, then look at it"
            )
    if problems:
        raise RequestError(
            "triage.jsonl names verdicts triage cannot record; fix them and run triage again:\n  "
            + "\n  ".join(problems)
        )
```

In `synthbench/cli.py`, import `triage` and set
`COMMANDS = (sample, check, render, camera, triage)`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/ -q -n0 -p no:randomly`

Expected: PASS. Then run `uv run mypy synthbench/` and
`uv run ruff check synthbench/ backend/tests/unit/synthbench/`; both are clean.

- [ ] **Step 5: Commit**

```bash
F="synthbench/commands/triage.py synthbench/cli.py backend/tests/unit/synthbench/test_cli_triage.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "feat(synthbench): triage - final verdicts, one reroll per event, a 10% batch cap

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `report`: report.md and sheet.html

**Files:**

- Create: `synthbench/commands/report.py`
- Modify: `synthbench/cli.py` (add `report` to `COMMANDS`)
- Test: `backend/tests/unit/synthbench/test_cli_report.py`

**Interfaces:**

- Consumes: Task 3; Task 5's `SnapshotStatus`, `SnapshotHold`, `snapshots_file`,
  `read_status`, `write_status`; Task 7's statuses.
- Produces:

  - `STATES` (in report order).
  - `event_state(spec, prov, status) -> str`.
  - `Event(spec, prov, state)`.
  - `markdown(record, events, snapshots, generated) -> str`; `sheet(record, events) -> str`.
  - `add_parser`, `run`. `run` rewrites `batches/<b>/report.md` and `sheet.html` (the design's
    §3 step 8 contents).

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_cli_report.py`:

```python
"""`report --batch <b>` (agent-driven design §3 step 8)."""

from __future__ import annotations

import json
from pathlib import Path

from synthbench import cli
from synthbench.commands import report
from synthbench.contract.corpus import BatchRecord
from synthbench.contract.provenance import Provenance
from synthbench.status import SnapshotHold, SnapshotStatus, snapshots_file, write_status

from backend.tests.unit.synthbench import helpers as h


def _report(root: Path) -> str:
    assert h.run(root, "report", "--batch", "pilot-1") == cli.EXIT_OK
    return (h.store(root).batch_dir("pilot-1") / "report.md").read_text(encoding="utf-8")


def _verdicts(root: Path, rows: list[dict[str, object]]) -> None:
    path = h.store(root).batch_dir("pilot-1") / "triage.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_the_report_counts_states_reasons_and_timing(tmp_path: Path) -> None:
    specs = h.stilled_batch(tmp_path, n=10)  # one triage reroll allowed
    rows: list[dict[str, object]] = [
        {"event_id": specs[0].event_id, "k": 1, "verdict": "reroll", "reason": "blank"},
        {"event_id": specs[1].event_id, "k": 1, "verdict": "reroll", "reason": "no_person"},
    ]
    rows += [{"event_id": s.event_id, "k": 1, "verdict": "ok"} for s in specs[2:9]]
    _verdicts(tmp_path, rows)
    assert h.run(tmp_path, "triage", "--batch", "pilot-1") == cli.EXIT_ASK  # specs[1]: over the cap
    text = _report(tmp_path)
    assert "| ready | 7 |" in text
    assert "| awaiting render | 1 |" in text  # specs[0], attempt 2
    assert "| failed | 1 |" in text  # specs[1]
    assert "| awaiting verdict | 1 |" in text  # specs[9]
    assert "| blank | 1 |" in text
    assert "| no_person | 1 |" in text
    assert "10 image(s) rendered: median 8.0 s" in text
    assert "No snapshot status yet" in text
    assert f"| {specs[1].event_id} | {specs[1].cell.scenario} | no_person |" in text


def test_the_sheet_links_each_still(tmp_path: Path) -> None:
    specs = h.stilled_batch(tmp_path, n=2)
    _report(tmp_path)
    html = (h.store(tmp_path).batch_dir("pilot-1") / "sheet.html").read_text(encoding="utf-8")
    store = h.store(tmp_path)
    for spec in specs:
        still = store.read(store.provenance_file(spec.event_id), Provenance).attempts[-1].still
        assert still is not None
        assert f'src="../../events/B/{spec.event_id}/{still.path}"' in html


def test_the_sheet_escapes_prompts(tmp_path: Path) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)
    store = h.store(tmp_path)
    record = store.read(store.batch_file("pilot-1"), BatchRecord)
    odd = spec.updated(prompt="a man & a <b>dog</b>")
    html = report.sheet(record, [report.Event(odd, None, "not prompted")])
    assert "a man &amp; a &lt;b&gt;dog&lt;/b&gt;" in html
    assert "<b>dog</b>" not in html


def test_the_report_shows_a_snapshot_hold_and_can_be_rewritten(tmp_path: Path) -> None:
    h.stilled_batch(tmp_path, n=1)
    name = "primary/export/synthbench/corpus@synthbench-20260928T000000Z"
    hold = SnapshotHold(snapshot=name, count=2, paths=("/synthbench/corpus/x.png",))
    write_status(
        snapshots_file(h.env(tmp_path)), SnapshotStatus(time=h.NOW, snapshots=6, hold=hold)
    )
    assert f"**Held:** `{name}`" in _report(tmp_path)
    assert "**Held:**" in _report(tmp_path)  # a second run replaces the views
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_cli_report.py -q -n0 -p no:randomly`

Expected: FAIL with `ImportError: cannot import name 'report'`.

- [ ] **Step 3: Implement**

`synthbench/commands/report.py`:

```python
"""`report --batch <b>`: report.md and sheet.html for the owner (design §3 step 8).

report.md has counts by state, rerolls by reason, failed events, render timing and snapshot
holds. sheet.html is a contact sheet of every event's current still, opened from the corpus on
the host. Both are views: every run replaces them.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path

from pydantic import ValidationError

from synthbench.commands.common import (
    EXIT_OK,
    Parser,
    batch_name,
    now_iso,
    open_batch,
    read,
    read_index,
    replace_text,
    taxonomy,
)
from synthbench.contract.corpus import BatchRecord
from synthbench.contract.provenance import Provenance
from synthbench.contract.spec import Spec
from synthbench.status import SnapshotStatus, read_status, snapshots_file

STATES = (
    "not prompted",
    "awaiting render",
    "awaiting still",
    "awaiting verdict",
    "ready",
    "failed",
)


def event_state(spec: Spec, prov: Provenance | None, status: str | None) -> str:
    if not spec.frozen or prov is None:
        return "not prompted"
    if status == "failed":
        return "failed"
    last = prov.attempts[-1]
    if last.render is None:
        return "awaiting render"
    if last.still is None:
        return "awaiting still"
    if last.triage is None:
        return "awaiting verdict"
    return "ready" if last.triage.verdict == "ok" else "failed"


@dataclass(frozen=True)
class Event:
    spec: Spec
    prov: Provenance | None
    state: str


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "report", help="write the batch's report.md and sheet.html", allow_abbrev=False
    )
    parser.add_argument("--batch", type=batch_name, required=True, help="batch name")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_batch(tax, env, args.batch)
    index = read_index(store)
    events: list[Event] = []
    for event_id in record.event_ids:
        spec = read(store, store.spec_file(event_id), Spec)
        path = store.provenance_file(event_id)
        prov = read(store, path, Provenance) if path.exists() else None
        row = index.get(event_id)
        events.append(Event(spec, prov, event_state(spec, prov, row.status if row else None)))
    folder = store.batch_dir(record.name)
    replace_text(
        store,
        folder / "report.md",
        markdown(record, events, _snapshot_note(snapshots_file(env)), now_iso()),
    )
    replace_text(store, folder / "sheet.html", sheet(record, events))
    states = Counter(event.state for event in events)
    summary = ", ".join(f"{state} {states[state]}" for state in STATES if states[state])
    sys.stdout.write(
        f"report {record.name}: {summary}\n  {folder / 'report.md'}\n  {folder / 'sheet.html'}\n"
    )
    return EXIT_OK


def _snapshot_note(path: Path) -> str:
    if not path.exists():
        return "No snapshot status yet: the snapshot timer has not run."
    try:
        status = read_status(path, SnapshotStatus)
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        return f"Cannot read {path} ({type(error).__name__})."
    if status.hold is None:
        return f"None. {status.snapshots} snapshot(s) kept as of {status.time:%Y-%m-%d %H:%M} UTC."
    hold = status.hold
    paths = "\n".join(f"- `{p}`" for p in hold.paths)
    return (
        f"**Held:** `{hold.snapshot}` holds the only copy of {hold.count} removed or changed "
        f"file(s); the owner resolves it (operator runbook). First paths:\n\n{paths}"
    )


def _still_link(spec: Spec, prov: Provenance | None) -> str | None:
    """A still's path relative to batches/<b>/, where the views live."""
    still = prov.attempts[-1].still if prov else None
    if still is None:
        return None
    return f"../../events/{spec.event_id[0]}/{spec.event_id}/{still.path}"


def markdown(record: BatchRecord, events: Sequence[Event], snapshots: str, generated: str) -> str:
    states = Counter(event.state for event in events)
    attempts = [a for event in events if event.prov for a in event.prov.attempts]
    reasons = Counter(a.triage.reason for a in attempts if a.triage and a.triage.reason)
    failed = [event for event in events if event.state == "failed"]
    seconds = sorted(a.render_seconds for a in attempts if a.render_seconds is not None)
    job_failures = [
        (event.spec.event_id, failure)
        for event in events
        if event.prov
        for a in event.prov.attempts
        for failure in a.render_failures
    ]
    only = f", only {', '.join(record.only)}" if record.only else ""
    lines = [
        f"# Batch {record.name} (corpus {record.version})",
        "",
        f"Generated {generated} by `python -m synthbench report`: {record.n} events, sampler "
        f"seed {record.seed}{only}.",
        "",
        "## Progress",
        "",
        "| State | Events |",
        "| --- | ---: |",
        *(f"| {state} | {states[state]} |" for state in STATES),
        "",
        "## Rerolls by reason",
        "",
    ]
    if reasons:
        lines += ["| Reason | Verdicts |", "| --- | ---: |"]
        lines += [f"| {reason} | {count} |" for reason, count in sorted(reasons.items())]
    else:
        lines.append("None.")
    lines += ["", "## Failed events", ""]
    if failed:
        lines += ["| Event | Scenario | Reroll reasons |", "| --- | --- | --- |"]
        for event in failed:
            assert event.prov is not None
            why = ", ".join(
                a.triage.reason for a in event.prov.attempts if a.triage and a.triage.reason
            )
            lines.append(f"| {event.spec.event_id} | {event.spec.cell.scenario} | {why} |")
        by_scenario = Counter(event.spec.cell.scenario for event in failed)
        lines += [
            "",
            "Failed by scenario: "
            + ", ".join(f"{s} {c}" for s, c in sorted(by_scenario.items()))
            + ".",
        ]
    else:
        lines.append("None.")
    lines += ["", "## Render timing", ""]
    if seconds:
        p90 = seconds[int(0.9 * (len(seconds) - 1))]
        lines.append(
            f"{len(seconds)} image(s) rendered: median {statistics.median(seconds):.1f} s, "
            f"p90 {p90:.1f} s, total {sum(seconds) / 60:.1f} min."
        )
    else:
        lines.append("No image rendered yet.")
    lines.append(f"Failed render jobs: {len(job_failures)}.")
    lines += [f"- {event_id}: {failure.error}" for event_id, failure in job_failures[:20]]
    lines += ["", "## Snapshot holds", "", snapshots, "", "## Events", ""]
    lines += [
        "| Event | Scenario | Label | Lighting | Weather | Attempt | State | Still |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for event in events:
        spec = event.spec
        k = event.prov.attempts[-1].k if event.prov else 0
        link = _still_link(spec, event.prov)
        still = f"[still]({link})" if link else "-"
        lines.append(
            f"| {spec.event_id} | {spec.cell.scenario} | {spec.label} | {spec.cell.lighting} | "
            f"{spec.cell.weather} | {k} | {event.state} | {still} |"
        )
    return "\n".join(lines) + "\n"


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font: 14px system-ui, sans-serif; margin: 16px; background: #111; color: #ddd; }}
main {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(480px, 1fr)); gap: 12px; }}
figure {{ margin: 0; background: #1c1c1c; padding: 8px; border-left: 4px solid #555; }}
figure.ready {{ border-color: #3a3; }}
figure.failed {{ border-color: #c33; }}
figure.awaiting-verdict {{ border-color: #ca3; }}
img {{ width: 100%; height: auto; }}
.none {{ padding: 40px; text-align: center; color: #777; }}
</style></head><body><h1>{title}</h1><main>
{cards}
</main></body></html>
"""


def sheet(record: BatchRecord, events: Sequence[Event]) -> str:
    cards: list[str] = []
    for event in events:
        spec = event.spec
        last = event.prov.attempts[-1] if event.prov else None
        link = _still_link(spec, event.prov)
        image = (
            f'<img src="{escape(link)}" loading="lazy" alt="{escape(spec.event_id)}">'
            if link
            else '<div class="none">no still yet</div>'
        )
        verdict = "no verdict"
        if last is not None and last.triage is not None:
            verdict = last.triage.verdict + (
                f" ({last.triage.reason})" if last.triage.reason else ""
            )
        caption = (
            f"<b>{escape(spec.event_id)}</b> {escape(spec.cell.scenario)} - {escape(spec.label)} - "
            f"{escape(spec.cell.lighting)}, {escape(spec.cell.weather)} - attempt "
            f"{last.k if last else 0} - {escape(event.state)} - {escape(verdict)}"
            f"<br>{escape(spec.prompt or '')}"
        )
        css = escape(event.state.replace(" ", "-"))
        cards.append(f'<figure class="{css}">{image}<figcaption>{caption}</figcaption></figure>')
    title = escape(f"Batch {record.name} ({record.version})")
    return _HTML.format(title=title, cards="\n".join(cards))
```

In `synthbench/cli.py`, import `report` and set
`COMMANDS = (sample, check, render, camera, triage, report)`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/ -q -n0 -p no:randomly`

Expected: PASS. `test_the_sheet_escapes_prompts` calls `spec.updated(prompt=…)`, which leaves
`camera_suffix` set and so passes the frozen-together validator. Then run
`uv run mypy synthbench/` and `uv run ruff check synthbench/ backend/tests/unit/synthbench/`;
both are clean.

- [ ] **Step 5: Commit**

```bash
F="synthbench/commands/report.py synthbench/cli.py backend/tests/unit/synthbench/test_cli_report.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "feat(synthbench): report - report.md with states, rerolls, timing and holds; a contact sheet

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: The host guard, the renderer unit, and the unit files

The host side of design §1 and §5:

- **The guard** writes `status/flagship.json` every 5 s. After 3 failed health checks in a row
  it stops the renderer; it never touches the flagship.
- **The renderer unit** runs ComfyUI in the foreground under systemd. Its pre-start check
  refuses to start ComfyUI unless the flagship is healthy, the flagship's util gate is at most
  0.76, and FLUX.2 fits in free memory. After start it renders one warm-up image.
- **`units install`** renders the four unit files from the checkout that runs it.

**Files:**

- Create: `synthbench/host/__init__.py`, `synthbench/host/guard.py`,
  `synthbench/host/renderer.py`, `synthbench/host/units.py`
- Modify: `synthbench/generate/comfy/serve.py` (`run_args(cfg, *, detach=True, extra=())`)
- Test: `backend/tests/unit/synthbench/test_host_guard.py`,
  `backend/tests/unit/synthbench/test_host_renderer.py`,
  `backend/tests/unit/synthbench/test_host_units.py`,
  `backend/tests/unit/synthbench/test_serve.py` (one test added)

**Interfaces:**

- Consumes: Task 5 (`FlagshipStatus`, `write_status`, `fresh_flagship`, `FlagshipUnknown`,
  `flagship_file`); P1 (`serve.ServeConfig`, `serve.stop`, `serve.container_alive`,
  `serve.wait_ready`, `serve.baked_farm_root`, `serve.CONTAINER`, `ComfyClient`,
  `flux2_dev_t2i`, `window.FLAGSHIP`).
- Produces (`serve.py`): `run_args(cfg, *, detach=True, extra=())`. Without `-d` when
  `detach=False`; `extra` goes after the image, as ComfyUI arguments.
- Produces (`host/guard.py`):
  - Constants: `FLAGSHIP_URL = "http://127.0.0.1:8000"`, `INTERVAL_S = 5.0`,
    `FAILURES_TO_STOP = 3`, `RENDERER_UNIT = "synthbench-renderer.service"`.
  - `parse_metrics(text) -> tuple[int, int]` (running, waiting);
    `probe(url, get) -> tuple[bool, int | None, int | None]`.
  - `Guard(status_file, *, url, get, stop_renderer, now, say)`, with `.tick() ->
FlagshipStatus`.
  - `stop_renderer(run)`; `main(argv)`, taking `--flagship-url`, `--status-file` and
    `--ticks`.
- Produces (`host/renderer.py`):
  - Constants: `MAX_UTIL = 0.76`, `MIN_FREE_GIB = 60.0`,
    `RESERVE_VRAM_ARGS = ("--reserve-vram", "4")`.
  - `PrecheckError`.
  - `flagship_util(run) -> float`; `gpu_free_gib(run) -> float`.
  - `prepare(cfg) -> list[str]`; `precheck(status_file, *, run, now) -> list[str]`.
  - `warmup(cfg, *, client=None, ready=None) -> float`.
  - `main(argv)`, taking `precheck` or `warmup`.
- Produces (`host/units.py`):

  - Unit names: `GUARD`, `RENDERER`, `SNAPSHOT`, `SNAPSHOT_TIMER`.
  - `UnitContext(checkout, python, podman, root, hf_home, podman_root)`, with `.current()`.
  - `render_units(ctx) -> dict[str, str]`; `install(ctx, unit_dir, run) -> list[str]`.
  - `main(argv)`, taking `install` or `show`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/synthbench/test_serve.py`:

```python
def test_the_renderer_unit_runs_comfyui_in_the_foreground_with_extra_arguments() -> None:
    cfg = serve.ServeConfig.from_env({})
    argv = serve.run_args(cfg, detach=False, extra=("--reserve-vram", "4"))
    assert "-d" not in argv
    assert argv[-3:] == [serve.IMAGE, "--reserve-vram", "4"]
    assert "-d" in serve.run_args(cfg)
```

If `test_serve.py` imports the module under another name, use that name.

`backend/tests/unit/synthbench/test_host_guard.py`:

```python
"""The flagship guard (agent-driven design §1, §5.1): status file, and the renderer stop."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from synthbench.host.guard import Guard, parse_metrics, stop_renderer
from synthbench.status import FlagshipStatus, read_status

from backend.tests.unit.synthbench import helpers as h

METRICS = """# HELP vllm:num_requests_running Number of requests in model execution batches.
vllm:num_requests_running{engine="0",model_name="claude-flagship"} 3.0
vllm:num_requests_waiting{engine="0",model_name="claude-flagship"} 2.0
vllm:num_requests_waiting_by_reason{engine="0",model_name="claude-flagship",reason="capacity"} 7.0
"""


class FakeFlagship:
    def __init__(self) -> None:
        self.healthy = True
        self.urls: list[str] = []

    def get(self, url: str, timeout: float) -> httpx.Response:
        self.urls.append(url)
        if not self.healthy:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(200, text=METRICS if url.endswith("/metrics") else "")


def _guard(tmp_path: Path, flagship: FakeFlagship, stops: list[int]) -> Guard:
    return Guard(
        tmp_path / "flagship.json",
        get=flagship.get,
        stop_renderer=lambda: stops.append(1),
        now=lambda: h.NOW,
        say=lambda _message: None,
    )


def test_metrics_sum_every_engine_and_skip_the_by_reason_series() -> None:
    assert parse_metrics(METRICS) == (3, 2)
    assert parse_metrics(METRICS + 'vllm:num_requests_running{engine="1"} 4.0\n') == (7, 2)
    assert parse_metrics("vllm:num_requests_running 1\nvllm:num_requests_waiting 0\n") == (1, 0)
    with pytest.raises(ValueError, match="num_requests_waiting"):
        parse_metrics("vllm:num_requests_running 1\n")


def test_each_tick_writes_the_status_file(tmp_path: Path) -> None:
    flagship, stops = FakeFlagship(), []
    status = _guard(tmp_path, flagship, stops).tick()
    assert (status.healthy, status.running, status.waiting, status.failures) == (True, 3, 2, 0)
    assert read_status(tmp_path / "flagship.json", FlagshipStatus) == status
    assert flagship.urls == ["http://127.0.0.1:8000/health", "http://127.0.0.1:8000/metrics"]


def test_three_failed_checks_in_a_row_stop_the_renderer_once_per_outage(tmp_path: Path) -> None:
    flagship, stops = FakeFlagship(), []
    guard = _guard(tmp_path, flagship, stops)
    flagship.healthy = False
    guard.tick()
    guard.tick()
    assert stops == []
    assert guard.tick().failures == 3
    assert stops == [1]
    guard.tick()
    assert stops == [1]
    flagship.healthy = True
    assert guard.tick().failures == 0
    flagship.healthy = False
    for _ in range(3):
        guard.tick()
    assert stops == [1, 1]


@pytest.mark.parametrize(
    "answer",
    [
        lambda url: (
            httpx.Response(503) if url.endswith("/health") else httpx.Response(200, text=METRICS)
        ),
        lambda _url: httpx.Response(200, text="garbage"),
    ],
    ids=["health-503", "no-metrics"],
)
def test_a_bad_answer_counts_as_unhealthy(
    tmp_path: Path, answer: Callable[[str], httpx.Response]
) -> None:
    guard = Guard(
        tmp_path / "flagship.json",
        get=lambda url, **_kw: answer(url),
        stop_renderer=lambda: None,
        now=lambda: h.NOW,
        say=lambda _message: None,
    )
    status = guard.tick()
    assert (status.healthy, status.running, status.failures) == (False, None, 1)


def test_stop_renderer_stops_the_unit_then_any_hand_started_container() -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    stop_renderer(run)
    assert calls[0] == ["systemctl", "--user", "stop", "synthbench-renderer.service"]
    assert calls[1][-4:] == ["--ignore", "--time", "30", "synthbench-comfyui"]
```

`backend/tests/unit/synthbench/test_host_renderer.py`:

```python
"""The renderer unit's pre-start check and warm-up (agent-driven design §1, §5.3)."""

from __future__ import annotations

import json
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from synthbench.generate.comfy.client import ComfyClient
from synthbench.generate.comfy.serve import ServeConfig
from synthbench.host.renderer import (
    PrecheckError,
    flagship_util,
    gpu_free_gib,
    precheck,
    warmup,
)
from synthbench.status import FlagshipStatus, write_status

from backend.tests.unit.synthbench import helpers as h

ENV = "PATH=/usr/bin\nENGINE_ARGS=--served-model-name claude-flagship --gpu-memory-utilization {util} --kv-cache-memory-bytes 59055800320\n"


class FakeHost:
    """docker inspect, nvidia-smi and `podman container exists`, by argv[0]."""

    def __init__(
        self, *, util: str = "0.76", used_mib: int = 191404, container: bool = False
    ) -> None:
        self.util = util
        self.used_mib = used_mib
        self.container = container

    def __call__(self, argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[0] == "docker":
            out = ENV.format(util=self.util) if self.util else "PATH=/usr/bin\n"
            return subprocess.CompletedProcess(argv, 0, out, "")
        if argv[0] == "nvidia-smi":
            return subprocess.CompletedProcess(argv, 0, f"256703, {self.used_mib}\n", "")
        return subprocess.CompletedProcess(argv, 0 if self.container else 1, "", "")


def test_flagship_util_reads_engine_args() -> None:
    assert flagship_util(FakeHost(util="0.84")) == 0.84
    with pytest.raises(PrecheckError, match="no --gpu-memory-utilization"):
        flagship_util(FakeHost(util=""))


def test_gpu_free_gib() -> None:
    assert gpu_free_gib(FakeHost(used_mib=191404)) == pytest.approx((256703 - 191404) / 1024)


def test_precheck_passes_a_host_ready_for_the_renderer(tmp_path: Path) -> None:
    status = tmp_path / "flagship.json"
    write_status(status, FlagshipStatus(time=h.NOW, healthy=True, running=1, waiting=0))
    assert precheck(status, run=FakeHost(), now=lambda: h.NOW) == []


def test_precheck_lists_every_reason_not_to_start(tmp_path: Path) -> None:
    status = tmp_path / "flagship.json"
    write_status(status, FlagshipStatus(time=h.NOW, healthy=True, running=1, waiting=0))
    host = FakeHost(util="0.84", used_mib=200000, container=True)
    problems = precheck(status, run=host, now=lambda: h.NOW + timedelta(seconds=60))
    joined = "\n".join(problems)
    assert "util gate 0.84 is above 0.76" in joined
    assert "GiB free on the GPU" in joined
    assert "already running" in joined
    assert "s old" in joined


def test_warmup_renders_one_1280x720_image(tmp_path: Path) -> None:
    graphs: list[dict[str, Any]] = []

    def comfy(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            graphs.append(json.loads(request.content)["prompt"])
            return httpx.Response(200, json={"prompt_id": "w1", "node_errors": {}})
        if request.url.path == "/history/w1":
            image = {"filename": "w.png", "subfolder": "", "type": "output"}
            entry = {"status": {"status_str": "success"}, "outputs": {"13": {"images": [image]}}}
            return httpx.Response(200, json={"w1": entry})
        return httpx.Response(200, content=h.png())

    cfg = ServeConfig.from_env({"SYNTHBENCH_ROOT": str(tmp_path)})
    client = ComfyClient(cfg.base_url, transport=httpx.MockTransport(comfy))
    warmup(cfg, client=client, ready=lambda: None)
    (graph,) = graphs
    assert (graph["7"]["inputs"]["width"], graph["7"]["inputs"]["height"]) == (1280, 720)
    assert graph["13"]["inputs"]["filename_prefix"] == "synthbench/warmup"
```

`backend/tests/unit/synthbench/test_host_units.py`:

```python
"""The host's systemd user units (agent-driven design §1; plan ruling P3-R8)."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from synthbench.host.units import (
    GUARD,
    RENDERER,
    SNAPSHOT,
    SNAPSHOT_TIMER,
    UnitContext,
    install,
    render_units,
)

CHECKOUT = Path("/synthbench/host-checkout")
PYTHON = CHECKOUT / ".venv" / "bin" / "python"
CTX = UnitContext(
    checkout=CHECKOUT,
    python=PYTHON,
    podman=Path("/usr/bin/podman"),
    root=Path("/synthbench"),
    hf_home=Path("/export/models"),
    podman_root=Path("/export/models/containers"),
)


def test_the_renderer_runs_comfyui_in_the_foreground_bound_to_the_guard() -> None:
    text = render_units(CTX)[RENDERER]
    assert "BindsTo=synthbench-guard.service" in text
    assert f"ExecStartPre={PYTHON} -m synthbench.host.renderer precheck" in text
    assert f"ExecStartPost={PYTHON} -m synthbench.host.renderer warmup" in text
    exec_start = next(line for line in text.splitlines() if line.startswith("ExecStart="))
    argv = shlex.split(exec_start.removeprefix("ExecStart="))
    assert argv[0] == "/usr/bin/podman"
    assert "-d" not in argv
    assert argv[-2:] == ["--reserve-vram", "4"]
    assert "127.0.0.1:8188:8188" in argv
    assert "[Install]" not in text  # started by hand, never at boot


def test_the_guard_always_runs_from_the_checkout() -> None:
    text = render_units(CTX)[GUARD]
    assert f"WorkingDirectory={CHECKOUT}" in text
    assert f"ExecStart={PYTHON} -m synthbench.host.guard" in text
    assert "Restart=always" in text
    assert "WantedBy=default.target" in text
    # pragma: allowlist nextline secret
    assert "Environment=SYNTHBENCH_ROOT=/synthbench" in text


def test_the_timer_snapshots_every_six_hours_utc() -> None:
    units = render_units(CTX)
    assert "OnCalendar=*-*-* 00/6:00:00 UTC" in units[SNAPSHOT_TIMER]
    assert "Persistent=true" in units[SNAPSHOT_TIMER]
    assert f"ExecStart={PYTHON} -m synthbench corpus snapshot" in units[SNAPSHOT]


def test_install_writes_changed_units_and_reloads_once(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    assert sorted(install(CTX, tmp_path, run)) == sorted(render_units(CTX))
    assert calls == [["systemctl", "--user", "daemon-reload"]]
    assert install(CTX, tmp_path, run) == []
    assert len(calls) == 1
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_host_guard.py backend/tests/unit/synthbench/test_host_renderer.py backend/tests/unit/synthbench/test_host_units.py backend/tests/unit/synthbench/test_serve.py -q -n0 -p no:randomly`

Expected: FAIL. `ModuleNotFoundError: No module named 'synthbench.host'` stops the three host
test files, and the serve test fails with `TypeError: run_args() got an unexpected keyword
argument 'detach'`.

- [ ] **Step 3: Implement**

`synthbench/generate/comfy/serve.py`: change `run_args` (its callers keep the default):

```python
def run_args(cfg: ServeConfig, *, detach: bool = True, extra: Sequence[str] = ()) -> list[str]:
    """podman run arguments. The renderer unit runs it in the foreground (detach=False) so the
    unit's state is the container's; `extra` goes after the image, to ComfyUI's main.py."""
    return [
        *podman_argv(),
        "run",
        *(["-d"] if detach else []),
        "--rm",
        "--name",
        CONTAINER,
        "--label",
        GPU_LABEL,
        "--log-driver",
        "k8s-file",
        "--log-opt",
        f"path={cfg.log_file}",
        "--device",
        "nvidia.com/gpu=all",
        "--shm-size",
        "16g",
        "-p",
        f"127.0.0.1:{cfg.port}:8188",
        "-v",
        f"{cfg.models_root}:{cfg.models_root}:ro",
        "-v",
        f"{cfg.out_dir}:/opt/ComfyUI/output",
        "-v",
        f"{cfg.cache_dir}:/root/.cache",
        IMAGE,
        *extra,
    ]
```

`synthbench/host/__init__.py`:

```python
"""Host-only code: the guard, the renderer unit and the snapshot timer (design §1).

It runs under systemd user units from the host checkout. The sandbox agent never runs it.
"""
```

`synthbench/host/guard.py`:

```python
"""The flagship guard (agent-driven design §1, §5.1).

Every 5 s it checks the flagship vLLM and writes status/flagship.json (time, healthy, running,
waiting). After 3 failed checks in a row it stops the renderer, so a flagship that crashed beside
it can boot again. It never stops or starts the flagship.

    python -m synthbench.host.guard            # the synthbench-guard unit
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx

from synthbench.generate.comfy import serve
from synthbench.status import FlagshipStatus, flagship_file, write_status

FLAGSHIP_URL = "http://127.0.0.1:8000"
INTERVAL_S = 5.0
FAILURES_TO_STOP = 3
RENDERER_UNIT = "synthbench-renderer.service"

Runner = Callable[..., subprocess.CompletedProcess[str]]
_METRIC = re.compile(r"^(vllm:num_requests_(?:running|waiting))(?:\{[^}]*\})?\s+(\S+)")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _say(message: str) -> None:
    sys.stderr.write(f"[synthbench-guard] {message}\n")


def parse_metrics(text: str) -> tuple[int, int]:
    """(running, waiting) summed over every engine, from vLLM's /metrics."""
    totals: dict[str, float] = {}
    for line in text.splitlines():
        if found := _METRIC.match(line):
            totals[found.group(1)] = totals.get(found.group(1), 0.0) + float(found.group(2))
    wanted = ("vllm:num_requests_running", "vllm:num_requests_waiting")
    if missing := [name for name in wanted if name not in totals]:
        raise ValueError(f"/metrics has no {', '.join(missing)}")
    return int(totals[wanted[0]]), int(totals[wanted[1]])


def probe(url: str, get: Callable[..., httpx.Response]) -> tuple[bool, int | None, int | None]:
    """(healthy, running, waiting); healthy needs /health 200 and readable request metrics."""
    try:
        health = get(f"{url}/health", timeout=3.0)
        metrics = get(f"{url}/metrics", timeout=3.0)
    except httpx.HTTPError:
        return False, None, None
    if health.status_code != 200 or metrics.status_code != 200:
        return False, None, None
    try:
        running, waiting = parse_metrics(metrics.text)
    except ValueError:
        return False, None, None
    return True, running, waiting


def stop_renderer(run: Runner = subprocess.run) -> None:
    """Stop the renderer unit, then any renderer container started by hand."""
    run(
        ["systemctl", "--user", "stop", RENDERER_UNIT],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    serve.stop(run)


class Guard:
    def __init__(
        self,
        status_file: Path,
        *,
        url: str = FLAGSHIP_URL,
        get: Callable[..., httpx.Response] = httpx.get,
        stop_renderer: Callable[[], None] = stop_renderer,
        now: Callable[[], datetime] = _utc_now,
        say: Callable[[str], None] = _say,
    ) -> None:
        self.status_file = status_file
        self.url = url
        self.get = get
        self.stop_renderer = stop_renderer
        self.now = now
        self.say = say
        self.failures = 0
        self.stopped = False

    def tick(self) -> FlagshipStatus:
        healthy, running, waiting = probe(self.url, self.get)
        self.failures = 0 if healthy else self.failures + 1
        status = FlagshipStatus(
            time=self.now(),
            healthy=healthy,
            running=running,
            waiting=waiting,
            failures=self.failures,
        )
        write_status(self.status_file, status)  # before any stop: render yields at once
        if healthy:
            if self.stopped:
                self.say(
                    "flagship healthy again; the renderer stays stopped until the owner starts it"
                )
            self.stopped = False
        elif self.failures >= FAILURES_TO_STOP and not self.stopped:
            self.say(
                f"flagship failed {self.failures} health checks in a row: stopping the renderer"
            )
            self.stop_renderer()
            self.stopped = True
        return status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.host.guard")
    parser.add_argument("--flagship-url", default=FLAGSHIP_URL)
    parser.add_argument("--status-file", type=Path, default=None)
    parser.add_argument(
        "--ticks", type=int, default=0, help="stop after this many checks (0: never)"
    )
    args = parser.parse_args(argv)
    guard = Guard(args.status_file or flagship_file(), url=args.flagship_url)
    _say(f"watching {args.flagship_url}; status file {guard.status_file}")
    ticks = 0
    while True:
        guard.tick()
        ticks += 1
        if args.ticks and ticks >= args.ticks:
            return 0
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    sys.exit(main())
```

`synthbench/host/renderer.py`:

```python
"""The renderer unit's pre-start check and warm-up (agent-driven design §1, §5.3).

systemd runs ComfyUI in the foreground (`podman run --rm`, no -d), so the unit's state is the
container's. `precheck` (ExecStartPre) refuses to start it unless the guard is fresh and the
flagship healthy, the flagship's util gate is at most 0.76, and FLUX.2 [dev] fits beside it.
`warmup` (ExecStartPost) renders one image so FLUX.2 is resident before the agent's first job.

    python -m synthbench.host.renderer precheck|warmup
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from synthbench.generate.comfy.client import ComfyClient
from synthbench.generate.comfy.graphs import flux2_dev_t2i
from synthbench.generate.comfy.serve import (
    CONTAINER,
    ServeConfig,
    baked_farm_root,
    container_alive,
    wait_ready,
)
from synthbench.generate.window import FLAGSHIP
from synthbench.status import FlagshipUnknown, flagship_file, fresh_flagship

MAX_UTIL = 0.76  # design §5.3: 0.76 x 249.81 GiB passes beside the renderer at its peak
MIN_FREE_GIB = 60.0  # FLUX.2 [dev] peaked at 56.2 GiB beside the flagship, plus --reserve-vram 4
RESERVE_VRAM_ARGS = ("--reserve-vram", "4")
WARMUP_PROMPT = "An empty suburban driveway on an overcast afternoon, photorealistic."

Runner = Callable[..., subprocess.CompletedProcess[str]]
_UTIL = re.compile(r"--gpu-memory-utilization[= ]([0-9]*\.?[0-9]+)")


class PrecheckError(RuntimeError):
    """A pre-start fact could not be read."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def flagship_util(run: Runner = subprocess.run) -> float:
    """The live flagship's --gpu-memory-utilization, from its container's ENGINE_ARGS."""
    done = run(
        ["docker", "inspect", "--format", "{{range .Config.Env}}{{println .}}{{end}}", FLAGSHIP],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if done.returncode != 0:
        raise PrecheckError(f"docker inspect {FLAGSHIP} failed: {(done.stderr or '').strip()}")
    for line in done.stdout.splitlines():
        if line.startswith("ENGINE_ARGS=") and (found := _UTIL.search(line)):
            return float(found.group(1))
    raise PrecheckError(f"{FLAGSHIP} has no --gpu-memory-utilization in ENGINE_ARGS")


def gpu_free_gib(run: Runner = subprocess.run) -> float:
    done = run(
        ["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    try:
        total, used = (float(value) for value in done.stdout.splitlines()[0].split(","))
    except (IndexError, ValueError) as error:
        raise PrecheckError(f"cannot read nvidia-smi: {done.stdout!r} {done.stderr!r}") from error
    return (total - used) / 1024


def prepare(cfg: ServeConfig) -> list[str]:
    """The renderer's directories, and the farm the image was built for."""
    farm, baked = cfg.models_root / "comfyui", baked_farm_root()
    if farm != baked:
        return [f"the farm under HF_HOME is {farm}, but the image loads models from {baked}"]
    for directory in (cfg.out_dir, cfg.cache_dir, cfg.log_file.parent):
        directory.mkdir(parents=True, exist_ok=True)
    return []


def precheck(
    status_file: Path, *, run: Runner = subprocess.run, now: Callable[[], datetime] = _utc_now
) -> list[str]:
    """Every reason not to start the renderer; empty when it may start."""
    problems: list[str] = []
    try:
        if not fresh_flagship(status_file, now()).healthy:
            problems.append("the flagship is not healthy (status/flagship.json)")
    except FlagshipUnknown as error:
        problems.append(f"{error}; start synthbench-guard first")
    try:
        util = flagship_util(run)
        if util > MAX_UTIL:
            problems.append(
                f"the flagship's util gate {util} is above {MAX_UTIL}: it could not boot again "
                "beside the renderer (design §5.3); apply the stack change first"
            )
    except PrecheckError as error:
        problems.append(str(error))
    try:
        free = gpu_free_gib(run)
        if free < MIN_FREE_GIB:
            problems.append(
                f"{free:.1f} GiB free on the GPU; FLUX.2 [dev] needs {MIN_FREE_GIB:.0f}"
            )
    except PrecheckError as error:
        problems.append(str(error))
    if container_alive(run):
        problems.append(
            f"a {CONTAINER} container is already running; stop it with "
            "`python -m synthbench.generate.comfy.serve down`"
        )
    return problems


def warmup(
    cfg: ServeConfig,
    *,
    client: ComfyClient | None = None,
    ready: Callable[[], object] | None = None,
) -> float:
    """Wait for ComfyUI, then render one 1280x720 image; returns its seconds."""
    if ready is None:
        wait_ready(cfg.base_url, alive=container_alive, log_file=cfg.log_file)
    else:
        ready()
    comfy = client if client is not None else ComfyClient(cfg.base_url)
    graph = flux2_dev_t2i(WARMUP_PROMPT, seed=0, width=1280, height=720)
    for node in graph.values():
        if node["class_type"] == "SaveImage":
            node["inputs"]["filename_prefix"] = "synthbench/warmup"
    started = time.monotonic()
    try:
        comfy.run(graph, timeout_s=900)
    finally:
        comfy.close()
    return time.monotonic() - started


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.host.renderer")
    parser.add_argument("command", choices=["precheck", "warmup"])
    args = parser.parse_args(argv)
    cfg = ServeConfig.from_env()
    if args.command == "precheck":
        problems = prepare(cfg) + precheck(flagship_file())
        for problem in problems:
            sys.stderr.write(f"[synthbench-renderer] refusing to start: {problem}\n")
        return 1 if problems else 0
    seconds = warmup(cfg)
    sys.stderr.write(f"[synthbench-renderer] warm-up image rendered in {seconds:.1f} s\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`synthbench/host/units.py`:

```python
"""systemd user units for the host side (agent-driven design §1; plan ruling P3-R8).

    /synthbench/host-checkout/.venv/bin/python -m synthbench.host.units install

writes them for the checkout it runs from, with that checkout's python. The guard and the
snapshot timer are enabled at boot; the renderer has no [Install] section, so the owner starts
it by hand.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from synthbench.generate.comfy.serve import ServeConfig, run_args
from synthbench.generate.podman import podman_root
from synthbench.host.renderer import RESERVE_VRAM_ARGS

GUARD = "synthbench-guard.service"
RENDERER = "synthbench-renderer.service"
SNAPSHOT = "synthbench-snapshot.service"
SNAPSHOT_TIMER = "synthbench-snapshot.timer"
DEFAULT_UNIT_DIR = Path.home() / ".config" / "systemd" / "user"

Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class UnitContext:
    checkout: Path  # the repository root whose code the units run
    python: Path  # that checkout's .venv python (not resolved: the venv is the point)
    podman: Path
    root: Path  # SYNTHBENCH_ROOT
    hf_home: Path
    podman_root: Path

    @classmethod
    def current(cls, env: Mapping[str, str] | None = None) -> UnitContext:
        e = os.environ if env is None else env
        return cls(
            checkout=Path(__file__).resolve().parents[2],
            python=Path(sys.executable),
            podman=Path(shutil.which("podman") or "/usr/bin/podman"),
            root=Path(e.get("SYNTHBENCH_ROOT", "/synthbench")),
            hf_home=Path(e.get("HF_HOME", "/export/models")),
            podman_root=podman_root(e),
        )


def render_units(ctx: UnitContext) -> dict[str, str]:
    env = "".join(
        f"Environment={key}={value}\n"
        for key, value in (
            ("SYNTHBENCH_ROOT", ctx.root),
            ("HF_HOME", ctx.hf_home),
            ("SYNTHBENCH_PODMAN_ROOT", ctx.podman_root),
        )
    )
    cfg = ServeConfig(
        port=8188,
        models_root=ctx.hf_home,
        out_dir=ctx.root / "comfy-out",
        cache_dir=ctx.root / "cache",
    )
    podman = run_args(cfg, detach=False, extra=RESERVE_VRAM_ARGS)
    podman[0] = str(ctx.podman)
    docs = f"Documentation=file://{ctx.checkout}/docs/synthbench/operator-runbook.md\n"
    service = f"WorkingDirectory={ctx.checkout}\n{env}"
    py = f"{ctx.python} -m"
    return {
        GUARD: (
            "[Unit]\n"
            "Description=synthbench guard: flagship status for render; stops the renderer when "
            "the flagship fails\n"
            f"{docs}\n"
            "[Service]\nType=simple\n"
            f"{service}ExecStart={py} synthbench.host.guard\n"
            "Restart=always\nRestartSec=5\n\n"
            "[Install]\nWantedBy=default.target\n"
        ),
        RENDERER: (
            "[Unit]\n"
            "Description=synthbench renderer: ComfyUI with FLUX.2 [dev] beside the flagship\n"
            f"{docs}BindsTo={GUARD}\nAfter={GUARD}\n\n"
            "[Service]\nType=simple\n"
            f"{service}ExecStartPre={py} synthbench.host.renderer precheck\n"
            f"ExecStart={shlex.join(podman)}\n"
            f"ExecStartPost={py} synthbench.host.renderer warmup\n"
            f"ExecStop={py} synthbench.generate.comfy.serve down\n"
            "TimeoutStartSec=1200\nTimeoutStopSec=90\nRestart=no\n"
        ),
        SNAPSHOT: (
            "[Unit]\nDescription=synthbench corpus snapshot and prune (design §6)\n"
            f"{docs}\n"
            "[Service]\nType=oneshot\n"
            f"{service}ExecStart={py} synthbench corpus snapshot\n"
        ),
        SNAPSHOT_TIMER: (
            "[Unit]\nDescription=Every 6 h: snapshot and prune the synthbench corpus\n\n"
            "[Timer]\nOnCalendar=*-*-* 00/6:00:00 UTC\nPersistent=true\n\n"
            "[Install]\nWantedBy=timers.target\n"
        ),
    }


def install(ctx: UnitContext, unit_dir: Path, run: Runner = subprocess.run) -> list[str]:
    """Write the units that differ; reload systemd once if any did. Returns their names."""
    unit_dir.mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    for name, text in render_units(ctx).items():
        path = unit_dir / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
            changed.append(name)
    if changed:
        run(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    return changed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.host.units")
    parser.add_argument("command", choices=["install", "show"])
    parser.add_argument("--unit-dir", type=Path, default=DEFAULT_UNIT_DIR)
    args = parser.parse_args(argv)
    ctx = UnitContext.current()
    if args.command == "show":
        for name, text in render_units(ctx).items():
            sys.stdout.write(f"# {name}\n{text}\n")
        return 0
    changed = install(ctx, args.unit_dir)
    sys.stdout.write(
        f"{len(changed)} unit file(s) changed in {args.unit_dir}: {', '.join(changed) or 'none'}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/ -q -n0 -p no:randomly`

Expected: PASS, including every P1 `test_serve.py` test. Its `run_args` expectations keep
`-d`, because detaching is the default. Then:

- run `uv run python -m synthbench.host.units show` and read the four units: absolute paths,
  and a renderer `ExecStart` without `-d` and ending in `--reserve-vram 4`;
- run `uv run mypy synthbench/` and `uv run ruff check synthbench/ backend/tests/unit/synthbench/`;
  both are clean.

- [ ] **Step 5: Commit**

```bash
F="synthbench/generate/comfy/serve.py synthbench/host/__init__.py synthbench/host/guard.py synthbench/host/renderer.py synthbench/host/units.py backend/tests/unit/synthbench/test_serve.py backend/tests/unit/synthbench/test_host_guard.py backend/tests/unit/synthbench/test_host_renderer.py backend/tests/unit/synthbench/test_host_units.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "feat(synthbench): host guard, renderer unit pre-start check and warm-up, systemd unit files

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: `corpus snapshot` and the prune rule

**Files:**

- Create: `synthbench/host/snapshot.py`, `synthbench/commands/corpus.py`
- Modify: `synthbench/cli.py` (add `corpus` to `COMMANDS`)
- Test: `backend/tests/unit/synthbench/test_corpus_snapshot.py`. The name avoids P1's
  `test_snapshot.py`, which tests the ComfyUI `/object_info` snapshot.

**Interfaces:**

- Consumes: Task 5 (`SnapshotHold`, `SnapshotStatus`, `write_status`, `snapshots_file`);
  Task 3 (`AskOwner`, `Parser`).
- Produces (`host/snapshot.py`):
  - Constants: `DATASET = "primary/export/synthbench/corpus"`, `PREFIX = "synthbench-"`,
    `KEEP = 5`, `CHURN`.
  - `Change(kind, file_type, path, new_path)`; `parse_diff(text) -> list[Change]`.
  - `Verdict(removed, modified)`, with a `.held` property; `classify(changes) -> Verdict`.
  - `prune(snapshots, *, diff, destroy, keep=KEEP) -> tuple[SnapshotHold | None, int]`.
  - zfs wrappers: `take_snapshot`, `list_snapshots`, `zfs_diff`, `destroy_snapshot` (refuses
    any name but `<dataset>@synthbench-…`).
  - `snapshot_and_prune(env, *, run, now) -> SnapshotStatus`.
- Produces (`commands/corpus.py`): `add_parser` (the `corpus` group with `snapshot`),
  `run_snapshot`, `execute_snapshot(env, *, run, now) -> int`. It exits 0 with no hold and 2
  with a hold or a zfs failure.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_corpus_snapshot.py`:

```python
"""Corpus snapshots and the prune rule (agent-driven design §6; plan rulings P3-R5, P3-R6)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from synthbench import cli
from synthbench.commands import corpus
from synthbench.commands.common import AskOwner
from synthbench.host.snapshot import (
    DATASET,
    classify,
    destroy_snapshot,
    parse_diff,
    prune,
)
from synthbench.status import SnapshotHold, SnapshotStatus, read_status, snapshots_file

from backend.tests.unit.synthbench import helpers as h

BASE = "/synthbench/corpus/.p3probe"
# Recorded on maui 2026-09-28 with `zfs diff -FH` across: a replace (rename over), an in-place
# write, a deletion, an append, a rename, a temp file left by a crash, and write_new's link.
PROBE = "".join(
    f"{line}\n"
    for line in (
        f"-\tF\t{BASE}/replaced.json",
        f"M\tF\t{BASE}/inplace.json",
        f"-\tF\t{BASE}/gone.png",
        f"M\tF\t{BASE}/log.jsonl",
        f"R\tF\t{BASE}/renamed_src.json\t{BASE}/renamed_dst.json",
        f"+\tF\t{BASE}/replaced.json",
        f"+\tF\t{BASE}/sub/.leftover.json.abc.tmp",
        f"M\t/\t{BASE}",
        f"M\t/\t{BASE}/sub",
        f"+\tF\t{BASE}/sub/new.json",
    )
)


def test_the_recorded_probe_classifies_as_the_rule_says() -> None:
    verdict = classify(parse_diff(PROBE))
    assert verdict.removed == (f"{BASE}/gone.png", f"{BASE}/renamed_src.json")
    assert verdict.modified == (
        f"{BASE}/inplace.json",
        f"{BASE}/log.jsonl",
        f"{BASE}/replaced.json",
    )
    assert verdict.held == verdict.removed


@pytest.mark.parametrize(
    ("lines", "held"),
    [
        (
            [
                "M\tF\t/c/v/index.jsonl",
                "-\tF\t/c/v/e/spec.json",
                "+\tF\t/c/v/e/spec.json",
                "M\tF\t/c/v/b/report.md",
                "M\tF\t/c/v/b/sheet.html",
            ],
            (),
        ),
        (["M\tF\t/c/v/e/renders/a1-s1.png"], ("/c/v/e/renders/a1-s1.png",)),
        (
            ["-\tF\t/c/v/e/stills/a1-s1.jpg", "+\tF\t/c/v/e/stills/a1-s1.jpg"],
            ("/c/v/e/stills/a1-s1.jpg",),
        ),
        (["-\tF\t/c/v/e/.spec.json.x1y2.tmp"], ()),
        (["M\tF\t/c/v/notes.txt"], ("/c/v/notes.txt",)),
        (["+\tF\t/c/v/e/renders/a2-s9.png", "M\t/\t/c/v/e/renders"], ()),
        (["M\tF\t/c/v/e/renders/a1-s1.png\t(+1)"], ("/c/v/e/renders/a1-s1.png",)),
    ],
    ids=[
        "json-churn",
        "image-edited",
        "image-replaced",
        "temp-removed",
        "unknown-type",
        "added",
        "link-count",
    ],
)
def test_what_holds_a_snapshot(lines: list[str], held: tuple[str, ...]) -> None:
    assert classify(parse_diff("".join(f"{line}\n" for line in lines))).held == held


def test_an_unknown_diff_line_is_an_error() -> None:
    with pytest.raises(ValueError, match="unexpected zfs diff line"):
        parse_diff("?\tF\t/c/x\n")


def test_prune_destroys_only_churn_snapshots_down_to_five() -> None:
    snaps = [f"{DATASET}@synthbench-{i}" for i in range(8)]
    destroyed: list[str] = []
    hold, count = prune(
        snaps, diff=lambda _a, _b: "M\tF\t/c/v/index.jsonl\n", destroy=destroyed.append
    )
    assert (hold, count) == (None, 3)
    assert destroyed == snaps[:3]


def test_a_hold_stops_pruning_and_nothing_past_it_is_destroyed() -> None:
    snaps = [f"{DATASET}@synthbench-{i}" for i in range(8)]
    destroyed: list[str] = []

    def diff(older: str, _newer: str) -> str:
        return (
            "-\tF\t/c/v/e/renders/a1-s1.png\n" if older == snaps[1] else "M\tF\t/c/v/index.jsonl\n"
        )

    hold, count = prune(snaps, diff=diff, destroy=destroyed.append)
    assert destroyed == [snaps[0]]
    assert count == 1
    assert hold == SnapshotHold(snapshot=snaps[1], count=1, paths=("/c/v/e/renders/a1-s1.png",))


@pytest.mark.parametrize("name", [DATASET, f"{DATASET}@manual", "primary/export@synthbench-1"])
def test_destroy_refuses_anything_but_a_synthbench_snapshot_of_the_dataset(name: str) -> None:
    def never(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError(f"ran {argv}")

    with pytest.raises(ValueError, match="refusing"):
        destroy_snapshot(name, DATASET, never)


class FakeZfs:
    """zfs snapshot, list, diff and destroy over an in-memory snapshot list."""

    def __init__(self, existing: list[str], diffs: dict[str, str] | None = None) -> None:
        self.snaps = list(existing)
        self.diffs = diffs or {}

    def __call__(self, argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        verb, out = argv[1], ""
        if verb == "snapshot":
            self.snaps.append(argv[2])
        elif verb == "list":
            out = "".join(f"{name}\n" for name in self.snaps)
        elif verb == "diff":
            out = self.diffs.get(argv[3], "M\tF\t/c/v/index.jsonl\n")
        elif verb == "destroy":
            self.snaps.remove(argv[2])
        return subprocess.CompletedProcess(argv, 0, out, "")


def test_the_command_snapshots_prunes_and_writes_the_status(tmp_path: Path) -> None:
    zfs = FakeZfs([f"{DATASET}@synthbench-2026092{i}T000000Z" for i in range(5)])
    env = h.env(tmp_path)
    assert corpus.execute_snapshot(env, run=zfs, now=h.NOW) == cli.EXIT_OK
    assert len(zfs.snaps) == 5
    assert zfs.snaps[-1] == f"{DATASET}@synthbench-20260928T120000Z"
    status = read_status(snapshots_file(env), SnapshotStatus)
    assert (status.snapshots, status.hold) == (5, None)


def test_a_hold_is_written_and_asks_the_owner(tmp_path: Path) -> None:
    snaps = [f"{DATASET}@synthbench-2026092{i}T000000Z" for i in range(5)]
    zfs = FakeZfs(snaps, diffs={snaps[0]: "-\tF\t/c/v/e/renders/a1-s1.png\n"})
    env = h.env(tmp_path)
    with pytest.raises(AskOwner, match="holds the only copy"):
        corpus.execute_snapshot(env, run=zfs, now=h.NOW)
    status = read_status(snapshots_file(env), SnapshotStatus)
    assert status.hold is not None
    assert status.hold.snapshot == snaps[0]
    assert status.snapshots == 6
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_corpus_snapshot.py -q -n0 -p no:randomly`

Expected: FAIL with `ImportError: cannot import name 'corpus'`.

- [ ] **Step 3: Implement**

`synthbench/host/snapshot.py`:

```python
"""Corpus snapshots and the prune rule (agent-driven design §6; plan rulings P3-R5, P3-R6).

`python -m synthbench corpus snapshot` (the 6-hourly timer) snapshots the corpus dataset, then
prunes. While more than KEEP synthbench snapshots exist, it looks at the oldest only:

- A removed file, or a changed file other than JSON, JSONL or a batch view, means the oldest
  holds the only copy. Pruning stops, and status/snapshots.json names the snapshot.
- Otherwise the changes are expected churn: the oldest is destroyed and the loop repeats.

Only the oldest is ever destroyed, so no deletion slips through a gap.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath

from synthbench.status import SnapshotHold, SnapshotStatus, snapshots_file, write_status

DATASET = "primary/export/synthbench/corpus"
PREFIX = "synthbench-"
KEEP = 5
CHURN = frozenset({".json", ".jsonl", ".md", ".html"})  # files commands replace (P3-R6)
HOLD_PATHS_SHOWN = 20

Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class Change:
    kind: str  # "-", "+", "M" or "R"
    file_type: str  # zfs diff -F: "F" file, "/" directory, "@" link, ...
    path: str
    new_path: str | None = None  # R only


def parse_diff(text: str) -> list[Change]:
    """`zfs diff -FH` lines: change, type, path, and the new path of a rename. A fourth field on
    another change is a link-count note such as `(+1)`, and is dropped."""
    changes: list[Change] = []
    for line in text.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) not in (3, 4) or fields[0] not in {"-", "+", "M", "R"}:
            raise ValueError(f"unexpected zfs diff line: {line!r}")
        new_path = fields[3] if fields[0] == "R" and len(fields) == 4 else None
        changes.append(Change(fields[0], fields[1], fields[2], new_path))
    return changes


def _store_temp(path: str) -> bool:
    name = PurePosixPath(path).name
    return name.startswith(".") and name.endswith(".tmp")


@dataclass(frozen=True)
class Verdict:
    removed: tuple[str, ...]
    modified: tuple[str, ...]

    @property
    def held(self) -> tuple[str, ...]:
        """Paths the older snapshot holds the only copy of (design §6)."""
        edited = tuple(p for p in self.modified if PurePosixPath(p).suffix not in CHURN)
        return (*self.removed, *edited)


def classify(changes: Sequence[Change]) -> Verdict:
    """A replace shows as `-` and `+` on one path: that is a modification (P3-R5)."""
    gone: set[str] = set()
    made: set[str] = set()
    changed: set[str] = set()
    for change in changes:
        if change.file_type == "/" or _store_temp(change.path):
            continue
        if change.kind == "-":
            gone.add(change.path)
        elif change.kind == "+":
            made.add(change.path)
        elif change.kind == "M":
            changed.add(change.path)
        else:  # R: the old path is gone, the new one made
            gone.add(change.path)
            if change.new_path is not None:
                made.add(change.new_path)
    changed |= gone & made
    return Verdict(removed=tuple(sorted(gone - made)), modified=tuple(sorted(changed)))


def prune(
    snapshots: Sequence[str],
    *,
    diff: Callable[[str, str], str],
    destroy: Callable[[str], None],
    keep: int = KEEP,
) -> tuple[SnapshotHold | None, int]:
    """Destroy the oldest while more than `keep` remain and it holds no only copy.

    Returns the hold that stopped pruning (or None) and how many snapshots were destroyed.
    """
    remaining = list(snapshots)
    destroyed = 0
    while len(remaining) > keep:
        oldest, following = remaining[0], remaining[1]
        held = classify(parse_diff(diff(oldest, following))).held
        if held:
            hold = SnapshotHold(snapshot=oldest, count=len(held), paths=held[:HOLD_PATHS_SHOWN])
            return hold, destroyed
        destroy(oldest)
        remaining.pop(0)
        destroyed += 1
    return None, destroyed


def take_snapshot(dataset: str, now: datetime, run: Runner) -> str:
    name = f"{dataset}@{PREFIX}{now:%Y%m%dT%H%M%SZ}"
    run(["zfs", "snapshot", name], check=True, capture_output=True, text=True, timeout=120)
    return name


def list_snapshots(dataset: str, run: Runner) -> list[str]:
    """The dataset's synthbench snapshots, oldest first."""
    done = run(
        [
            "zfs",
            "list",
            "-H",
            "-t",
            "snapshot",
            "-o",
            "name",
            "-s",
            "createtxg",
            "-d",
            "1",
            dataset,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return [name for name in done.stdout.split() if name.startswith(f"{dataset}@{PREFIX}")]


def zfs_diff(older: str, newer: str, run: Runner) -> str:
    done = run(
        ["zfs", "diff", "-FH", older, newer],
        check=True,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    return done.stdout


def destroy_snapshot(name: str, dataset: str, run: Runner) -> None:
    if not name.startswith(f"{dataset}@{PREFIX}"):
        raise ValueError(f"refusing to destroy {name!r}: not a {PREFIX} snapshot of {dataset}")
    run(["zfs", "destroy", name], check=True, capture_output=True, text=True, timeout=600)


def snapshot_and_prune(env: Mapping[str, str], *, run: Runner, now: datetime) -> SnapshotStatus:
    dataset = env.get("SYNTHBENCH_CORPUS_DATASET", DATASET)
    take_snapshot(dataset, now, run)
    snapshots = list_snapshots(dataset, run)
    hold, destroyed = prune(
        snapshots,
        diff=lambda older, newer: zfs_diff(older, newer, run),
        destroy=lambda name: destroy_snapshot(name, dataset, run),
    )
    status = SnapshotStatus(time=now, snapshots=len(snapshots) - destroyed, hold=hold)
    write_status(snapshots_file(env), status)
    return status
```

`synthbench/commands/corpus.py`:

```python
"""`corpus snapshot`: host-side corpus maintenance, run by the owner's timer (design §6)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from synthbench.commands.common import EXIT_OK, AskOwner, Parser
from synthbench.host.snapshot import snapshot_and_prune
from synthbench.status import snapshots_file

Runner = Callable[..., subprocess.CompletedProcess[str]]


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    corpus = commands.add_parser(
        "corpus",
        help="host-side corpus maintenance (the owner's timer runs it)",
        allow_abbrev=False,
    )
    actions = corpus.add_subparsers(dest="corpus_command", required=True, parser_class=Parser)
    snapshot = actions.add_parser(
        "snapshot",
        help="snapshot the corpus dataset, then prune by the design's §6 rule",
        allow_abbrev=False,
    )
    snapshot.set_defaults(run=run_snapshot)


def run_snapshot(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    del args  # no options
    return execute_snapshot(env, run=subprocess.run, now=datetime.now(UTC))


def execute_snapshot(env: Mapping[str, str], *, run: Runner, now: datetime) -> int:
    try:
        status = snapshot_and_prune(env, run=run, now=now)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError) as error:
        raise AskOwner(f"the corpus snapshot failed ({type(error).__name__}: {error}).") from error
    if status.hold is not None:
        raise AskOwner(
            f"{status.hold.snapshot} holds the only copy of {status.hold.count} removed or changed "
            f"file(s); pruning stopped with {status.snapshots} snapshots. See "
            f"{snapshots_file(env)} and the operator runbook."
        )
    sys.stdout.write(f"corpus snapshot: {status.snapshots} kept, no hold\n")
    return EXIT_OK
```

In `synthbench/cli.py`, import `corpus` and set
`COMMANDS = (sample, check, render, camera, triage, report, corpus)`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/ -q -n0 -p no:randomly`

Expected: PASS. Then run `uv run mypy synthbench/` and
`uv run ruff check synthbench/ backend/tests/unit/synthbench/`; both are clean.

- [ ] **Step 5: Commit**

```bash
F="synthbench/host/snapshot.py synthbench/commands/corpus.py synthbench/cli.py backend/tests/unit/synthbench/test_corpus_snapshot.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "feat(synthbench): corpus snapshot - 6-hourly ZFS snapshots, prune only churn, hold only copies

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: The four documents and the command-reference test

**Files:**

- Create: `docs/synthbench/AGENTS.md`, `docs/synthbench/agent-handoff.md`,
  `docs/synthbench/command-reference.md`, `docs/synthbench/operator-runbook.md`
- Modify:
  - Indexes: `docs/AGENTS.md` (a row for `synthbench/`), `synthbench/AGENTS.md`,
    `backend/tests/unit/synthbench/AGENTS.md`.
  - The design doc: in §3 step 1, `--cells <filter>` becomes `--only <scenario ids>`; §3.1
    rule 3 gets its number; §7 says calibration is deferred.
  - The parent spec: §7.3's P3 row notes the calibration deferral.
- Test: `backend/tests/unit/synthbench/test_command_reference.py`

**Interfaces:**

- Consumes: `cli.build_parser()` (every command registered by Tasks 3-10).
- Produces: the four documents (design §8). One test checks that each `## \`<command>\``
  section of the command reference lists exactly that command's options; another checks that
  the handoff names only the six agent commands.

- [ ] **Step 1: Write the failing test**

`backend/tests/unit/synthbench/test_command_reference.py`:

```python
"""docs/synthbench (agent-driven design §8): the command reference matches argparse, and the
agent's handoff names only the agent's commands."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from synthbench import cli

REPO_ROOT = Path(__file__).resolve().parents[4]
DOCS = REPO_ROOT / "docs" / "synthbench"
AGENT_COMMANDS = {"sample", "check", "render", "camera", "triage", "report"}


def _leaves(
    parser: argparse.ArgumentParser, prefix: str = ""
) -> dict[str, argparse.ArgumentParser]:
    """Every runnable command by its full name: "check", "corpus snapshot"."""
    groups = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    if not groups:
        return {prefix: parser}
    found: dict[str, argparse.ArgumentParser] = {}
    for name, child in groups[0].choices.items():
        found |= _leaves(child, f"{prefix} {name}".strip())
    return found


def _options(parser: argparse.ArgumentParser) -> set[str]:
    return {s for a in parser._actions for s in a.option_strings if s not in {"-h", "--help"}}


def _documented() -> dict[str, set[str]]:
    """`## \\`<command>\\`` sections, and the `--options` named in each one's table rows."""
    sections: dict[str, set[str]] = {}
    current: str | None = None
    for line in (DOCS / "command-reference.md").read_text(encoding="utf-8").splitlines():
        if heading := re.fullmatch(r"## `([a-z ]+)`", line):
            current = heading.group(1)
            sections[current] = set()
        elif line.startswith("## "):
            current = None
        elif current is not None and (row := re.match(r"\| `(--[a-z-]+)", line)):
            sections[current].add(row.group(1))
    return sections


def test_the_reference_documents_every_command_and_option() -> None:
    commands = _leaves(cli.build_parser())
    documented = _documented()
    assert sorted(documented) == sorted(commands)
    for name, parser in commands.items():
        assert documented[name] == _options(parser), name


def test_the_handoff_names_only_the_agents_commands() -> None:
    text = (DOCS / "agent-handoff.md").read_text(encoding="utf-8")
    assert set(re.findall(r"python -m synthbench ([a-z]+)", text)) == AGENT_COMMANDS
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_command_reference.py -q -n0 -p no:randomly`

Expected: FAIL with `FileNotFoundError` for `docs/synthbench/command-reference.md`.

- [ ] **Step 3: Write the documents**

`docs/synthbench/AGENTS.md`:

```markdown
# docs/synthbench - Agent Guide

## Purpose

Documents for agent-driven Tier B generation beside the flagship (agent-driven design §8,
`docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md`). The code is
in `synthbench/`.

## Files

| File                   | Reader             | What                                                                                     |
| ---------------------- | ------------------ | ---------------------------------------------------------------------------------------- |
| `agent-handoff.md`     | the flagship agent | start here if you drive generation: the loop, prompt rules, triage, limits, stop-and-ask |
| `command-reference.md` | the agent          | each command's options, files and exit codes                                             |
| `operator-runbook.md`  | the owner          | host units, the renderer, snapshot holds, the agent's sandbox, reviewing a batch         |

## Rules

- `command-reference.md` must list exactly each command's options: its `## \`<command>\``sections are checked against argparse by`backend/tests/unit/synthbench/test_command_reference.py`.
  Change the document with the parser.
- `agent-handoff.md` names only the six agent commands (same test). It never describes GPU
  windows or host units (design G11); those belong in `operator-runbook.md`.
```

`docs/synthbench/agent-handoff.md`:

```markdown
# Synthbench Tier B generation: agent handoff

**Start here if you are the agent driving synthbench generation.** Read this whole file before
you run anything. `command-reference.md` beside it lists every option.

## What this run is

You write scene prompts for a synthetic security-camera benchmark, render them, look at every
image, and report to the owner.

A seeded sampler has already fixed the facts of each event: the place, camera, lighting,
weather, time, people, animals and objects, and the label. Those facts become ground truth for
the benchmark. You write the words; you never change the facts.

The images come from FLUX.2 [dev], which runs in ComfyUI on the host beside the model you run
on. Rendering slows that model, so `render` waits whenever the model has requests queued.

## What you can and cannot do

You can:

- run `uv run python -m synthbench <command>` from the root of your repository clone;
- write two files per batch in the corpus: `prompts.jsonl` and `triage.jsonl`;
- open any image the commands made, to look at it;
- read `/synthbench/status/`.

You cannot, and must not try to:

- start, stop or restart the renderer, the model server, docker, podman, or anything on the
  GPU;
- delete, move, rename or edit any other file in `/synthbench/corpus/`. The corpus is
  append-only, and `check` detects a changed image;
- change the library code to get past a rule. The owner runs `check` again on the host.

## How to run the commands

- Run every command from the repository root: `uv run python -m synthbench <command> --batch <name>`.
- Give `render` a Bash timeout of 600000 ms (10 minutes). It stops starting images after
  480 s, prints `N still to render`, and you run it again until N is 0.
- Every command exits `0` when done, and `1` when your request or your file needs fixing: read
  the message, fix it, and run the command again.
- Exit `2` means **stop and ask the owner**. Do not retry it and do not work around it. Tell
  the owner the command and its full message, and wait.

## The loop for one batch

Batch names are lowercase letters, digits and hyphens, and each one is new: `pilot-1`,
`batch-1`, `batch-2`. The corpus version is in each spec as `corpus_version` (`tierb-v0` today).
Below, `<corpus>` is `/synthbench/corpus/<version>`.

1. **Sample.** `uv run python -m synthbench sample --batch <b> --n <n>`. It prints where the
   specs are: `<corpus>/events/B/<event id>/spec.json`.
   - A pilot is 10 events and a full batch is 50.
   - Before the first batch in a new area, run a 10-event pilot. `--only <scenario ids>` limits
     a pilot to some scenarios.
2. **Write prompts.** Read every spec in the batch. Write `<corpus>/batches/<b>/prompts.jsonl`,
   one JSON object per line: `{"event_id": "B-<b>-000", "prompt": "..."}`. The rules are in the
   next section.
3. **Check.** `uv run python -m synthbench check --batch <b>`.
   - On exit 1 it lists each problem as `<event id>: rule N: ...`. Fix those rows and run it
     again.
   - When every prompt passes, it freezes them. A frozen prompt never changes.
4. **Render.** `uv run python -m synthbench render --batch <b>`, repeated until it prints
   `0 still to render`.
5. **Camera.** `uv run python -m synthbench camera --batch <b>`. It turns each new render into
   the 1920x1080 still the pipeline will see.
6. **Look, and write verdicts.** Open every new still. Its path is
   `<corpus>/events/B/<event id>/stills/a<k>-s<seed>.jpg`; the attempt number `k` and the
   seed are in that event's `provenance.json`. Add one line per still to
   `<corpus>/batches/<b>/triage.jsonl`:

   - `{"event_id": "B-<b>-000", "k": 1, "verdict": "ok"}`, or
   - `{"event_id": "B-<b>-000", "k": 1, "verdict": "reroll", "reason": "blank"}`.

   Keep the earlier lines when you add new ones.

7. **Triage.** `uv run python -m synthbench triage --batch <b>`. If it scheduled rerolls,
   repeat steps 4-7 for them. Their attempt number is 2.
8. **Report.** `uv run python -m synthbench report --batch <b>`, then write your report to the
   owner (below).

Every command resumes where it stopped. If you were interrupted, run the same step again.

## Writing prompts (what `check` enforces)

Describe the scene in plain, concrete words:

- the place, and the viewpoint of the spec's camera;
- the time of day, the light and the weather;
- each person or animal: what they wear and what they do;
- each object.

Use the spec's facts, and add no person, animal or weapon that is not in it.

1. **Name every subject and prop.** For each entry in `subjects` and `props`, use one word or
   phrase from its class's list under `terms:` in `synthbench/taxonomy/tier_b_v0.yaml`. For
   class `handgun` write "handgun" or "pistol"; for `package`, "package" or "parcel".
2. **Keep it realistic and non-graphic.**
   - Show what a camera sees: a weapon in a hand, a forced door, a person lying on the ground.
     Never injury detail, blood or gore.
   - Every person is anonymous. Describe people generically ("a man in a gray hoodie"); never
     name or suggest a real or famous person.
3. **Length:** at most 1,200 characters.
4. **No camera styling.** Do not write "security camera", "CCTV", "footage", "timestamp",
   "watermark" or the like. `check` adds a fixed camera description to every prompt, and the
   camera stage draws the real timestamp.

What the spec's fields mean:

| Field                                          | Meaning                                                                               |
| ---------------------------------------------- | ------------------------------------------------------------------------------------- |
| `cell.property_type`, `cell.zone`              | the place                                                                             |
| `cell.camera`                                  | the viewpoint: doorbell_fisheye, eave_wide, garage_mounted, pole_lot or indoor_corner |
| `cell.lighting`                                | day, golden_hour, dusk, ir_night or porch_lit_night                                   |
| `cell.weather`, `cell.artifacts`, `scene_time` | weather, lens effects, and the time (HH:MM)                                           |
| `subjects[].attributes.clothing`               | what a person wears                                                                   |
| `props[].held_by`                              | which subject holds the prop                                                          |

For `ir_night`, write a night scene; the camera stage turns it into infrared grey.

## Triage: when you may reroll

Look at every still. Reroll an event only for one of these reasons, and at most once per event:

| Reason                | Meaning                                                                    |
| --------------------- | -------------------------------------------------------------------------- |
| `blank`               | a black, white, flat or noise image                                        |
| `refusal_card`        | a safety or error card instead of a scene                                  |
| `wrong_scene`         | not the spec's kind of place (indoors for a driveway, a street for a pool) |
| `no_person`           | the spec has people and the image has none                                 |
| `broken_anatomy`      | merged or duplicated bodies, grossly broken limbs                          |
| `not_security_camera` | the image does not read as a fixed security camera's view                  |
| `text_overlay`        | text drawn into the scene: a watermark, a caption, a second timestamp      |

The date and time in the top-left corner are the camera's own overlay. They are not a reason.

Everything else is `ok`. In particular, "I cannot make out the knife" is **not** a reason:
whether a prop is visible is decided later by an independent checker and the owner. Rerolling
until an image looks right to you would bias the benchmark toward what your own model sees.

Limits:

- One reroll per event. A second failed triage marks the event failed.
- A batch may reroll at most 10% of its events: 1 in a 10-event pilot, 5 in a 50-event batch.
  Past that, `triage` marks the event failed and exits 2.
- Failed events stay in the corpus, and the report lists them.

## Your report to the owner

After `report`, write a short message with:

- the batch name, the corpus version, and the paths of `report.md` and `sheet.html`;
- counts: events, ready, rerolled (by reason), and failed;
- the median render time per image, and any failed render jobs;
- any snapshot hold the report shows;
- what you noticed across the batch, such as a scenario that keeps coming out wrong or wording
  that worked;
- after a pilot, what you will change in your wording for the full batch.

## Stop and ask the owner when

- any command exits 2;
- `check` reports a problem that is not in your own prompt rows (for example, a spec whose
  facts differ);
- you are unsure whether a prompt meets the content rules;
- a still shows something disturbing, or out of place in a way no triage reason covers;
- you think a rule or a limit is wrong. Say so; do not work around it.

## Out of scope

This run does not cover:

- Tier A (sites, cast, clips);
- the independent verifier and the audit page;
- benchmark runs;
- any change to the taxonomy, the camera parameters or the library code.

If the owner wants one of these, they will give you a different document.
```

`docs/synthbench/command-reference.md`:

```markdown
# synthbench command reference

Every command runs from the repository root as `uv run python -m synthbench <command> …`.

| Exit code | Meaning                                       |
| --------- | --------------------------------------------- |
| `0`       | done                                          |
| `1`       | the request or one of your files needs fixing |
| `2`       | stop and ask the owner                        |

Paths below are relative to the corpus version directory,
`$SYNTHBENCH_ROOT/corpus/<version>/` (today `/synthbench/corpus/tierb-v0/`). `<b>` is a
batch name and `<id>` an event id.

Each section's options table lists exactly the command's options; a test compares it with
argparse (`backend/tests/unit/synthbench/test_command_reference.py`).

## `sample`

Samples fact-only Tier B specs into a new batch (design §3 step 1). The same request gives the
same specs, and running it again finishes a batch that was only partly written.

| Option         | Default             | Meaning                                                 |
| -------------- | ------------------- | ------------------------------------------------------- |
| `--batch <b>`  | required            | a new batch name: lowercase letters, digits and hyphens |
| `--n <n>`      | required            | number of events, 1-500 (a pilot is 10, a batch 50)     |
| `--seed <s>`   | from the batch name | sampler seed                                            |
| `--only <ids>` | every scenario      | comma-separated scenario ids                            |

- **Reads:** `synthbench/taxonomy/tier_b_v0.yaml`, `corpus.json`, `index.jsonl`.
- **Writes:**
  - `corpus.json` (the version's first batch only);
  - `batches/<b>/batch.json`;
  - `events/B/<id>/spec.json`;
  - `index.jsonl` rows with status `sampled`.
- **Exit 1:** a bad option, an unknown scenario, or a batch name already used with other
  options.
- **Exit 2:** the taxonomy changed since the corpus version was created; a spec differs from
  what the sampler makes; or a corpus file cannot be read or written.

## `check`

Validates `batches/<b>/prompts.jsonl` and freezes the prompts when every one passes (design §3
step 3, rules in §3.1). It also verifies the whole batch: facts against the sampler, frozen
prompts against the rules, and every recorded image against its sha256. The owner runs it on
the host to confirm a batch.

| Option        | Default  | Meaning    |
| ------------- | -------- | ---------- |
| `--batch <b>` | required | batch name |

- **Reads:** the batch's specs, `prompts.jsonl`, each `provenance.json`, and the images it
  names.
- **Writes (only when every prompt passes):**
  - `spec.json` with `prompt` and `camera_suffix` frozen;
  - `provenance.json` with attempt 1;
  - `index.jsonl` rows with status `prompted`.
- **Exit 1:** a prompt breaks a rule (`<id>: rule N: …`); a row is missing, malformed, unknown
  or duplicated; a row differs from its frozen prompt; or specs were never written (it prints
  the `sample` command that finishes the batch).
- **Exit 2:** a spec's facts differ from the sampler's; a frozen prompt now breaks a rule; the
  camera suffix changed; or an image is missing, modified, or not named by provenance.

## `render`

Renders each frozen event's pending attempt at 1280x720 through ComfyUI (design §3 step 4).
Before every image it reads `/synthbench/status/flagship.json`, and waits, polling every
5 s, while the flagship is unhealthy or has requests waiting.

| Option                 | Default  | Meaning                                              |
| ---------------------- | -------- | ---------------------------------------------------- |
| `--batch <b>`          | required | batch name                                           |
| `--budget-seconds <s>` | 480      | start no new image after this many seconds (30-3600) |

- **Reads:** specs, `provenance.json`, the status file.
- **Writes:**
  - `events/B/<id>/renders/a<k>-s<seed>.png`;
  - `provenance.json` (the render's sha256, seconds and model hashes, or a failed job);
  - `index.jsonl` rows with status `rendered`.
- **Prints:** `N rendered now, M still to render`. Run it again until M is 0.
- **Exit 1:** an event has no frozen prompt (run `check` first).
- **Exit 2:**
  - the renderer is unreachable, or stops answering mid-run;
  - the status file is missing or older than 30 s;
  - one attempt failed to render 3 times;
  - an unrecorded file is in the way.

## `camera`

Turns each new render into a 1920x1080 Foscam-style JPEG still (design §3 step 5, §7): resize,
lens distortion, IR grey at night, sensor noise, the timestamp, JPEG.

| Option        | Default  | Meaning    |
| ------------- | -------- | ---------- |
| `--batch <b>` | required | batch name |

- **Reads:** each render and its sha256.
- **Writes:** `events/B/<id>/stills/a<k>-s<seed>.jpg`, and `provenance.json` (the still's
  sha256, the parameter set, and the drawn timestamp).
- **Exit 2:** a render no longer matches its sha256; an unrecorded still differs; or the stage
  fails.

## `triage`

Records the verdicts in `batches/<b>/triage.jsonl` and schedules the allowed rerolls (design §3
step 7, §4). Each row is `{"event_id": …, "k": <attempt>, "verdict": "ok"}` or
`{…, "verdict": "reroll", "reason": <one of the seven>}`.

| Option        | Default  | Meaning    |
| ------------- | -------- | ---------- |
| `--batch <b>` | required | batch name |

- **Writes:** `provenance.json` (the verdict; attempt `k + 1` for a scheduled reroll), and
  `index.jsonl` rows with status `ready`, `rerolled` or `failed`.
- **Exit 1:**
  - a malformed, unknown or duplicated row;
  - an attempt that does not exist or has no still;
  - a changed verdict (verdicts are final).
- **Exit 2:** a reroll past the batch's 10% cap. That event is marked failed; its verdict is
  recorded.

## `report`

Writes `batches/<b>/report.md` and `batches/<b>/sheet.html` (design §3 step 8). Every run
replaces them.

| Option        | Default  | Meaning    |
| ------------- | -------- | ---------- |
| `--batch <b>` | required | batch name |

- **report.md:**
  - counts by state;
  - rerolls by reason;
  - failed events, and failures by scenario;
  - render timing (median, p90, total) and failed jobs;
  - snapshot holds from `/synthbench/status/snapshots.json`;
  - one row per event.
- **sheet.html:** a contact sheet of every event's current still.
- **Exit 2:** a corpus file cannot be read or written.

## `corpus snapshot`

Host only; the owner's `synthbench-snapshot.timer` runs it every 6 h (design §6). It snapshots
`primary/export/synthbench/corpus` as `@synthbench-<UTC time>` and prunes to the newest 5,
destroying only the oldest, and only when it holds no only copy. It writes
`/synthbench/status/snapshots.json`.

No options.

- **Exit 2:** a hold (the oldest snapshot holds the only copy of a removed or changed file), or
  a zfs failure.
```

`docs/synthbench/operator-runbook.md`:

````markdown
# Synthbench generation: operator runbook

For the owner. It covers the host side of agent-driven Tier B generation
(`docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md`): the host
units, the renderer, snapshot holds, the agent's sandbox, and reviewing a batch. The agent's
own document is `agent-handoff.md`.

## The pieces

| Piece                         | What it does                                                                                                                                               | How it runs                |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| `synthbench-guard.service`    | Every 5 s writes `status/flagship.json`. After 3 failed flagship health checks in a row it stops the renderer. It never stops or starts the flagship.      | user unit, enabled at boot |
| `synthbench-renderer.service` | ComfyUI with FLUX.2 [dev] on `127.0.0.1:8188`, `--reserve-vram 4`, bound to the guard. The pre-start check is listed below. One warm-up image after start. | user unit, started by hand |
| `synthbench-snapshot.timer`   | Every 6 h (UTC): snapshot `primary/export/synthbench/corpus`, prune by design §6, write `status/snapshots.json`.                                           | user unit, enabled at boot |
| `/synthbench/host-checkout`   | a detached worktree with its own `.venv`; the units run its code                                                                                           | updated by the owner       |

The renderer's pre-start check requires:

- a fresh guard status file and a healthy flagship;
- a flagship util gate at most 0.76;
- at least 60 GiB free on the GPU.

## Install or update the host checkout and units

```bash
cd ~/github/nemotron-v3-home-security-intelligence && git fetch origin
git worktree add --detach /synthbench/host-checkout origin/main     # the first time
git -C /synthbench/host-checkout checkout --detach origin/main      # to update
cd /synthbench/host-checkout && uv sync --frozen
mkdir -p /synthbench/status
.venv/bin/python -m synthbench.host.units install
systemctl --user enable --now synthbench-guard.service synthbench-snapshot.timer
systemctl --user restart synthbench-guard.service                          # after an update
```

`units install` writes `~/.config/systemd/user/synthbench-*` for the checkout it runs from, and
reloads systemd when a file changed. `units show` prints them.

## The renderer

- **Start:** `systemctl --user start synthbench-renderer.service`. It returns after the warm-up
  image, a few minutes the first time.
- **Stop:** `systemctl --user stop synthbench-renderer.service`. The agent's next `render`
  exits 2, and it asks you.
- **Why it refused to start:** `journalctl --user -u synthbench-renderer -n 50` names every
  reason.
- **ComfyUI's own log:** `/synthbench/logs/comfyui.log`.
- **Never enable it at boot.** It holds about 50 GiB beside the flagship, and each render slows
  the flagship's decode by about 59%.
- **Before an owner-only GPU window** (parent spec §3.6), stop the renderer unit. The window
  stops every container labelled `synthbench.gpu=1` anyway. Start the unit again after the
  window has restored the flagship.

## Read the guard

- `cat /synthbench/status/flagship.json` shows the time (UTC), `healthy`, `running`,
  `waiting` and consecutive `failures`.
- `journalctl --user -u synthbench-guard -n 50` shows "stopping the renderer" when it acted.
- After the guard stops the renderer, the renderer stays stopped. Check the flagship first
  (`curl -s 127.0.0.1:8000/health`, `docker ps --filter name=dgx-inference-vllm-1`), then start
  the renderer again.

## Resolve a snapshot hold

A hold means the oldest snapshot holds the only copy of a removed or changed file. The batch
report shows it, `status/snapshots.json` names it, and the timer's last run exited 2
(`systemctl --user status synthbench-snapshot.service`).

1. List the snapshots, oldest first, and look at what changed after the held one:

   ```bash
   zfs list -H -t snapshot -o name -s createtxg -d 1 primary/export/synthbench/corpus
   zfs diff -FH <held snapshot> <the next snapshot>
   ```

2. Either copy the files back from `/synthbench/corpus/.zfs/snapshot/<name>/…` to the
   same paths, or accept the loss with `zfs destroy <held snapshot>`.
3. Run `systemctl --user start synthbench-snapshot.service`. `status/snapshots.json` shows
   `"hold": null` once pruning gets through.

Snapshots accumulate past 5 until you resolve the hold. A file created and deleted within the
same 6 h is in no snapshot. ComfyUI keeps its own copy of every render under
`/synthbench/comfy-out/synthbench/<version>/<event id>/`.

## Create the agent's sandbox

Run this from the repository checkout at the commit the agent should use. Its workspace is a
clone of that checkout.

```bash
cd ~/github/nemotron-v3-home-security-intelligence
agent-dgx run synthbench-gen --agent claude --endpoint dgx \
  --mount /synthbench/corpus:rw --mount /synthbench/status:ro
```

Then tell the agent: "Read docs/synthbench/agent-handoff.md and follow it", with the batches you
want (for example: a 10-event pilot `pilot-1`, then a 50-event `batch-1`).

- The sandbox reaches the renderer through the host's loopback (P3 probe,
  `docs/benchmarks/synthbench/p3-probes.md`).
- The agent sometimes ends a turn mid-task after a line such as "Now rendering:". If its
  transcript goes quiet mid-batch, type "continue"; every command resumes.
- To remove the sandbox: `agent-dgx stop synthbench-gen && agent-dgx session rm synthbench-gen --force`.
- Never run `agent-dgx help` or `agent-dgx ls`: an unknown word starts a real session.

## Review a batch

1. Read the agent's report and `<corpus>/batches/<b>/report.md`.
2. Open `<corpus>/batches/<b>/sheet.html` in a browser on the host.
3. Confirm the batch from the host checkout: `cd /synthbench/host-checkout &&
.venv/bin/python -m synthbench check --batch <b>` must exit 0. It re-checks every fact
   against the sampler, every frozen prompt against the rules, and every image against its
   sha256. The agent's own clone could have been edited; this checkout was not.

## The agent's stop-and-ask questions

| The agent reports                          | You                                                                                    |
| ------------------------------------------ | -------------------------------------------------------------------------------------- |
| the renderer is unreachable or stopped     | read the guard's journal; start the renderer once the flagship is healthy              |
| the status file is stale or missing        | `systemctl --user restart synthbench-guard.service`                                    |
| the reroll cap                             | look at the failed stills; sample a replacement batch if the scenario needs the events |
| an attempt failed to render 3 times        | read its `render_failures` in `provenance.json` and ComfyUI's log                      |
| the taxonomy changed                       | a changed taxonomy needs a new corpus version: edit `version:` in the YAML             |
| a spec, prompt or image is not as expected | find out who changed it (`zfs diff` against the last snapshot) before going on         |
````

- [ ] **Step 4: Update the indexes and the design documents**

- `docs/AGENTS.md`:
  - Add a Quick Navigation row: `| \`synthbench/\` | Synthbench generation: agent handoff, command reference, operator runbook | [AGENTS.md](synthbench/AGENTS.md) |`.
  - Add the matching row to the "AGENTS.md Index" table: `| \`synthbench/AGENTS.md\` | Synthbench generation documents |`.
- `synthbench/AGENTS.md`, Layout table: add these rows.

  | Path                 | What                                                                                                              |
  | -------------------- | ----------------------------------------------------------------------------------------------------------------- |
  | `commands/`          | one module per command (`sample`, `check`, `render`, `camera`, `triage`, `report`, `corpus`); `cli.py` dispatches |
  | `prompt/`            | the prompt rules and the content blocklist that `check` enforces                                                  |
  | `status.py`          | the host status files (`status/flagship.json`, `status/snapshots.json`)                                           |
  | `generate/render.py` | ComfyUI discovery, yield to the flagship, the per-attempt FLUX.2 graph                                            |
  | `generate/camera/`   | the camera stage and its committed default parameters                                                             |
  | `host/`              | host-only: the guard, the renderer unit's checks, the unit files, snapshots and pruning                           |

  Add a Rules bullet: "`synthbench/host/` runs only on the host, under systemd, from
  `/synthbench/host-checkout`; the sandbox agent never runs it. The agent's document is
  `docs/synthbench/agent-handoff.md`."

- `backend/tests/unit/synthbench/AGENTS.md`: add a row to the Directory Structure table for
  each new file:

  - `helpers.py`, `fixtures/tiny_taxonomy.yaml`;
  - `test_cli_main.py`, `test_prompt_rules.py`, `test_cli_check.py`, `test_render.py`;
  - `test_camera.py`, `test_cli_camera.py`, `test_cli_triage.py`, `test_cli_report.py`;
  - `test_host_guard.py`, `test_host_renderer.py`, `test_host_units.py`;
  - `test_corpus_snapshot.py`, `test_command_reference.py`.

  Add a Gotchas bullet: "`helpers.stilled_batch` records stand-in image bytes (fast). Only
  `test_camera.py` and `test_cli_camera.py` run the real camera stage, on small parameters where
  they can."

- Design doc:
  - §3 step 1: `--cells <filter>` becomes `--only <scenario ids>`.
  - §3.1 rule 3: add "(1,200 characters; P3 plan ruling P3-R4)".
  - §7: after "Until it fits these…", add "Calibration is a follow-up plan (owner ruling
    2026-09-28, P3-R3)."
- Parent spec §7.3, P3 row: append "; camera calibration (D13) is a follow-up plan (owner,
  2026-09-28)".

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/ -q -n0 -p no:randomly`

Expected: PASS. Then run `SKIP=semgrep uvx pre-commit run --files docs/synthbench/*.md`;
prettier may reformat the tables. Run the test again after it does.

- [ ] **Step 6: Commit**

```bash
F="docs/synthbench/AGENTS.md docs/synthbench/agent-handoff.md docs/synthbench/command-reference.md docs/synthbench/operator-runbook.md docs/AGENTS.md synthbench/AGENTS.md backend/tests/unit/synthbench/AGENTS.md docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md backend/tests/unit/synthbench/test_command_reference.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "docs(synthbench): agent handoff, command reference, operator runbook; the reference is tested

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 7: The whole-suite gate**

```bash
uv run pytest backend/tests/unit/synthbench/ -n auto -q -p randomly
uv run mypy synthbench/
uv run ruff check synthbench/ backend/tests/unit/synthbench/
uv run ruff format --check synthbench/ backend/tests/unit/synthbench/
uv run vulture backend/ vulture_whitelist.py --config pyproject.toml
uv run pytest backend/tests/unit/synthbench/ -n0 -q --cov=synthbench --cov-report=term-missing:skip-covered | tail -30
```

Expected: every command is clean. The coverage run lists no `synthbench/commands/`,
`synthbench/prompt/`, `synthbench/host/snapshot.py` or `synthbench/status.py` line uncovered,
other than `main()` loops and the real-subprocess defaults. Push the branch and open the PR
against `docs/synthbench-agent-driven-generation` (not `main`) with
`gh pr create --base docs/synthbench-agent-driven-generation`. The body names the stacking and
ends with the `🤖 Generated with [Claude Code](https://claude.com/claude-code)` line.

---

### Task 12: The stack change: util 0.76 and the sandbox route to 8188 (another repository, owner-gated)

Design §5.3 and R2. The change is in `~/gitlab/dgx-station-inference-stack`, which is also the
live stack's working directory. **Never switch that checkout's branch for this task.** Work in
a temporary worktree, and follow that repository's own `AGENTS.md`/`CLAUDE.md` for commits.

**Files (in the stack repository):**

- Modify: `stack/profiles/vllm/qwen38-flash-next.env` (`ENGINE_ARGS` util and its comment)
- Modify: `docs/operations/agent-dgx-sessions.md` (the "Sandbox access to the host's loopback"
  section)

**Interfaces:**

- Produces: a flagship whose live `ENGINE_ARGS` carry `--gpu-memory-utilization 0.76` (Task 9's
  pre-start check reads it), and a documented, explicit sbx rule for port 8188.

- [ ] **Step 1: Find the base**

```bash
cd ~/gitlab/dgx-station-inference-stack && git fetch origin
git merge-base --is-ancestor c4e7040 origin/main && echo "MR !7 merged: base origin/main" || echo "MR !7 open: base origin/perf/flagship-kv-55gib"
git worktree add -b perf/flagship-util-076 /synthbench/tmp/stack-util-076 <the base printed above>
```

- [ ] **Step 2: Lower the util gate**

In the worktree's `stack/profiles/vllm/qwen38-flash-next.env`, change `--gpu-memory-utilization
0.84` to `--gpu-memory-utilization 0.76` in `ENGINE_ARGS`. Directly above the existing
"# --gpu-memory-utilization" comment block, add:

```bash
# --gpu-memory-utilization 0.76, LOWERED FROM 0.84 ON 2026-09-28 so the flagship can boot beside
# a resident synthbench renderer (nemotron-v3-home-security-intelligence repo,
# docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md §5.3).
# The gate needs util x 249.81 GiB (the measured PyTorch-visible total) free at boot:
#     0.84 -> 209.84 GiB. Free with FLUX.2 [dev] resident is 193.6 GiB at its 56.2 GiB peak and
#             199.7 GiB between jobs (50.1 GiB), so a crash would loop until the guard stops it.
#     0.76 -> 189.86 GiB. Passes with the renderer at its peak by 3.7 GiB, and stays 3.3 GiB
#             above the flagship's steady 186.6 GiB, so a boot that passes the gate can load.
#     0.77 -> 192.35 GiB. Passes at peak by only 1.2 GiB (rejected).
# Still costs nothing here: --kv-cache-memory-bytes pins the pool, so util is only the gate.
```

- [ ] **Step 3: Document the route**

In the worktree's `docs/operations/agent-dgx-sessions.md`, at the end of "Sandbox access to the
host's loopback", add:

````markdown
### Port 8188: the synthbench renderer (intended)

The synthbench renderer (ComfyUI, `127.0.0.1:8188`, nemotron-v3-home-security-intelligence repo)
is meant to be reachable from sandboxes: a synthbench agent renders through it. It has no
authentication, so every sandbox can reach it; this is accepted on this single-user host
(synthbench design R7). An explicit allow rule keeps it reachable if the default rule ever
becomes deny-all:

```bash
sbx policy allow network 'localhost:8188,127.0.0.1:8188,host.docker.internal:8188'
sbx policy check network host.docker.internal:8188     # Allowed
```

`MEASURED maui 2026-09-28` (synthbench P3 probe): a fresh sandbox reached a stub server on the
host's `127.0.0.1:8188` through the address recorded in the probe. Like the rules above, this
rule lives in sbx's local policy state; re-apply it after `sbx policy reset`.
````

Replace "through the address recorded in the probe" with the address Task 1 recorded.

- [ ] **Step 4: Commit and push; the owner opens the MR**

```bash
cd /synthbench/tmp/stack-util-076
git add stack/profiles/vllm/qwen38-flash-next.env docs/operations/agent-dgx-sessions.md
git commit -m "Lower the flagship's util gate to 0.76 for a resident synthbench renderer; document port 8188"
git push -u origin perf/flagship-util-076
```

GitLab is reached through the owner's laptop. If the push fails for SSH reasons, stop and hand
it to the owner. The owner opens the MR against the base from Step 1 and merges it. Then remove
the worktree: `git -C ~/gitlab/dgx-station-inference-stack worktree remove /synthbench/tmp/stack-util-076`.

- [ ] **Step 5 (owner): Apply it and add the sbx rule**

After the merge, the owner:

1. Updates the live checkout the way the stack's docs say.
2. Runs `stack/scripts/swap.sh qwen38-flash-next`. The flagship is down for about 4 minutes,
   and every flagship sandbox pauses.
3. Makes a real request through LiteLLM.
4. Runs the two `sbx policy` commands from Step 3.

Then verify:

```bash
docker inspect dgx-inference-vllm-1 --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -o 'gpu-memory-utilization [0-9.]*'
curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8000/health
sbx policy check network host.docker.internal:8188
```

Expected: `gpu-memory-utilization 0.76`, then `200`, then `Allowed: host.docker.internal:8188`.
Record the three outputs in `docs/benchmarks/synthbench/p3-probes.md` under a new "Stack
change (2026-MM-DD)" heading, and commit that file in this repository:
`docs(synthbench): record the flagship util 0.76 change`.

---

### Task 13: Host install and a live smoke (owner-gated)

**Prerequisites:** Tasks 1-12 are done, and Task 12 is applied (util 0.76 is live). The owner
agrees to start the renderer beside the flagship.

**Files:**

- Modify: `docs/benchmarks/synthbench/p3-probes.md` (a "Host install and smoke" section)

- [ ] **Step 1: The host checkout and units**

```bash
cd ~/github/nemotron-v3-home-security-intelligence && git fetch origin
git worktree add --detach /synthbench/host-checkout origin/feat/synthbench-p3
cd /synthbench/host-checkout && uv sync --frozen
mkdir -p /synthbench/status
.venv/bin/python -m synthbench.host.units install
systemctl --user enable --now synthbench-guard.service synthbench-snapshot.timer
sleep 6; cat /synthbench/status/flagship.json
journalctl --user -u synthbench-guard -n 5 --no-pager
```

Expected:

- `flagship.json` has a `time` within the last 10 s, and `"healthy":true`;
- the journal shows `watching http://127.0.0.1:8000`;
- `systemctl --user list-timers synthbench-snapshot.timer` shows the next run.

- [ ] **Step 2: Start the renderer beside the flagship**

```bash
systemctl --user start synthbench-renderer.service
systemctl --user status synthbench-renderer.service --no-pager | head -15
journalctl --user -u synthbench-renderer -n 20 --no-pager
curl -s 127.0.0.1:8188/system_stats | head -c 200; echo
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8000/health
```

Expected:

- the unit is `active (running)`;
- the journal shows `warm-up image rendered in N s`;
- ComfyUI answers;
- GPU use is about 50 GiB above the flagship alone;
- the flagship still answers `200`.

If the pre-start check refused, the journal lists each reason. Fix them, or stop and ask.

- [ ] **Step 3: A live smoke on a scratch root, not the corpus**

```bash
export SYNTHBENCH_ROOT=/synthbench/tmp/p3-smoke
mkdir -p "$SYNTHBENCH_ROOT" && ln -s /synthbench/status "$SYNTHBENCH_ROOT/status"
cd /synthbench/host-checkout
.venv/bin/python -m synthbench sample --batch smoke --n 3
```

Read the three specs. Write `$SYNTHBENCH_ROOT/corpus/tierb-v0/batches/smoke/prompts.jsonl`
with one prompt per spec, following `docs/synthbench/agent-handoff.md`. Then run:

```bash
.venv/bin/python -m synthbench check --batch smoke
.venv/bin/python -m synthbench render --batch smoke
.venv/bin/python -m synthbench camera --batch smoke
```

Open the three stills (the paths are in each `provenance.json`). Write `triage.jsonl` with an
honest verdict for each, then run:

```bash
.venv/bin/python -m synthbench triage --batch smoke
.venv/bin/python -m synthbench report --batch smoke
.venv/bin/python -m synthbench check --batch smoke
```

Expected:

- every command exits 0;
- `render` reports about 8-9 s per image at the flagship's normal load (design: 8.2-8.5 s);
- the stills are 1920x1080, with the timestamp top-left;
- the final `check` verifies 6 files.

Record the render seconds and anything that looked wrong. Then
`rm -rf /synthbench/tmp/p3-smoke && unset SYNTHBENCH_ROOT`.

- [ ] **Step 4 (owner approves): The guard's stop path, live**

The owner approves this step: it really stops the renderer. It points a second guard at a dead
port, with its own status file:

```bash
cd /synthbench/host-checkout
.venv/bin/python -m synthbench.host.guard --flagship-url http://127.0.0.1:9 --status-file /synthbench/tmp/guard-test.json --ticks 3
systemctl --user is-active synthbench-renderer.service
cat /synthbench/status/flagship.json
rm -f /synthbench/tmp/guard-test.json
systemctl --user start synthbench-renderer.service
```

Expected:

- the test guard logs `failed 3 health checks in a row: stopping the renderer`;
- the renderer is `inactive`;
- the real status file still says `"healthy":true`, because the real guard never stopped;
- the renderer starts again.

- [ ] **Step 5: The first snapshot**

```bash
systemctl --user start synthbench-snapshot.service
systemctl --user status synthbench-snapshot.service --no-pager | tail -3
cat /synthbench/status/snapshots.json
zfs list -t snapshot -r primary/export/synthbench/corpus
```

Expected: `corpus snapshot: 1 kept, no hold`, `"hold":null`, and one `@synthbench-…`
snapshot.

- [ ] **Step 6: Record and commit**

Add a "Host install and smoke (2026-MM-DD)" section to `docs/benchmarks/synthbench/p3-probes.md`
with the renderer's warm-up seconds, GPU memory before and after, render seconds per smoke
image, the guard stop-path result, and the first snapshot's name. Then:

```bash
F=docs/benchmarks/synthbench/p3-probes.md
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "docs(synthbench): host install and live smoke beside the flagship

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Acceptance: the live handoff dry run (owner)

Design §9. A flagship agent in a fresh sandbox, given only `docs/synthbench/agent-handoff.md`,
completes a 10-event pilot and then a 50-event batch.

**Gates**, all before Step 1:

- The owner signs off on `synthbench/taxonomy/tier_b_v0.yaml`. The P2 handoff lists the review
  items: generic terms such as `gun` and `bat`, the label mix, zone shares, clothing against
  scenario and weather, and lighting coverage. Any edit is free before the first real batch.
- The owner accepts `synthbench/prompt/blocklist.yaml` and the camera defaults
  (`default-v1.json`).
- Tasks 12 and 13 are done, and the renderer is running.
- The P3 PR is pushed, and the owner's checkout is at its head, because the sandbox clones it.

**Files:**

- Create: `docs/benchmarks/synthbench/p3-acceptance.md`

- [ ] **Step 1 (owner): Create the sandbox and hand over**

```bash
cd ~/github/nemotron-v3-home-security-intelligence
git switch feat/synthbench-p3 && git pull --ff-only
agent-dgx run synthbench-gen --agent claude --endpoint dgx \
  --mount /synthbench/corpus:rw --mount /synthbench/status:ro
```

The owner's only instruction:

> Read docs/synthbench/agent-handoff.md and follow it. Run a 10-event pilot named pilot-1 and
> report. Then run a 50-event batch named batch-1 and report.

The owner answers stop-and-ask questions and nothing else. The one exception: if the agent
stalls mid-turn after a line ending in ":", type "continue". Keep a list of every question the
agent asked and every nudge.

- [ ] **Step 2: Watch the flagship during the run**

Every hour or so, and after each report:

```bash
cat /synthbench/status/flagship.json
journalctl --user -u synthbench-guard --since "-2h" --no-pager | grep -c "stopping the renderer"
curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8000/health
```

Expected: healthy, `0` stops, and `200`.

- [ ] **Step 3: Confirm both batches on the host**

```bash
cd /synthbench/host-checkout && git fetch origin && git checkout --detach origin/feat/synthbench-p3
.venv/bin/python -m synthbench check --batch pilot-1
.venv/bin/python -m synthbench check --batch batch-1
```

Expected: both exit 0.

- [ ] **Step 4 (owner): Look at the camera stage against a real still**

Plan ruling P3-R16 is **[A]**. The owner compares one pilot still with a real Foscam still on
the host:

- the timestamp's position, format and size;
- noise, contrast and JPEG look.

Differences become inputs to the calibration follow-up, not fixes here.

- [ ] **Step 5: Record the result**

`docs/benchmarks/synthbench/p3-acceptance.md`:

```markdown
# Synthbench P3 acceptance: the live handoff dry run (2026-MM-DD)

Design §9: a flagship agent in a fresh sandbox, given only `docs/synthbench/agent-handoff.md`,
completes a 10-event pilot and a 50-event batch.

| Criterion (design §9)                                  | Result |
| ------------------------------------------------------ | ------ |
| the reports arrive                                     |        |
| the owner's host `check` passes on both batches        |        |
| the flagship stays healthy throughout (guard stops: 0) |        |
| the owner only read reports and answered stop-and-ask  |        |

## Batches

| Batch   | Events | Ready | Rerolled (by reason) | Failed | Median render s | Failed jobs |
| ------- | ------ | ----- | -------------------- | ------ | --------------- | ----------- |
| pilot-1 |        |       |                      |        |                 |             |
| batch-1 |        |       |                      |        |                 |             |

## Stop-and-ask questions and nudges

## What the agent changed after the pilot

## Camera stage against a real still (owner)

## Follow-ups
```

Fill every cell from the reports, `report.md` and the owner's notes. Commit it:
`docs(synthbench): P3 acceptance - live handoff dry run`.

**Pass:** all four criteria hold. **Fail:** record which criterion failed and why, and stop
for an owner decision. Do not change the plan's code to force a pass.

---

## After the plan

- **Retarget the PR.** When #6703 merges, retarget this plan's PR from
  `docs/synthbench-agent-driven-generation` to `main` with `gh api -X PATCH`. If P2 changes in
  review, rebase this branch onto it instead of merging.
- **Calibration** (P3-R3, parent D13) gets its own plan. `synthbench camera calibrate` reads
  `/export/foscam` on the host and writes a committed parameter file of numbers only. It needs
  the owner to map the five real cameras to camera types, and Task 14's camera notes.
- **The P3 design notes the P2 handoff raised are all in this plan:**
  - the replace path: P3-R5, P3-R6, Task 2;
  - the sandbox mount: Task 1;
  - rerun compares facts only: Task 2;
  - line-atomic index appends: Task 2;
  - validation gaps: Task 2;
  - quota semantics: P3-R12;
  - the `--cells`/`--only` naming: Task 11;
  - `main()` error handling: Task 3.
- **Next phase:** P4, the verifier and audit page (parent §4, §7.3), follows from a corpus that
  Task 14 proved can be generated.
