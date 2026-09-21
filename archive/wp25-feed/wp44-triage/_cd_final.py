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
DEF={"health_endpoint":None,"health_cmd":None,"startup_grace_period":60,"max_failures":5,"restart_backoff_base":5.0,"restart_backoff_max":300.0}
SELFHEAL={"startup_grace_period","max_failures","restart_backoff_base","restart_backoff_max"}
HEALTH={"health_endpoint","health_cmd"}
def eqval(f,v):
    d=DEF[f]; v2=v.strip('"')
    try: v3=float(v)
    except ValueError: v3=v2
    return d==v3 or str(d)==v2

final=collections.Counter(); ex=collections.defaultdict(list)
for k in surv:
    tail=k.split(".")[-1]; base=re.match(r"(.+)__mutmut_\d+$",tail).group(1)
    fn=base.split("ǁ")[-1] if "ǁ" in base else (base[2:] if base.startswith("x_") else base)
    v=mf[tail]; b=of[fn]
    raw=[norm(l) for l in difflib.unified_diff(b.splitlines(),v.splitlines(),lineterm="",n=0)
         if l and l.startswith(("-","+")) and not l.startswith(("---","+++"))]
    minus=[l[1:].strip() for l in raw if l.startswith("-") and not l[1:].strip().startswith("def ")]
    plus=[l[1:].strip() for l in raw if l.startswith("+") and not l[1:].strip().startswith("def ")]
    kwmin=[x for x in minus if re.match(r'^(\w+)=(.+),$',x)]
    if fn=="build_service_configs" and len(kwmin)==1 and all((re.match(r'^\),?$',p) or p=='') for p in plus):
        f,val=re.match(r'^(\w+)=(.+),$',kwmin[0]).groups()
        if f in DEF and eqval(f,val): c="C14-removal-eq-default"
        elif f in SELFHEAL: c="C06-removal-selfheal-real"
        elif f in HEALTH: c="C07-health-removal"
        else: c="C15-removal-other"
        final[c]+=1; ex[c].append((k,f+"="+val)); continue
    if fn!="build_service_configs":
        final[fn]+=1; ex[fn].append((k,(minus[0] if minus else plus[0])[:100])); continue
    o=minus[0] if minus else ""; n=plus[0] if plus else ""
    m=re.match(r"^(\w+)_port = settings\.\1_port if settings else \d+$",o)
    if m and "if (settings) and False" in n: c="C04-port-ternary-andFalse"
    elif m and re.search(r"if settings or True",n): c="C05-port-ternary-orTrue"
    elif m and n==m.group(1)+"_port = None": c="C03-port-assign-None"
    elif m and re.match(rf"^{m.group(1)}_port = settings\.{m.group(1)}_port if settings else \d+$",n): c="C02-port-default-tweak"
    elif re.match(r'^"[\w.-]+": ServiceConfig\($',o): c="C08-entrykey-mutate"
    elif n=="category=None,": c="C13-category-None"
    elif o.startswith("display_name="): c="C09-display_name-mutate"
    elif n=="port=None,": c="C10-portkw-None"
    elif re.match(r"^(startup_grace_period|max_failures)=(None|\d+),$",n) or re.match(r"^restart_backoff_(base|max)=(None|[\d.]+),$",n):
        c="C11-selfheal-None" if n=="None," or "=None," in n else "C12-selfheal-tweak"
    elif re.match(r"^health_(endpoint|cmd)=None,$",n): c="C01-health-None"
    elif o.startswith("health_endpoint=") or o.startswith("health_cmd="): c="C09b-health-textmutate"
    elif not plus and not kwmin: c="C16-line-del"
    else: c="C17-UNCLASS"
    final[c]+=1
    ex[c].append((k,(o[:70]+" => "+n[:70]) if plus else o[:90]))

print("TOTAL",sum(final.values()))
for c,n in sorted(final.items()):
    print(f"{n:4d} {c}")
    if "UNCLASS" in c or c.endswith("other") or c=="C16-line-del":
        for kk,s in ex[c][:6]: print("      ",s)
json.dump({c:{"n":n,"ex":ex[c][:4]} for c,n in final.items()},open("/tmp/wp25/wp44-triage/_cd_final.json","w"),indent=1)
