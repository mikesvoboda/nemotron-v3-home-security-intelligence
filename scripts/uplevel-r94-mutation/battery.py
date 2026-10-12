"""`[r94]` mutation battery: proves the pins in test_r94_env_preserving_reruns.py bite.

Contract rule 3 (`docs/uplevel/rules.md`, UR-10): the harness a package's evidence
relies on lives in the repo, not a home directory. Precedents:
`scripts/uplevel-f13-done-when/` (`ef359d96f`) and `scripts/uplevel-real-tier/`
(`51d908d68`) -- rule-3 harnesses for one package's evidence, in this directory.

WHAT THIS IS. A list of mutants, each one a TRANSCRIBED shape from a site that exists
in the product code today (`setup.py`, `setup_lib/core.py`) — never an invented
near-miss, because an invented mutant can score 16/16 quiet against a guard that works.
For each mutant: apply it to the working tree, run the suite, restore the file from an
in-memory snapshot, and verify the restore by SHA-256. A mutant with ZERO reds is
reported QUIET and exits nonzero: that is a gap in the pins, not a passing test, and it
is the only outcome here that means the suite would let the defect through.

The `count` field on every mutant is load-bearing twice over. It refuses a mutant whose
pattern no longer matches (a silent no-op mutant scores as "quiet" rather than as
evidence), and it refuses one that matches MORE places than intended: `setup.py` has
two interactive modes, so a mutant that only reaches one of them undercounts the suite
and can make a weak pin look strong.

Run from anywhere:

    uv run python scripts/uplevel-r94-mutation/battery.py

It rewrites `setup.py` and `setup_lib/core.py` for a few seconds at a time and always
restores them (restore is in a `finally`, and the hash is checked), so run it on a
clean tree and expect `git status` to look unchanged afterwards.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SUITE = "backend/tests/unit/setup_lib/test_r94_env_preserving_reruns.py"

# (label, repo-relative file, expected occurrences, old, new)
MUTANTS: list[tuple[str, str, int, str, str]] = [
    # ---- Fix 1: a re-run's prompt defaults come from the existing .env ----
    (
        "M1 saved_answer hands the raw .env word to the y/n prompt",
        "setup.py",
        1,
        '    return "y" if _expose_lan_is_truthy(existing_env[saved_key]) else "n"',
        "    return existing_env[saved_key]",
    ),
    (
        "M2 saved_or always falls back to the first-run default",
        "setup.py",
        1,
        "    return saved if saved else fallback",
        "    return fallback",
    ),
    (
        "M3 saved_port ignores the saved port",
        "setup.py",
        1,
        "        return int(saved) if saved else fallback",
        "        return fallback",
    ),
    (
        "M4 both modes stop using the saved port as the starting point",
        "setup.py",
        2,
        '        default_port = saved_port(existing_env, service, info["port"])',
        '        default_port = info["port"]',
    ),
    (
        "M5 both expose prompts stop offering the saved state",
        "setup.py",
        2,
        '        saved_answer(existing_env, "EXPOSE_LAN", "n"),',
        '        "n",',
    ),
    # ---- Fix 2: the flag's CLI contract (exit codes are the operator's signal) ----
    (
        "M6 the flag's handler never runs",
        "setup.py",
        1,
        "    if args.convert_monitoring_key:",
        "    if args.convert_monitoring_key and False:",
    ),
    (
        "M7 'already scoped' reports failure instead of success",
        "setup.py",
        1,
        'print("+ Already scoped: the monitoring key\'s API_KEYS entry needs no change.")\n'
        "            sys.exit(0)",
        'print("+ Already scoped: the monitoring key\'s API_KEYS entry needs no change.")\n'
        "            sys.exit(1)",
    ),
    (
        "M8 a refusal exits 0 (silently 'succeeded')",
        "setup.py",
        1,
        '        print(f"  {env_target} is unchanged.")\n        sys.exit(1)',
        '        print(f"  {env_target} is unchanged.")\n        sys.exit(0)',
    ),
    # ---- Fix 2: convert_monitoring_key's byte discipline and refusals ----
    (
        "M9 the conversion drops the line's own terminator (the bug this caught)",
        "setup_lib/core.py",
        1,
        '    body = line.rstrip("\\r\\n")\n    terminator = line[len(body) :]',
        '    body, _, terminator = line.partition("\\n")',
    ),
    (
        "M10 a scope-less object is reported as already converted",
        "setup_lib/core.py",
        1,
        '        return env_text, "unchanged" if "scope" in entries[object_at[0]] else "not-plain"',
        '        return env_text, "unchanged"',
    ),
    (
        "M11 the plain-and-object ambiguity is not refused",
        "setup_lib/core.py",
        1,
        "    if len(plain_at) > 1 or (plain_at and object_at):",
        "    if len(plain_at) > 1:",
    ),
    (
        "M12 two API_KEYS lines are not refused",
        "setup_lib/core.py",
        1,
        "    if len(indices) > 1:",
        "    if len(indices) > 2:",
    ),
    (
        "M13 the rewrite re-emits with default (spaced) separators",
        "setup_lib/core.py",
        1,
        """json.dumps(entries, separators=(',', ':'))""",
        "json.dumps(entries)",
    ),
    (
        "M14 the quote pair is dropped from the rewritten line",
        "setup_lib/core.py",
        1,
        """f"{prefix}={quote}{json.dumps(entries, separators=(',', ':'))}{quote}{terminator}\"""",
        """f"{prefix}={json.dumps(entries, separators=(',', ':'))}{terminator}\"""",
    ),
    (
        "M15 _value_of takes the FIRST match, not the last",
        "setup_lib/core.py",
        1,
        "                found = value",
        "                found = found if found is not None else value",
    ),
    (
        "M16 emission keeps 'no quote as found' (the pre-fix policy)",
        "setup_lib/core.py",
        1,
        '    quote = "\'"',
        '    quote = ""',
    ),
]


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _run_suite() -> tuple[int, list[str], str]:
    """Run the suite once; return (red count, failing test names, tally line)."""
    proc = subprocess.run(  # real: the suite this package ships
        [sys.executable, "-m", "pytest", SUITE, "-q", "-p", "no:randomly", "-n0", "--no-header"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
        timeout=900,
    )
    blob = proc.stdout + proc.stderr
    reds = sorted({ln.split("::")[-1] for ln in blob.splitlines() if ln.startswith("FAILED ")})
    tally = next((ln.strip() for ln in blob.splitlines() if " passed" in ln or " failed" in ln), "")
    if not reds and (proc.returncode not in (0, 1) or not tally):
        # A collection crash reports no FAILED lines; scoring that as "survived"
        # would be a false pass, so say plainly that the suite did not run.
        print(f"    SUITE DID NOT RUN (rc={proc.returncode}): {tally or blob[-400:]}")
    return len(reds), reds, tally


def main() -> int:
    originals = {rel: (REPO / rel).read_text(encoding="utf-8") for _, rel, _, _, _ in MUTANTS}
    quiet: list[str] = []
    damaged: list[str] = []

    try:
        for label, rel, expected, old, new in MUTANTS:
            target = REPO / rel
            hits = originals[rel].count(old)
            if hits != expected:
                # A pattern that stopped matching would leave the mutant identical to
                # the product code, which would then be reported as QUIET and read as
                # a pin gap in the suite rather than a stale harness. Refuse it here.
                print(f"PIN-ERROR {label}\n    pattern occurs {hits}x, expected {expected}")
                quiet.append(label)
                continue
            try:
                target.write_text(originals[rel].replace(old, new), encoding="utf-8")
                n_red, reds, tally = _run_suite()
            finally:
                target.write_text(originals[rel], encoding="utf-8")
                if _digest(target.read_text(encoding="utf-8")) != _digest(originals[rel]):
                    print(f"RESTORE-FAILED {label} — {rel} left MUTATED")
                    damaged.append(rel)
            if n_red:
                print(f"RED   {label}  ({n_red} test{'s' if n_red > 1 else ''})")
                for name in reds[:6]:
                    print(f"         {name}")
            else:
                # The tally is printed here deliberately: "QUIET" is only meaningful if
                # the suite actually ran, and a run that collected 0 tests also has no
                # FAILED lines. The tally line is the proof of which one this is.
                print(f"QUIET {label}  <- pin gap: the suite passed with this defect in ({tally})")
                quiet.append(label)
    finally:
        for rel, text in originals.items():
            (REPO / rel).write_text(text, encoding="utf-8")

    caught = len(MUTANTS) - len(quiet)
    print(f"\n{caught}/{len(MUTANTS)} mutants caught by the suite; quiet: {quiet or 'none'}")
    if damaged:
        print(
            f"RESTORE-FAILED for: {sorted(set(damaged))} — verify with git diff before trusting anything"
        )
        return 8
    return 0 if not quiet else 1


if __name__ == "__main__":
    sys.exit(main())
