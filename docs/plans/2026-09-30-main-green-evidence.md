# Make main green for the right reasons — measured evidence (2026-09-30)

**Provenance, and a warning.** The first draft of this doc was assembled from
eight subagents. **I re-measured its load-bearing claims myself and several were
fabricated** — quotes absent from logs I then read end to end, `file:line`
citations past a file's last line, and files that do not exist. Every claim below
is something I read with my own tools on 2026-09-30. Where a claim is NOT mine it
is marked **(unverified)**. Discarded fabrications are listed in §6 so nobody
re-imports them from the earlier draft.

Re-take anything with:

```bash
R=mikesvoboda/nemotron-v3-home-security-intelligence
gh api "repos/$R/commits/<sha>/check-runs?per_page=100" --paginate \
  --jq '.check_runs[] | [.status, .conclusion // "null", .name] | @tsv'
gh api "repos/$R/actions/jobs/<job-id>/logs"
gh api "repos/$R/check-runs/<check-run-id>/annotations" \
  --jq '.[] | "\(.path):\(.start_line) \(.message)"'
```

`--paginate` is not optional. And a SHA's check-runs span **several workflow
runs**, not one — these totals are not comparable to a single run's job count.

## 1. Baseline table (my own `--paginate` pulls)

| SHA        | role                              | total | success | skipped | failure | cancelled | CI Gate (Required Checks) |
| ---------- | --------------------------------- | ----- | ------- | ------- | ------- | --------- | ------------------------- |
| `18339acd` | pre-R8-S3                         | 137   | 78      | 48      | 8       | 3         | **failure**               |
| `cc1fde32` | previous main tip                 | 131   | 90      | 30      | 10      | 1         | success                   |
| `67ca4870` | current main tip (PR #6740 merge) | 118   | 85      | 22      | 9       | 2         | success                   |

At `18339acd` the Gate was red **while `Deploy to Staging` succeeded** (observed:
`completed / success / Deploy to Staging`), and its eight failures were
`Analyze (python)`, `Analyze (javascript-typescript)`, `Create Linear Issue on
Main CI Failure`, `Rollback to Stable Images`, `SBOM & Sign (frontend)`,
`Smoke Test Deployment`, `validate-agents-md` — the three `Build ai-*` jobs that
failed later were **not** red yet, which is the R8-debt boundary: they flipped
green→failure at S3. Which of those eight is the _required_ member that fails the
Gate is **not visible from the repo** (no `required_status_checks` in any
`.github/workflows/*.yml`; the branch-protection API is not readable from here) —
do not assert a cause for it.

### 1a. PR #6740's proof, restated with correct numbers

At `cc1fde32` exactly three retired-image check-runs existed, all red:
`Build ai-florence (linux/amd64)`, `Build ai-clip (linux/amd64)`,
`Build ai-enrichment (linux/amd64)`. At `67ca4870` a case-insensitive grep of all
118 rows for `ai-florence|ai-clip|ai-enrichment` returns **zero matches**.
Totals moved **131 → 118**, not 121 → 113 (121 was a single-run job count — a
category error). `Deploy to Staging`: **skipped** at `cc1fde32` → **success** at
`67ca4870` (`job 110089183542`, `attempt 1`).

### 1b. Failure-set diff, `cc1fde32` → `67ca4870`

Gone: the three `Build ai-*` jobs, `Visual Regression Tests`.
New: `Dependabot` ×2, `SBOM & Sign (frontend)` — but at `cc1fde32` that job is
**skipped under its unexpanded placeholder name** `SBOM & Sign (${{ matrix.image
}})`, and it fails **byte-identically at pre-S3 `18339acd`**. So it is
newly-**revealed**, not newly-caused. Everything else was already red:
`Smoke Test Deployment`, `Rollback to Stable Images`, `Analyze (python)`,
`Analyze (javascript-typescript)`, `validate-agents-md`,
`Create Linear Issue on Main CI Failure`.
Also cancelled at both `cc1fde32` and `67ca4870`: `ZAP API Scan` (at
`18339acd` three check-runs are cancelled; I did not name them).

## 2. Deploy tier

### 2.1 `Smoke Test Deployment` — the runner cannot run these two containers

`.github/workflows/deploy.yml` step `Start services` runs
`docker compose -f docker-compose..github/workflows/ci.yml up -d`. At `67ca4870`
(`job 110089183722`, `attempt 1`) the log says, verbatim:

```
 Container nemotron-v3-home-security-intelligence-postgres-1  Error
 Container nemotron-v3-home-security-intelligence-redis-1  Error
dependency failed to start: container ...-postgres-1 exited (1)
##[error]Process completed with exit code 1.
=== Postgres Logs ===   postgres-1 | chown: /var/lib/postgresql/data: Operation not permitted
=== Redis Logs ===      redis-1    | setpriv: setresuid failed: Operation not permitted
... postgres-1  postgres:16-alpine          Exited (1)
... redis-1     redis:7.4-alpine3.21        Exited (127)
```

`127` is real but it is redis's **exit code**, not a missing command: the alpine
entrypoint's `setpriv` is refused. Cause is in `docker-compose..github/workflows/ci.yml`: postgres
`:20-26` and redis `:51-56` both set `security_opt: no-new-privileges:true` plus
`cap_drop:` — hardening the entrypoints then need `chown`/`setpriv` the runner
will not grant. Identical text at Identical text at `18339acd`,
`run 36648672656 / job 109680187140` (log lines 501-537) — a job id taken from
that SHA's own `check-runs` `details_url`, because the id I first guessed returned 404. Pre-existing and unchanged by R8. Fix is one file, either compose-side (run the DB containers
with the privileges their entrypoints assume, or pre-initialized volumes) or
runner-side. **`Post-Deployment Validation` is skipped by design**: `if: failure()`
— it is a failure-only job, not collateral.

### 2.2 `SBOM & Sign (frontend)` — signing a tag that was never pushed

Failing step `Sign container image`, `job 110089183606` at `67ca4870` and
`job 109685442011` at `18339acd`, same message modulo the SHA:

```
Error: signing [.../frontend:67ca48707b6110e38e6b1ecf3b5f142de9f82972]: accessing entity:
entity not found in registry, error: GET .../frontend/manifests/67ca48707b6110e38e6b1ecf3b5f142de9f82972:
MANIFEST_UNKNOWN: manifest unknown
```

That is **not** a permission or key problem: the first `cosign sign` of the same
step (`:latest`) got as far as `Generating ephemeral keys… Signing artifact…`
with no error, and `.github/workflows/deploy.yml:356-358` already grants
`id-token: write`. The tag simply does not exist. `merge-core` extracts its tags
with `type=sha,prefix=` (`.github/workflows/deploy.yml:147-149`) whose default is the **short** SHA
— its own log lists exactly `frontend:latest` and **`frontend:67ca487`** — while
`.github/workflows/deploy.yml:391-392` signs `:latest` and **`:${{ github.sha }}`** (40 chars).
So the pair never matched: `:latest` is signed, the full-SHA tag is not, and the
step exits 1. Same one-line mismatch explains `18339acd`. `:508`
`echo "3. … Tags: latest, ${{ github.sha }}"` repeats the false claim.
**Repo-side, small.** `SBOM & Sign (backend)` = `cancelled` is matrix fail-fast
of this same cause — one bug, not two. (Corroborating detail I did _not_
independently confirm: cosign's own warning that tag-based signing will stop
working — the durable fix is to sign by digest.)

### 2.3 `Rollback to Stable Images` — my original framing was right; it fails on a permission

`.github/workflows/rollback.yml:3-8`, verbatim:

```yaml
on:
  # Triggered automatically on deployment failures detected by smoke tests
  workflow_run:
    workflows: ['Deploy']
    types: [completed]
    branches: [main]
```

so it **does** fire on a failed Deploy, and `evaluate-rollback` is gated by
`:19` `if: github.event.workflow_run.conclusion == 'failure'`. Fix §2.1 + §2.2
and the Deploy run concludes `success` → evaluation skipped → nothing fires.
No need to edit this file to silence anything.

And its red is **not** a failed rollback. At `67ca4870` (`job 110090308559`) the
steps are: `Set up job`, `Checkout`, `Log in to Container Registry`,
`Get current image tags`, `Verify previous images exist`,
`Document rollback decision`, `Upload rollback report` — all success — then
**`Create rollback issue` = failure**:

```
RequestError [HttpError]: Resource not accessible by integration - https://docs.github.com/rest/issues/issues#create-an-issue
```

Because the `rollback` job's permissions are `contents: read` + `packages: read`
(`.github/workflows/rollback.yml:75-79`) and `Create rollback issue` (`:154`) runs
`actions/github-script` with `secrets.GITHUB_TOKEN`. **One missing
`issues: write`.** Repo-side. Note the job _did_ run (`if:`
`needs.evaluate-rollback.outputs.should-rollback == 'true'`, `:74`), so a
rollback was judged necessary on every one of these pushes — worth reading before
trusting that decision logic.

## 3. Advisory / security

### 3.1 CodeQL — two files, one bug pattern, CodeQL 2.27.1

Pulled from the check-run annotations verbatim (`codeql database run-queries`,
exit code 2):

```
ERROR: getValue() cannot be resolved for type FastApiModifyingDecorator.extends
  (.github/codeql/custom-queries/python/fastapi-missing-auth.ql:24,12-20)
ERROR: getName() cannot be resolved for type DangerousHtmlAttribute.extends
  (.github/codeql/custom-queries/javascript/react-dangerous-html.ql:20,35-42)
```

Two **different** files, same shape: a `class … extends <LibraryClass>` whose
constructor body calls `this.getValue()` / `this.getName()` inside `exists(…)`.
I read the python one: `:19 class FastApiModifyingDecorator extends Decorator`
and `:24 this.getValue() = call and`. So the line is **24, not 19** (19 is where
the class opens). **Neither language is failing on findings — both fail to
compile**, so the custom pack contributes zero results today. Whether `Decorator`
/ `HtmlDecorator` even expose a name accessor at 2.27.1 is **not determinable
from this repo**: the CodeQL library is not vendored here and CI runs
`build-mode: none`, so these queries are never compiled until they break. Fix by
reading the installed library's own `.qll` in a scratch CodeQL checkout, not by
guessing.

### 3.2 Both Linear reds are ONE missing/invalid `LINEAR_API_KEY`

`Create Linear Issue on Main CI Failure` (`job 110089694040`), failing step
`Create new Linear issue for CI failure`:

```
Response: {"errors":[{"message":"Authentication required, not authenticated","extensions":{"type":"authentication error","code":"AUTHENTICATION_ERROR","statusCode":401,…}}]}
```

`validate-agents-md` — which I had assumed was an unrelated doc check — fails the
same way: `job 110087866933` logs
`Error searching for existing task: Client error '401 Unauthorized' for url 'https://api.linear.app/graphql'`.
It is `.github/workflows/agents-md.yml:17` running
`scripts/agents_md_linear_sync.py` with `LINEAR_API_KEY: ${{
secrets.LINEAR_API_KEY }}` (`:59`). (**There is no
`scripts/validate-agents-md.py`** — the job name and the script name differ.)
So **§3.2 is one owner-side fix, two reds.** I did not verify _why_ (unset vs
expired vs scoped) — that is owner territory; do not probe by rotating.

### 3.3 The two `Dependabot` check-runs are GitHub's, and they are failing upstream _(superseded on 2026-10-01 — the headline is wrong; see 3.3a at the end of this section)_

They are **not** repo workflows: `path = dynamic/dependabot/dependabot-updates`,
`event = dynamic`, and the run titles are real security-update jobs —
`uv in /. for cryptography, ecdsa - Update #1600839002` and
`npm_and_yarn in /archive for @vitest/mocker, nanoid, … - Update #1600839005`.
The updater log opens with
`🤖 ~ Failed to parse GITHUB_REGISTRIES_PROXY environment variable ~` and then repeats
`<Error><Code>AccessDenied</Code><Message>Access Denied</Message>…` from blob
storage. Nothing in this repo is at fault. **But do not shrug it off**: it means
Dependabot security updates against `cryptography` (advisories listed up to
`< 50.0.0`) and `ecdsa` are not landing. `gh run list --workflow Dependabot`
finds nothing (it is not a repo workflow), so "is this new?" is **unverifiable**
— it is not per-push and should not be charged to a main push.

#### 3.3a. Correction, 2026-10-01 (ledger row 63, PR #6748) — the headline above is WRONG

Row **63** on `chore/main-green-dependabot` fetched BOTH updater job logs
(`gh api repos/$R/actions/jobs/110087949686/logs` — 2100+ lines) and read them
end to end. The failure table at the end of the uv-job log names two errors,
**neither one AccessDenied**:

- `cryptography` — `dependency_file_not_resolvable`: the patched version for
  CVE-2026-69247 (alert 305, high, affected `>= 44.0.0, < 50.0.0`, open since
  2026-08-04) is 50.0.0, and **our** optional `nemo` extra blocks the bump —
  `pyproject.toml:165` pins `data-designer>=0.9.2`, whose engine caps
  `cryptography>=48.0.1,<=49` (`pyproject.toml:160` records the ceiling). The
  resolution fails on the `python_full_version >= '3.15'` split, and
  `uv.lock:710` sits at `cryptography==49.0.0` — INSIDE the advisory range, so
  the repo stays exposed no matter how often Dependabot retries.
- `ecdsa` — `security_update_not_found` at `dependency-version: 0.19.2`: the
  lock ALREADY has `ecdsa==0.19.2` (`uv.lock:922`); alert 10's affected range
  is `>= 0` — CVE-2024-23342, for which there IS no patched version. Nothing
  can land because there is nothing to update.

The 211 `AccessDenied` bodies are real but sit on the updater's proxy fetches of
alternate index URLs (`403 https://download.pytorch.org:443/whl/cpu/httpx/`),
which the job survived; the second job (`110087944118`, archive/npm) has **zero**
AccessDenied lines and carries the same `GITHUB_REGISTRIES_PROXY` parse notice —
that notice fires on a legitimately-empty env var and shows up in succeeding
jobs too. What survives of the section above: these check-runs are GitHub's, not
repo workflows, and not per-push. What does not survive: "nothing in this repo
is at fault" — half the cause is OUR `cryptography` ceiling. Owner options 1/2/3
(wait for a `data-designer` release; restructure the `nemo` extra; accept with
who/when on the accepted-red list) are recorded in row 63, deliberately not
executed. The paragraph above stays verbatim as what was measured on 2026-09-30;
this section is what was measured on 2026-10-01.

## 4. Repo residue — verified, and two claims I could not reproduce

Retired names: `ai-florence`, `ai-clip`, `ai-enrichment`, `ai-llm`, `ai-yolo26`.

| claim | verdict | what I actually measured |
| ----------------------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/seed-events.py:5674` names a retired service | **CONFIRMED, live code** | `instances = ["ai-gateway:8090", "ai-vlm:8098", "ai-florence:8092", "backend:8000"]` — a health probe pointed at a deleted container |
| `setup_lib/image_pull.py` size keys | **CONFIRMED** (numbers were wrong in the old draft) | flat ints at `:219-222`: `"ai-yolo26": 8000, "ai-florence": 6000, "ai-clip": 6000, "ai-enrichment": 6000` — yolo26 stays, three go |
| conflict markers | **CONFIRMED, one file, resolvable** | `git grep -n '^<<<<<<< '` returns exactly one file: `data/ai-pipeline-evaluation/04-fastapi-backend-evaluation.md` `:447 <<<<<<< HEAD`, `:449 =======`, `:451 >>>>>>> 95005836` (all three markers — _not_ an unresolvable pair) |
| `ai/gateway/export/` "57 hits / 18 files, florence exporters to delete" | **REFUTED as stated** | 18 `ls` entries. `grep -ilE 'florence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | ai-clip | clip | enrichment'`→ **9** files:`AGENTS.md`, `README.md`, `export_clip.py`, `export_clip_text.py`, `export_fashion_clip.py`, `export_reid.py`, `export_yolo_pose.py`, `export_yolo_threat.py`, `ai/gateway/export/export_all.sh`. **`florence`appears in ZERO files** — the old draft's delete list named six files that do not exist. Survivors present:`copy_yolo26_engine.py`, `export_yolo26.py`, `export_yolo_threat.py`, `export_yolo_pose.py`, `export_reid.py`. Its own docs disagree: `ai/gateway/export/README.md:29`calls`export_clip.py`a CLIP ViT-L/14 exporter,`ai/gateway/export/AGENTS.md:14`and`ai/gateway/export/export_all.sh:112`say SigLIP 2 replaced CLIP ViT-L. **Per-file ruling, never`rm -rf`\*\* |
| `model_downloader.py` live module / dead dispatch | **CONFIRMED in substance, line numbers differ** | live: `prompt_and_download_models` at `:913`, called from `setup.py`. Unreachable dispatch **calls** at `:1040 download_nemotron_gguf`, `:1060 download_stgcnpp` (that is the real name), `:1065 download_yolo_world`, `:1070 download_marqo_fashionsiglip`. `models.yml` is at the **repo root, not `config/`**, and its `method:` histogram is **skip 5, yolo26 1, osnet 1 = 7** — none of them selects those four. No `download_yolov8s` call found |
| ghcr `ai-vlm` gap | **REAL, but not the shape I wrote** | `^  ai-vlm:` counts: ci **0**, ghcr **0**, **prod 1**, test **0**. In `docker-compose.ghcr.yml` the only `ai-vlm` hits are comments (`:26`, `:241`); `backend`'s `depends_on:` (`:268-276`) names postgres, redis, ai-gateway, go2rtc — **no dangling `ai-vlm` dependency**. `.env.example:417` is accurate. So the gap is **compose parity**: the prod stack can run the VLM verdict engine, the ghcr-published stack cannot. Already recorded as an owner-adjudicated publish gap in `.github/workflows/deploy.yml:30-32`. **report-only** |
| R8 S1 leftover: legacy still selectable? | **NO — clean** | `backend/core/config.py:1074-1082` raises; no `LegacyPipeline` class anywhere; `backend/services/pipeline_factory.py:11` documents the retirement. `docker-compose.prod.yml:484` is `PIPELINE_MODE=${PIPELINE_MODE:-vlm}`. **No `PIPELINE_MODE` in `docker-compose.test.yml`, and none in `backend/tests/conftest.py`** — the claim that prod/test still boot legacy is false |

**Retired names in `.github/workflows/` — the true list is two lines, both
comments.** Grepping every workflow for the five names returns only
`.github/workflows/ci.yml:1869` and `.github/workflows/deploy.yml:25-26`, both deletion notes (allowed prose). The
claimed live residues in `nightly-validation.yml`, `sbom.yml`,
`ai-platform-status.yml` are **in files that do not exist** — `.github/workflows/`
has 43 files and none of those three is among them. So there is **no workflow-side
residue sweep to do**, and `.github/workflows/deploy.yml` is already clean apart from its own
comment.

## 5. Standing rulings this work must respect

The ghcr compose-parity gap, the `ai/gateway/export/` per-file calls,
`ai-llm-vllm`, `models.yml`, anything under `docs/vss-integration/**` (frozen
research), any spec's `Status:`/rev line, generated renders, and the coverage
floors **84 unit / 37 integration** (`.github/workflows/ci.yml:613`, `:1215`) — report direction,
never lower. The suppression registry is regenerated, never hand-edited
(`.github/suppression-registry.yml:781,814` carry `reason: ai-vlm service not
available` today). `backend/services/notification_filter.py:35 should_notify`
stays. The OWNER merges; agents never merge their own.

## 6. Fabricated claims discarded (do not re-import)

1. `scripts/smoke-test.sh:43` sourcing `backend/venv/bin/activate`, a `set -u`
   `$VIRTUAL_ENV` error, and a `elif[[ ` typo — **zero `venv` hits in that job
   log**; `scripts/smoke-test.sh` is not even invoked by the failing step, which only runs
   `docker compose -f docker-compose..github/workflows/ci.yml up -d`.
2. "`.github/workflows/rollback.yml` has no `workflow_run`, is `workflow_dispatch`-only, 310 lines
   of which `:131/:143` are dead expressions" — the trigger **is**
   `workflow_run` (`:3-8`); the real bug is a missing `issues: write`.
3. "`validate-agents-md` runs `scripts/validate-agents-md.py` and never touches
   Linear; it reports docs drift since 2026-08-20" — the script does not exist;
   the job's own log is a Linear 401.
4. "`SBOM & Sign` lacks `id-token: write`; ghcr answered `DENIED: Request denied
by usage policy`" — `id-token: write` is at `.github/workflows/deploy.yml:358`; the log says
   `MANIFEST_UNKNOWN`, no `DENIED` anywhere in the file.
5. Six `ai/gateway/export/*florence*` filenames, and `export_demographics.py` /
   `export_depth.py` / `export_pet.py` / `export_vehicle.py` / `export_stgcn.py`
   as clip-hit files.
6. `.github/workflows/nightly-validation.yml:147 "Verify Florence Available"`,
   `sbom.yml:122,137`, `ai-platform-status.yml:41,43`,
   `.github/workflows/deploy.yml:1131-1135 for SERVICE in ai-florence ai-enrichment` (the file is
   **637** lines), `backend/core/config.py:1070 if value not in {"vlm",
"legacy"}`, `docker-compose.test.yml:78 PIPELINE_MODE: legacy`,
   `backend/tests/conftest.py:55`, `data/…/04-…md` having only two conflict
   markers, `models.yml` living in `config/`, `ai-vlm` being referenced from
   `docker-compose.ghcr.yml:162`, and the JS CodeQL failure being "5 real alerts
   in 2 files" (it is a compile error, §3.1).
7. "`LINEAR_API_KEY` absent in 0 of 232 runs", "the rollback run printed
   `Decision: No rollback needed`", and "`Visual Regression` failed on a retry
   then passed". (Careful with the neighbouring one: `Deploy to Staging` =
   **success at `18339acd`**, **skipped at `cc1fde32`**, **success again at
   `67ca4870`** — I briefly conflated the first two. The `cc1fde32` skip is the
   poisoning PR #6740 removed; the Gate red at `18339acd` is still unexplained,
   see §1.)

**(unverified) carried forward, cheap to check when needed:** whether the
rollback job's `should-rollback` decision is correct on these pushes; whether any
earlier Dependabot security job ever succeeded; why `LINEAR_API_KEY` fails auth.
