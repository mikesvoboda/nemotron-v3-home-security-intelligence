# WP4.4 triage-wave detector; source copy .wp25-feed/new-stable.py.
"""Print modules newly crossing the triage-stability bar (not yet dispatched)."""

import json
import subprocess
import sys
from pathlib import Path

out = subprocess.run(
    ["uv", "run", "python", "scripts/mutation-score.py"],
    capture_output=True,
    text=True,
    check=False,
    cwd=str(Path(__file__).resolve().parents[1]),
)
if out.returncode != 0:
    sys.exit(0)  # scorer refuses on nothing-measured; never happened mid-run
r = json.loads(out.stdout)
disp = Path(__file__).resolve().parents[1] / ".wp25-feed" / "triage-waves" / "dispatched.txt"
done = set(disp.read_text().split()) if disp.exists() else set()
new = sorted(
    m["module"]
    for m in r["modules"]
    if m["total"] - m["not_checked"] >= 150 and m["survived"] >= 100 and m["module"] not in done
)
if new:
    with disp.open("a") as f:
        f.write("\n".join(new) + "\n")
    for n in new:
        print(n)
