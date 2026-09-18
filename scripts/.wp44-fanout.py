#!/usr/bin/env python3
# ruff: noqa: S108  # program convention: /tmp/wp25 state; this is a CLI tool
"""WP4.4 fan-out census: parallel kill-probe workers, one per module.

Approved carve-out to the one-heavy-job rule: up to N (default 7, hard cap 8)
concurrent SINGLE-FILE UNIT pytest workers — mutant kill-probes touch neither
mutmut's cache/progress state nor security_test_gwN schemas. Tier mutmut runs,
integration pytest, and validate.sh stay strictly serial: while their sentinel
pause file exists this launcher holds zero workers (kills running ones, waits).

Each module runs scripts/.wp44-killcount.py (resumable JSONL per module under
/tmp/wp25/wp44-kills/). Test file resolution: dossier-declared test_files_
involved (folded dossiers in .wp25-feed), else recursive test_<stem>.py match
under backend/tests/unit, else skipped with a printed note (never guessed).

Usage: python scripts/.wp44-fanout.py <max_parallel> [module ...]
Without explicit modules: untouched band (0 < survived <= 60, no dossier yet)
from the arbiter /tmp/wp25/final-score.json.
"""

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("/agents/agent-nemo2/workspace")
KILLS = Path("/tmp/wp25/wp44-kills")
PAUSE = Path("/tmp/wp25/fanout.pause")
FEED = REPO / ".wp25-feed" / "wp44-triage"
ARB = Path("/tmp/wp25/final-score.json")
BAND_MAX = 60  # untouched band cap (61+ survivors come from triage waves first)
HARD_CAP = 8


def test_for(module: str) -> str | None:
    base = Path(module).stem
    dp = FEED / (base + ".md")
    if dp.exists():
        m = re.search(r"(backend/tests/\S+\.py)", dp.read_text())
        if m and (REPO / m.group(1)).exists():
            return m.group(1)
    cands = sorted(REPO.glob(f"backend/tests/unit/**/test_{base}.py"))
    if not cands:
        return None
    # mirror match: tests/unit/<same-rel-dir>/test_x.py beats any other twin
    rel = Path(module).relative_to("backend").parent
    mirror = REPO / "backend/tests/unit" / rel / f"test_{base}.py"
    pick = mirror if mirror in cands else cands[0]
    return str(pick.relative_to(REPO))


def main() -> None:
    max_par = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    max_par = min(max_par, HARD_CAP)
    explicit = sys.argv[2:]

    arb = json.loads(ARB.read_text())
    dossiers = {f.name for f in FEED.iterdir() if f.suffix == ".md"}
    mods = explicit or [
        m["module"]
        for m in arb["modules"]
        if 0 < m["survived"] <= BAND_MAX and Path(m["module"]).stem + ".md" not in dossiers
    ]

    KILLS.mkdir(parents=True, exist_ok=True)
    procs: dict[str, tuple[subprocess.Popen, Path]] = {}
    skipped: list[str] = []
    queue = list(mods)
    print(f"fan-out: {len(mods)} modules, max {max_par} workers", flush=True)

    while queue or procs:
        if PAUSE.exists():
            print("PAUSED (pause file present); killing worker process groups", flush=True)
            # workers spawn pytest children; terminate() alone reparents them to
            # init and they keep burning CPU (observed: 23 xdist strays survived
            # a pause and contended validate.sh). Workers start their own
            # session (start_new_session below) -> killpg reaches the whole tree.

            for _, (p, _) in procs.items():
                try:
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                except ProcessLookupError, PermissionError:
                    p.terminate()
            for _, (p, _) in procs.items():
                p.wait()
            procs.clear()
            while PAUSE.exists():
                time.sleep(30)
            continue
        while queue and len(procs) < max_par:
            spec = queue.pop(0)
            # "mod#N" = N-way survivor shard (keys i, i+N, ...; disjoint JSONLs
            # so big modules beat the one-worker-per-module serial tail).
            # Overshoot of max_par by up to N-1 during the shard burst is fine
            # at -n 0 per probe; shard workers keep the killpg process-group.
            mod, _, nsh_s = spec.partition("#")
            nsh = int(nsh_s) if nsh_s else 1
            tf = test_for(mod)
            if not tf:
                skipped.append(mod)
                print(f"SKIP(no test file): {mod}", flush=True)
                continue
            for i in range(nsh):
                sfx = f".shard{i}" if nsh > 1 else ""
                out = KILLS / (Path(mod).stem + sfx + ".jsonl")
                logf = (KILLS / (Path(mod).stem + sfx + ".log")).open("w")  # Popen holds fd
                argv = [  # venv python direct: no uv resolve/lock contention
                    str(REPO / ".venv/bin/python"),
                    "scripts/.wp44-killcount.py",
                    mod,
                    tf,
                    str(out),
                ]
                if nsh > 1:
                    argv += [str(i), str(nsh)]
                p = subprocess.Popen(
                    argv,
                    cwd=REPO,
                    stdout=logf,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # own process group so PAUSE killpg is total
                )
                procs[mod if nsh == 1 else f"{mod}#{i}"] = (p, out)
                print(f"START {mod if nsh == 1 else spec} -> {tf} ({out.name})", flush=True)
        time.sleep(20)
        for mod in list(procs):
            p, out = procs[mod]
            if p.poll() is not None:
                n = sum(1 for _ in out.open()) if out.exists() else 0
                print(f"DONE  {mod}: {n} probes -> {out}", flush=True)
                del procs[mod]
    print(f"FAN-OUT COMPLETE. skipped-no-testfile: {len(skipped)}")
    for s in skipped:
        print(f"  skip: {s}")


if __name__ == "__main__":
    main()
