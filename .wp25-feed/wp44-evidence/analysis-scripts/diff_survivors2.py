import json, re, difflib

path = "/agents/agent-nemo2/workspace/mutants/backend/services/zone_household_service.py"
src = open(path).read().splitlines()

defs = []
for i, line in enumerate(src):
    m = re.match(r'\s*(?:async )?def (\S+?)\s*\(', line)
    if m and '__mutmut_' in m.group(1):
        defs.append((m.group(1), i))

def trim(body):
    out = []
    for l in body:
        if 'mutmut generated' in l or l.strip().startswith('@_mutmut_mutated'):
            break
        out.append(l)
    return out

funcs = {}
for j, (name, start) in enumerate(defs):
    end = defs[j+1][1] if j+1 < len(defs) else len(src)
    funcs[name] = trim(src[start:end])

meta = json.load(open("/agents/agent-nemo2/workspace/mutants/backend/services/zone_household_service.py.meta"))
keys = meta["exit_code_by_key"]
prefix = "backend.services.zone_household_service."
surv = sorted(k for k, v in keys.items() if v == 0)

out = []
for k in surv:
    fname = k[len(prefix):]
    m = re.match(r'(.+__mutmut)_\d+$', fname)
    base = m.group(1) + "_orig"
    a = funcs[base][:]; b = funcs[fname][:]
    a[0] = 'def F('; b[0] = 'def F('
    diff = [l for l in difflib.unified_diff(a, b, lineterm='', n=0) if l.startswith(('+','-')) and not l.startswith(('+++','---'))]
    diff = [l for l in diff if l[1:].strip()]
    out.append(f"{k}:\n" + "\n".join("   " + d for d in diff))

print("\n".join(out))
