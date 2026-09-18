import json, re, difflib

lines = open("mutants/backend/services/retry_handler.py").read().splitlines()
meta = json.load(open("mutants/backend/services/retry_handler.py.meta"))
surv = sorted(k for k,v in meta["exit_code_by_key"].items() if v == 0)

funcs = {}
i = 0; n = len(lines)
def_re = re.compile(r'^(\s*)(?:async\s+)?def (\S+?)\(')
while i < n:
    m = def_re.match(lines[i])
    if m:
        indent = len(m.group(1)); name = m.group(2)
        depth = 0
        j = i
        while j < n:
            l = lines[j]
            depth += l.count("(") + l.count("[") + l.count("{") - l.count(")") - l.count("]") - l.count("}")
            if j > i and depth <= 0 and l.strip():
                cur = len(l) - len(l.lstrip())
                if cur <= indent:
                    break
            j += 1
        funcs[name] = (i, j); i = j
    else:
        i += 1

out = []
for key in surv:
    mangled = key.split(".")[-1]
    base = re.sub(r'__mutmut_\d+$', '__mutmut_orig', mangled)
    if mangled not in funcs:
        out.append((key,"MISSING-FUNC")); continue
    if base not in funcs:
        out.append((key,"NO-ORIG")); continue
    s,e = funcs[mangled]; os_,oe = funcs[base]
    a = [l.strip() for l in lines[os_:oe] if l.strip()]
    b = [l.strip() for l in lines[s:e] if l.strip()]
    diffs=[]
    for op,i1,i2,j1,j2 in difflib.SequenceMatcher(None,a,b).get_opcodes():
        if op=="equal": continue
        # skip the def-name rename alone
        ol=" | ".join(a[i1:i2]); nl=" | ".join(b[j1:j2])
        ol2 = ol.replace("__mutmut_orig","__mutmut_N"); nl2 = nl.replace("__mutmut_"+mangled.split("__mutmut_")[-1],"__mutmut_N")
        if ol2==nl2: continue
        diffs.append(f"    -{ol}\n    +{nl}")
    out.append((key,"\n".join(diffs) if diffs else "IDENTICAL-TO-ORIG"))

with open("/tmp/wp25/wp44-triage/diffs2.txt","w") as f:
    for k,d in out:
        f.write(k+"\n"+d+"\n")
bad = [k for k,d in out if d=="IDENTICAL-TO-ORIG" or d in ("MISSING-FUNC","NO-ORIG")]
print("wrote",len(out),"identical/missing:",len(bad))
for k in bad: print(" ",k)
