import json, re, difflib

copy_path = "mutants/backend/services/retry_handler.py"
meta_path = "mutants/backend/services/retry_handler.py.meta"

meta = json.load(open(meta_path))
surv = sorted(k for k,v in meta["exit_code_by_key"].items() if v == 0)

lines = open(copy_path).read().splitlines()
funcs = {}
i = 0; n = len(lines)
def_ind_re = re.compile(r'^(\s*)(?:async\s+)?def (\S+?)\(')
while i < n:
    m = def_ind_re.match(lines[i])
    if m:
        indent = len(m.group(1)); name = m.group(2)
        j = i+1
        while j < n:
            l = lines[j]
            if l.strip()=="":
                j+=1; continue
            cur = len(l) - len(l.lstrip())
            if cur <= indent: break
            j+=1
        funcs[name] = (i, j); i = j
    else:
        i += 1

out = []
for key in surv:
    mangled = key.split(".")[-1]
    base = re.sub(r'__mutmut_\d+$', '__mutmut_orig', mangled)
    if mangled not in funcs:
        out.append((key, "MISSING-FUNC")); continue
    if base not in funcs:
        out.append((key, "NO-ORIG")); continue
    s,e = funcs[mangled]; os_,oe = funcs[base]
    a = [l.strip() for l in lines[os_:oe] if l.strip()]
    b = [l.strip() for l in lines[s:e] if l.strip()]
    diffs=[]
    for op, i1,i2,j1,j2 in difflib.SequenceMatcher(None,a,b).get_opcodes():
        if op=="equal": continue
        ol = " | ".join(a[i1:i2]); nl = " | ".join(b[j1:j2])
        diffs.append(f"    -{ol}\n    +{nl}")
    out.append((key, "\n".join(diffs) if diffs else "IDENTICAL-TO-ORIG"))

with open("/tmp/wp25/wp44-triage/diffs.txt","w") as f:
    for k,d in out:
        f.write(k+"\n"+d+"\n")
print("wrote", len(out))
bad = sum(1 for k,d in out if d in ("MISSING-FUNC","NO-ORIG","IDENTICAL-TO-ORIG"))
print("bad:", bad)
