"""Print modules newly crossing the triage-stability bar (not yet dispatched)."""
import json, subprocess, sys
from pathlib import Path
out = subprocess.run(["uv", "run", "python", "scripts/mutation-score.py"],
                     capture_output=True, text=True, cwd="/agents/agent-nemo2/workspace")
if out.returncode != 0:
    sys.exit(0)  # scorer refuses on nothing-measured; never happened mid-run
r = json.loads(out.stdout)
disp = Path("/tmp/wp25/triage-waves/dispatched.txt")
done = set(disp.read_text().split()) if disp.exists() else set()
new = sorted(m["module"] for m in r["modules"]
             if m["total"] - m["not_checked"] >= 150 and m["survived"] >= 100
             and m["module"] not in done)
if new:
    with disp.open("a") as f:
        f.write("\n".join(new) + "\n")
    for n in new:
        print(n)
