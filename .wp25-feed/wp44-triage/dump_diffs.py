import json, subprocess, sys
with open('mutants/backend/services/transcoding.py.meta') as f:
    data = json.load(f)
surv = sorted([k for k,v in data['exit_code_by_key'].items() if v == 0],
              key=lambda s: int(s.split('__mutmut_')[-1]))
out = open('/tmp/wp25/wp44-triage/diffs.txt','w')
for k in surv:
    try:
        r = subprocess.run(['uv','run','mutmut','show',k], capture_output=True, text=True, timeout=60)
        out.write(r.stdout)
        if r.returncode != 0:
            out.write(f"### ERROR key={k} rc={r.returncode}: {r.stderr[:200]}\n")
    except Exception as e:
        out.write(f"### EXC key={k}: {e}\n")
    out.flush()
out.close()
print("done", len(surv))
