import json, re, ast, difflib, collections

BASE="/agents/agent-nemo2/workspace"
mut_src=open(BASE+"/mutants/backend/services/container_discovery.py").read()
orig_src=open(BASE+"/backend/services/container_discovery.py").read()
def funcs(src):
    t=ast.parse(src); out={}
    for n in ast.walk(t):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            s=ast.get_source_segment(src,n)
            if s: out.setdefault(n.name,s)
    return out
mf=funcs(mut_src); of=funcs(orig_src)
meta=json.load(open(BASE+"/mutants/backend/services/container_discovery.py.meta"))
surv=sorted(k for k,v in meta["exit_code_by_key"].items() if v==0)
def norm(l): return re.sub(r"\s+"," ",l.strip())

portline=re.compile(r"^(\w+)_port = settings\.\1_port if settings else (\d+)$")
keyline=re.compile(r'^"([\w.-]+)": ServiceConfig\($')

def classify(o,n):
    m=portline.match(o)
    if m:
        f,dflt=m.group(1),m.group(2)
        if n=="None": return ("port-assign-None",f)
        if "and False" in n: return ("port-ternary-and-False",f)
        if "or True" in n: return ("port-ternary-or-True",f)
        mn=re.match(rf"^{f}_port = settings\.{f}_port if settings else (\d+)$",n)
        if mn: return ("port-default-numeric-tweak",(f,dflt,mn.group(1)))
        if n==f"{f}_port = dflt" if False else False: return ("x",f)
        return ("port-other",(o,n))
    if keyline.match(o):
        ok=keyline.match(o).group(1)
        mn=re.match(r'^"(.*)": ServiceConfig\($',n)
        if mn:
            nk=mn.group(1)
            if nk==ok.upper(): return ("entrykey-uppercase",ok)
            if nk=="XX"+ok+"XX": return ("entrykey-XXwrap",ok)
            if nk=="": return ("entrykey-empty",ok)
            return ("entrykey-other",(ok,nk))
        if n=="None:": return ("entrykey-None",ok)
        return ("entrykey-other",(o,n))
    mk=re.match(r"^(\w+)=(.+),$",o)
    if mk:
        f,v=mk.group(1),mk.group(2)
        mn=re.match(r"^(\w+)=(.+),$",n)
        if mn and mn.group(1)==f:
            nv=mn.group(2)
            if nv=="None": return (f"kw-{f}-None",f)
            try:
                float(v); float(nv); return (f"kw-{f}-numeric-tweak",f)
            except ValueError: pass
            vs=v.strip('"')
            if nv=='"XX'+vs+'XX"': return (f"kw-{f}-XXwrap",f)
            if nv=='"'+vs.upper()+'"': return (f"kw-{f}-case-flip",f)
            if vs.startswith('"'): vs2=vs
            if v.startswith('"') and nv.startswith('"'): return (f"kw-{f}-string-tweak",(vs,nv.strip('"')))
            return (f"kw-{f}-other",(v,nv))
        return ("kw-name-or-structure-change",(o,n))
    return ("MISC",(o,n))

buckets=collections.Counter(); examples=collections.defaultdict(list)
for k in surv:
    tail=k.split(".")[-1]; base=re.match(r"(.+)__mutmut_\d+$",tail).group(1)
    short=base.split("ǁ")[-1] if "ǁ" in base else (base[2:] if base.startswith("x_") else base)
    v=mf[tail]; b=of[short]
    raw=[norm(l) for l in difflib.unified_diff(b.splitlines(),v.splitlines(),lineterm="",n=0)
         if l and l.startswith(("-","+")) and not l.startswith(("---","+++"))]
    minus=[l[1:].strip() for l in raw if l.startswith("-") and not l[1:].strip().startswith("def ")]
    plus=[l[1:].strip() for l in raw if l.startswith("+") and not l[1:].strip().startswith("def ")]
    if len(minus)==1 and len(plus)==1:
        cat,slot=classify(minus[0],plus[0])
    elif len(minus)==1 and len(plus)==0:
        mk=re.match(r'^(\w+)=',minus[0])
        cat="kwarg-removed" if mk else "line-deleted"
        slot=mk.group(1) if mk else minus[0][:60]
    elif len(minus)==0 and len(plus)==1:
        cat="line-added"; slot=plus[0][:60]
    else:
        cat="multi"; slot=" ;; ".join(minus[:2])[:80]+"  =>  "+" ;; ".join(plus[:2])[:80]
    buckets[(short,cat)]+=1
    examples[(short,cat)].append((k,str(slot),minus[0][:100] if minus else "",plus[0][:100] if plus else ""))

print("TOTAL",sum(buckets.values()))
for (fn,cat),n in sorted(buckets.items(),key=lambda x:(-x[1],x[0])):
    print(f"{n:4d}  {fn:30s} {cat}")
json.dump({f"{fn}|{cat}":{"n":n,"ex":examples[(fn,cat)][:4]} for (fn,cat),n in buckets.items()},
          open("/tmp/wp25/wp44-triage/_cd_buckets2.json","w"),indent=1)
