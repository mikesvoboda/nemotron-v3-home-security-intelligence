import json, re, difflib

MUT = "/agents/agent-nemo2/workspace/mutants/backend/services/dedupe.py"
with open(MUT) as f:
    lines = f.readlines()

def sig_end(i, n=6):
    for j in range(i, min(i+n, len(lines))):
        s = lines[j].rstrip()
        if s.endswith(':') and s.count('(') <= s.count(')'):
            return j
    return None

funcs = {}
def_changes = {}
i = 0
N = len(lines)
def_re = re.compile(r'^\s*(async\s+)?def (x\S*__mutmut_(?:orig|\d+))\b')
while i < N:
    m = def_re.match(lines[i])
    if m:
        name = m.group(2)
        def_line = lines[i].strip()
        indent = len(lines[i]) - len(lines[i].lstrip())
        se = sig_end(i)
        if se is None:
            i += 1; continue
        body = []
        j = se + 1
        while j < N:
            ln = lines[j]
            if ln.strip() == "":
                body.append(ln); j += 1; continue
            if len(ln) - len(ln.lstrip()) <= indent:
                break
            body.append(ln[indent:])
            j += 1
        funcs[name] = body
        def_changes.setdefault(name, []).append(def_line)
        i = j
    else:
        i += 1

with open("/agents/agent-nemo2/workspace/mutants/backend/services/dedupe.py.meta") as f:
    meta = json.load(f)
surv = sorted([k for k,v in meta["exit_code_by_key"].items() if v == 0])

out = []
for key in surv:
    tail = key.split(".")[-1]
    origname = re.sub(r"__mutmut_\d+$", "__mutmut_orig", tail)
    if tail not in funcs or origname not in funcs:
        out.append((key, "MISSING", ""))
        continue
    a, b = funcs[origname], funcs[tail]
    diff = list(difflib.unified_diff(a, b, lineterm="", n=1))
    removed = [l[1:].rstrip("\n") for l in diff if l.startswith('-') and not l.startswith('---')]
    added   = [l[1:].rstrip("\n") for l in diff if l.startswith('+') and not l.startswith('+++')]
    # also compare def lines
    dl_orig = def_changes.get(origname, [''])[0]
    dl_mut  = def_changes.get(tail, [''])[0]
    if dl_orig != dl_mut and dl_orig:
        removed.append('DEF: '+dl_orig); added.append('DEF: '+dl_mut)
    out.append((key, " | ".join(x.strip() for x in removed), " | ".join(x.strip() for x in added)))

with open("/tmp/wp25/wp44-triage/diffs.txt","w") as f:
    for key, rm, ad in out:
        f.write(f"KEY {key}\n  - {rm}\n  + {ad}\n")
print("wrote", len(out), "diffs; blank:", sum(1 for _,r,a in out if not r.strip() and not a.strip()))
