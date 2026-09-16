#!/usr/bin/env python3
"""Gate test for the WP0.8 flaky-marker governance (run explicitly; outside testpaths).

    uv run python scripts/test_flaky_marker_governance.py

WP0.8 invariant: @pytest.mark.flaky is a QUARANTINE, and quarantines are
governed — a marked test only collects if .github/flake-allowlist.yml carries a
matching entry (tracking ref + expiry enforced by check-flake-allowlist.py).
Historical harm this pins: backend/tests/conftest.py's pytest_runtest_makereport
silently converted failures on ANY flaky-marked test to skips — no owner, no
expiry, no review — while the governed allowlist mechanism (spec §5.2) sat
beside it with `flakes: []`. The nightly detector even recommended the ungoverned
marker as remediation.

Cases:
  1. a flaky-marked test with NO allowlist entry fails COLLECTION naming it;
  2. the same test with an entry collects fine (registration unblocks);
  3. an entry whose id does not match still fails collection (typo ≠ governance);
  4. the repo's real tree collects clean (no unregistered marks shipped).

Uses FLAKE_ALLOWLIST_FILE as the test seam (same seam conftest's gate reads),
so nothing here mutates the repo's real allowlist.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRATCH_DIR = ROOT / "backend" / "tests" / "unit"
HEADERS = '"""tmp governance probe (created/removed by scripts/test_flaky_marker_governance.py)."""\nimport pytest\n\n'


def run_pytest(path: Path, allowlist: Path | None) -> subprocess.CompletedProcess[str]:
    import os

    env = dict(os.environ)
    if allowlist is not None:
        env["FLAKE_ALLOWLIST_FILE"] = str(allowlist)
    else:
        env.pop("FLAKE_ALLOWLIST_FILE", None)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(path),
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
        env=env,
    )


def write_probe(tmp: Path, name: str, marker: str = "@pytest.mark.flaky") -> Path:
    p = SCRATCH_DIR / f"test_wp08_probe_{name}.py"
    body = HEADERS + f"{marker}\ndef test_probe_{name}():\n    assert True\n"
    p.write_text(body)
    return p


def allowlist_with(tmp: Path, *ids: str) -> Path:
    al = tmp / "allowlist.yml"
    lines = ["flakes:"]
    for i in ids:
        lines += [f"  - id: {i}", "    tracking: NEM-GATE-TEST", "    expires: 2099-01-01"]
    al.write_text("\n".join(lines) + "\n")
    return al


def main() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            print(f"FAIL: {msg}", file=sys.stderr)
            failures.append(msg)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        probe = write_probe(tmp, "unreg")
        try:
            # 1. unregistered mark -> collection fails, names the test
            r = run_pytest(probe, None)
            check(
                r.returncode != 0, "unregistered @pytest.mark.flaky collected (gate is toothless)"
            )
            combined = r.stdout + r.stderr
            check(
                "test_wp08_probe_unreg" in combined,
                f"collection failure did not name the offending test: {combined[-400:]}",
            )

            # 2. registered -> collects clean
            r = run_pytest(probe, allowlist_with(tmp, "test_probe_unreg"))
            check(
                r.returncode == 0, f"registered mark blocked anyway: {(r.stdout + r.stderr)[-400:]}"
            )

            # 3. non-matching entry (typo) -> still fails
            r = run_pytest(probe, allowlist_with(tmp, "test_probe_typo_here"))
            check(
                r.returncode != 0,
                "a non-matching allowlist entry un-quarantined an unregistered test",
            )

            # 3b. an EXPIRED entry does NOT satisfy the collection gate either —
            # expiry is revocation (check-flake-allowlist fails CI on it anyway,
            # but the collection gate must not bless expired quarantine).
            al = tmp / "expired.yml"
            al.write_text(
                "flakes:\n  - id: test_probe_unreg\n    tracking: NEM-GATE-TEST\n"
                "    expires: 2020-01-01\n"
            )
            r = run_pytest(probe, al)
            check(
                r.returncode != 0, "an EXPIRED allowlist entry still satisfied the collection gate"
            )
        finally:
            probe.unlink(missing_ok=True)

        # 4. the shipped tree carries no unregistered marks (real allowlist in effect)
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(SCRATCH_DIR),
                "--collect-only",
                "-q",
                "-p",
                "no:cacheprovider",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=False,
        )
        check(
            r.returncode == 0,
            f"real unit tier fails its own WP0.8 collection gate:\n{(r.stdout + r.stderr)[-600:]}",
        )

    if failures:
        print(f"FAILED: {len(failures)} WP0.8 governance assertion(s)", file=sys.stderr)
        return 1
    print("OK: @pytest.mark.flaky is allowlist-governed (4 cases + real-tree sweep)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
