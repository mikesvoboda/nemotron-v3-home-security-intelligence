#!/usr/bin/env python3
"""Gate test for the integration-shard retry wiring (WP0.5 follow-through).

    uv run python scripts/test_shard_retry_wiring.py

Evidence this pins (run 35353201418, commit 4805d98d, 2026-09-18): the API
shard 1/2 job degraded across three full attempts of the SAME commit —
23m54s pass -> per-test 30s timeouts -> cancelled at GitHub's 30m0s job cap.
Two defects in one class came out of that:

  1. INVISIBILITY: `integration-tests-summary` forgave anything that was not
     the literal string "failure", so a CANCELLED shard printed "All
     integration tests passed" and `CI Gate` — the repo's ONLY branch-
     protection context — went green with the shard dead. WP0.6's graph test
     couldn't catch it: statically the result IS read; the sever is the
     runtime string comparison.

  2. NO RECOVERY: a slow-runner cancellation burned the whole attempt. A
     retry INSIDE the job cannot help the observed terminal mode — the
     binding constraint was the job cap the first attempt exhausted. Recovery
     must be a fresh JOB with a fresh budget.

Doctrine (owner ruling 2026-09-18, extending WP0.5's "runner-job retry of the
AUDIT step's inputs, decided then"): retry ONLY `cancelled` — never
`failure`. Retrying genuine test failures is the retry-mask class (see
validate.sh's own comment at the "retry-mask" line); a slow-runner `failure`
indistinguishable from a regression stays red and comes back to the owner.

Mechanism: `integration-tests-api` becomes a call to a reusable workflow;
`integration-tests-api-retry` is the same call gated on the parent result
being `cancelled`; artifact names carry an `-retry` suffix (upload-artifact
names must be unique per run, and the TPA/coverage globs `test-results-*` /
`coverage-integration-*` still match). The summary forgives `cancelled` ONLY
against a green retry.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / ".github" / "workflows" / "ci.yml"
REUSABLE = ROOT / ".github" / "workflows" / "integration-shard.yml"

REUSABLE_REF = "./.github/workflows/integration-shard.yml"

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        failures.append(msg)


def load(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh)


def step_script(job: dict, needle: str) -> str:
    """Concatenated run-scripts of every step of a job (for text assertions)."""
    parts = []
    for step in job.get("steps") or []:
        run = step.get("run")
        if run and needle in run:
            parts.append(run)
    return "\n".join(parts)


def main() -> int:
    ci = load(CI)
    jobs = ci["jobs"]

    # --- 1. the shard job delegates to a reusable workflow -------------------
    api = jobs.get("integration-tests-api") or {}
    check(
        api.get("uses") == REUSABLE_REF,
        "integration-tests-api must call the reusable shard workflow "
        f"(uses: {REUSABLE_REF}); found: {api.get('uses')!r}",
    )
    check(
        api.get("strategy", {}).get("matrix", {}).get("shard") == [1, 2, 3, 4],
        "integration-tests-api must keep the 4-way shard matrix (WP3.7 2-way superseded 2026-09-19)",
    )
    check(
        api.get("secrets") == "inherit",
        "integration-tests-api caller must pass secrets: inherit",
    )

    # --- 2. the retry job exists and is gated on CANCELLED ONLY --------------
    retry = jobs.get("integration-tests-api-retry") or {}
    check(
        retry.get("uses") == REUSABLE_REF,
        "integration-tests-api-retry must call the same reusable workflow",
    )
    check(
        "integration-tests-api" in (retry.get("needs") or []),
        "the retry job must need integration-tests-api",
    )
    retry_if = str(retry.get("if", ""))
    check("'cancelled'" in retry_if, "retry if: must fire on result == 'cancelled'")
    check(
        "'failure'" not in retry_if,
        "retry if: must NOT fire on 'failure' — retrying real test failures "
        "is the retry-mask class (WP0.5 doctrine)",
    )
    check(
        "always()" in retry_if,
        "retry if: needs always() or the skipped-parent case kills it",
    )
    retry_with = retry.get("with") or {}
    check(
        retry_with.get("artifact-suffix") == "-retry",
        "the retry call must suffix its artifacts (-retry): upload-artifact "
        "names are unique per run, and the prior attempt's files must not "
        "be overwritten or collide",
    )

    # --- 3. the reusable workflow is a real tier -----------------------------
    if REUSABLE.exists():
        ws = load(REUSABLE)["jobs"]
        check(len(ws) == 1, "reusable workflow must define exactly one job")
        wjob = next(iter(ws.values()))
        check(
            wjob.get("timeout-minutes") == 30,
            "reusable shard job keeps the 30-min cap UNRAISED (raising it "
            "would widen the gate to pass — prohibited)",
        )
        check(
            "postgres" in (wjob.get("services") or {}) and "redis" in (wjob.get("services") or {}),
            "reusable shard job must carry the postgres+redis services",
        )
        body = step_script(wjob, "pytest")
        check("--splits 4" in body, "reusable shard runs pytest-split --splits 4")
        check(
            "inputs.shard" in body,
            "shard group must come from workflow_call inputs",
        )
        check(
            "inputs.artifact-suffix" in body,
            "junit/coverage filenames must include the suffix input",
        )
        check(
            "flake-k-filter.py" in body,
            "the allowlist flake pre-rerun (WP governance) must survive the move",
        )
        # YAML `on:` loads to Python True (bool key) — that's the workflow_call root.
        wc_inputs = (load(REUSABLE).get(True) or {}).get("workflow_call", {}).get("inputs", {})
        for name in ("shard", "artifact-suffix", "python-version"):
            check(
                name in wc_inputs,
                f"workflow_call inputs must include {name!r}",
            )
        # The reusable workflow gets NO top-level env from the caller — the
        # UV_VERSION mirror inside it must equal ci.yml's or the retry tier
        # silently installs a different uv than the primary.
        ci_uv = (ci.get("env") or {}).get("UV_VERSION")
        check(
            (wjob.get("env") or {}).get("UV_VERSION") == str(ci_uv),
            "reusable workflow must mirror ci.yml's env.UV_VERSION exactly "
            f"(ci.yml: {ci_uv!r}); top-level caller env does NOT flow into "
            "reusable workflows, so a drifting mirror is a silent version skew",
        )
        uploads = " ".join(
            str((s.get("with") or {}).get("name", ""))
            for s in wjob.get("steps") or []
            if s.get("uses", "").startswith("actions/upload-artifact")
        )
        check(
            "artifact-suffix" in uploads,
            "artifact NAMES must carry the suffix (uniqueness per run)",
        )
        # Globs that downstream consumers use must still match suffixed names.
        for prefix, glob in (
            ("test-results-integration-api-", "test-results-*"),
            ("coverage-integration-api-", "coverage-integration-*"),
        ):
            stem = glob.replace("*", "")
            check(
                any(u.strip().startswith(stem) for u in uploads.split()),
                f"artifact name {prefix}... must keep matching glob {glob}",
            )
    else:
        failures.append(f"missing reusable workflow: {REUSABLE}")

    # --- 4. the summary forgives cancelled ONLY against a green retry --------
    summary = jobs.get("integration-tests-summary") or {}
    sbody = step_script(summary, "needs.")
    check(
        "integration-tests-api-retry.result" in sbody,
        "summary must read the retry job's result",
    )
    check(
        "cancelled" in sbody,
        "summary must treat 'cancelled' explicitly — today's bug is that "
        "only the literal 'failure' turns it red, so a cap-cancelled shard "
        "silently passed CI Gate (attempt 4, 2026-09-18)",
    )

    # --- 5. coverage merge sees the retry's artifacts ------------------------
    merge = jobs.get("integration-coverage-merge") or {}
    check(
        "integration-tests-api-retry" in (merge.get("needs") or []),
        "coverage merge must need the retry job so its artifacts are "
        "finalized before the pattern download",
    )

    # --- 6. this file is in the anti-rot runner list -------------------------
    # (the list lives in the collection-sanity job — assert presence in the
    # workflow rather than pinning that job id, which has drifted before)
    check(
        "scripts/test_shard_retry_wiring.py" in CI.read_text(),
        "this gate test must ride ci.yml's anti-rot list",
    )

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        print(f"\n{len(failures)} failure(s): shard-retry wiring drifted (see docstring).")
        return 1
    print("shard-retry wiring: all invariants hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
