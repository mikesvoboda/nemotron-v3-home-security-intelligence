"""`[UR-48]` F1 mutation battery: proves the pins in test_webhooks.py bite.

Contract rule 3 (`docs/uplevel/rules.md`, UR-10): "tools live in the repo; work from
`/tmp` or a home directory does not count as evidence." Precedents in the same shape:
`scripts/uplevel-r94-mutation/` (PR #7038) and `scripts/uplevel-real-tier/` (B1.4).

WHAT THIS IS. Each mutant is a defect shape the cure could plausibly have shipped
instead: a field left raw, routing moved onto the sanitised value, the RESOLVED line
dropping a field, the `description` -> `summary` fallback removed. For each one: apply
it to the working tree, run the suite, restore from an in-memory snapshot and verify
the restore by SHA-256. A mutant the suite does not turn red is reported QUIET and the
battery exits nonzero -- that is a gap in the pins, not a result.

The `count` field is load-bearing twice over: it refuses a mutant whose anchor no
longer matches (a silent no-op would otherwise score as "killed"), and it refuses one
that matches MORE sites than intended, which would undercount the suite and let a weak
pin look strong.

Run from anywhere:

    uv run python scripts/uplevel-f1-webhook-sanitize/battery.py

It rewrites `backend/api/routes/webhooks.py` for a few seconds at a time and always
restores it (restore in a `finally`, hash-checked), so run it on a clean tree.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = "backend/api/routes/webhooks.py"
SUITE = "backend/tests/unit/api/routes/test_webhooks.py"

# (label, expected occurrences, old, new)
MUTANTS: list[tuple[str, int, str, str]] = [
    (
        "M1 every FIRING alert logs at info (the level ladder is gone)",
        1,
        """            if severity == "critical":
                logger.error(log_msg)
            elif severity in ("warning", "high"):
                logger.warning(log_msg)
            else:
                logger.info(log_msg)""",
        """            logger.info(log_msg)""",
    ),
    (
        "M2 routing reads the SANITIZED severity (the refactor the comment forbids)",
        1,
        '            if severity == "critical":',
        '            if safe_severity == "critical":',
    ),
    (
        "M3 the RESOLVED line drops `component`",
        1,
        """                f"[ALERT RESOLVED] {safe_alertname} ({safe_severity}) - "
                f"component={safe_component}: resolved after firing since {alert.startsAt}"
""",
        """                f"[ALERT RESOLVED] {safe_alertname} ({safe_severity}) - "
                f"resolved after firing since {alert.startsAt}"
""",
    ),
    (
        "M4 the description -> summary fallback is dropped",
        1,
        'description = alert.annotations.get("description", alert.annotations.get("summary", ""))',
        'description = alert.annotations.get("description", "")',
    ),
    (
        "M5 `severity` left raw in the FIRING line",
        1,
        'f"[ALERT FIRING] {safe_alertname} ({safe_severity}) - "',
        'f"[ALERT FIRING] {safe_alertname} ({severity}) - "',
    ),
    (
        "M6 `component` left raw in the RESOLVED line",
        1,
        'f"component={safe_component}: resolved after firing since {alert.startsAt}"',
        'f"component={component}: resolved after firing since {alert.startsAt}"',
    ),
    (
        "M7 the RESOLVED branch logs nothing at all",
        1,
        """            logger.info(
                f"[ALERT RESOLVED] {safe_alertname} ({safe_severity}) - "
                f"component={safe_component}: resolved after firing since {alert.startsAt}"
            )""",
        """            pass""",
    ),
    # ---- M8/M9: the two shapes M3 does NOT cover, both measured survivors ----
    # M3 drops `component` and the marker count catches it. Dropping `startsAt`
    # leaves the count unchanged and the prefix intact, so nothing saw it; and the
    # ("warning", "high") arm is documented in docs/developer/api/webhooks.md yet
    # no test posts severity="high".
    (
        "M8 the RESOLVED line drops `startsAt` (survivor before the exact-text pin)",
        1,
        'component={safe_component}: resolved after firing since {alert.startsAt}"',
        'component={safe_component}: resolved after firing since unknown"',
    ),
    (
        "M9 the documented `high` -> WARNING arm is narrowed away (survivor before its pin)",
        1,
        'elif severity in ("warning", "high"):',
        'elif severity in ("warning",):',
    ),
]


def run_pytest() -> tuple[int, str]:
    """One suite run against the mutant on disk. Returns (exit code, tally line).

    The tally is printed even on a green run: a suite that collected 0 tests also
    exits 0, and the tally line is what tells those two apart.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            SUITE,
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:randomly",
            "-o",
            "addopts=",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    lines = [
        ln.strip()
        for ln in proc.stdout.splitlines()
        if " passed" in ln or " failed" in ln or " error" in ln or "no tests ran" in ln
    ]
    return proc.returncode, (lines[-1] if lines else "NO TALLY LINE")


def main() -> int:
    target = REPO / TARGET
    source = target.read_text(encoding="utf-8")
    source_hash = hashlib.sha256(source.encode()).hexdigest()

    quiet: list[str] = []
    damaged: list[str] = []
    try:
        for label, count, old, new in MUTANTS:
            found = source.count(old)
            if found != count:
                print(f"ANCHOR {label}  <- refusing to run: expected {count}, found {found}")
                quiet.append(label)
                continue
            target.write_text(source.replace(old, new), encoding="utf-8")
            if target.read_text(encoding="utf-8") != source.replace(old, new):
                print(f"NOT-ON-DISK {label}  <- refusing to score an unapplied mutant")
                quiet.append(label)
                continue
            code, tally = run_pytest()
            if code == 0:
                print(f"QUIET   {label}  <- pin gap: suite passed with this defect in ({tally})")
                quiet.append(label)
            else:
                print(f"caught  {label}  ({tally})")
    finally:
        target.write_text(source, encoding="utf-8")
        if hashlib.sha256(target.read_text(encoding="utf-8").encode()).hexdigest() != source_hash:
            damaged.append(TARGET)

    caught = len(MUTANTS) - len(quiet)
    print(f"\n{caught}/{len(MUTANTS)} mutants caught by the suite; quiet: {quiet or 'none'}")
    if damaged:
        print(f"RESTORE-FAILED for: {damaged} -- verify with git diff before trusting any of this")
        return 8
    return 0 if not quiet else 1


if __name__ == "__main__":
    sys.exit(main())
