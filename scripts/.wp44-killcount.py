#!/usr/bin/env python3
"""WP4.4 serial-lane kill counter: run the target test file under each surviving
mutant (mutmut trampoline semantics: cwd=mutants/, MUTANT_UNDER_TEST=full key).
Writes kill/survive verdicts incrementally to a JSONL so partial progress is
foldable. Usage: python scripts/.wp44-killcount.py <module-path> <test-path> <out.jsonl>
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("/agents/agent-nemo2/workspace")
module_path = sys.argv[1]  # e.g. backend/services/container_discovery.py
test_path = sys.argv[2]  # e.g. backend/tests/unit/services/test_container_discovery.py
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
            test_path,
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
        killed = proc.returncode != 0
        out.write(
            json.dumps({"num": num, "key": key, "killed": killed, "rc": proc.returncode}) + "\n"
        )
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
