#!/usr/bin/env python3
"""WP4.4 serial-lane kill counter: run the target test file under each surviving
mutant (mutmut trampoline semantics: cwd=mutants/, MUTANT_UNDER_TEST=full key).
Writes kill/survive verdicts incrementally to a JSONL so partial progress is
foldable. Usage: python scripts/.wp44-killcount.py <module-path> <test-paths> <out.jsonl>
<test-paths> is comma-separated (multi-suite mutants: pytest takes each as a
separate path arg).
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("/agents/agent-nemo2/workspace")
module_path = sys.argv[1]  # e.g. backend/services/container_discovery.py
# comma-separated list: mutants can be covered by several test files (e.g.
# routes/system: routes/test_system.py + routes/test_system_routes.py + ...);
# pytest takes them all as separate path args.
test_paths = sys.argv[2].split(",")
out_path = Path(sys.argv[3])
# optional survivor-sharding so big modules can use >1 worker without sharing
# one JSONL (append-interleave hazard): worker i of n keeps keys i, i+n, ...
shard_i = int(sys.argv[4]) if len(sys.argv) > 4 else 0
shard_n = int(sys.argv[5]) if len(sys.argv) > 5 else 1

mod = module_path.replace("/", ".")[:-3]
meta = json.loads((REPO / "mutants" / (module_path + ".meta")).read_text())
survivors = sorted(
    (int(m.group(1)), k)
    for k, v in meta["exit_code_by_key"].items()
    if v == 0
    for m in [re.search(r"__mutmut_(\d+)$", k)]
    if m
)

done = set()
if out_path.exists():
    for line in out_path.read_text().splitlines():
        if line.strip():
            done.add(json.loads(line)["key"])

with out_path.open("a") as out:
    for num, key in survivors:
        if key in done or num % shard_n != shard_i:
            continue
        env = dict(os.environ, MUTANT_UNDER_TEST=key)
        # argv is this CLI's own path args (operator-supplied) never external
        # input - precedent: async_utils.py:175 subprocess annotation
        # argv elements are operator CLI paths, no shell involved - precedent:
        # async_utils.py subprocess annotation
        argv = [  # nosemgrep
            sys.executable,
            "-m",
            "pytest",
            *test_paths,
            "-x",
            "-q",
            "-p",
            "no:randomly",
            "-p",
            "no:cacheprovider",
            # repo addopts carry -n 8; per-probe xdist clusters = 8 workers x
            # 8 spawned clusters on 16 CPUs (load 46 measured). One file per
            # probe: -n 0 keeps verdicts identical (unit tests hermetic) and
            # cuts the spawn/oversubscription tax.
            "-n",
            "0",
        ]  # nosemgrep
        proc = subprocess.run(
            argv,  # nosemgrep
            cwd=REPO / "mutants",
            env=env,
            capture_output=True,
            text=True,
            check=False,  # verdict IS the return code
        )
        rc = proc.returncode
        if rc == 2:  # pytest INTERRUPTED (lost/crashed xdist worker, usage
            # error): a NO-VERDICT, not a kill. One immediate retry on a
            # quieter box usually lands on a real verdict.
            proc = subprocess.run(
                argv,  # nosemgrep
                cwd=REPO / "mutants",
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            rc = proc.returncode
        # scorer-consistent kills only (mutation-score.py CODE_MAP: 1,3);
        # rc==2 after retry stays recorded as no_verdict -> re-probed later.
        killed = rc in (1, 3)
        out.write(json.dumps({"num": num, "key": key, "killed": killed, "rc": rc}) + "\n")
        out.flush()
        if (num % 50) == 0:
            print(
                f"{num}: {'KILL' if killed else 'SURVIVE'} (running tally: "
                f"{sum(1 for rec in out_path.read_text().splitlines() if json.loads(rec)['killed'])} killed)",
                flush=True,
            )

text = out_path.read_text()
recs = [json.loads(rec) for rec in text.splitlines() if rec.strip()]
k = sum(1 for r in recs if r["killed"])
print(f"FINAL: {k} killed / {len(recs)} probed / {len(survivors)} survivors on disk")
