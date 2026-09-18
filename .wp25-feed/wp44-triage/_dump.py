import json, subprocess, re, sys, os
os.chdir("/agents/agent-nemo2/workspace")
surv=json.load(open("/tmp/wp25/wp44-triage/_surv_batch_agg.json"))
KEYS=[f"backend.services.batch_aggregator.xǁ{k}ǁ__mutmut_{i}" if "ǁ" in k or k.startswith("BatchAggregator") else f"backend.services.batch_aggregator.x{k}__mutmut_{i}" for k,vs in surv.items() for i in vs]
# rebuild keys correctly from saved fn names
def key(fn,i):
    if fn.startswith("ǁ"):  # class-qualified stored as ǁClassǁmethod
        return f"backend.services.batch_aggregator.x{fn}__mutmut_{i}"
    return f"backend.services.batch_aggregator.x{fn}__mutmut_{i}"
KEYS=[]
FNIDX=[(fn,i) for fn,vs in surv.items() for i in vs]
out={}
for fn,i in FNIDX:
    k=f"backend.services.batch_aggregator.x{fn}__mutmut_{i}"
    try:
        r=subprocess.run(["uv","run","mutmut","show",k],capture_output=True,text=True,timeout=45)
        txt=r.stdout
    except Exception as ex:
        out[k]={"err":str(ex)}; continue
    # parse hunks: lines starting with - or + (excluding --- / +++), plus @@ line num
    lines=txt.splitlines()
    hunk=None; rem=[]; add=[]
    for ln in lines:
        if ln.startswith("@@"):
            mm=re.search(r'@@ -\d+(?:,\d+)? \+(\d+)',ln)
            hunk=int(mm.group(1)) if mm else None
        elif ln.startswith("---") or ln.startswith("+++"): continue
        elif ln.startswith("-"): rem.append(ln[1:].strip())
        elif ln.startswith("+"): add.append(ln[1:].strip())
    out[k]={"fn":fn,"idx":i,"line":hunk,"removed":rem,"added":add}
json.dump(out,open("/tmp/wp25/wp44-triage/_diffs_batch_agg.json","w"),indent=1)
print("DONE",len(out))
